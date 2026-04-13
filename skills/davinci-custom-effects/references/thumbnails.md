# Thumbnail Files

Each `.setting` ships with a bundle of PNGs named after the `.setting` file. They're not embedded — they live as sibling files in the same folder. Resolve indexes them at launch and uses them for the tiles in the Effects Library.

## Naming Rule

If your effect file is `My Cool Thing.setting`, every thumbnail starts with `My Cool Thing.` followed by a suffix describing which slot it fills. Spaces in the base name are fine — Resolve matches on exact prefix.

## Dimensions by Slot

| Suffix | Dimensions (normal) | Dimensions (`@2x`) | Used by |
|--------|---------------------|--------------------|---------|
| `.large.png` | 128 × 128 | 256 × 256 | Edit Effects, Edit Generators, Fusion Tools, Backgrounds, Generators, Lens Flares, Motion Graphics, Particles, Shaders, Styled Text, How To |
| `.small.png` | 30 × 30 | 60 × 60 | All categories that have a list/icon view (Edit Effects, Transitions, Generators, Fusion tools, etc.) |
| `.wide.png` | 52 × 29 | 104 × 58 | Edit Transitions, Edit Titles (instead of `.large`) |
| `.small.active.png` | 30 × 30 | 60 × 60 | Button "pressed/active" state for small icon |
| `.small.hover.png` | 30 × 30 | 60 × 60 | Mouse-hover state |
| `.small.push.png` | 30 × 30 | 60 × 60 | Mouse-down state |
| `.wide.active.png` | 52 × 29 | — | Active state for wide tiles (rare) |
| `.wide.hover.png` | 52 × 29 | — | Hover state for wide tiles |
| `.wide.push.png` | 52 × 29 | — | Push state for wide tiles |

`@2x` variants are optional but recommended — they're what Retina / HiDPI displays render.

## Required vs Optional

| Category | Truly required | Recommended | Optional |
|----------|---------------|-------------|----------|
| Edit / Effects | none (Resolve uses `_default.png`) | `.large.png`, `.large@2x.png`, `.small.png`, `.small@2x.png` | all `.small.active/hover/push` variants, `.wide.png` |
| Edit / Transitions | none | `.small.png`, `.small@2x.png`, `.wide.png`, `.wide@2x.png` | `.small.active/hover/push` variants |
| Edit / Titles | none | `.wide.png`, `.wide@2x.png` | — (titles don't use `.large` or `.small`) |
| Edit / Generators | none | `.large.png`, `.large@2x.png`, `.small.png`, `.small@2x.png` | button-state variants |
| Fusion / Tools & Backgrounds & Generators & Shaders & Particles & Styled Text & Motion Graphics & Lens Flares & How To | none | `.large.png`, `.large@2x.png` | everything else |

**Minimum viable ship:** a single `.large.png` (or `.wide.png` for titles/transitions) at the spec'd dimensions. Resolve will handle the rest with fallbacks.

## Creating Thumbnails Quickly

For a new effect you're building:

1. Apply the effect to a clip in Resolve.
2. Grab a frame (File → Export → Still, or viewer right-click → Grab Still).
3. Crop to the tile dimensions with any image tool. Keep transparency if the tile looks better without a background (alpha PNGs are supported).
4. Name the crops per the suffix rules above and drop next to the `.setting` file.

For button states (`.active`, `.hover`, `.push`), you can start from the base `.small.png` and just brighten / darken / tint by ~10% — that matches the stock library's look.

## Fallback Behavior

- If only the non-`@2x` variant exists, Retina users see an upscaled version.
- If only the `@2x` variant exists, non-Retina users see a downscaled version.
- If neither exists for a given slot, Resolve uses a generic `_default.png` placeholder (which ships in some stock folders).

You will not break anything by shipping with just `.large.png` + `.large@2x.png`. The effect will work; the Effects Library tile will just be plain.

## File Size

Stock PNGs are typically 1-20 KB. Keep your thumbnails small — they're loaded into memory for the entire Effects Library browser, so don't ship megabyte-scale PNGs.
