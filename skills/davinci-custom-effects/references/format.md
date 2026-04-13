# `.setting` File Format Reference

## 1. Lua-Table Syntax

`.setting` files are parsed by Fusion's table reader — a slightly relaxed Lua-table dialect. Key points:

- **Tables:** `{ key = value, other = value }` — trailing commas allowed.
- **Ordered tables:** `ordered() { key = value, ... }` — same as a table but Fusion preserves insertion order. Use this wherever display order matters (`Inputs`, `Tools`, `UserControls`).
- **Strings:** double-quoted, backslash-escaped. Keys with spaces or dots must be quoted and bracketed: `["Gamut.SLogVersion"] = Input { ... }`.
- **Numbers:** integers, floats, negative. Scientific notation works.
- **Nested tables:** freely. Values can be tables, lists, or other tables.
- **Comments:** not officially supported — Fusion may strip them on round-trip.

## 2. Top-Level Shape

Every `.setting` file is a single top-level table:

```lua
{
    Tools = ordered() {
        <name> = <NodeType> { ... },   -- one or more nodes at the top level
        ...
    },
    ActiveTool = "<name>"              -- optional; names the "primary" node
}
```

Three legal top-level shapes observed in the stock library:

| Shape | Used for | Example |
|-------|---------|---------|
| **One GroupOperator** wrapping internal tools | Most Edit effects/transitions/titles/generators, most Fusion macros that want a clean inspector | `Binoculars`, `Block Glitch`, `Background Reveal` |
| **One raw node** (not wrapped) | Single-node effects that expose the node's native UI | `Lens Flare V01` (HotSpot), `Blowing Leaves` (pEmitter) |
| **Multiple raw nodes** | Fusion macros that drop a subgraph into the user's comp (user sees all nodes) | `Circle Values` (Merge + Background + BrightnessContrast) |

If you're authoring for the Edit page (Effects/Transitions/Titles/Generators), **always use the wrapped GroupOperator form** — the Edit page doesn't know how to display raw node graphs in the inspector.

## 3. The GroupOperator Block

```lua
MyEffect = GroupOperator {
    CtrlWZoom = false,            -- UI detail, harmless; copy from stock files
    NameSet   = true,             -- optional; marks the name as explicitly set
    Inputs    = ordered() { ... exposed controls ... },
    Outputs   = { ... MainOutput1, optional extra outputs ... },
    ViewInfo  = GroupInfo { Pos = { 0, 0 } },  -- position in the Fusion graph editor
    Tools     = ordered() { ... internal nodes ... },
},
```

Fields:

- **`Inputs`** — InstanceInputs (controls). Order = inspector order.
- **`Outputs`** — InstanceOutputs. `MainOutput1` is mandatory for anything that renders pixels. You can expose multiple outputs; the first is what downstream Resolve nodes read.
- **`ViewInfo`** — `GroupInfo { Pos = {x, y}, Flags = {...}, Size = {...}, Direction, PipeStyle, Scale, Offset }`. Only `Pos` is necessary for templates; the rest are cosmetic. Flags like `AllowPan`, `ConnectedSnap`, `AutoSnap`, `RemoveRouters` are all optional booleans.
- **`Tools`** — the internal graph.

## 4. Node Definitions (Internal `Tools`)

Every internal node looks like:

```lua
NodeName1 = NodeType {
    CtrlWZoom    = false,            -- optional UI state
    CtrlWShown   = false,            -- optional UI state
    NameSet      = true,             -- optional
    Inputs = {
        Param1 = Input { Value = 0.5, },
        Param2 = Input {
            SourceOp = "OtherNode",    -- connection to another node's output
            Source   = "Output",
        },
        ["Namespaced.Param"] = Input { Value = FuID { "EnumValue" }, },
    },
    ViewInfo = OperatorInfo { Pos = { 304, -52 } },
    UserControls = ordered() { ... optional custom controls ... },
},
```

Key points:

- **Connections** use `SourceOp` + `Source` inside an `Input {}`. The referenced node must be in the same `Tools` list. Output names depend on node type: image nodes output `"Output"`, masks output `"Mask"`, value-node splines output `"Value"`, TextPlus outputs `"Output"` (pixels) and `"Result"` (stretched keyframes when piped through KeyStretcher).
- **Scalar values** use `Input { Value = N }`.
- **Typed enums** use `Input { Value = FuID { "EnumValue" } }` — see "FuID Enums" below.
- **Gradients** use `Input { Value = Gradient { Colors = { [0] = {r,g,b,a}, [1] = {r,g,b,a}, ... } } }`.
- **Keyed animation** uses `SourceOp = "SomeBezier"` pointing at a `BezierSpline` defined as a sibling node.
- **StyledText inputs** (TextPlus `StyledText`, `ManualFontKerningPlacement`) wrap the string in `StyledText { Value = "...", Array = { ... } }`.

## 5. Exposing Controls (`InstanceInput`)

Inside `GroupOperator.Inputs`, each entry is an `InstanceInput`:

```lua
InputN = InstanceInput {
    SourceOp = "InternalNodeName",     -- which internal node
    Source   = "InternalParamName",    -- which parameter
    Name     = "Label Shown To User",  -- optional; defaults to Source
    Default  = 0.5,                    -- optional; initial value
    MinScale = 0,                      -- soft slider minimum (value can be below)
    MaxScale = 1,                      -- soft slider maximum
    MinAllowed = -10,                  -- hard minimum (optional)
    MaxAllowed = 10,                   -- hard maximum (optional)
    Page         = "Controls",         -- inspector tab name
    ControlGroup = 4,                  -- group id for paired/nested controls
    Width        = 0.5,                -- width 0-1 for side-by-side layouts
    DefaultX     = 0.5,                -- for point/size inputs (2-component)
    DefaultY     = 0.5,
    IconString   = "...",              -- rarely used; icon on the control row
},
```

**Reserved names:**

- **`MainInput1`** — in effects, points at the internal input that should receive the source clip. In transitions, points at Background. In titles/generators, omitted.
- **`MainInput2`** — transitions: Foreground. Otherwise free to use.
- **`MainInput3` / `MainInput4` / ...** — additional "main" inputs; Fusion treats them as additional pipeline connections. Rarely used outside of 3D / material tools.

Non-reserved keys (`Input1`, `Input2`, `Intensity`, `Blur`, anything) are displayed as normal controls. The key itself is the internal identifier; `Name` is the label.

`ControlGroup` collapses consecutive inputs sharing the same group id into one visual widget — that's how R/G/B/A become one color picker:

```lua
Input4 = InstanceInput { SourceOp = "BG", Source = "TopLeftRed",   Name = "Color", ControlGroup = 4, Default = 1 },
Input5 = InstanceInput { SourceOp = "BG", Source = "TopLeftGreen",                  ControlGroup = 4, Default = 1 },
Input6 = InstanceInput { SourceOp = "BG", Source = "TopLeftBlue",                   ControlGroup = 4, Default = 1 },
Input7 = InstanceInput { SourceOp = "BG", Source = "TopLeftAlpha",                  ControlGroup = 4, Default = 1 },
```

Result: a single "Color" swatch in the inspector.

## 6. Outputs (`InstanceOutput`)

```lua
Outputs = {
    MainOutput1 = InstanceOutput {
        SourceOp = "FinalNode",       -- which internal node's output
        Source   = "Output",           -- which output (usually "Output")
    },
    Output2 = InstanceOutput {         -- optional additional outputs
        SourceOp = "SomeOtherNode",
        Source   = "Value",
    },
},
```

`MainOutput1` is mandatory if the effect produces pixels. For Edit effects, transitions, and titles, Resolve reads `MainOutput1` and pipes it to the next node in the timeline.

## 7. FuID Enums

Many node parameters are enumerated. Fusion stores them as `FuID { "EnumValue" }`:

```lua
Filter     = Input { Value = FuID { "Fast Gaussian" }, },   -- Blur.Filter
Operation  = Input { Value = FuID { "DFTLumaRamp" }, },     -- Dissolve.Operation
Channel    = Input { Value = FuID { "Luminance" }, },       -- BitmapMask.Channel
Shape      = Input { Value = FuID { "SurfaceCylinderInputs" }, },  -- Shape3D.Shape
Region     = Input { Value = FuID { "CubeRgn" }, },         -- pEmitter.Region
```

You can't guess these names — inspect the node in Fusion (right-click → Paste Settings / Copy Settings) or read the reference `.setting` files in the stock library.

## 8. `BezierSpline` (Keyframe Animation)

Animation curves are sibling nodes, referenced by `SourceOp`:

```lua
TextAlpha = BezierSpline {
    SplineColor = { Red = 180, Green = 180, Blue = 180 },
    NameSet = true,
    KeyFrames = {
        [13]  = { 0, RH = { 20, 0.333 } },
        [34]  = { 1, LH = { 27, 0.666 }, RH = { 56, 1 }, Flags = { Linear = true } },
        [101] = { 1, LH = { 78, 1 }, RH = { 105, 0.666 }, Flags = { Linear = true } },
        [115] = { 0, LH = { 110, 0.333 }, Flags = { Linear = true } },
    }
},
```

Keyframe format: `[frameNumber] = { value, LH = {tx, ty}, RH = {tx, ty}, Flags = { Linear = true } }`. `LH` / `RH` are left/right handles (time, value). `Flags.Linear` disables Bezier interpolation on that side.

## 9. `LUTLookup` + `LUTBezier` (Time Ramps)

Transitions and titles use `LUTLookup` to turn clip-time into a 0→1 ramp that drives whatever parameter should animate over the clip length. Pattern:

```lua
AnimCurves1 = LUTLookup {
    Inputs = {
        Source = Input { Value = FuID { "Duration" }, },  -- "Duration" = full clip length
        Curve  = Input { Value = FuID { "Easing" }, },
        EaseIn = Input { Value = FuID { "Cubic" }, },
        EaseOut = Input { Value = FuID { "Cubic" }, },
        Lookup = Input {
            SourceOp = "AnimCurves1Lookup",
            Source = "Value",
        },
        Scale = Input { Value = 10 },      -- output multiplied by Scale
        Offset = Input { Value = 0 },
    },
},
AnimCurves1Lookup = LUTBezier {
    KeyColorSplines = {
        [0] = {
            [0] = { 0, RH = { 0.333, 0.333 }, Flags = { Linear = true } },
            [1] = { 1, LH = { 0.666, 0.666 }, Flags = { Linear = true } }
        }
    },
    SplineColor = { Red = 255, Green = 255, Blue = 255 },
},
```

Then any internal node can pull from it:

```lua
Dissolve1 = Dissolve {
    Inputs = {
        Mix = Input { SourceOp = "AnimCurves1", Source = "Value" },
        ...
    },
},
```

That's the entire transition-progress mechanism. Don't expose it to the user. Don't try to find a "Progress" input on the Group — there isn't one.

## 10. `CustomData` and Preset Variants

Many stock effects include a `CustomData` block inside nodes. Two common uses:

```lua
CustomData = { Settings = { [1] = { Tools = ordered() { ... } }, [2] = { Tools = ordered() { ... } } } }
```

This stores multiple **preset variations** of the node. The `CurrentSettings = 2` field on the parent node picks which preset is live. You see this a lot on TextPlus-based titles (where each preset is a different style) and on pEmitter-based particle effects.

```lua
CustomData = { AltSettings9 = { Tools = ordered() { ... } } }
```

Same idea, different key naming. Lens Flares use this.

**For hand-authored templates, you can ignore CustomData entirely** — it's a convenience Fusion writes when you save variations from the UI. Your template will still load and work with just a single variant.

## 11. `UserControls` (Adding Controls Not Tied to a Node Input)

Any internal node can add **new** controls that don't map to an existing parameter, via a `UserControls` block. Those controls become addressable as if they were real inputs on that node, and you can then re-expose them via `InstanceInput` up to the GroupOperator.

```lua
BUTTONS = Fuse.Wireless {               -- a fake "no-op" node that hosts the controls
    UserControls = ordered() {
        Button01 = {
            INPID_InputControl = "ButtonControl",
            LINKID_DataType    = "Number",
            LINKS_Name         = "Top",
            ICS_ControlPage    = "Controls",
            ICD_Width          = 0.5,
            INP_Integer        = false,
            BTNCS_Execute      = "tool:SetInput('Input9',{0.5,1})\n tool:SetInput('Input10',{0.5,0})",
        },
    },
},
```

`Fuse.Wireless` is the idiomatic carrier for "free-floating" UI controls (buttons that run Lua, labels, etc.) that don't belong to any real node. See `controls.md` for the full list of control types and attributes.

## 12. Minimum Viable File

The smallest file Fusion will accept as an Edit effect:

```lua
{
    Tools = ordered() {
        MinimalEffect = GroupOperator {
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
                    MaxScale = 50,
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
                        Filter   = Input { Value = FuID { "Fast Gaussian" } },
                        XBlurSize = Input { Value = 5 },
                    },
                },
            },
        },
    },
    ActiveTool = "MinimalEffect",
}
```

Drop that into `Templates/Edit/Effects/MyBlur.setting`, restart Resolve, and it works.
