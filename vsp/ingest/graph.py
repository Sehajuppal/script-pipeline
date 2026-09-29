"""Instagram Graph API client — Instagram API with Facebook Login for Business
(graph.facebook.com, version pinned; research doc §1-§4).

    client = GraphClient.from_env(budget=HashtagBudget(con))   # VSP_IG_* env
    client.whoami()                       GET /me?fields=id,username
    client.token_debug()                  GET /debug_token (validity, expiry, scopes)
    client.permissions()                  GET /me/permissions
    client.ig_account()                   GET /{ig-user-id}?fields=id,username,...
    client.hashtag_id(tag)                GET /ig_hashtag_search (cached forever)
    client.top_media(tag) / recent_media(tag)   GET /{hashtag-id}/top_media ...
    client.recently_searched_hashtags()   GET /{ig-user-id}/recently_searched_hashtags
    client.business_discovery(handle)     GET /{ig-user-id}?fields=business_discovery...
    client.own_media(since)               GET /{ig-user-id}/media
    client.media_insights(media_id)       GET /{media-id}/insights (Reels metrics)
    client.account_insights(day)          GET /{ig-user-id}/insights (period=day)

Guarantees:
  * every HTTP call goes through `transport(method, url, headers, body,
    timeout) -> Response(status, headers, body)`; urllib by default, canned
    fixtures in the self-checks (vsp.fixtures.FixtureTransport);
  * the 30-unique-hashtags-per-rolling-7-days budget is checked and recorded
    in hashtag_budget BEFORE any hashtag call (hashtag calls without a budget
    are refused);
  * X-App-Usage / X-Business-Use-Case-Usage are honoured: above 80 % the
    client sleeps before each call, at 95 % (or when Meta reports a regain
    time) it raises RateLimited so a job stops cleanly and resumes next run;
  * HTTP 429 / 5xx and Graph codes 1, 2, 4, 17, 32, 613 (+ is_transient) are
    retried with full-jitter exponential backoff (Retry-After honoured);
  * errors name the missing permission / feature (Instagram Public Content
    Access, instagram_manage_insights, ...) and never contain the token;
  * appsecret_proof is sent when VSP_IG_APP_SECRET is set;
  * media_url is returned to the caller for transient use only (optional
    transcription) — vsp.ingest.normalize never copies it into a row.
"""
import collections
import hashlib
import hmac
import json
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from vsp.ingest.settings import PLATFORM_HASHTAG_CAP, norm_handle, norm_tag
from vsp.ingest.util import parse_ts, sql_ts, utcnow

DEFAULT_VERSION = "v26.0"
BASE_URL = "https://graph.facebook.com"
ENV_TOKEN, ENV_USER, ENV_VERSION, ENV_SECRET, ENV_APP_ID = (
    "VSP_IG_ACCESS_TOKEN", "VSP_IG_USER_ID", "VSP_IG_GRAPH_VERSION",
    "VSP_IG_APP_SECRET", "VSP_IG_APP_ID")

HASHTAG_MEDIA_FIELDS = ("id", "caption", "media_type", "media_url", "permalink",
                        "timestamp", "like_count", "comments_count")
BD_MEDIA_FIELDS = ("id", "caption", "permalink", "timestamp", "media_type",
                   "media_product_type", "media_audio_type", "like_count",
                   "comments_count", "view_count", "media_url")
BD_OPTIONAL_FIELDS = ("media_product_type", "media_audio_type")   # §3: UNVERIFIED
OWN_MEDIA_FIELDS = ("id", "caption", "media_type", "media_product_type",
                    "permalink", "timestamp", "like_count", "comments_count")
REELS_METRICS = ("views", "reach", "likes", "comments", "saved", "shares",
                 "reposts", "total_interactions", "ig_reels_avg_watch_time",
                 "ig_reels_video_view_total_time", "reels_skip_rate")
ACCOUNT_METRICS = ("follows_and_unfollows", "profile_links_taps", "views", "reach")

RETRY_CODES = {1, 2, 4, 17, 32, 613}
RATE_LIMIT_CODES = {4, 17, 32, 613} | set(range(80001, 80015))
TOKEN_CODES = {102, 190, 463, 467}
PERMISSION_CODES = {3, 10} | set(range(200, 300))

NEEDS = {
    "hashtag": ("the Instagram Public Content Access feature (App Review + "
                "Business Verification) and the instagram_basic permission"),
    "business_discovery": ("instagram_basic + instagram_manage_insights + "
                           "pages_read_engagement (Business Discovery; the target "
                           "must be a Business or Creator account)"),
    "own_media": ("instagram_basic + pages_show_list + pages_read_engagement, and "
                  "the Instagram account linked to a Facebook Page"),
    "media_insights": ("instagram_manage_insights (+ instagram_basic, "
                       "pages_read_engagement)"),
    "account_insights": ("instagram_manage_insights (+ instagram_basic, "
                         "pages_read_engagement); follows_and_unfollows needs "
                         ">= 100 followers"),
    "token": "a valid token in VSP_IG_ACCESS_TOKEN",
}

Response = collections.namedtuple("Response", "status headers body")


# ------------------------------------------------------------------ errors
class GraphError(Exception):
    def __init__(self, message, status=None, code=None, subcode=None, kind=None,
                 endpoint=None, fbtrace_id=None, transient=False, hint=None,
                 error_type=None):
        self.message = str(message or "Graph API error")
        self.status, self.code, self.subcode = status, code, subcode
        self.kind, self.endpoint, self.fbtrace_id = kind, endpoint, fbtrace_id
        self.transient, self.error_type = bool(transient), error_type
        self.hint = hint if hint is not None else _hint(self)
        super().__init__(self.__str__())

    @property
    def retryable(self):
        return (self.status == 429 or (self.status is not None and 500 <= self.status < 600)
                or self.code in RETRY_CODES or self.transient)

    @property
    def rate_limited(self):
        return self.status == 429 or self.code in RATE_LIMIT_CODES

    @property
    def token_problem(self):
        return self.code in TOKEN_CODES

    @property
    def permission_problem(self):
        return self.code in PERMISSION_CODES

    @property
    def not_found(self):
        """Object missing: deleted media, or not visible to this account."""
        return (self.code == 100 and self.subcode == 33) or (
            self.code == 100 and "does not exist" in self.message.lower())

    def __str__(self):
        where = f"{self.endpoint}: " if self.endpoint else ""
        bits = []
        if self.status is not None:
            bits.append(f"HTTP {self.status}")
        if self.code is not None:
            bits.append(f"code {self.code}" + (f"/{self.subcode}" if self.subcode else ""))
        tail = f" ({', '.join(bits)})" if bits else ""
        return f"{where}{self.message}{tail}" + (f" — {self.hint}" if self.hint else "")


class RateLimited(GraphError):
    """Usage headers or throttling codes say: stop now, resume next run."""


class NotConfigured(RuntimeError):
    def __init__(self, missing):
        self.missing = list(missing)
        super().__init__(
            "Instagram API not configured: set " + ", ".join(self.missing)
            + " (run `python3 -m vsp.ingest doctor` for the exact setup steps)")


class TransportError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    def __init__(self, tag, used, limit, next_free_at):
        self.tag, self.used, self.limit, self.next_free_at = tag, used, limit, next_free_at
        super().__init__(
            f"hashtag budget exhausted: #{tag} would be unique hashtag {used + 1} "
            f"in the rolling 7 days (limit {limit}, Instagram cap "
            f"{PLATFORM_HASHTAG_CAP}); next slot frees at {next_free_at} UTC")


def _hint(e):
    kind = e.kind or ""
    msg = e.message.lower()
    if e.code in TOKEN_CODES:
        sub = {463: "expired", 460: "invalidated (password change)",
               458: "app not authorized", 464: "unconfirmed user",
               467: "invalid"}.get(e.subcode, "invalid or expired")
        return (f"the access token is {sub}: mint a new long-lived token (see "
                f"docs/ws-data-notes.md › Tokens) and update {ENV_TOKEN}")
    if "30 unique hashtags" in msg or ("hashtag" in msg and "limit" in msg):
        return ("Instagram's 30-unique-hashtags-per-7-days limit was hit — the "
                "local hashtag_budget is out of sync; run `python3 -m vsp.ingest "
                "doctor` (syncs recently_searched_hashtags)")
    if e.code in PERMISSION_CODES or "permission" in msg:
        return f"missing permission/feature: this call needs {NEEDS.get(kind, 'more permissions')}"
    if kind == "business_discovery" and (e.code == 110 or "cannot find user" in msg
                                         or "invalid user" in msg):
        return "handle not found, or it is a personal (not Business/Creator) account"
    if e.code == 100 and "nonexisting field" in msg:
        return "a requested field is not available on this API version/node"
    if e.not_found and kind in ("media_insights", "own_media"):
        return "media not found — deleted, or not owned by this account"
    if e.code == 100 and "user_id" in msg:
        return (f"{ENV_USER} must be the Instagram Business account id (not the Page "
                f"id): GET /me/accounts?fields=instagram_business_account")
    if e.rate_limited:
        return "rate limited — back off; the job resumes on its next run"
    return None


def error_from_response(status, data, kind=None, endpoint=None):
    err = (data or {}).get("error") if isinstance(data, dict) else None
    if not isinstance(err, dict):
        cls = RateLimited if status == 429 else GraphError
        return cls(f"unexpected HTTP {status} response", status=status,
                   kind=kind, endpoint=endpoint)
    cls = RateLimited if (status == 429 or err.get("code") in RATE_LIMIT_CODES) else GraphError
    return cls(err.get("message") or "Graph API error", status=status,
               code=err.get("code"), subcode=err.get("error_subcode"), kind=kind,
               endpoint=endpoint, fbtrace_id=err.get("fbtrace_id"),
               transient=bool(err.get("is_transient")), error_type=err.get("type"))


# --------------------------------------------------------------- transport
def redact(url):
    return re.sub(r"(access_token|appsecret_proof|input_token|client_secret)=[^&]*",
                  r"\1=***", url or "")


def urllib_transport(method, url, headers=None, body=None, timeout=30.0):
    req = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Response(r.status, {k.lower(): v for k, v in r.headers.items()},
                            r.read())
    except urllib.error.HTTPError as e:
        hdrs = {k.lower(): v for k, v in (e.headers.items() if e.headers else [])}
        try:
            body = e.read() or b""
        except Exception:  # noqa: BLE001
            body = b""
        return Response(e.code, hdrs, body)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise TransportError(f"{method} {redact(url)}: {e}")


def _usage_pct(headers):
    """(max percent over X-App-Usage + X-Business-Use-Case-Usage, regain min)."""
    pct, regain = 0.0, 0.0
    h = {str(k).lower(): v for k, v in (headers or {}).items()}
    for key in ("x-app-usage", "x-business-use-case-usage", "x-ad-account-usage"):
        raw = h.get(key)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        stack = [data]
        while stack:
            cur = stack.pop()
            if isinstance(cur, list):
                stack.extend(cur)
            elif isinstance(cur, dict):
                for k, v in cur.items():
                    if isinstance(v, (dict, list)):
                        stack.append(v)
                    elif isinstance(v, (int, float)) and not isinstance(v, bool):
                        if k in ("call_count", "total_time", "total_cputime",
                                 "acc_id_util_pct"):
                            pct = max(pct, float(v))
                        elif k == "estimated_time_to_regain_access":
                            regain = max(regain, float(v))
    return pct, regain


# ------------------------------------------------------------------ budget
class HashtagBudget:
    """Instagram allows 30 unique hashtags per account per rolling 7 days
    (research doc §2): a tag's clock starts at its first query; repeats inside
    the window are free and do not reset it. Stored in hashtag_budget(tag,
    first_used_at, last_used_at, hashtag_id); hashtag ids are static and cached
    forever. `limit` is the local cap (config budget.max_active_hashtags,
    default 25 = 5 spare), never above the platform's 30."""
    WINDOW = timedelta(days=7)

    def __init__(self, con, limit=None, clock=None):
        self.con = con
        self.limit = min(PLATFORM_HASHTAG_CAP, int(limit or PLATFORM_HASHTAG_CAP))
        self.clock = clock or utcnow

    def _now(self):
        return self.clock()

    def _cutoff(self):
        return sql_ts(self._now() - self.WINDOW)

    def active(self):
        return [dict(r) for r in self.con.execute(
            "SELECT tag, first_used_at, last_used_at, hashtag_id FROM hashtag_budget "
            "WHERE first_used_at > ? ORDER BY first_used_at, tag", (self._cutoff(),))]

    def used(self):
        return self.con.execute("SELECT COUNT(*) FROM hashtag_budget WHERE "
                                "first_used_at > ?", (self._cutoff(),)).fetchone()[0]

    def remaining(self):
        return max(0, self.limit - self.used())

    def is_active(self, tag):
        row = self.con.execute("SELECT first_used_at FROM hashtag_budget WHERE tag=?",
                               (norm_tag(tag),)).fetchone()
        return bool(row and row[0] and row[0] > self._cutoff())

    def next_free_at(self):
        row = self.con.execute("SELECT MIN(first_used_at) FROM hashtag_budget WHERE "
                               "first_used_at > ?", (self._cutoff(),)).fetchone()
        if not row or not row[0]:
            return sql_ts(self._now())
        return sql_ts(parse_ts(row[0]) + self.WINDOW)

    def plan(self, tags):
        """Split tags into (allowed, refused) WITHOUT recording anything:
        active tags are free; new ones fit while slots remain."""
        allowed, refused, free = [], [], self.remaining()
        for t in tags:
            t = norm_tag(t)
            if t in allowed:
                continue
            if self.is_active(t):
                allowed.append(t)
            elif free > 0:
                allowed.append(t)
                free -= 1
            else:
                refused.append(t)
        return allowed, refused

    def reserve(self, tag):
        """Record a use of `tag` before the API call. -> True if it opened a new
        slot, False if the tag was already active. Raises BudgetExceeded."""
        t = norm_tag(tag)
        now = sql_ts(self._now())
        row = self.con.execute("SELECT first_used_at, hashtag_id FROM hashtag_budget "
                               "WHERE tag=?", (t,)).fetchone()
        if row and row[0] and row[0] > self._cutoff():
            self.con.execute("UPDATE hashtag_budget SET last_used_at=? WHERE tag=?", (now, t))
            self.con.commit()
            return False
        used = self.used()
        if used >= self.limit:
            raise BudgetExceeded(t, used, self.limit, self.next_free_at())
        self.con.execute(
            "INSERT OR REPLACE INTO hashtag_budget(tag, first_used_at, last_used_at, "
            "hashtag_id) VALUES (?, ?, ?, ?)", (t, now, now, row[1] if row else None))
        self.con.commit()
        return True

    def cached_id(self, tag):
        row = self.con.execute("SELECT hashtag_id FROM hashtag_budget WHERE tag=?",
                               (norm_tag(tag),)).fetchone()
        return row[0] if row and row[0] else None

    def set_id(self, tag, hashtag_id):
        t, hid = norm_tag(tag), str(hashtag_id)
        ph = self.con.execute("SELECT first_used_at FROM hashtag_budget WHERE tag=?",
                              ("?" + hid,)).fetchone()
        if ph:          # a remote-synced placeholder for this id: merge it
            self.con.execute("DELETE FROM hashtag_budget WHERE tag=?", ("?" + hid,))
            self.con.execute("UPDATE hashtag_budget SET first_used_at=MIN(first_used_at, ?) "
                             "WHERE tag=? AND first_used_at IS NOT NULL", (ph[0], t))
        cur = self.con.execute("UPDATE hashtag_budget SET hashtag_id=? WHERE tag=?", (hid, t))
        if not cur.rowcount:
            self.con.execute("INSERT INTO hashtag_budget(tag, hashtag_id) VALUES (?, ?)",
                             (t, hid))
        self.con.commit()

    def sync_remote(self, ids):
        """Mark ids from GET recently_searched_hashtags as active. Unknown ids
        (searched by another tool on this account) become '?<id>' placeholder
        slots so the local count never under-counts. -> placeholders added."""
        added, now, cutoff = 0, sql_ts(self._now()), self._cutoff()
        for hid in ids or []:
            hid = str(hid)
            row = self.con.execute("SELECT tag, first_used_at FROM hashtag_budget "
                                   "WHERE hashtag_id=? OR tag=?", (hid, "?" + hid)).fetchone()
            if row:
                if not row[1] or row[1] <= cutoff:     # active remotely: count it now
                    self.con.execute("UPDATE hashtag_budget SET first_used_at=?, "
                                     "last_used_at=? WHERE tag=?", (now, now, row[0]))
                continue
            self.con.execute("INSERT INTO hashtag_budget(tag, first_used_at, last_used_at, "
                             "hashtag_id) VALUES (?, ?, ?, ?)", ("?" + hid, now, now, hid))
            added += 1
        self.con.commit()
        return added


# ------------------------------------------------------------------ client
class GraphClient:
    def __init__(self, token, ig_user_id=None, version=None, app_secret=None,
                 app_id=None, transport=None, budget=None, sleep=None, rng=None,
                 max_retries=4, base_url=BASE_URL, timeout=30.0, log=None,
                 usage_backoff_pct=80.0, usage_stop_pct=95.0, backoff_base=2.0,
                 backoff_cap=60.0):
        if not token:
            raise NotConfigured([ENV_TOKEN])
        self.token = token
        self.ig_user_id = str(ig_user_id) if ig_user_id else None
        self.version = version or DEFAULT_VERSION
        if not re.fullmatch(r"v\d+\.\d+", self.version):
            raise ValueError(f"graph version {self.version!r} must look like v26.0")
        self.app_secret, self.app_id = app_secret or None, app_id or None
        self.transport = transport or urllib_transport
        self.budget = budget
        self.sleep = sleep or time.sleep
        self.rng = rng or random.Random()
        self.max_retries, self.timeout = int(max_retries), float(timeout)
        self.base_url = base_url.rstrip("/")
        self.log = log or (lambda msg: None)
        self.usage_backoff_pct, self.usage_stop_pct = usage_backoff_pct, usage_stop_pct
        self.backoff_base, self.backoff_cap = backoff_base, backoff_cap
        self.usage_pct, self.regain_min = 0.0, 0.0
        self.calls, self.retries, self.throttled = 0, 0, 0
        self.slept = []                          # every delay, for reports/tests
        self._bd_fields = list(BD_MEDIA_FIELDS)
        self._reels_metrics = list(REELS_METRICS)
        self.dropped_metrics = set()
        self.last_paging = {}

    @classmethod
    def from_env(cls, env=None, require_user=True, **kw):
        e = os.environ if env is None else env
        missing = [n for n in ([ENV_TOKEN] + ([ENV_USER] if require_user else []))
                   if not (e.get(n) or "").strip()]
        if missing:
            raise NotConfigured(missing)
        return cls(e[ENV_TOKEN].strip(), (e.get(ENV_USER) or "").strip() or None,
                   version=(e.get(ENV_VERSION) or "").strip() or None,
                   app_secret=(e.get(ENV_SECRET) or "").strip() or None,
                   app_id=(e.get(ENV_APP_ID) or "").strip() or None, **kw)

    # ------------------------------------------------------------ plumbing
    def _proof(self, token):
        return hmac.new(self.app_secret.encode("utf-8"), token.encode("utf-8"),
                        hashlib.sha256).hexdigest()

    def _url(self, path, params, token=None):
        q = {k: v for k, v in (params or {}).items() if v is not None}
        tok = token or self.token
        q["access_token"] = tok
        if self.app_secret and "|" not in tok:     # app tokens need no proof
            q["appsecret_proof"] = self._proof(tok)
        return f"{self.base_url}/{self.version}/{path.lstrip('/')}?" + \
            urllib.parse.urlencode(q)

    def _backoff(self, attempt):
        return self.rng.uniform(0, min(self.backoff_cap, self.backoff_base * (2 ** attempt)))

    def _do_sleep(self, seconds, why):
        seconds = max(0.0, float(seconds))
        self.slept.append((round(seconds, 3), why))
        if seconds:
            self.sleep(seconds)

    def _pre_throttle(self):
        if self.regain_min > 0 or self.usage_pct >= self.usage_stop_pct:
            extra = (f"; Meta estimates {self.regain_min:g} min to regain access"
                     if self.regain_min > 0 else "")
            raise RateLimited(
                f"API usage at {self.usage_pct:g}% (stop threshold "
                f"{self.usage_stop_pct:g}%){extra} — stopping now; the job resumes on "
                f"its next run", kind="usage", hint="")
        if self.usage_pct >= self.usage_backoff_pct:
            self.throttled += 1
            delay = min(self.backoff_cap, self.backoff_base *
                        2 ** ((self.usage_pct - self.usage_backoff_pct) / 5.0))
            self.log(f"usage {self.usage_pct:g}% >= {self.usage_backoff_pct:g}%: "
                     f"backing off {delay:.1f}s")
            self._do_sleep(delay, f"usage {self.usage_pct:g}%")

    def _note_usage(self, headers):
        pct, regain = _usage_pct(headers)
        self.usage_pct, self.regain_min = pct, regain

    def call(self, path, params=None, kind=None, token=None, method="GET"):
        """One Graph request with throttling + retries -> parsed JSON dict."""
        endpoint = re.sub(r"\d{6,}", "{id}", path.split("?")[0])
        attempt = 0
        while True:
            self._pre_throttle()
            url = self._url(path, params, token=token)
            self.calls += 1
            try:
                resp = self.transport(method, url, {"Accept": "application/json"},
                                      None, self.timeout)
            except TransportError as e:
                if attempt < self.max_retries:
                    self.retries += 1
                    self._do_sleep(self._backoff(attempt), "network error")
                    attempt += 1
                    continue
                raise GraphError(f"network error: {e}", kind=kind, endpoint=endpoint,
                                 hint="check connectivity; nothing was stored")
            self._note_usage(resp.headers)
            try:
                data = json.loads((resp.body or b"{}").decode("utf-8") or "{}")
            except (UnicodeDecodeError, ValueError):
                data = None
            if 200 <= resp.status < 300 and isinstance(data, dict) and "error" not in data:
                return data
            err = error_from_response(resp.status, data, kind=kind, endpoint=endpoint)
            if err.retryable and attempt < self.max_retries:
                self.retries += 1
                ra = (resp.headers or {}).get("retry-after")
                try:
                    delay = min(self.backoff_cap, float(ra)) if ra else self._backoff(attempt)
                except ValueError:
                    delay = self._backoff(attempt)
                why = f"retry {attempt + 1}: HTTP {resp.status}"
                if err.code is not None:
                    why += f" code {err.code}"
                self._do_sleep(delay, why)
                attempt += 1
                continue
            raise err

    def paged(self, path, params, max_pages, kind, stop=None):
        """Follow paging.cursors.after up to max_pages. Stops on an empty page,
        a missing `next`, a repeated cursor, or stop(item) -> True."""
        items, seen, after, pages, truncated = [], set(), None, 0, False
        ids = set()
        while pages < max(1, int(max_pages)):
            p = dict(params)
            if after:
                p["after"] = after
            data = self.call(path, p, kind=kind)
            pages += 1
            batch = data.get("data") or []
            halt = False
            for it in batch:
                if isinstance(it, dict) and it.get("id") in ids:
                    continue
                if stop and stop(it):
                    halt = True
                    break
                if isinstance(it, dict):
                    ids.add(it.get("id"))
                items.append(it)
            paging = data.get("paging") or {}
            nxt = (paging.get("cursors") or {}).get("after")
            if halt or not batch or not nxt or not paging.get("next") or nxt in seen:
                break
            seen.add(nxt)
            after = nxt
            if pages >= max_pages:
                truncated = True
        self.last_paging = {"pages": pages, "truncated": truncated, "items": len(items)}
        return items

    def _need_user(self):
        if not self.ig_user_id:
            raise NotConfigured([ENV_USER])

    # ------------------------------------------------------------ identity
    def whoami(self):
        try:
            return self.call("me", {"fields": "id,username"}, kind="token")
        except GraphError as e:
            # a Facebook User token has no `username` field (#12/#100):
            # fall back to id,name so the token is still verified
            if e.code in (12, 100) and "username" in e.message.lower():
                return self.call("me", {"fields": "id,name"}, kind="token")
            raise

    def token_debug(self):
        access = (f"{self.app_id}|{self.app_secret}" if self.app_id and self.app_secret
                  else None)
        data = self.call("debug_token", {"input_token": self.token}, kind="token",
                         token=access)
        return data.get("data") or {}

    def permissions(self):
        data = self.call("me/permissions", {}, kind="token")
        return {p.get("permission"): p.get("status") for p in data.get("data") or []
                if isinstance(p, dict)}

    def ig_account(self):
        self._need_user()
        return self.call(self.ig_user_id,
                         {"fields": "id,username,name,followers_count,media_count"},
                         kind="own_media")

    # ------------------------------------------------------------ hashtags
    def _reserve(self, tag):
        if self.budget is None:
            raise RuntimeError("hashtag calls need a HashtagBudget (the research DB "
                               "records the 30-per-7-days budget before any call)")
        return self.budget.reserve(tag)

    def hashtag_id(self, tag):
        t = norm_tag(tag)
        self._need_user()
        self._reserve(t)                                  # BEFORE any call
        cached = self.budget.cached_id(t)
        if cached:
            return cached
        data = self.call("ig_hashtag_search", {"user_id": self.ig_user_id, "q": t},
                         kind="hashtag")
        ids = [x.get("id") for x in data.get("data") or [] if isinstance(x, dict)
               and x.get("id")]
        if not ids:
            raise GraphError(f"hashtag #{t} not found", kind="hashtag",
                             endpoint="ig_hashtag_search", hint="")
        self.budget.set_id(t, ids[0])
        return str(ids[0])

    def _hashtag_media(self, edge, tag, limit, max_pages, fields):
        t = norm_tag(tag)
        self._need_user()
        self._reserve(t)                                  # media calls count too
        hid = self.hashtag_id(t)
        return self.paged(f"{hid}/{edge}",
                          {"user_id": self.ig_user_id, "fields": ",".join(fields),
                           "limit": max(1, min(50, int(limit)))},
                          max_pages, kind="hashtag")

    def top_media(self, tag, limit=50, max_pages=2, fields=HASHTAG_MEDIA_FIELDS):
        return self._hashtag_media("top_media", tag, limit, max_pages, fields)

    def recent_media(self, tag, limit=50, max_pages=1, fields=HASHTAG_MEDIA_FIELDS):
        return self._hashtag_media("recent_media", tag, limit, max_pages, fields)

    def recently_searched_hashtags(self):
        self._need_user()
        data = self.call(f"{self.ig_user_id}/recently_searched_hashtags",
                         {"limit": 30}, kind="hashtag")
        return [str(x.get("id")) for x in data.get("data") or []
                if isinstance(x, dict) and x.get("id")]

    # -------------------------------------------------- business discovery
    def business_discovery(self, handle, limit=25, max_pages=1):
        """-> (account {id, username, name, followers_count, media_count},
        media items). Optional fields the BD expansion may not support
        (media_product_type, media_audio_type — UNVERIFIED) are dropped once
        on a 'nonexisting field' error and remembered."""
        h = norm_handle(handle)
        self._need_user()
        items, account, after, pages, retried = [], None, None, 0, False
        while pages < max(1, int(max_pages)):
            media = ("media" + (f".after({after})" if after else "")
                     + f".limit({max(1, min(50, int(limit)))})"
                     + "{" + ",".join(self._bd_fields) + "}")
            expr = (f"business_discovery.username({h})"
                    "{id,username,name,followers_count,media_count," + media + "}")
            try:
                data = self.call(self.ig_user_id, {"fields": expr},
                                 kind="business_discovery")
            except GraphError as e:
                bad = [f for f in BD_OPTIONAL_FIELDS if f in self._bd_fields]
                if (e.code == 100 and "nonexisting field" in e.message.lower()
                        and bad and not retried):
                    named = [f for f in bad if f in e.message] or bad
                    self._bd_fields = [f for f in self._bd_fields if f not in named]
                    self.log(f"business_discovery: dropped unsupported fields {named}")
                    retried = True
                    continue
                raise
            bd = data.get("business_discovery") or {}
            if account is None:
                account = {k: bd.get(k) for k in ("id", "username", "name",
                                                   "followers_count", "media_count")}
            m = bd.get("media") or {}
            batch = m.get("data") or []
            items.extend(x for x in batch if isinstance(x, dict))
            pages += 1
            paging = m.get("paging") or {}
            cur = (paging.get("cursors") or {}).get("after")
            if not batch or not cur or cur == after or not paging.get("next"):
                break
            after = cur
        self.last_paging = {"pages": pages, "items": len(items)}
        return account or {}, items

    # ------------------------------------------------------------ own media
    def own_media(self, since=None, limit=50, max_pages=10, fields=OWN_MEDIA_FIELDS):
        """Own media, newest first, optionally since a timestamp (sent as the
        `since` unix param and enforced client-side; paging stops at the first
        older item)."""
        self._need_user()
        since_dt = parse_ts(since) if since else None
        params = {"fields": ",".join(fields), "limit": max(1, min(50, int(limit)))}
        if since_dt:
            params["since"] = int(since_dt.timestamp())

        def older(it):
            ts = parse_ts((it or {}).get("timestamp"))
            return bool(since_dt and ts and ts < since_dt)
        return self.paged(f"{self.ig_user_id}/media", params, max_pages,
                          kind="own_media", stop=older if since_dt else None)

    # ------------------------------------------------------------- insights
    def media_insights(self, media_id, metrics=None):
        """-> {metric: number} (missing data -> {} — Instagram returns an empty
        set, never 0). Metrics the API rejects for this media / version are
        dropped (remembered in dropped_metrics) and the call is retried."""
        mid = str(media_id)
        mets = list(metrics or self._reels_metrics)
        attempts = 0
        while True:
            try:
                data = self.call(f"{mid}/insights", {"metric": ",".join(mets)},
                                 kind="media_insights")
                return parse_insights(data)
            except GraphError as e:
                drop = unsupported_metrics(e, mets)
                attempts += 1
                if e.code == 100 and drop and len(drop) < len(mets) and attempts <= 4:
                    mets = [m for m in mets if m not in drop]
                    self.dropped_metrics |= set(drop)
                    if metrics is None:
                        self._reels_metrics = mets
                    self.log(f"insights: metric(s) {drop} unsupported, retrying without")
                    continue
                raise

    def account_insights(self, day, metrics=ACCOUNT_METRICS):
        """Daily account insights for the UTC day `day` (date / datetime /
        'YYYY-MM-DD'): -> {"date", "values": [(metric, breakdown, value)],
        "warnings": [...]}. follows_and_unfollows is fetched with
        breakdown=follow_type; a metric the account cannot have (e.g. < 100
        followers) becomes a warning, not a failure."""
        self._need_user()
        start = parse_ts(str(day)[:10] + " 00:00:00")
        if start is None:
            raise ValueError(f"bad day {day!r}")
        since, until = int(start.timestamp()), int((start + timedelta(days=1)).timestamp())
        out = {"date": start.strftime("%Y-%m-%d"), "values": [], "warnings": []}
        groups = []
        if "follows_and_unfollows" in metrics:
            groups.append((["follows_and_unfollows"], "follow_type"))
        rest = [m for m in metrics if m != "follows_and_unfollows"]
        if rest:
            groups.append((rest, None))
        for mets, breakdown in groups:
            params = {"metric": ",".join(mets), "period": "day",
                      "metric_type": "total_value", "since": since, "until": until}
            if breakdown:
                params["breakdown"] = breakdown
            try:
                data = self.call(f"{self.ig_user_id}/insights", params,
                                 kind="account_insights")
            except RateLimited:
                raise
            except GraphError as e:
                if e.token_problem:
                    raise
                out["warnings"].append(f"{','.join(mets)}: {e}")
                continue
            out["values"] += parse_account_insights(data)
        return out


# ------------------------------------------------------------ parse helpers
def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def parse_insights(data):
    out = {}
    for it in (data or {}).get("data") or []:
        if not isinstance(it, dict) or not it.get("name"):
            continue
        v = None
        tv = it.get("total_value")
        if isinstance(tv, dict):
            v = _num(tv.get("value"))
        if v is None:
            vals = it.get("values") or []
            if vals and isinstance(vals[-1], dict):
                v = _num(vals[-1].get("value"))
        if v is not None:
            out[it["name"]] = v
    return out


def parse_account_insights(data):
    rows = []
    for it in (data or {}).get("data") or []:
        if not isinstance(it, dict) or not it.get("name"):
            continue
        tv = it.get("total_value") if isinstance(it.get("total_value"), dict) else {}
        total = _num(tv.get("value"))
        if total is None:
            vals = it.get("values") or []
            if vals and isinstance(vals[-1], dict):
                total = _num(vals[-1].get("value"))
        if total is not None:
            rows.append((it["name"], "", total))
        for bd in tv.get("breakdowns") or []:
            for res in (bd or {}).get("results") or []:
                dims = res.get("dimension_values") or []
                v = _num(res.get("value"))
                if v is not None and dims:
                    rows.append((it["name"], ":".join(str(d) for d in dims).lower(), v))
    return rows


def unsupported_metrics(err, metrics):
    """Metric names a Graph (#100) insights error rejects."""
    msg = err.message or ""
    m = re.search(r"must be one of the following values:\s*(.+)", msg, re.I)
    if m:
        allowed = {x.strip().strip(".").lower() for x in re.split(r"[,\s]+", m.group(1))
                   if x.strip()}
        bad = [x for x in metrics if x.lower() not in allowed]
        if bad:
            return bad
    idx = re.search(r"metric\[(\d+)\]", msg)
    if idx and int(idx.group(1)) < len(metrics):
        return [metrics[int(idx.group(1))]]
    return [x for x in metrics if re.search(r"\b" + re.escape(x) + r"\b", msg)]
