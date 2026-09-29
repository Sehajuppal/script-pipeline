"""Hermetic fixtures for vsp.trends (the selfcheck and demos). Every
permalink contains "FIXTURE" so fixture evidence can never pass for a real
reel (steer hides it unless VSP_FIXTURE_OK=1, like gate 2 / D151).

    NOW / TODAY                   the pinned clock (2026-09-29 12:00 UTC)
    demo_raw(now)                 raw observations: 4 trends in 3 niches with
                                  nano..mega creators (a nano creator with a
                                  2,000-view median and a 50,000-view post)
    stage_series_raw(now)         -> (raw, {key: expected stage}, {key: speed})
    youtube_fixture()             {filename: body} canned Data API responses
    write_youtube_fixture(dir)    writes them (python3 -m vsp.trends.fixtures youtube DIR)
    tiktok_cc_csv()               a hand-copied Creative Center list
    build_ingest_db(path)         vsp.ingest's fixture DB + Business Discovery
                                  history for one creator (a baseline)
    build_demo_dataset(dir, now)  init + add + score + lifecycle + synth
"""
import json
import os
from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 9, 29, 12, 0, 0, tzinfo=timezone.utc)
TODAY = "2026-09-29"


def ago(days, now=NOW, hours=0):
    return (now - timedelta(days=days, hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def ig(code):
    return f"https://www.instagram.com/reel/FIXTURE{code}/"


def tt(handle, n):
    return f"https://www.tiktok.com/@FIXTURE{handle}/video/74000000000000{n:05d}"


def yt(code):
    return f"https://www.youtube.com/shorts/FIXTURE{code}"


def _post(link, platform, handle, followers, views, day, now, **kw):
    rec = {"platform": platform, "permalink": link, "handle": handle,
           "followers": followers, "views": views, "posted_at": ago(day, now),
           "observed_at": ago(0, now, hours=1), "source": kw.pop("source", "agent_observed")}
    rec.update(kw)
    return rec


POV = {"format_key": "pov-reveal", "archetype": "curiosity-gap", "frame0": "result-reveal",
       "emotion": "surprise", "participation": "comment_prompt", "cta": "comment_keyword",
       "audio_type": "trending_sound", "sound_id": "fx100", "sound_title": "Fixture Beat",
       "replicability": 4, "production_cost": "low", "loop": True, "payoff_reveal": True,
       "beats": ["hook", "setup", "reveal", "payoff"], "duration_s": 22, "cuts_per_10s": 5,
       "vibe": "before-after-reveal", "needs_real_person": False, "niche": "beauty",
       "tags": ["povreveal", "skincare"]}
DANCE = {"format_key": "mirror-dance", "archetype": "challenge", "frame0": "face-reaction",
         "emotion": "humor", "participation": "duet", "audio_type": "trending_sound",
         "sound_id": "fx300", "sound_title": "Fixture Groove", "replicability": 3,
         "production_cost": "low", "needs_real_person": True, "niche": "beauty",
         "beats": ["mirror", "beat drop", "dance", "freeze"], "duration_s": 15,
         "cuts_per_10s": 3}
DESK = {"format_key": "desk-setup-asmr", "archetype": "showcase",
        "frame0": "satisfying-macro", "emotion": "satisfaction", "participation": "template",
        "audio_type": "licensed_music", "sound_title": "Fixture Lofi", "vibe": "asmr-satisfying",
        "replicability": 5, "production_cost": "med", "duration_s": 15, "cuts_per_10s": 2,
        "loop": True, "beats": ["macro detail", "setup reveal", "final frame"],
        "needs_real_person": False, "niche": "gadgets", "tags": ["desksetup"]}
DAYN = {"format_key": "day-n-of", "archetype": "day-counter", "frame0": "day-counter",
        "emotion": "aspirational", "participation": "challenge",
        "audio_type": "original_voiceover", "replicability": 4, "production_cost": "low",
        "series": True, "needs_real_person": False, "niche": "fitness", "duration_s": 30,
        "beats": ["day marker", "attempt", "result"]}


def demo_raw(now=NOW):
    """Raw observations for the demo dataset (see module doc)."""
    out = []
    # nano creator: six older posts around 2,000 views (median 2,000) ...
    for i, (day, views) in enumerate(((10, 1800), (12, 1900), (14, 2000), (16, 2000),
                                      (18, 2100), (20, 2200))):
        out.append(_post(ig(f"nanog{i}"), "instagram", "fixture_nano_glow", 4200, views, day,
                         now, niche="beauty", replicability=3))
    # ... and a 50,000-view pov-reveal post two days ago: 25x, breakout
    out.append(_post(ig("nanogX"), "instagram", "fixture_nano_glow", 4200, 50000, 2, now,
                     first_words="Nobody tells you this about serum pilling",
                     on_screen_text="wait for the last second", **POV))
    out += [
        _post(ig("micro1"), "instagram", "fixture_micro_skin", 45000, 60000, 9, now,
              median_views=20000, baseline_n=12, **POV),
        _post(ig("micro2"), "instagram", "fixture_micro_skin", 45000, 150000, 3, now,
              median_views=20000, baseline_n=12, **POV),
        _post(ig("mid1"), "instagram", "fixture_mid_beauty", 250000, 400000, 11, now,
              median_views=100000, baseline_n=20, **POV),
        _post(tt("nanotwo", 1), "tiktok", "fixture_nano_two", 8000, 90000, 1, now, **POV),
        _post(ig("mega1"), "instagram", "fixture_mega_star", 3000000, 2000000, 4, now,
              median_views=1500000, baseline_n=30, **POV),
    ]
    out += [
        _post(tt("dance1", 2), "tiktok", "fixture_dance_one", 20000, 80000, 8, now, **DANCE),
        _post(tt("dance2", 3), "tiktok", "fixture_dance_two", 5000, 60000, 2, now, **DANCE),
        _post(tt("dance3", 4), "tiktok", "fixture_dance_three", 30000, 200000, 3, now,
              **DANCE),
        _post(tt("dance4", 5), "tiktok", "fixture_dance_four", 9000, 45000, 5, now, **DANCE),
    ]
    out += [
        _post(ig("desk1"), "instagram", "fixture_gadget_nano", 3000, 30000, 1, now,
              median_views=2500, baseline_n=8, **DESK),
        _post(yt("dsk1"), "youtube", "fixture_gadget_micro", 60000, 240000, 2, now,
              median_views=40000, baseline_n=15, **DESK),
        _post(tt("desk3", 6), "tiktok", "fixture_gadget_mid", 300000, 900000, 5, now, **DESK),
    ]
    fit = [(8, 20000, 60000), (9, 15000, 30000), (12, 9000, 40000), (1, 25000, 90000),
           (2, 12000, 50000), (4, 7000, 21000), (40, 18000, 70000)]
    for i, (day, fol, views) in enumerate(fit):
        out.append(_post(ig(f"fit{i}"), "instagram", f"fixture_fit_{i}", fol, views, day, now,
                         **DAYN))
    return out


def stage_series_raw(now=NOW):
    """Synthetic dated sightings that hit every stage and speed.
    -> (raw observations, {key: stage}, {key: speed})."""
    plan = {  # key: [(days ago, creator suffix)]
        "fx-emerging": [(1, "a"), (3, "b")],
        "fx-rising": [(8, "a"), (10, "b"), (1, "c"), (2, "d"), (3, "e"), (4, "f")],
        "fx-peak": [(20, "z")] + [(7 + i % 7, f"p{i}") for i in range(10)] +
                   [(i % 7, f"q{i}") for i in range(11)],
        "fx-saturated": [(25, "z")] + [(7 + i % 7, f"p{i}") for i in range(30)] +
                        [(i % 7, f"q{i}") for i in range(22)],
        "fx-declining": [(30, "z")] + [(7 + i % 7, f"p{i}") for i in range(8)] +
                        [(i % 3, f"q{i}") for i in range(3)],
        "fx-silent": [(20, "a"), (22, "b"), (25, "c")],
        "fx-steady": [(30, "z"), (8, "a"), (9, "b"), (12, "c"), (1, "d"), (2, "e"), (4, "f")],
        "fx-signal": [(100, "a"), (60, "b"), (1, "c"), (2, "d")],
        "fx-force": [(200, "a"), (90, "b"), (1, "c"), (3, "d")],
        "fx-solo": [(1, "a"), (2, "a"), (3, "a")],
    }
    stages = {"fx-emerging": "emerging", "fx-rising": "rising", "fx-peak": "peak",
              "fx-saturated": "saturated", "fx-declining": "declining",
              "fx-silent": "declining", "fx-steady": "steady"}
    speeds = {"fx-emerging": "moment", "fx-signal": "signal", "fx-force": "force"}
    raw = []
    n = 0
    for key in sorted(plan):
        for day, who in plan[key]:
            n += 1
            raw.append({"platform": "instagram", "permalink": ig(f"s{n:04d}"),
                        "handle": f"fixture_s_{key.replace('-', '_')}_{who}",
                        "followers": 5000, "views": 1000, "posted_at": ago(day, now),
                        "observed_at": ago(0, now, hours=1), "source": "agent_observed",
                        "niche": "home", "format_key": key})
    return raw, {"format:" + k: v for k, v in stages.items()}, \
        {"format:" + k: v for k, v in speeds.items()}


# ----------------------------------------------------------------- YouTube
CH1, CH2 = "UCFIXTURE000000000000001", "UCFIXTURE000000000000002"


def _video(vid, channel, day, views, seconds, title, now=NOW, likes=None, comments=None):
    return {"kind": "youtube#video", "id": vid,
            "snippet": {"publishedAt": ago(day, now), "channelId": channel, "title": title,
                        "description": "FIXTURE description #desksetup #shorts",
                        "defaultAudioLanguage": "en"},
            "statistics": {"viewCount": str(views),
                           "likeCount": str(likes if likes is not None else views // 20),
                           "commentCount": str(comments if comments is not None
                                               else views // 400)},
            "contentDetails": {"duration": f"PT{seconds // 60}M{seconds % 60}S"
                               if seconds >= 60 else f"PT{seconds}S"}}


def youtube_fixture(now=NOW):
    """{file name: canned response body} for FixtureYouTube (importers)."""
    search = [_video("FIXTUREyt01", CH1, 2, 50000, 35, "Desk setup that fixes posture #desksetup",
                     now),
              _video("FIXTUREyt02", CH2, 3, 120000, 58, "The cable trick nobody uses", now),
              _video("FIXTUREyt03", CH2, 1, 900000, 240, "A 4 minute video (not a Short)", now),
              _video("FIXTUREyt04", CH1, 5, 2600, 20, "Tiny tidy desk", now)]
    uploads1 = [_video(f"FIXTUREc1u{i}", CH1, d, v, s, f"upload {i}", now)
                for i, (d, v, s) in enumerate(((8, 1800, 30), (10, 1900, 25), (12, 2000, 40),
                                               (15, 2100, 50), (18, 2200, 45), (21, 2000, 30),
                                               (3, 99999, 30), (25, 50000, 600)), 1)]
    uploads2 = [_video(f"FIXTUREc2u{i}", CH2, d, v, 30, f"upload {i}", now)
                for i, (d, v) in enumerate(((9, 40000), (11, 42000), (13, 39000),
                                            (16, 41000)), 1)]
    return {
        "search.list.json": {"kind": "youtube#searchListResponse",
                             "items": [{"kind": "youtube#searchResult",
                                        "id": {"kind": "youtube#video", "videoId": v["id"]}}
                                       for v in search]},
        "videos.list.json": {"items": search + uploads1 + uploads2},
        "channels.list.json": {"items": [
            {"id": CH1, "snippet": {"title": "Fixture Desk", "customUrl": "@fixturedesk"},
             "statistics": {"subscriberCount": "4200", "hiddenSubscriberCount": False},
             "contentDetails": {"relatedPlaylists": {"uploads": "UU" + CH1[2:]}}},
            {"id": CH2, "snippet": {"title": "Fixture Hidden"},
             "statistics": {"hiddenSubscriberCount": True},
             "contentDetails": {"relatedPlaylists": {"uploads": "UU" + CH2[2:]}}}]},
        "playlistItems.list.json": {
            "UU" + CH1[2:]: {"items": [{"contentDetails": {"videoId": v["id"]}}
                                       for v in uploads1]},
            "UU" + CH2[2:]: {"items": [{"contentDetails": {"videoId": v["id"]}}
                                       for v in uploads2]}},
    }


def write_youtube_fixture(d, now=NOW):
    os.makedirs(d, exist_ok=True)
    for name, body in youtube_fixture(now).items():
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            json.dump(body, f, indent=1, sort_keys=True)
            f.write("\n")
    return d


# ----------------------------------------------------------- TikTok CC
def tiktok_cc_csv():
    return ("rank,hashtag,song,posts,growth,region,industry,date\n"
            "1,povreveal,,48.2K,+40%,US,Beauty & Personal Care,2026-09-28\n"
            "2,girldinner,,120K,+85%,US,Food & Beverage,2026-09-28\n"
            "3,,Fixture Beat,31K,+120%,US,,2026-09-28\n")


# ------------------------------------------------------------ ingest DB
def build_ingest_db(path):
    """vsp.fixtures.build_ingest_fixture_db plus seven older Business
    Discovery reels of fixture_glowlab (median 50,000 views), so its
    1,250,000-view reel is a 25x breakout. -> path."""
    from vsp.fixtures import build_ingest_fixture_db
    from vsp.ingest import db as idb
    from vsp.ingest.normalize import normalize_item, upsert_reel
    build_ingest_fixture_db(path)
    con = idb.connect(path)
    try:
        for i, (day, views) in enumerate(((10, 40000), (12, 45000), (14, 50000), (16, 50000),
                                          (18, 55000), (20, 60000), (22, 48000))):
            item = {"id": f"1790000000000095{i}", "media_type": "VIDEO",
                    "media_product_type": "REELS", "like_count": views // 30,
                    "comments_count": views // 500, "view_count": views,
                    "timestamp": (datetime(2026, 9, 28, 12, tzinfo=timezone.utc) -
                                  timedelta(days=day)).strftime("%Y-%m-%dT%H:%M:%S+0000"),
                    "permalink": f"https://www.instagram.com/reel/FIXTUREgl{i:02d}/",
                    "caption": f"Glow check {i} #skincareroutine #glassskin"}
            row, _ = normalize_item(item, source="ig_bd", source_query="@fixture_glowlab",
                                    niche="beauty", username="fixture_glowlab",
                                    followers=48000, now="2026-09-28 12:00:00")
            upsert_reel(con, row)
        con.commit()
    finally:
        con.close()
    return path


def build_demo_dataset(d, now=NOW, k=10, invent=3):
    """A ready dataset: init, add demo_raw, score, lifecycle, synth. -> d."""
    from vsp.trends import jobs, schema as S, store
    store.init(d)
    recs = []
    for raw in demo_raw(now):
        rec, errs = S.normalize_observation(raw, now=now)
        if errs:
            raise ValueError(f"fixture observation invalid: {errs}")
        recs.append(rec)
    store.add_observations(d, recs, now)
    jobs.run_score(d, now)
    jobs.run_lifecycle(d, now)
    jobs.run_synth(d, now, niches=["beauty", "gadgets", "fitness"], k=k, invent=invent)
    return d


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "youtube":
        print(write_youtube_fixture(sys.argv[2]))
    else:
        print("usage: python3 -m vsp.trends.fixtures youtube DIR")
        sys.exit(2)
