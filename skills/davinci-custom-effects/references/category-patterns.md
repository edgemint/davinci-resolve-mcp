# Category Patterns

Every category hooks into Resolve slightly differently. This file shows the **minimum viable skeleton** for each, and what changes between them. Start with the shape that matches your target category, then modify.

## 1. Edit Effect (clip filter)

**Role:** pixel filter applied to a single clip. Reads the clip, writes a processed version.

**Hook:** exactly one `MainInput1` connected to the internal "entry" node's `Input` parameter.

```lua
{
    Tools = ordered() {
        MyEffect = GroupOperator {
            Inputs = ordered() {
                MainInput1 = InstanceInput {
                    SourceOp = "Blur1",
                    Source   = "Input",
                },
                Strength = InstanceInput {
                    SourceOp = "Blur1",
                    Source   = "XBlurSize",
                    Default  = 5,
                    MinScale = 0,
                    MaxScale = 100,
                },
            },
            Outputs = {
                MainOutput1 = InstanceOutput {
                    SourceOp = "Blur1",
                    Source   = "Output",
                },
            },
            Tools = ordered() {
                Blur1 = Blur {
                    Inputs = {
                        Filter    = Input { Value = FuID { "Fast Gaussian" } },
                        XBlurSize = Input { Value = 5 },
                        LockXY    = Input { Value = 1 },
                    },
                },
            },
        },
    },
    ActiveTool = "MyEffect",
}
```

**Install path:** `Templates/Edit/Effects/`.

## 2. Edit Transition

**Role:** blends between two clips over a duration.

**Hook:** two MainInputs — `MainInput1` (Background, the outgoing clip) and `MainInput2` (Foreground, the incoming clip). Both feed a `Dissolve` or `Merge` node.

**Progress animation:** driven by a `LUTLookup` reading `FuID { "Duration" }` with an easing curve. Fusion automatically evaluates the curve across the transition length and outputs a 0→1 ramp.

```lua
{
    Tools = ordered() {
        MyTransition = GroupOperator {
            Inputs = ordered() {
                MainInput1 = InstanceInput {
                    SourceOp = "Dissolve1",
                    Source   = "Background",
                },
                MainInput2 = InstanceInput {
                    SourceOp = "Dissolve1",
                    Source   = "Foreground",
                },
                Softness = InstanceInput {
                    SourceOp = "Dissolve1",
                    Source   = "DFTLumaRamp.Softness",
                    Default  = 0.05,
                    MinScale = 0,
                    MaxScale = 1,
                },
            },
            Outputs = {
                MainOutput1 = InstanceOutput {
                    SourceOp = "Dissolve1",
                    Source   = "Output",
                },
            },
            Tools = ordered() {
                Dissolve1 = Dissolve {
                    Inputs = {
                        Operation = Input { Value = FuID { "DFTDissolve" } },
                        Mix = Input {
                            SourceOp = "ProgressCurve",
                            Source   = "Value",
                        },
                    },
                },
                ProgressCurve = LUTLookup {
                    Inputs = {
                        Source = Input { Value = FuID { "Duration" } },
                        Curve  = Input { Value = FuID { "Easing" } },
                        EaseIn  = Input { Value = FuID { "Cubic" } },
                        EaseOut = Input { Value = FuID { "Cubic" } },
                        Lookup = Input {
                            SourceOp = "ProgressCurveLookup",
                            Source   = "Value",
                        },
                    },
                },
                ProgressCurveLookup = LUTBezier {
                    KeyColorSplines = {
                        [0] = {
                            [0] = { 0, RH = { 0.333, 0.333 }, Flags = { Linear = true } },
                            [1] = { 1, LH = { 0.666, 0.666 }, Flags = { Linear = true } }
                        }
                    },
                    SplineColor = { Red = 255, Green = 255, Blue = 255 },
                },
            },
        },
    },
    ActiveTool = "MyTransition",
}
```

**Install path:** `Templates/Edit/Transitions/`.

**Transition operations worth knowing (for `Dissolve.Operation`):**

| FuID | Effect |
|------|--------|
| `DFTDissolve` | Straight cross-dissolve |
| `DFTLumaRamp` | Wipe driven by the `Map` input's luma — lets you shape the wipe with any image |
| `DFTAdditiveDissolve` | Additive blend |

`DFTLumaRamp` is the workhorse for wipes: pipe a gradient or shape into `Map` and you get a controllable wipe. Box Wipe and most stock transitions use this pattern.

## 3. Edit Title

**Role:** text generator with stretched animation.

**Hooks:** no MainInput. Wraps a `TextPlus` node. Internal animation is piped through a `KeyStretcher` so it stretches to the clip's actual duration.

```lua
{
    Tools = ordered() {
        MyTitle = GroupOperator {
            Inputs = ordered() {
                Input1 = InstanceInput { SourceOp = "Text", Source = "StyledText" },
                Input2 = InstanceInput { SourceOp = "Text", Source = "Font",  ControlGroup = 2 },
                Input3 = InstanceInput { SourceOp = "Text", Source = "Style", ControlGroup = 2 },
                Size   = InstanceInput { SourceOp = "Text", Source = "Size",   Default = 0.08 },
                Pos    = InstanceInput { SourceOp = "Text", Source = "Center", Name = "Position" },
                Red    = InstanceInput { SourceOp = "Text", Source = "Red",   Name = "Color", ControlGroup = 10, Default = 1 },
                Green  = InstanceInput { SourceOp = "Text", Source = "Green", Name = "Color", ControlGroup = 10, Default = 1 },
                Blue   = InstanceInput { SourceOp = "Text", Source = "Blue",  Name = "Color", ControlGroup = 10, Default = 1 },
                Alpha  = InstanceInput { SourceOp = "Text", Source = "Alpha", Name = "Color", ControlGroup = 10, Default = 1 },
            },
            Outputs = {
                MainOutput1 = InstanceOutput {
                    SourceOp = "Stretcher",
                    Source   = "Result",
                },
            },
            Tools = ordered() {
                Text = TextPlus {
                    Inputs = {
                        GlobalOut = Input { Value = 500 },
                        Width     = Input { Value = 1920 },
                        Height    = Input { Value = 1080 },
                        UseFrameFormatSettings = Input { Value = 1 },
                        StyledText = Input { Value = "SAMPLE" },
                        Font       = Input { Value = "Open Sans" },
                        Style      = Input { Value = "Bold" },
                        Size       = Input { Value = 0.08 },
                        VerticalJustificationNew   = Input { Value = 3 },
                        HorizontalJustificationNew = Input { Value = 3 },
                    },
                },
                Stretcher = KeyStretcher {
                    Inputs = {
                        Keyframes = Input {
                            SourceOp = "Text",
                            Source   = "Output",
                        },
                        SourceEnd   = Input { Value = 119 },
                        StretchStart = Input { Value = 10 },
                        StretchEnd   = Input { Value = 100 },
                    },
                },
            },
        },
    },
    ActiveTool = "MyTitle",
}
```

**Install path:** `Templates/Edit/Titles/`.

Key details:

- `MainOutput1` pulls `Source = "Result"` from the `KeyStretcher` (not `"Output"` — that's the unstretched pixels).
- Animation on the `TextPlus` (via `BezierSpline` inputs for Alpha, Size, Color, etc.) gets stretched to match the clip length by `KeyStretcher`.
- Stock titles often expose *many* text controls (font, style, size, tracking, line spacing, V/H anchor, color, background color). Copy the pattern from `Edit/Titles/Background Reveal.setting` if you want the full treatment.

## 4. Edit Generator

**Role:** pure pixel source. No input clip — just produces an image.

**Hooks:** no MainInput. One `MainOutput1`.

```lua
{
    Tools = ordered() {
        MyGenerator = GroupOperator {
            Inputs = ordered() {
                Detail = InstanceInput {
                    SourceOp = "Noise1",
                    Source   = "Detail",
                    Default  = 5,
                    MinScale = 0,
                    MaxScale = 10,
                },
                Scale = InstanceInput {
                    SourceOp = "Noise1",
                    Source   = "XScale",
                    Default  = 10,
                    MinScale = 1,
                    MaxScale = 50,
                },
            },
            Outputs = {
                MainOutput1 = InstanceOutput {
                    SourceOp = "Noise1",
                    Source   = "Output",
                },
            },
            Tools = ordered() {
                Noise1 = FastNoise {
                    Inputs = {
                        Width  = Input { Value = 1920 },
                        Height = Input { Value = 1080 },
                        UseFrameFormatSettings = Input { Value = 1 },
                        Detail = Input { Value = 5 },
                        XScale = Input { Value = 10 },
                    },
                },
            },
        },
    },
    ActiveTool = "MyGenerator",
}
```

**Install path:** `Templates/Edit/Generators/`.

## 5. Fusion Macro (Fusion page)

Tools, Backgrounds, Generators, Particles, Shaders, Styled Text, Motion Graphics, Lens Flares, How To — all of these live on the Fusion page and have more latitude:

- You can use a wrapped `GroupOperator` (same as Edit effects) for a clean inspector.
- OR you can ship **raw nodes** at the top level and the user gets the whole subgraph dropped into their comp.

For a Fusion *Tool* (applies like a filter on the Fusion page), use the Edit-effect shape with `MainInput1`. For a Fusion *Background* / *Generator* / *Shader* / *Particle* source, drop the MainInput and just expose `MainOutput1`. For a Fusion *Motion Graphic* where the user should see and tweak the full node graph, ship multiple raw nodes at the top level with no GroupOperator wrapper.

**Install paths:** `Templates/Fusion/Tools/`, `Templates/Fusion/Backgrounds/`, `Templates/Fusion/Generators/`, `Templates/Fusion/Particles/`, `Templates/Fusion/Shaders/`, `Templates/Fusion/Styled Text/`, `Templates/Fusion/Motion Graphics/`, `Templates/Fusion/Lens Flares/`, `Templates/Fusion/How To/`.

## Role → Shape Cheat Sheet

| Role | Wrap in GroupOperator? | MainInput1 | MainInput2 | MainOutput1 source | Output field |
|------|-----------------------|------------|------------|---------------------|-------------|
| Edit Effect | Yes | Required, → `Input` of first node | — | Terminal node | `Output` |
| Edit Transition | Yes | Required → `Background` | Required → `Foreground` | Dissolve/Merge | `Output` |
| Edit Title | Yes | — | — | KeyStretcher | `Result` |
| Edit Generator | Yes | — | — | Terminal node | `Output` |
| Fusion Tool | Yes | Required | Optional | Terminal node | `Output` |
| Fusion Background / Generator / Shader | Yes | — | — | Terminal node | `Output` / `MaterialOutput` for materials |
| Fusion Motion Graphic (raw graph) | No — ship raw top-level tools | — | — | — | — |
| Fusion Lens Flare (single raw node) | No — raw HotSpot at top | — | — | — | — |
| Fusion Particle preset | Can be either; stock uses raw `pEmitter` with `CustomData.Settings` for presets | — | — | — | — |
