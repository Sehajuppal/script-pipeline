# Voice: Cartesia TTS for the voice plan and the render agent's rules pack

Prepared 2026-09-29. Feeds a per-run `voice_plan.json` (one entry per spoken line) and the Cartesia rules pack for the Antigravity render agent (Gemini Omni video, Cartesia voice). Read: docs.cartesia.ai at API version `2026-08-14` (legacy versions for deprecated fields), platform help centres, FTC and state law, and the sample `v2.1-sample/sunrise-alarm-lamp` (brief VOICEOVER + voice spec, direction pacing table, `script.json` beats). Nothing was test-rendered (no API key in the sandbox), so every "sounds like" claim is Cartesia's or marked [A].

Grades: **[P]** official docs, platform or legal text · **[S]** independent study or standards body · **[M]** vendor marketing or vendor-run test · **[A]** our assumption, to calibrate. **UNKNOWN** = not documented anywhere I found.

## 0. TL;DR
1. **Model:** `sonic-3.6` is the latest and recommended; the alias tracks the newest stable snapshot, so pin `sonic-3.6-2026-08-27` for reproducible renders. 44 languages. `sonic-3-2025-10-27`, all `sonic-2*` and `sonic-turbo*` stop working on 2026-10-20. [P]
2. **Controls are few, and speed, volume and emotion are only "guidance":** `generation_config {speed 0.6–1.5, volume 0.5–2.0, emotion}` per request, or inline `<speed ratio="…"/>`, `<volume ratio="…"/>`, `<emotion value="…"/>`, `<break time="…"/>`, `<spell>…</spell>`, plus `[laughter]`. Speed, volume and emotion are beta. [P]
3. **Emotion:** 58 values, English only, most reliable on Emotive-tagged voices and on the six primary emotions `neutral, calm, angry, content, sad, scared`. A tag only works when the words already carry that emotion. [P]
4. **Leave prosody alone by default.** Sonic 3.6 sets pace, pause length and intonation from punctuation and context; Cartesia calls the controls a refinement. [P] We set emotion only where the energy curve needs lift, and speed only to hit a window. [A]
5. **Legacy fields are gone:** `__experimental_controls` (emotion:level arrays, −1…1 speed), the `speed` enum, voice embeddings and `{mode:"id"}` voice objects. The current API takes `"voice": "<id>"`. [P]
6. **Timestamps only on SSE and WebSocket:** `add_timestamps: true` returns `word_timestamps {words[], start[], end[]}` in seconds. For 48 kHz WAV + words.json, call SSE with raw `pcm_s16le` at 48000, wrap it in WAV, and offset each line by where it is placed. [P]/[A]
7. **Generate per line** (dialogue and rehook) with one voice, model, locale and format; set emotion and speed per line; place each clip in its window and fill spare time with silence, not slower speech. A single continuous take gives smoother prosody, but mid-take emotion changes are "highly experimental". [P]/[A]
8. **Transcript hygiene:** normal casing (the model tends to read an ALL-CAPS word letter by letter, so "comment LAMP" is sent as "comment lamp"); conventional numbers ($19.99, 12%); ranges with "to"; no emoji, arrows or markdown; codes in `<spell>`; brand names in a pronunciation dictionary. [P]
9. **Voices:** 500+ library voices. The API filters only by text query, gender and language/locale; there is no age or style filter. An IVC needs 10–60 s of audio (Pro plan). A PVC needs ≥30 min (Startup plan) and ignores speed and volume. [P]
10. **Consent:** Cartesia's AUP allows only your own voice, or someone else's with explicit consent. It bans impersonation (celebrities included) and output that represents minors. No verification step is documented. Commercial use needs Pro or above. [P]
11. **AI persona:** a disclosed synthetic voice with curator framing (D137). Turn on every platform AI label, plus the NY synthetic-performer disclosure. FTC 16 CFR 465 bans testimonials from people who don't exist or never used the product. **Creator clone:** needs a consent record, per-script approval, and first-person claims only if true. YouTube exempts own-voice clones; TikTok and Meta document no exemption, so label there. [P]
12. **Loudness:** −14 LUFS integrated with true peak ≤ −1 dBTP is a convention, not a published Reels/TikTok rule; AES TD1008 anchors speech-led streams at −18 LUFS. Deliver at 48 kHz, YouTube's recommended rate. [A]/[S]/[P]

## 1. Models, ids, languages, latency
| model_id | status on 2026-09-29 | langs | our use |
|---|---|---|---|
| `sonic-3.6` | alias → newest stable 3.6 snapshot | 44 | dev, calibration |
| `sonic-3.6-2026-08-27` | dated snapshot, never changes | 44 (adds `or`, `ur`) | **production pin** |
| `sonic-preview` | beta, changes without notice, no PVCs | — | never in renders |
| `sonic-3.5` / `sonic-3.5-2026-05-04` | stable | 42 | fallback |
| `sonic-3` / `sonic-3-2026-01-12` | stable; `sonic-3-2025-10-27` sunsets 2026-10-20 | 42 | Infill only (§4.1) |
| `sonic-2*`, `sonic-turbo*` | stop working 2026-10-20 | 8–9 | never |
| `sonic-latest` | deprecated alias of `sonic-preview`, still in the enum | — | never |

Sources: [Sonic 3.6](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest), [older models](https://docs.cartesia.ai/build-with-cartesia/tts-models/older-models), [deprecations](https://docs.cartesia.ai/build-with-cartesia/tts-models/api-changes). [P]
- **What 3.6 changes.** It is a drop-in replacement for 3.5 (same voices, request shape and prompts). It adapts pacing, pauses and intonation to the transcript's emotional context. Written disfluencies get a natural "thinking" pace. Heteronyms and codes read better in every language ([changelog](https://docs.cartesia.ai/changelog/2026)). [P] In Cartesia's blind test, listeners preferred 3.6 to 3.5 about 2:1 on English. [M]
- **Languages (3.6):** en de es fr ja pt zh hi ko it nl pl ru sv tr tl bg ro ar cs el fi hr ms sk da ta uk hu no vi bn th he ka id te gu kn ml mr pa or ur. [P]
- **Latency.** Cartesia claims about 90 ms to first audio byte for Sonic 3.5 ([overview](https://docs.cartesia.ai/get-started/overview)); 3.6 is called fastest but no number is given. [M] Offline renders care about throughput instead: 2 / 3 / 5 / 15 concurrent TTS requests on Free / Pro / Startup / Scale ([pricing](https://www.cartesia.ai/pricing)). [P]
- **Cost.** About 1 credit per character on every TTS endpoint; failed requests are free ([pricing docs](https://docs.cartesia.ai/pricing)). [P] A 30 s VO (≈450–600 characters) costs ≈500 credits per full take. [A]
- **Headers.** REST calls send `Authorization: Bearer <key>` and `Cartesia-Version: 2026-08-14`. The WebSocket takes `cartesia_version` as a query parameter, plus an `X-API-Key` header or an `access_token` query ([WebSocket ref](https://docs.cartesia.ai/api-reference/tts/websocket)). [P]

## 2. Controls
### 2.1 Inline SSML-like tags ([SSML tags](https://docs.cartesia.ai/build-with-cartesia/capability-guides/ssml-tags)) [P]
| tag | exact syntax | values | rules |
|---|---|---|---|
| speed | `<speed ratio="1.1"/>` | 0.6–1.5, default 1.0; sonic-3+ | Treated as guidance, not a multiplier. Small steps are hard to hear (Cartesia suggests 0.7 rather than 0.9 for a clear slow-down). No effect on PVCs. Never split the number across streamed chunks. |
| volume | `<volume ratio="0.8"/>` | 0.5–2.0, default 1.0; sonic-3+ | Same buffering rule. |
| emotion (beta) | `<emotion value="calm"/>` | enum (§2.3) | "Highly experimental" when it shifts mid-generation. Cartesia advises a separate context per emotion and Emotive voices. |
| break | `<break time="400ms"/>` / `<break time="1s"/>` | `ms` or `s`; min/max UNKNOWN | Use punctuation first. A break splits the generation, so the speech around it has less context. Several breaks close together can make the model hallucinate. Counts as 1 character; no spaces needed. |
| spell | `<spell>AB12CD</spell>` | letters, digits | Read character by character, with an automatic pause between letter and digit runs; a space inside adds a longer pause. Other punctuation inside may be read aloud ("dot"). Never chain with `<break>`. Phone numbers stay plain text. |

- **Placement.** Tags go inline anywhere in `transcript`. Self-closing tags act from their position onward: Cartesia's starter prompt resets speed with `<speed ratio="1.0"/>` ([prompting tips](https://docs.cartesia.ai/build-with-cartesia/capability-guides/prompting-tips)). [P] Which value wins when a tag and `generation_config` disagree is UNKNOWN.
- **Tags live only in the voice plan.** Our D44 gate treats brackets inside dialogue as stage directions, so tags go only in the voice plan's `transcript`, never in `script.json` dialogue. [P: repo]

### 2.2 `generation_config` ([Volume, Speed, Emotion](https://docs.cartesia.ai/build-with-cartesia/capability-guides/volume-speed-emotion)) [P]
- `{speed, volume, emotion}` works on sonic-3 and newer. It applies to one request only; there is no account default.
- `speed` accepts any double from 0.6 to 1.5 (default 1.0) and `volume` 0.5 to 2.0 (default 1.0). `emotion` is optional; when omitted, the model reads the emotional subtext itself.
- Cartesia prefers `generation_config` over tags for speed and volume, and tags for sentence-level changes. It says most well-punctuated transcripts need neither.
- PVCs take speed and volume from their training audio and ignore both controls; IVCs honour them ([PVC](https://docs.cartesia.ai/build-with-cartesia/capability-guides/clone-voices-pro)).

### 2.3 Emotions [P]
- **Full enum (58)** ([TTS ref](https://docs.cartesia.ai/api-reference/tts/bytes)): neutral, happy, excited, enthusiastic, elated, euphoric, triumphant, amazed, surprised, flirtatious, curious, content, peaceful, serene, calm, grateful, affectionate, trust, sympathetic, anticipation, mysterious, angry, mad, outraged, frustrated, agitated, threatened, disgusted, contempt, envious, sarcastic, ironic, sad, dejected, melancholic, disappointed, hurt, guilty, bored, tired, rejected, nostalgic, wistful, apologetic, hesitant, insecure, confused, resigned, anxious, panicked, alarmed, scared, proud, confident, distant, skeptical, contemplative, determined.
- **Best results** come from the six primary emotions: `neutral, calm, angry, content, sad, scared`. Values outside the enum are unsupported, and their behaviour may change without notice.
- **The tag only amplifies the words.** A "sad" tag on an excited sentence is unlikely to work, so the script's words must carry the tone.
- **Voices with the strongest emotional response:** Leo, Jace, Kyle, Gavin, Maya, Tessa, Dana, Marian (ids in §8). Emotion may be unreliable on voices without the Emotive tag.

### 2.4 Nonverbal tags
- Only `[laughter]` is documented ([Volume, Speed, Emotion](https://docs.cartesia.ai/build-with-cartesia/capability-guides/volume-speed-emotion)). [P] Other bracket tags (sighs, breaths): UNKNOWN.
- Our F142 bans scripted laughs, so the voice plan never emits a nonverbal tag.

### 2.5 Deprecated vs current [P]
| legacy | status | current |
|---|---|---|
| `voice.__experimental_controls {speed, emotion[]}`: speed −1.0…1.0 or `slowest…fastest`; emotion `anger\|positivity\|surprise\|sadness\|curiosity` + optional `:lowest\|:low\|:high\|:highest` | unsupported after 2026-06-01 ([2024-11-13 ref](https://docs.cartesia.ai/2024-11-13/api-reference/tts/bytes)) | `generation_config` + inline tags |
| top-level `speed: slow\|normal\|fast` | deprecated ([2026-03-01 ref](https://docs.cartesia.ai/2026-03-01/api-reference/tts/bytes)) | `generation_config.speed` |
| `voice {"mode": "embedding", …}`; `POST /voices/mix`; `/voices/clone/clip` | removed 2026-06-01 | voice ids; `POST /voices/clone` |
| `voice {"mode": "id", "id": …}` | 2026-03-01 shape | `"voice": "<id>"` or `{"id": "<id>"}` (2026-08-14) |
| `duration` (max seconds; could truncate) | absent in 2026 versions | none: there is no target-duration parameter |

### 2.6 Automatic prosody: when to leave it alone
- Sonic 3.6 varies pace and intonation to fit the transcript's emotional context, and adapts pause length to each sentence, without tags ([Sonic 3.6](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest)). [P] Heavy preprocessing (stripped punctuation, forced caps) hurts output ([3.5 migration](https://docs.cartesia.ai/build-with-cartesia/tts-models/sonic-3-to-sonic-3-5)). [P]
- **Leave it alone** when the line is a complete, well-punctuated sentence, fits its window at speed 1.0, and sounds right on a listen. [A]
- **Otherwise intervene in this order** [A]: (1) rewrite the words or punctuation; (2) set `emotion`, only on an Emotive voice and only where the curve needs lift (hook, payoff); (3) set `speed` to hit a window or a wpm floor; (4) add one `<break>` for a deliberate dramatic pause.

### 2.7 Writing transcripts ([prompting tips](https://docs.cartesia.ai/build-with-cartesia/capability-guides/prompting-tips), [normalization](https://docs.cartesia.ai/build-with-cartesia/capability-guides/text-normalization), [pronunciations](https://docs.cartesia.ai/build-with-cartesia/capability-guides/custom-pronunciations)) [P] unless marked
- **Sentences and punctuation.** Use full sentences with normal capitalization, and end every request with `.`, `?` or `!`. Never send a number, code or spell tag on its own.
- **Caps.** Use ALL CAPS only for initialisms that should be spelled out (`USA`, `LED`); other all-caps words may be spelled letter by letter. Caps never add emphasis. For emphasis, put the key word last in a short sentence. [A]
- **Symbols.** No markdown, bullets, emoji, hashtags or asterisks: Sonic reads them aloud. Our overlays ("TEST: alarm lamp · expected a nightlight → fills the room") never enter a transcript.
- **Numbers.** Write numbers, currency, dates, times, percentages, phone numbers, emails and everyday units in their normal written form (`$19.99`, `12%`, `7:00 PM`, `1,234`). The locale-aware normalizer (`normalization: "auto"`) reads them aloud; `"off"` or a locale code pins other reading conventions.
- **Normalizer gaps.** Hyphenated ranges (`$10-15`: write "10 to 15 dollars"), fractions ("two thirds"), equations, uncommon units (V, Pa) and industry abbreviations must be written out.
- **Codes.** Put codes and model numbers in `<spell>` inside a sentence, or space-separate the characters (`A B C, 1 2 3`). Periods between letters is the old Sonic 3 format.
- **Disfluencies are content.** Write `uh`, `um` or `hmm` in standard spelling, set off by commas, sparingly; they work best on 3.6. Sonic never inserts them itself.
- **Pronunciation dictionaries** handle names, brands and heteronyms. Create one with `POST /pronunciation-dicts/` and `{name, items: [{text, pronunciation, case_sensitive}], access}` ([create](https://docs.cartesia.ai/api-reference/pronunciation-dicts/create)); update it with `PATCH /pronunciation-dicts/{id}`. `pronunciation` is IPA (`<<ˈ|b|ɑ|ˈ|j|u>>`) or a sounds-like respelling ("chop-uh-TOO-liss"). The dictionary is a search-and-replace applied before the model; pass its id as `pronunciation_dict_id` (sonic-3+). `case_sensitive` defaults to false (case-insensitive matching needs 3.6+). Dictionaries are private unless `access` is `"public"`.
- **Last resort.** Pre-normalize the line ("nineteen dollars and ninety-nine cents") and set `normalization: "off"`; tags and dictionaries still apply.

## 3. Voices
### 3.1 Finding voices
- **Library.** 500+ voices; featured voices carry a check mark ([choosing a voice](https://docs.cartesia.ai/build-with-cartesia/capability-guides/choosing-a-voice)). [P]
- **`GET /voices` filters** ([list](https://docs.cartesia.ai/api-reference/voices/list)) [P]: `q` (matches name, description or id), `gender` (`masculine|feminine|gender_neutral`), `language` (`en` or `en-GB`), `is_owner`, `include_archived`; paging with `limit` (1–100), `starting_after`, `ending_before`; `expand[]=preview_file_url` returns a free audio preview.
- **No age or style filter** exists in the API. The playground adds tags such as Emotive; any other playground filters are UNKNOWN. Voice records carry `description`, `gender`, `is_pro` and `accents[] {accent, locale, is_native}`. [P]
- **Cartesia's own split** [P]: stable, realistic voices for agents (Daniel, Archie, Parker, Jameson, Corey; Skylar, Gemma, Jacqueline, Emma, Lauren) and Emotive voices for characters (Brandon, Cory, Alec; Lucy, Ariana, Dorothy).

### 3.2 Instant vs Pro voice clones ([IVC](https://docs.cartesia.ai/build-with-cartesia/capability-guides/clone-voices), [PVC](https://docs.cartesia.ai/build-with-cartesia/capability-guides/clone-voices-pro), [clone API](https://docs.cartesia.ai/api-reference/voices/clone)) [P]
| | Instant (IVC) | Professional (PVC) |
|---|---|---|
| audio | ≥10 s; up to 60 s used on 3.6+ (older models use only the first 10 s); ≤16 MB; flac, mp3, mpeg, mpga, oga, ogg, wav, webm | ≥30 min clean single-speaker audio; one language per PVC |
| time / plan | seconds / Pro+ | up to 3 h of training / Startup (2 slots), Scale (4) |
| controls | speed and volume work | speed and volume fixed by the dataset |
| models | any | auto-trained on `sonic-3.5-2026-05-04` and `sonic-3.6-2026-08-27`, and adapted to future models; `sonic-preview` returns `voice_model_mismatch` |
| API | `POST /voices/clone` (multipart: `clip`, `name`, `language`, optional `tagline` ≤32 chars, `description`, `accent`, `base_voice_id`, `access`) | `POST /datasets` → `/datasets/{id}/files` → `POST /fine-tunes` → `GET /fine-tunes/{id}/voices` |

- **A clone copies its recording:** the mood, accent, pace and energy of the clip. Cartesia says to speak naturally rather than like an announcer, with no music, noise or echo. [P]
- **For UGC,** record the IVC clip as a relaxed "telling a friend" read at the brand's energy. [A]

### 3.3 Consent, verification, terms
- **Acceptable Use Policy** ([AUP](https://www.cartesia.ai/legal/acceptable-use.html), rev. 2025-07-23) [P]: no impersonating any person or business, celebrities included. Upload only your own voice, or others' with their explicit consent; you alone answer for the rights and consents. No violating publicity rights, and no output that relates to or represents people under 18.
- **Verification.** No voice-verification or consent-capture step is documented for IVC or PVC: UNKNOWN. Consent is contractual, so we keep our own record. [A]
- **Commercial use.** The [Terms](https://www.cartesia.ai/legal/terms.html) license personal, non-commercial use unless the plan permits commercial use. The pricing page lists a commercial licence from Pro ($5/mo) up, so the render agent's account must be Pro or above. [P]
- **End-user disclosure.** [Cartesia's disclosure rules](https://www.cartesia.ai/legal/disclosure-requirements) require apps whose end users interact with its AI to say so first. [P] That targets interactive apps; our D138 covers posted videos.

### 3.4 Localization and accents ([multilingual voices](https://docs.cartesia.ai/build-with-cartesia/capability-guides/multilingual-voices)) [P]
- **`locale`** (3.6+, e.g. `en-GB`) picks both the regional accent and the reading conventions. `language` takes base codes. Set one, never both (400). A voice without the requested accent falls back to its native one.
- **`accent`** forces a deliberate accent (e.g. English with a Hindi accent). It must be one of the voice's `accents`, or the request fails with a 400.
- **Adding accents.** IVCs gain accents with `PATCH /voices/{id}/accents`: up to 10 per voice, same voice id. Public voices and PVCs need `POST /voices/localize`, which creates a new voice id. Each added accent costs 225 credits.
- **English accent ids** (clone metadata): african-american, arabic-english, australian, british, california, canadian-english, general-american, indian-english, irish, midwestern-american, new-york, new-zealand, philippine-english, singaporean, south-african, southern-us.

### 3.5 Picking a UGC voice (conversational, not announcer) [A] unless marked
1. Query `GET /voices?language=en-US&gender=<persona>&q=conversational&expand[]=preview_file_url`, then `q=casual|friendly|natural`. Drop any voice whose description says narrator, announcer, trailer, commercial or radio.
2. Match the rendered presenter's apparent age and gender (PRESENTER identity lock) and the market's accent. A face–voice realism mismatch reads as uncanny (vibe-tone-music.md §4). [S]
3. Use an Emotive voice if the plan sets emotions (§2.3) [P]; otherwise use a stable voice with no emotion tags.
4. Audition on the run's own hook, payoff and CTA lines (Cartesia: test on representative content). [P] Keep voices that read those lines at about 165–185 wpm at speed 1.0.
5. Render each line three times and reject voices whose timbre or energy drifts. Lock one voice per persona for life (RULES §3/§4).

## 4. API
### 4.1 Endpoints ([compare](https://docs.cartesia.ai/use-the-api/compare-tts-endpoints), [SSE](https://docs.cartesia.ai/api-reference/tts/sse), [infill](https://docs.cartesia.ai/api-reference/infill/bytes)) [P]
| endpoint | timestamps | continuations | containers | use |
|---|---|---|---|---|
| `POST /tts/bytes` (one streamed body) | no | no | wav, mp3, raw | files without timings |
| `POST /tts/sse` (events `chunk`, `timestamps`, `phoneme_timestamps`, `done`, `error`) | yes | no (`context_id` is only echoed) | raw | **our default**: one line per request, with word timings |
| `wss://api.cartesia.ai/tts/websocket` | yes | yes | raw | text arriving in pieces, many contexts on one socket, flush and cancel |
| `POST /infill/bytes` (`left_audio` → `transcript` → `right_audio`) | no | — | — | patching a line inside a take; `sonic-3` models only; 300 credits + ~1/char |

Cartesia's own advice: if you are not streaming text from a model, use bytes or SSE, not continuations. [P]

### 4.2 Request fields (2026-08-14) [P]
- **Required:** `model_id`, `transcript`, `voice` (`"<id>"` or `{"id"}`), and `output_format {container, encoding, sample_rate}` (+ `bit_rate` for mp3).
- **Optional on every endpoint:** `language` or `locale`, `accent`, `normalization`, `pronunciation_dict_id`, `generation_config`.
- **SSE and WS only:** `add_timestamps`, `add_phoneme_timestamps`, `use_normalized_timestamps` (normalized vs original tokens; not explained further; default null).
- **WS only:** `context_id` (required), `continue`, `max_buffer_delay_ms`, `flush`, and the separate `{context_id, cancel: true}` message.

### 4.3 WebSocket contexts, continuations, buffering, flush [P]
- **Continuations** ([contexts](https://docs.cartesia.ai/use-the-api/tts-websocket/contexts)). Use one `context_id` per utterance: `continue: true` on partial inputs, then `false` (or an empty transcript with `false`) on the last. Chunks are joined verbatim, so keep the spaces.
- **Same fields per context.** Every field except `transcript`, `continue` and `duration` must stay the same within a context. Yet the SDK examples push a new `generation_config` mid-context ([emotion example](https://docs.cartesia.ai/examples/tts-websocket-emotion)). The docs conflict, so treat mid-context changes as UNVERIFIED.
- **Lifecycle.** A context expires 1 s after its last audio goes out. `done: true` arrives only after the whole context. `cancel` stops only inputs that have not started generating.
- **Buffering** ([buffering](https://docs.cartesia.ai/use-the-api/tts-websocket/buffering)). `max_buffer_delay_ms` runs 0–5000 (default 3000). Send finished sentences with 0, or the server may wait up to 3 s for more text. Chunks without end punctuation add latency and can end in odd sounds.
- **Flush** ([flushing](https://docs.cartesia.ai/use-the-api/tts-websocket/context-flushing-and-flush-i-ds)). An empty transcript with `flush: true, continue: true` increments `flush_id`, which maps audio chunks back to the text that produced them; the server confirms with a `flush_done` message.

### 4.4 Word timestamps → words.json
- **Response shape** ([SSE ref](https://docs.cartesia.ai/api-reference/tts/sse)) [P]. With `add_timestamps: true`, events of `type: "timestamps"` carry `word_timestamps {words[], start[], end[]}` in seconds. Phoneme events carry `phoneme_timestamps {phonemes, start, end}`.
- **Assumptions and unknowns.** Streams can carry several timestamp events, so concatenate them in order. Times are relative to the start of the generation (Cartesia's example starts at 0). [A] Whether tags or punctuation appear as tokens is UNKNOWN.
- **Start times are the weaker signal.** Since 3.5, end-of-word times are stable but start times deserve testing ([3.5 migration](https://docs.cartesia.ai/build-with-cartesia/tts-models/sonic-3-to-sonic-3-5)) [P], so clamp each start to the previous word's end.
- **Tokens.** `use_normalized_timestamps: false` should return the transcript's own tokens (`$19.99`) rather than the normalized words [A: semantics undocumented]. Captions want the transcript tokens.
```python
def words_json(lines, duration_s):
    """lines in plan order; each has placed_s (clip start on the master timeline minus any
    head trim) and events (the SSE events of its generation)."""
    out = []
    for ln in lines:
        for ev in ln["events"]:
            if ev.get("type") == "timestamps":
                wt = ev["word_timestamps"]
                for w, s, e in zip(wt["words"], wt["start"], wt["end"]):
                    out.append({"word": w, "start": round(ln["placed_s"] + s, 3),
                                "end": round(ln["placed_s"] + e, 3)})
    out.sort(key=lambda x: x["start"])
    for a, b in zip(out, out[1:]):
        b["start"] = max(b["start"], a["end"])        # starts are the weaker signal
        b["end"] = max(b["end"], b["start"])
    return {"words": out, "duration_s": round(duration_s, 3)}
```
QA: every word falls inside [0, duration_s]; the tokens match the display text word for word, ignoring case and punctuation; no word crosses its line's window. [A]

### 4.5 Limits
- **Transcript length.** No per-request maximum is documented: UNKNOWN. Our lines are ≤ ~120 characters and a 30 s VO ≤ ~600. [A]
- **No seed and no previous-text conditioning** in the TTS spec. [P: absent] Takes are not guaranteed repeatable, so lock the accepted audio files, not the requests. [A]
- **Errors:** `concurrency_limited` (429), `quota_exceeded`, `voice_model_mismatch`, `voice_not_found`, `model_not_found`, `language_not_supported` ([conventions](https://docs.cartesia.ai/use-the-api/api-conventions)). [P]

### 4.6 Output format and loudness for video
- **Formats** ([output format](https://docs.cartesia.ai/build-with-cartesia/capability-guides/tts-output-audio-format)) [P]: containers `raw`, `wav`, `mp3` (only bytes offers all three; SSE and WS return `raw`); encodings `pcm_f32le`, `pcm_s16le`, `pcm_mulaw`, `pcm_alaw` (the last two are telephony formats); sample rates 8000, 16000, 22050, 24000, 44100, 48000; MP3 bit rates 32k–192k; defaults 44.1 kHz and 128 kbps. Channel count is not a parameter; assume mono. [A]
- **For video,** request `{"container":"raw","encoding":"pcm_s16le","sample_rate":48000}` on SSE and add the WAV header ourselves. 48 kHz is YouTube's recommended upload rate ([YouTube](https://support.google.com/youtube/answer/1722171?hl=en)). [P]
- **Loudness targets.** No platform publishes a Reels, TikTok or Shorts upload target (as in vibe-tone-music §2.3), so −14 LUFS integrated with true peak ≤ −1 dBTP is a convention. [A] Spotify normalizes music to −14 LUFS and leaves 1 dB of headroom for lossy encodes ([Spotify](https://support.spotify.com/et-am/artists/article/loudness-normalization/)) [P, music]. YouTube playing back near −14 LUFS is widely reported but not in its help pages [A]. AES TD1008 anchors speech-led streams at −18 LUFS ([summary](https://www.radioworld.com/tech-and-gear/tech-tips/streaming-audio-loudness-guidelines-explained)) [S].
- **Mix rule** [A]: bring every VO clip to the same loudness, shape the energy curve with ±1–2 dB of clip gain (payoff loudest), duck music −8 dB under speech, then master to −14 LUFS / −1 dBTP.

## 5. Best practice for voiceover-first production
### 5.1 Per line vs one continuous take
| | line mode (default) | take mode |
|---|---|---|
| how | one SSE request per `dialogue` and per `rehook`; same voice, model, locale and format | one SSE request for the whole VO; split at the word gaps the timestamps show; move only the silences |
| pros | each line lands in its window; per-line `generation_config`; cheap retries | one prosodic arc, like a creator's single take |
| cons | each line starts "fresh", but UGC talking heads are jump-cut per sentence anyway [A] | tone changes need inline emotion tags, "highly experimental" mid-generation [P]; one bad word re-renders the take [A] |
| use for | hype-energy, demo, ≥2 tone changes | cozy-calm, story, expert with one tone |

- **Continuations** are for text that arrives in pieces; our text is known up front. [P]
- **Multi-sentence beats** (e.g. DEMO) go in one request, so the model hears the full context. [P]

### 5.2 Fitting lines into a target window
- **The maker already sizes windows.** It gives each window 3.0 words/s (2.5 with a slow key) plus 1.15 slack (D43, `vsp/timing.py`), so lines should fit at a natural 160–185 wpm. [P: repo]
- **Fit loop** [A]: (1) render at the calibrated speed for `target_wpm` (§7.2); (2) measure speech time as the last `end` minus the first `start`; (3) if it overruns the budget (window minus gaps), raise speed once, up to 1.15; (4) if it still overruns, send the line back to `vsp/repair.py` to cut words, and never time-stretch or truncate audio; (5) if it underruns, keep the speech and fill with room tone. Never go below the beat's wpm floor: calm comes from pauses and fewer words (direction).
- **Calibrate each voice.** Speed is guidance, and its effect depends on the voice, the length and the punctuation. [P] Render three representative lines at speeds 0.9, 1.0, 1.1 and 1.2, store the measured wpm for each, and interpolate. [A]
- **QA.** Effective wpm = words ÷ speech time × 60. Fail above 200; warn above 190 (the direction's cap) or more than 10 below the floor. [A]

### 5.3 Matching the energy curve
- **Split the work:** words carry tone, `emotion` nudges it, `volume` and clip gain carry loudness, and cuts carry energy. Vocal arousal is inverted-U while visual variation is linear (vibe-tone-music §2.2). [S/M]
- **One peak:** energy 5 only on the payoff, the loudest line and the only `excited` read. Drop to warm right after it (A1), and never go wall-to-wall hype (A6). [P: repo]

### 5.4 Avoiding the "robotic TTS" feel
- **Text:** full sentences, contractions and terminal punctuation on every request. No caps emphasis, no symbols, and at most one `<break>` per line. [P]
- **Voice:** one voice and one pinned snapshot for every line of a video. Leave emotion off unless the voice is Emotive and the words agree. [P]
- **Speed** stays near 1.0; big jumps sound processed. [A]
- **Disfluencies:** at most one per 30 s ("so, um,"), never on proof, price or guarantee lines. The creator-clone lane may use the two its voice spec allows. [A]
- **Room tone:** lay matching room tone (bedroom, kitchen) and a light matching reverb under the dry TTS. Studio-dry speech over phone footage reads as dubbed. [A]
- **Lip-sync:** talking-head shots need the VO as their driving audio. Whether Gemini Omni accepts audio for lip-sync is UNKNOWN; if it doesn't, voice AI personas over B-roll, hands and off-lens shots. [A]

## 6. Compliance for synthetic voices and avatars
- **TikTok.** Creators must label AI-generated content that contains realistic images, audio or video ([AIGC](https://support.tiktok.com/en/using-tiktok/creating-videos/ai-generated-content)). [P] The API field `is_aigc: true` adds the AI-generated tag ([video object](https://developers.tiktok.com/docs/en/tiktok-api-v2-video-object)). [P] TikTok Shop bans AI voices in LIVE, and reportedly in shoppable videos (vibe-tone-music §3.1). [P/UNVERIFIED]
- **Meta.** People must use the disclosure tool when they post photorealistic video or realistic-sounding audio that was digitally created or altered, and Meta may penalize failure ([Feb 2024](https://about.fb.com/news/2024/02/labeling-ai-generated-images-on-facebook-instagram-and-threads/)). [P] "AI info" labels come from industry signals or self-disclosure ([2024 update](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/)). [P]
- **YouTube.** Realistic AI content (a real person saying something they didn't, a realistic event that never happened) must be disclosed via "AI use" in Studio. Cloning your own voice for voiceovers or dubs is listed as a minor edit that needs no disclosure. C2PA metadata can trigger automatic labels, and repeated non-disclosure risks removal or YPP suspension ([YouTube](https://support.google.com/youtube/answer/14328491?hl=en)). [P]
- **FTC 16 CFR 465** (in force 2024-10-21) bans reviews and testimonials that misrepresent that the reviewer exists (the FTC names AI-generated fake reviews), that they had actual experience with the product, or what that experience was. It covers creating, buying and disseminating such reviews, with civil penalties for knowing violators ([FTC](https://www.ftc.gov/news-events/news/press-releases/2024/08/federal-trade-commission-announces-final-rule-banning-fake-reviews-testimonials), [eCFR](https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-465)). [P]
- **FTC Endorsement Guides** (16 CFR 255, revised 2023). An endorser is whatever *appears* to be an individual, group or institution. The FTC says this covers fabricated and virtual endorsers as well as fake reviewers ([2023 notice](https://www.ftc.gov/system/files/ftc_gov/pdf/p204500_endorsement_guides_in_2023.pdf)). [P] So an AI persona's claims need substantiation and its material connections need disclosure ([Part 255](https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-255)). [P]
- **New York AI Synthetic Performers Disclosure Law** (signed 2025-12-11; in force June 2026 per D138): ads reaching NY consumers must conspicuously disclose an AI-generated human likeness. Fines are $1,000 for a first violation and $5,000 after ([Crowell](https://www.crowell.com/en/insights/client-alerts/synthetic-performers-real-consequences-implications-of-trailblazing-new-york-ai-ad-law)). [P, summary]
- **Tennessee ELVIS Act** (in force 2024-07-01): a person's voice, actual or simulated, is now a protected right. It adds liability for unauthorized commercial use and for tools whose primary purpose is producing someone's voice or likeness without authorization ([Skadden](https://www.skadden.com/insights/publications/2024/04/tennessee-law-addresses-proliferation-of-deepfakes)). [P, summary]
- **NO FAKES Act of 2026** (S.4591 / H.R.8915, introduced 2026-05-20): would create federal voice and likeness rights with notice-and-removal. Senate Judiciary reported it, and it was placed on the Senate calendar on 2026-06-24. It is not law as of today ([Congress.gov](https://www.congress.gov/bill/119th-congress/senate-bill/4591/all-actions)). [P]
- **Also:** California [AB 1836](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240AB1836) (consent for digital replicas of deceased personalities) and [AB 2602](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240AB2602) (limits on contract terms licensing a performer's digital replica). EU AI Act Art. 50 deepfake transparency applies from 2026-08-02 (D138). [P]

**(a) AI persona reading a product script** (basis [P], synthesis [A])
1. It is an endorser that never existed and never used the product, so it can never give a testimonial. Use curator or explainer framing, and run D137 on the TTS `transcript` too: no confessions, no "I tried/woke/noticed", no `[laughter]`.
2. Disclose everywhere: the D138 caption line and frame-0 label, TikTok `is_aigc`, the Meta AI label, YouTube "AI use = yes", and the NY conspicuous disclosure on paid ads.
3. The voice is a library voice on a commercial tier, or a clone of a paid voice actor under a written licence covering synthetic ad use, term and revocation. Never a sound-alike of a real person (AUP, ELVIS, NO FAKES).
4. Stay out of TikTok Shop.

**(b) A creator's own cloned voice**
1. Keep a consent record stored with the voice id: brand, campaign, term, per-script approval, revocation and clone deletion. Cartesia requires explicit consent for any voice that isn't the account holder's.
2. A clone speaking lines the creator never approved misstates their experience (§465.2). First-person claims are allowed only if true and approved line by line.
3. Labels: on YouTube an own-voice VO alone needs no disclosure. TikTok and Meta document no own-voice exemption and both target realistic synthetic audio, so label there. Any realistic AI-rendered visuals flip all three platforms to "yes", whatever the voice.
4. Material-connection disclosures (#ad, paid partnership) are unchanged.

## 7. Design implications for our pipeline
### 7.1 Per-line voice plan (`voice_plan.json`, one per run) [A]
There is one entry per spoken line, with dialogue and rehook as separate entries. `display` is the caption text and `transcript` is what Cartesia receives. The two may differ only in casing, punctuation, inline tags and normalization-safe rewrites; any word change is written back to the captions.
```json
{"schema_version": 1, "run": "led-sunrise-alarm-lamp", "lane": "creator_clone",
 "engine": {"provider": "cartesia", "api_version": "2026-08-14", "endpoint": "/tts/sse", "mode": "line",
            "model_id": "sonic-3.6-2026-08-27", "locale": "en-US", "normalization": "auto",
            "pronunciation_dict_id": null,
            "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": 48000}},
 "voice": {"id": "<creator-ivc-id>", "source": "ivc", "emotive": false, "consent_ref": "<consent-record-id>",
           "calibration_wpm": {"0.9": null, "1.0": null, "1.1": null, "1.2": null}},
 "disclosure": {"tiktok_is_aigc": true, "instagram_ai_label": true, "youtube_ai_use": "if_visuals_ai"},
 "mix": {"integrated_lufs": -14, "true_peak_dbtp": -1, "music_duck_db": -8, "room_tone": "bedroom"},
 "lines": [
  {"id": "L1", "beat": "VERBAL HOOK + LOCK", "role": "dialogue", "window": [0.5, 3.0], "anchor": "start",
   "display": "Tired of sunrise alarm lamps that fail fast?",
   "transcript": "Tired of sunrise alarm lamps that fail fast?",
   "tone": "confident", "energy": 4, "wpm": {"floor": 180, "target": 180, "max": 190},
   "generation_config": {"speed": 1.0, "volume": 1.05}, "gap_after_s": 0.3, "first_person_claim": false},
  {"id": "L6", "beat": "PAYOFF", "role": "dialogue", "window": [21.9, 25.4], "anchor": "start",
   "display": "Test result: I woke up before the alarm.",
   "transcript": "Test result: I woke up before the alarm.",
   "tone": "excited", "energy": 5, "wpm": {"floor": 150, "target": 150, "max": 190},
   "generation_config": {"speed": 1.0, "volume": 1.15}, "gap_before_s": 0.5, "gap_after_s": 0.4,
   "first_person_claim": true, "creator_approved": true},
  {"id": "L7", "beat": "COMMENT BAIT", "role": "dialogue", "window": [25.4, 28.0], "anchor": "start",
   "display": "Follow, comment LAMP for the link list.",
   "transcript": "Follow, comment lamp for the link list.",
   "tone": "playful", "energy": 4, "wpm": {"floor": 180, "target": 180, "max": 190},
   "generation_config": {"speed": 1.0, "volume": 1.05}, "first_person_claim": false}],
 "outputs": {"audio": "led-sunrise-alarm-lamp-vo.wav", "words": "led-sunrise-alarm-lamp-words.json"}}
```
- **Field notes:** `lane` is `ai_persona`, `creator_clone` or `real_voice`; `engine.mode` is `line` or `take`. `voice.source` is `library`, `ivc`, `pvc`, `actor_ivc` or `actor_pvc`, and every clone needs a `consent_ref`. `anchor` is `start` or `end`; `wpm.floor` comes from `direction.energy_curve[].wpm`. `generation_config` is passed to Cartesia verbatim, so omitted keys take Cartesia's defaults; `emotion` is omitted in the example because `emotive` is false.
- **Write-back:** per line, the render agent records `audio_file`, `placed_s`, `speech_s`, `effective_wpm`, `attempts` and `request_ids`.
- **Voice-plan gate:** D137 (`lexicon.AI_FIRST_PERSON`) runs on the tag-stripped `transcript` in `ai_persona`, and `creator_clone` claims need `creator_approved`. No nonverbal tags and no brackets other than the five tags. Values stay inside the API ranges and the house ranges (speed 0.9–1.15, volume 0.9–1.2), and `emotion` must be in the enum. `display` and `transcript` must be word-equal, and the lane must match the disclosure toggles.

### 7.2 Tone → Cartesia emotion, speed, volume [A] (P for value ranges)
- **`target_wpm`** is the beat's floor when its delivery has a slow key ("slow down", "unhurried", "never rushed"). Otherwise it is the larger of the floor and the tone band's midpoint, capped at 190.
- **`speed`** interpolates the voice's calibration at `target_wpm`, clamped to 0.9–1.15 (the API allows 0.6–1.5) and snapped to 1.0 within ±0.05. Omit it for PVCs.
- **`volume`** follows energy: 1–2 → 0.9, 3 → 1.0, 4 → 1.05, 5 → 1.15 (payoff only). The line after the peak returns to 1.0.
- **`emotion`** is set only on an Emotive voice with an English locale; otherwise it is omitted. Proof, price and guarantee lines get `neutral` or none.

| tone | band wpm | emotion → fallback | speed start | volume | notes |
|---|---|---|---|---|---|
| warm | 155–175 | `content` → omit | 1.0 | 1.0 | default; the post-peak line |
| confident | 160–180 | `confident` → `neutral` | 1.0 | 1.05 | hook, verdict; end on a period |
| excited | 170–190 | `excited` (payoff) / `enthusiastic` (demo) → `happy` | 1.05 | 1.1 (payoff 1.15) | AI: reveal lines only, never a testimonial |
| calm | 150–160 | `calm` → `peaceful` | 1.0, ≥ floor | 0.9 | best synthetic style |
| deadpan | 155–175 | `neutral` → omit | 1.0 | 1.0 | 0.4–0.6 s gap before the punchline |
| expert | 150–170 | `confident` → `neutral` | 1.0 | 1.0 | numbers in short sentences |
| playful | 165–185 | `happy` → `curious` | 1.05 | 1.0 | never on proof or price |
| empathetic | 150–165 | `sympathetic` → `calm` | 1.0 | 0.95 | AI: third person only |
| curious* | — | `curious` → `anticipation` | 1.0 | 1.0 | question hooks |
| serious* | — | `neutral` → `determined` | 1.0 | 1.0 | proof, price, guarantee |

\*Not in `creative_vocab.TONES` yet. Bands come from `TONE_PROFILES`. Only `content`, `calm` and `neutral` are primary emotions [P], so every other row needs a listen test on the chosen voice.

### 7.3 Pauses at beat boundaries [A] unless marked
1. **Anchors.** Dialogue starts at the window start + 0.10 s. A rehook ends at the window end − 0.10 s, because `vsp/timing.py` and `vsp/captions.py` speak it at the beat's end. [P: repo] The brief's "[8.0s] (spoken transition)" therefore means "ending at 8.0 s".
2. **Gaps.** Leave ≥0.30 s between lines (`timing.PAUSE`), 0.5 s before the payoff (under the riser) and 0.4 s after it. Any gap over 1.0 s gets room tone or SFX, never digital silence.
3. **No breaks at seams.** In line mode, silence goes in the edit, never in `<break>` tags, because breaks split the generation. [P] Inside a line, allow at most one `<break>` of 200–600 ms, never next to `<spell>`.
4. **Trim** each clip to 40 ms before its first `start` and 80 ms after its last `end`, and shift its word times by the same offset.

### 7.4 Numbers, prices, acronyms, keywords [P] unless marked
1. Use only numbers from the prompt (D37/D136); the voice plan never adds one.
2. Write prices and percentages as in the script (`$25`, `12%`). Write ranges with "to", and fractions and uncommon units in words.
3. Lower-case the comment word in `transcript` ("comment lamp"); caps stay in `display` and the captions.
4. Initialisms meant to be spelled out stay in caps (`LED`). Caps words meant as words are lowered. A misread acronym gets `<spell>` or a dictionary entry.
5. Keep one pronunciation dictionary per brand, referenced by `engine.pronunciation_dict_id` and logged with the run. [A]
6. Strip emoji, arrows, `·`, hashtags and parentheses from `transcript`.
7. Keep the maker's punctuation. If a colon-led line ("Confession: …", "Part 2: …") reads oddly on the chosen voice, swap the colon for a comma or period. [A]

### 7.5 Lane rules
| | `ai_persona` | `creator_clone` | `real_voice` |
|---|---|---|---|
| when | presenter=ai | human presenter who opted in to cloning | human presenter (today's default) |
| voice | licensed library voice or a voice actor's licensed clone | the creator's own IVC or PVC | the creator on the day; no TTS, no voice changer |
| consent | actor licence if cloned | creator consent + per-script approval | — |
| first-person use claims | never (D137, §465.2) | only true and creator-approved | only true |
| delivery controls | §7.2, restricted tones (vibe-tone-music §4) | §7.2 | the plan is a read guide: windows, wpm, pauses, stress |
| AI labels | all on + D138 caption line + frame-0 label | TikTok and Meta on; YouTube only if visuals are AI-realistic | set by the visuals alone |
| TikTok Shop | no | no: it is an AI voice [A] | yes |
| words.json | Cartesia timestamps | Cartesia timestamps | omit; the caption stage aligns |

### 7.6 Issues found in the sample
1. **Lane mismatch.** The lamp bundle is presenter=human with "Real voice… no TTS", yet the render agent voices with Cartesia. Either the lane is `real_voice` and nothing is synthesized, or it needs a consented `creator_clone` lane. The voice spec must name the lane.
2. **AI toggles.** The brief asks for generated, realistic shots of "a man in his late 20s…", yet `is_aigc`, `is_ai_generated` and `containsSyntheticMedia` are all false. If those shots are rendered, all three platforms need the AI label, and NY paid ads need the synthetic-performer disclosure. This needs a gate; it is not voice-specific.
3. **"comment LAMP"** would be spelled out letter by letter (§2.7). Timing of the spoken transitions is ambiguous in the brief (§7.3).

## 8. CARTESIA_CAPS
```json
{
 "as_of": "2026-09-29",
 "api": {"base_url": "https://api.cartesia.ai", "version_header": "Cartesia-Version", "version": "2026-08-14",
  "older_versions": ["2026-03-01", "2025-04-16", "2024-11-13", "2024-06-10"], "rest_auth": "Authorization: Bearer <api key>",
  "ws_url": "wss://api.cartesia.ai/tts/websocket", "ws_version_query": "cartesia_version", "ws_auth": ["X-API-Key header", "access_token query"]},
 "models": {"recommended": "sonic-3.6", "production_pin": "sonic-3.6-2026-08-27", "preview": "sonic-preview",
  "snapshots": {"sonic-3.6": ["sonic-3.6-2026-08-27"], "sonic-3.5": ["sonic-3.5-2026-05-04"], "sonic-3": ["sonic-3-2026-01-12", "sonic-3-2025-10-27"]},
  "deprecated_aliases": {"sonic-latest": "sonic-preview", "sonic-3-latest": "sonic-preview", "sonic-3-preview": "sonic-3"},
  "sunset_2026_10_20": ["sonic-2 (all snapshots)", "sonic-turbo (all snapshots)", "sonic-3-2025-10-27"],
  "sunset_2026_06_01": ["sonic", "sonic-english", "sonic-multilingual"],
  "languages_sonic_3_6": ["en", "de", "es", "fr", "ja", "pt", "zh", "hi", "ko", "it", "nl", "pl", "ru", "sv", "tr", "tl", "bg", "ro", "ar", "cs", "el", "fi", "hr", "ms", "sk", "da", "ta", "uk", "hu", "no", "vi", "bn", "th", "he", "ka", "id", "te", "gu", "kn", "ml", "mr", "pa", "or", "ur"],
  "ttfb_ms_claimed": {"sonic-3.5": 90, "sonic-3.6": null}},
 "endpoints": {
  "tts_bytes": {"method": "POST", "path": "/tts/bytes", "containers": ["wav", "mp3", "raw"], "timestamps": false, "continuations": false},
  "tts_sse": {"method": "POST", "path": "/tts/sse", "containers": ["raw"], "timestamps": true, "continuations": false, "events": ["chunk", "timestamps", "phoneme_timestamps", "done", "error"]},
  "tts_websocket": {"path": "/tts/websocket", "containers": ["raw"], "timestamps": true, "continuations": true, "messages": ["chunk", "timestamps", "phoneme_timestamps", "flush_done", "done", "error"]},
  "infill_bytes": {"method": "POST", "path": "/infill/bytes", "models": ["sonic-3", "sonic-3-2026-01-12"], "fields": ["left_audio", "right_audio", "transcript", "voice_id", "model_id", "language"]},
  "voices_list": "GET /voices", "voice_get": "GET /voices/{id}", "voice_clone": "POST /voices/clone",
  "voice_add_accents": "PATCH /voices/{id}/accents", "voice_localize": "POST /voices/localize",
  "pronunciation_dict_create": "POST /pronunciation-dicts/", "pronunciation_dict_update": "PATCH /pronunciation-dicts/{id}",
  "pvc": ["POST /datasets", "POST /datasets/{id}/files", "POST /fine-tunes", "GET /fine-tunes/{id}", "GET /fine-tunes/{id}/voices"]},
 "request": {"required": ["model_id", "transcript", "voice", "output_format"],
  "optional": ["language", "locale", "accent", "normalization", "pronunciation_dict_id", "generation_config"],
  "sse_ws_only": ["add_timestamps", "add_phoneme_timestamps", "use_normalized_timestamps"],
  "ws_only": ["context_id", "continue", "max_buffer_delay_ms", "flush", "cancel"],
  "voice_shape": {"2026-08-14": ["<voice_id>", {"id": "<voice_id>"}], "2026-03-01": {"mode": "id", "id": "<voice_id>"}},
  "language_xor_locale": true, "locale_min_model": "sonic-3.6", "normalization": ["auto", "off", "<language or locale code>"]},
 "output_format": {"containers": ["raw", "wav", "mp3"], "encodings": ["pcm_f32le", "pcm_s16le", "pcm_mulaw", "pcm_alaw"],
  "sample_rates": [8000, 16000, 22050, 24000, 44100, 48000], "mp3_bit_rates": [32000, 64000, 96000, 128000, 192000],
  "defaults": {"sample_rate": 44100, "wav_encoding": "pcm_s16le", "mp3_bit_rate": 128000}, "channels": null,
  "video_pick": {"endpoint": "sse", "container": "raw", "encoding": "pcm_s16le", "sample_rate": 48000, "wrap": "wav"}},
 "generation_config": {"min_model": "sonic-3", "scope": "per request", "pvc_ignores": ["speed", "volume"],
  "speed": {"min": 0.6, "max": 1.5, "default": 1.0}, "volume": {"min": 0.5, "max": 2.0, "default": 1.0},
  "emotion": {"beta": true, "languages": ["en"], "omitted": "model infers emotion from the text"}},
 "inline_tags": {"speed": {"syntax": "<speed ratio=\"1.0\"/>", "min": 0.6, "max": 1.5, "beta": true},
  "volume": {"syntax": "<volume ratio=\"1.0\"/>", "min": 0.5, "max": 2.0, "beta": true},
  "emotion": {"syntax": "<emotion value=\"calm\"/>", "beta": true},
  "break": {"syntax": "<break time=\"500ms\"/>", "units": ["ms", "s"], "min": null, "max": null, "counts_as_chars": 1},
  "spell": {"syntax": "<spell>ABC123</spell>"}, "tag_vs_generation_config_precedence": null},
 "nonverbal_tags": ["[laughter]"],
 "emotions": {"primary": ["neutral", "calm", "angry", "content", "sad", "scared"],
  "all": ["neutral", "happy", "excited", "enthusiastic", "elated", "euphoric", "triumphant", "amazed", "surprised", "flirtatious", "curious", "content", "peaceful", "serene", "calm", "grateful", "affectionate", "trust", "sympathetic", "anticipation", "mysterious", "angry", "mad", "outraged", "frustrated", "agitated", "threatened", "disgusted", "contempt", "envious", "sarcastic", "ironic", "sad", "dejected", "melancholic", "disappointed", "hurt", "guilty", "bored", "tired", "rejected", "nostalgic", "wistful", "apologetic", "hesitant", "insecure", "confused", "resigned", "anxious", "panicked", "alarmed", "scared", "proud", "confident", "distant", "skeptical", "contemplative", "determined"]},
 "voices_best_emotion": {"Leo": "0834f3df-e650-4766-a20c-5a93a43aa6e3", "Jace": "6776173b-fd72-460d-89b3-d85812ee518d", "Kyle": "c961b81c-a935-4c17-bfb3-ba2239de8c2f", "Gavin": "f4a3a8e4-694c-4c45-9ca0-27caf97901b5", "Maya": "cbaf8084-f009-4838-a096-07ee2e6612b1", "Tessa": "6ccbfb76-1fc6-48f7-b71d-91ac6298247b", "Dana": "cc00e582-ed66-4004-8336-0175b85c85f6", "Marian": "26403c37-80c1-4a1a-8692-540551ca2ae5"},
 "voices_stable": {"Skylar (en-US F)": "db6b0ed5-d5d3-463d-ae85-518a07d3c2b4", "Daniel (en-US M)": "47c38ca4-5f35-497b-b1a3-415245fb35e1", "Jacqueline (en-US F)": "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc", "Gemma (en-GB F)": "62ae83ad-4f6a-430b-af41-a9bede9286ca", "Archie (en-GB M)": "ef191366-f52f-447a-a398-ed8c0f2943a1"},
 "timestamps": {"request": ["add_timestamps", "add_phoneme_timestamps", "use_normalized_timestamps"],
  "word_event": {"type": "timestamps", "field": "word_timestamps", "keys": ["words", "start", "end"], "unit": "s"},
  "phoneme_event": {"type": "phoneme_timestamps", "field": "phoneme_timestamps", "keys": ["phonemes", "start", "end"], "unit": "s"},
  "origin": null, "tags_in_tokens": null, "normalized_semantics": null, "start_times_less_stable_since": "sonic-3.5"},
 "websocket": {"context_expiry_s": 1, "max_buffer_delay_ms": {"min": 0, "max": 5000, "default": 3000},
  "fields_fixed_per_context": "all except transcript, continue, duration", "mid_context_generation_config": null, "flush_id": true},
 "voices": {"library_size": "500+", "list_filters": ["q", "gender", "language", "is_owner", "include_archived", "limit", "starting_after", "ending_before", "expand[]"],
  "gender": ["masculine", "feminine", "gender_neutral"], "age_filter": null, "style_filter": null, "playground_tags": ["Emotive"],
  "max_accents_per_voice": 10, "localize_credits_per_accent": 225,
  "english_accents": ["african-american", "arabic-english", "australian", "british", "california", "canadian-english", "general-american", "indian-english", "irish", "midwestern-american", "new-york", "new-zealand", "philippine-english", "singaporean", "south-african", "southern-us"]},
 "cloning": {"ivc": {"min_s": 10, "max_used_s": 60, "max_mb": 16, "formats": ["flac", "mp3", "mpeg", "mpga", "oga", "ogg", "wav", "webm"], "plan": "pro", "speed_volume_controls": true},
  "pvc": {"min_minutes": 30, "training_h_max": 3, "plan": "startup", "slots": {"startup": 2, "scale": 4}, "speed_volume_controls": false, "sonic_preview": false},
  "verification_step": null, "consent": "own voice or explicit consent (AUP)"},
 "limits": {"max_transcript_chars": null, "credits_per_char": 1, "tts_concurrency": {"free": 2, "pro": 3, "startup": 5, "scale": 15},
  "seed": null, "previous_text_conditioning": null, "commercial_use_min_plan": "pro"},
 "deprecated": {"voice.__experimental_controls": {"unsupported_after": "2026-06-01", "speed": "-1.0..1.0 or slowest|slow|normal|fast|fastest", "emotion": "anger|positivity|surprise|sadness|curiosity with optional :lowest|:low|:high|:highest"},
  "speed_enum": ["slow", "normal", "fast"], "voice_mode_embedding": "rejected since 2026-06-01", "duration": "legacy max-duration cap, absent in 2026 versions"}
}
```

## Sources
- **Cartesia models:** [Sonic 3.6](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest) · [Older models](https://docs.cartesia.ai/build-with-cartesia/tts-models/older-models) · [Deprecations](https://docs.cartesia.ai/build-with-cartesia/tts-models/api-changes) · [3.5 migration](https://docs.cartesia.ai/build-with-cartesia/tts-models/sonic-3-to-sonic-3-5) · [Changelog 2026](https://docs.cartesia.ai/changelog/2026) · [Overview](https://docs.cartesia.ai/get-started/overview) · [Launch page](https://www.cartesia.ai/launch)
- **Cartesia controls:** [SSML tags](https://docs.cartesia.ai/build-with-cartesia/capability-guides/ssml-tags) · [Volume, speed, emotion](https://docs.cartesia.ai/build-with-cartesia/capability-guides/volume-speed-emotion) · [Prompting tips](https://docs.cartesia.ai/build-with-cartesia/capability-guides/prompting-tips) · [Text normalization](https://docs.cartesia.ai/build-with-cartesia/capability-guides/text-normalization) · [Advanced capabilities](https://docs.cartesia.ai/build-with-cartesia/capability-guides/advanced-capabilities) · [Custom pronunciations](https://docs.cartesia.ai/build-with-cartesia/capability-guides/custom-pronunciations) · [Create pronunciation dictionary](https://docs.cartesia.ai/api-reference/pronunciation-dicts/create)
- **Cartesia voices:** [Choosing a voice](https://docs.cartesia.ai/build-with-cartesia/capability-guides/choosing-a-voice) · [Multilingual voices](https://docs.cartesia.ai/build-with-cartesia/capability-guides/multilingual-voices) · [Instant clone](https://docs.cartesia.ai/build-with-cartesia/capability-guides/clone-voices) · [Pro clone](https://docs.cartesia.ai/build-with-cartesia/capability-guides/clone-voices-pro) · [Clone API](https://docs.cartesia.ai/api-reference/voices/clone) · [List voices](https://docs.cartesia.ai/api-reference/voices/list)
- **Cartesia API:** [Bytes](https://docs.cartesia.ai/api-reference/tts/bytes) · [SSE](https://docs.cartesia.ai/api-reference/tts/sse) · [WebSocket](https://docs.cartesia.ai/api-reference/tts/websocket) · [2026-03-01 bytes](https://docs.cartesia.ai/2026-03-01/api-reference/tts/bytes) · [2024-11-13 bytes](https://docs.cartesia.ai/2024-11-13/api-reference/tts/bytes) · [Compare endpoints](https://docs.cartesia.ai/use-the-api/compare-tts-endpoints) · [Contexts](https://docs.cartesia.ai/use-the-api/tts-websocket/contexts) · [Buffering](https://docs.cartesia.ai/use-the-api/tts-websocket/buffering) · [Flushing](https://docs.cartesia.ai/use-the-api/tts-websocket/context-flushing-and-flush-i-ds) · [Continuations](https://docs.cartesia.ai/build-with-cartesia/capability-guides/stream-inputs-using-continuations) · [Output format](https://docs.cartesia.ai/build-with-cartesia/capability-guides/tts-output-audio-format) · [SSE timestamps example](https://docs.cartesia.ai/examples/tts-sse-with-timestamps) · [WebSocket emotion example](https://docs.cartesia.ai/examples/tts-websocket-emotion) · [Infill](https://docs.cartesia.ai/api-reference/infill/bytes) · [API conventions](https://docs.cartesia.ai/use-the-api/api-conventions) · [Pricing docs](https://docs.cartesia.ai/pricing) · [Pricing page](https://www.cartesia.ai/pricing)
- **Cartesia legal:** [Acceptable use](https://www.cartesia.ai/legal/acceptable-use.html) · [Terms](https://www.cartesia.ai/legal/terms.html) · [Disclosure requirements](https://www.cartesia.ai/legal/disclosure-requirements)
- **Platforms:** [TikTok AIGC](https://support.tiktok.com/en/using-tiktok/creating-videos/ai-generated-content) · [TikTok video object](https://developers.tiktok.com/docs/en/tiktok-api-v2-video-object) · [Meta Feb 2024](https://about.fb.com/news/2024/02/labeling-ai-generated-images-on-facebook-instagram-and-threads/) · [Meta Apr–Sep 2024](https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/) · [YouTube AI disclosure](https://support.google.com/youtube/answer/14328491?hl=en) · [YouTube encoding](https://support.google.com/youtube/answer/1722171?hl=en)
- **Law:** [FTC fake-reviews rule](https://www.ftc.gov/news-events/news/press-releases/2024/08/federal-trade-commission-announces-final-rule-banning-fake-reviews-testimonials) · [16 CFR 465](https://www.ecfr.gov/current/title-16/chapter-I/subchapter-D/part-465) · [FTC 2023 Endorsement Guides notice](https://www.ftc.gov/system/files/ftc_gov/pdf/p204500_endorsement_guides_in_2023.pdf) · [16 CFR 255](https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-255) · [NY synthetic performers (Crowell)](https://www.crowell.com/en/insights/client-alerts/synthetic-performers-real-consequences-implications-of-trailblazing-new-york-ai-ad-law) · [ELVIS Act (Skadden)](https://www.skadden.com/insights/publications/2024/04/tennessee-law-addresses-proliferation-of-deepfakes) · [NO FAKES Act S.4591](https://www.congress.gov/bill/119th-congress/senate-bill/4591/all-actions) · [CA AB 1836](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240AB1836) · [CA AB 2602](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240AB2602)
- **Audio:** [AES TD1008 summary (Radio World)](https://www.radioworld.com/tech-and-gear/tech-tips/streaming-audio-loudness-guidelines-explained) · [Spotify loudness](https://support.spotify.com/et-am/artists/article/loudness-normalization/)
- **Repo:** RULES.md D37, D43, D44, D136–D138; `vsp/timing.py`; `vsp/captions.py`; `vsp/data/vibes.json` TONE_PROFILES; docs/research/vibe-tone-music.md §2–§4.

Content was rephrased for compliance with licensing restrictions.
