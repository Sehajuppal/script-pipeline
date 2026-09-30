---
trigger: glob
globs: "**/render.json, **/brief.md"
---

# Gemini Omni prompting

`render.json` already holds one finished prompt per generated shot (`shots[].prompt`) and per fallback (`shots[].ai_fallback.prompt`). Send them unchanged. Use this file to read them, check them, and write a prompt only when a human asks for a shot that is not in `render.json` (for example an alternate opening from `hooks.md`).

## The request

`POST https://generativelanguage.googleapis.com/v1beta/interactions`, header `x-goog-api-key: $GEMINI_API_KEY`.

```json
{"model": "gemini-omni-1.1-flash",
 "input": [{"type": "image", "data": "<base64>", "mime_type": "image/png"},
           {"type": "text", "text": "<the prompt>"}],
 "response_format": {"type": "video", "aspect_ratio": "9:16", "resolution": "360p",
                     "duration": "4s", "delivery": "inline"},
 "generation_config": {"video_config": {"task": "reference_to_video"}, "seed": 163107518},
 "store": true}
```

- `resolution`: `"360p"` for drafts, `"1080p"` for finals (upscaled; use `delivery: "uri"`, then download with the key). Never `"4k"`.
- `duration`: whole seconds from `"3s"` to `"10s"`. One call returns one clip at 24 fps.
- `task`: `image_to_video` when a still is the first frame (frame 0, the loop, the real-photo hero shots), `reference_to_video` for presenter/product/set references, `text_to_video` otherwise, `edit` for an edit turn.
- `store: true` keeps the interaction for edit turns (`previous_interaction_id`). `background: true` returns at once; poll `GET /v1beta/interactions/{id}`.
- The result is in `steps[]`: the `model_output` step holds a `content` item of `type "video"` with base64 `data` or a `uri`.
- There is no negative-prompt, system-instruction, temperature or audio-input field. `seed` exists in the API but Omni support is unverified: send it, and resend once without it if the API rejects it.

## The template (one string per shot)

```
[# Sources ...] [# References ...] {Scale}, {angle}, {one move}: {subject} {one action,
already in motion at the first frame} in {setting}, lit by {one named light source}.
Vertical 9:16 smartphone footage[, handheld with natural micro-shake]. Single continuous
shot, no scene cuts. Sound: {ambience or SFX}. {No dialogue, no voiceover. | The presenter,
{voice description}, says: {line} Delivery: {delivery}.} No music. No on-screen text,
captions, subtitles, logos or watermarks. {2-4 shot-specific negatives} {one closing
sentence per input image}
```

- **Subject.** The presenter identity lock (`identity.presenter_text`), only when the shot shows a face, pasted unchanged except for one thing: drop the word "AI" before the person ("a photorealistic AI woman ..." becomes "a photorealistic woman ..."), because it invites a synthetic, CGI look. The disclosure lives in the platform AI labels, the caption line and the frame-0 "AI persona" overlay, never in the picture prompt. The hands reference ("the presenter's hands, the sleeve of the ... just in frame") when it shows only hands. The product text when it shows only the product. Never the persona text in a product-only shot: it invites a face.
- **One move, one action.** Scale, angle and a single camera move open the prompt. One action in the present tense, already happening at the first frame. Never "then", never two beats, never a cross-shot reference such as "same as shot 2".
- **Setting and light.** The run's setting and one named source (a warm bedside lamp, soft window light from one side), never just "good lighting". Image-to-video prompts describe motion only: the still carries the setting.
- **Micro-shake** only for the handheld-phone vibes in a human creator's video (faceless AI B-roll that must match their phone footage), and never on a static shot. **Never on an AI-persona job** (`presenter_mode "ai"`): a faked shake on a generated person is a detectable synthetic flaw and reads as eerie. There the camera words stay smooth: a planned handheld move is written "slow dolly" and a speed ramp "fast push-in that slows sharply".
- **Negatives**, 2 to 4: face → "No face morphing."; hands → "Five natural fingers on each hand, no fused fingers."; product → "No invented logo or label text."; plus "No face in frame." / "No hands or people in frame." / "One speaker only." as they apply.

## Tags and images

- Images go in `input` in the order of first appearance in `inputs[]`, one item per distinct ref; they are numbered Image1, Image2, ... in that order. `<IMAGE_REF_N>` counts from 0.
- Header forms, declared at the start of the prompt:
  - `[# Sources <FIRST_FRAME>@Image1]`: the still is the first frame.
  - `[# Sources <FIRST_FRAME>@Image1 <LAST_FRAME>@Image1]`: the same still is the first and the last frame, which makes the loop. `<LAST_FRAME>` never appears without `<FIRST_FRAME>`.
  - `[# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2]`: references, not frames.
- Bind a reference inline right after the words it describes: `...wearing a plain gray crewneck <IMAGE_REF_0> speaks to the lens`.
- Close with one sentence per image: "Use Image1 as the starting frame.", "Use Image1 as the first frame and the last frame.", "Use Image2 as the product reference: ..., not a literal first frame."
- At most 10 images per call; PNG, JPEG or WebP, 20 MB or less each. Product images are real photos. The presenter sheet is a synthetic adult.

## Audio

- Every call returns audio, and there is no switch to turn it off. Describe exactly the sound you want.
- B-roll: `Sound: <ambience>.` then `No dialogue, no voiceover.` The ambience stays under the VO at about -12 dB. Transition SFX (whoosh, riser, pop, click) are added in the edit and never asked of Omni.
- Lip-sync shots: `Sound: quiet room tone.` then `The presenter, <voice>, says: <line> Delivery: <delivery>.` The line comes after a colon with no quotes, is at most 6 s (about 15 words), and has one speaker. The line text is the Cartesia transcript, so the mouth shapes match. Omni's own voice is dropped after the lip-sync pass.
- `No music.` in every prompt. Music is added at upload.

## Never in a prompt

- Quote marks of any kind (straight or curly). A contraction's apostrophe is fine.
- "render exactly", requests for on-screen text, captions, cards, labels or logos, brand or trademark names.
- Palette names or hex codes, the brief's 10-item NEGATIVE PROMPT block, rule ids (D123, F12), meta words (playbook, gate, dossier).
- Bracketed stage directions, "the presenter says" in a B-roll prompt, a second speaker.
- A real, famous or recognisable person, anyone who looks under 18, a real person's photo.

## Edit turns

A new request with `previous_interaction_id`, `task: "edit"` and one short instruction ending with "Keep everything else the same." Example: `Make the lamp glow warmer and remove the cable on the left. Keep everything else the same.` Use it for local fixes only (a colour, an object, a small artefact), at most 2 turns per clip; identity drift, bad hands or a cut mean a new take instead.

## Examples (generated for the LED sunrise alarm lamp, AI lane)

**Talking head with lip-sync** (shot 2, `reference_to_video`, 4 s; inputs `presenter_sheet`, `set_plate`):

> [# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2] Medium close-up, eye level, slow push-in: a photorealistic woman in her late 20s with dark hair tied back, natural look, wearing a plain gray crewneck <IMAGE_REF_0> speaks to the lens in a calm, tidy bedroom with a made bed, lit by a warm bedside lamp. Vertical 9:16 smartphone footage. Single continuous shot, no scene cuts. Sound: quiet room tone. The presenter, in a confident, conversational female voice, says: Tired of sunrise alarm lamps that fail fast? Delivery: brisk, confident. No music. No on-screen text, captions, subtitles, logos or watermarks. One speaker only. No face morphing. No extra people in frame. Use Image1 as the presenter reference: the same face, hair and outfit, not a literal first frame. Use Image2 as the set reference for the room and its light, not a literal first frame.

**Hands B-roll under the VO** (shot 3c, `reference_to_video`, 3 s; inputs `presenter_sheet`, `product_front`):

> [# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2] Close-up, slightly high angle, slow dolly: the presenter's hands, the sleeve of the plain gray crewneck just in frame, rest on and gently touch the LED sunrise alarm lamp, no speech, in a calm, tidy bedroom with a made bed, lit by a warm bedside lamp. Vertical 9:16 smartphone footage. Single continuous shot, no scene cuts. Sound: live room sound. No dialogue, no voiceover. No music. No on-screen text, captions, subtitles, logos or watermarks. Five natural fingers on each hand, no fused fingers. No invented logo or label text. No face in frame. Use Image1 only as the reference for skin tone and the sleeve, keep the face out of frame, not a literal first frame. Use Image2 as the product reference: the same shape, colour, size and finish, not a literal first frame.

**Product macro** (shot 3a, `reference_to_video`, 3 s; inputs `product_front`, `product_side`):

> [# References <IMAGE_REF_0>@Image1 <IMAGE_REF_1>@Image2] Extreme close-up, eye level, slow push-in: a compact dome-shaped sunrise lamp in matte white about 15 cm wide, glowing warm <IMAGE_REF_0>, its surface texture filling the frame, shallow depth of field, macro lens, in a calm, tidy bedroom with a made bed, lit by a warm bedside lamp. Vertical 9:16 smartphone footage. Single continuous shot, no scene cuts. Sound: close-miked texture sound. No dialogue, no voiceover. No music. No on-screen text, captions, subtitles, logos or watermarks. No invented logo or label text. No hands or people in frame. Use Image1 as the product reference: the same shape, colour, size and finish, not a literal first frame. Use Image2 as another product reference angle, not a literal first frame.

**Frame 0, image-to-video** (shot 1, `image_to_video`, 3 s; inputs `frame0` as the first frame, `product_front`):

> [# Sources <FIRST_FRAME>@Image1] [# References <IMAGE_REF_0>@Image2] Close-up, slightly high angle, slow push-in: the LED sunrise alarm lamp in the first frame, its working end already doing its job in real use, hands out of frame. Vertical 9:16 smartphone footage. Single continuous shot, no scene cuts. Sound: the product's real working sound, close-miked. No dialogue, no voiceover. No music. No on-screen text, captions, subtitles, logos or watermarks. No invented logo or label text. No hands or people in frame. Use Image1 as the starting frame. Use Image2 as the product reference: the same shape, colour, size and finish, not a literal first frame.

The loop shot uses the same frame-0 still for both ends: `[# Sources <FIRST_FRAME>@Image1 <LAST_FRAME>@Image1]` ... `Use Image1 as the first frame and the last frame.`
