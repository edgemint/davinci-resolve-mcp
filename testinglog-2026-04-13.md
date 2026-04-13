# Testing Log — 2026-04-13

## Task
Built new skill `skills/davinci-custom-effects/` for authoring DaVinci Resolve `.setting` files (custom effects, transitions, titles, generators, Fusion macros).

## What to verify

### 1. Skill is discoverable and internally consistent
- [ ] Read `skills/davinci-custom-effects/SKILL.md` end-to-end — does the anatomy section match your mental model of a Fusion macro?
- [ ] Confirm the role → shape cheat sheet in `references/category-patterns.md` matches the Edit-page and Fusion-page categories you care about.
- [ ] Spot-check `references/format.md` against `Core Davinci Effects/Edit/Effects/Colored Border.setting` (the simplest example) — are the attributes I documented all actually present there?

### 2. Templates are valid and produce working effects
These are the most important things to test — templates that don't load wreck user trust in the skill:

- [ ] **effect.setting**: copy to `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Templates\Edit\Effects\TestBlur.setting`, restart Resolve, apply to a clip. Expected: "Minimal Effect" shows up in Effects Library → Effects; dragging it onto a clip adds a blur with a "Strength" slider (0–100, default 5) and a "Lock X/Y" toggle.
- [ ] **transition.setting**: copy to `...\Templates\Edit\Transitions\TestWipe.setting`, restart Resolve. Expected: shows up in Video Transitions. Apply between two clips; the transition animates smoothly from clip A to clip B with a cubic ease. Softness slider affects the ramp width.
- [ ] **title.setting**: copy to `...\Templates\Edit\Titles\TestTitle.setting`, restart Resolve. Expected: shows up in Titles. Drop onto timeline; "SAMPLE TITLE" renders with Font / Size / Position / Color controls exposed. Animation (if any was on the KeyStretcher range) should stretch to the clip length.
- [ ] **generator.setting**: copy to `...\Templates\Edit\Generators\TestNoise.setting`, restart Resolve. Expected: shows up in Generators. Drop onto timeline; FastNoise generator renders with Detail, Contrast, Scale, Animation Speed, and Gradient controls.
- [ ] **fusion-macro.setting**: copy to `...\Templates\Fusion\Tools\TestGlow.setting`, restart Resolve. Expected: on the Fusion page, right-click in the node view → Add Tool → Templates → Tools → Minimal Fusion Macro. Adds a SoftGlow wrapped as a group with the three exposed inputs.

### 3. Gotchas checklist
- [ ] Confirm `ordered()` usage is preserved when Resolve re-saves a template you edit through its UI (don't lose ordering on round-trip).
- [ ] Verify a hand-edited transition's progress animation stretches to arbitrary transition durations (1-frame transition, 10-second transition).
- [ ] Confirm that editing `ActiveTool` to a mismatched name breaks the file in a recoverable way (you get a warning, not a crash).

### 4. Nice-to-have next steps
- [ ] Add PNG thumbnails for each template so they look polished in the Effects Library (not required for function).
- [ ] Consider adding one worked example that combines multiple internal nodes (e.g., a "bloom + vignette" effect) to show how multi-node internal graphs are wired — the current effect template is intentionally minimal.
- [ ] Test whether older Resolve versions (pre-18.5) accept the `FuID { "Duration" }` source on `LUTLookup` — I documented this as standard but only verified against stock Resolve 19 effects.

### 5. Known gaps in the skill
- Doesn't document `ofx.com.blackmagicdesign.resolvefx.*` OFX nodes specifically — those appear all over the stock library and have parameter names you can't guess. The format is covered, but users wanting to wrap a ResolveFX will need to inspect stock files directly. Could add a reference table later.
- `BezierSpline` keyframe syntax documented but not exhaustive (tension/continuity/bias flags, stepped interpolation).
- Particle effect (`pEmitter`) and 3D material (`MtlBlinn`, `MtlWard`) parameter catalogs not exhaustive — the relevant entries in `controls.md` cover the most common fields but not every option.
