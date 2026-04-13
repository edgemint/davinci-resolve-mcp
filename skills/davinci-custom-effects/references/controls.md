# Control Reference

Two distinct mechanisms for adding controls to your effect:

1. **`InstanceInput`** — re-expose an *existing* internal node parameter at the Group level. Used 95% of the time.
2. **`UserControls`** — declare a *brand new* control on any node. Use when you need a button, label, or control that doesn't map to an existing node input.

Most templates mix both: `UserControls` declares the new controls, `InstanceInput` re-exposes them on the Group so they appear in the Edit-page inspector.

## 1. `InstanceInput` Attributes (Complete Catalog)

```lua
Name = InstanceInput {
    -- REQUIRED
    SourceOp = "InternalNodeName",
    Source   = "InternalParamName",

    -- LABEL & PLACEMENT
    Name     = "Display Label",           -- defaults to Source
    Page     = "Controls",                -- inspector tab (creates tab if new)
    ControlGroup = 4,                      -- collapse adjacent inputs into one widget

    -- NUMERIC DEFAULTS & RANGE
    Default    = 0.5,                     -- scalar default
    DefaultX   = 0.5,                     -- 2-component default X (points/sizes)
    DefaultY   = 0.5,                     -- 2-component default Y
    MinScale   = 0,                       -- slider soft min
    MaxScale   = 1,                       -- slider soft max
    MinAllowed = -10,                     -- hard min (value can't go below)
    MaxAllowed = 10,                      -- hard max

    -- LAYOUT
    Width      = 0.5,                     -- 0..1 fraction of row width (for side-by-side)

    -- ADVANCED (rarely needed)
    IconString = "FuID { \"icon-name\" }",
},
```

### Common `Source` Values by Node Type

| Node type | Useful `Source` values |
|-----------|----------------------|
| `Blur` | `XBlurSize`, `YBlurSize`, `Filter`, `LockXY` |
| `Background` | `TopLeftRed/Green/Blue/Alpha`, `Type`, `Gradient`, `Center`, `Width`, `Height` |
| `Transform` | `Center`, `Size`, `Angle`, `Pivot`, `XSize`, `YSize` |
| `RectangleMask` / `EllipseMask` | `Center`, `Width`, `Height`, `Angle`, `BorderWidth`, `SoftEdge`, `Invert` |
| `Merge` | `Center`, `Size`, `Angle`, `Blend`, `ApplyMode`, `Operator` |
| `Dissolve` | `Mix`, `Operation`, `Map`, `["DFTLumaRamp.Softness"]`, `["DFTLumaRamp.Border"]` |
| `TextPlus` | `StyledText`, `Font`, `Style`, `Size`, `CharacterSpacingClone`, `LineSpacingClone`, `Center`, `VerticalJustificationTop/Center/Bottom`, `HorizontalJustificationLeft/Center/Right`, `Red`, `Green`, `Blue`, `Alpha`, `BackgroundColor` |
| `FastNoise` | `Detail`, `Contrast`, `Brightness`, `XScale`, `YScale`, `SeetheRate`, `Gradient`, `Type`, `GradientType`, `Center` |
| `Displace` | `Type`, `RefractionStrength`, `XRefraction`, `YRefraction`, `MaskChannel` |
| `ColorCorrector` | `WheelHue1..4`, `Saturation1..4`, `Gain1..4`, `Lift1..4`, `ColorRanges` |
| `Shape3D` | `Shape`, plus shape-specific namespaced params like `SurfaceCylinderInputs.Radius`, `SurfaceCylinderInputs.Height`, `SurfaceCylinderInputs.SubdivisionLevelBase` |
| `Transform3DOp` (inside any 3D node) | `Transform3DOp.Translate.X/Y/Z`, `Transform3DOp.Rotate.X/Y/Z`, `Transform3DOp.Pivot.X/Y/Z`, `Transform3DOp.Scale` |
| `MtlBlinn` / `MtlStdInputs` | `Diffuse.Color.Red/Green/Blue/Alpha`, `Specular.Color.*`, `Specular.Exponent`, `Diffuse.Opacity`, `Reflection.GlancingStrength`, `Reflection.FaceOnStrength` |
| `pEmitter` | `Number`, `["ParticleStyle.Size"]`, `["ParticleStyle.SizeVariance"]`, `["ParticleStyle.Red/Green/Blue"]`, `["CubeRgn.Width/Height/Depth"]`, `RandomSeed`, `Rotation`, `Spin`, `TemporalDistribution` |

Namespaced parameters (containing `.`) must be quoted and bracketed: `Source = "Diffuse.Color.Red"`.

### `ControlGroup` Patterns

Group ids are arbitrary integers. Consecutive `InstanceInput`s sharing the same id merge into one inspector widget. The *first* input in the group is the "lead" and gets the widget label. Common patterns:

- **Color pickers:** 4 consecutive R/G/B/A inputs with matching `ControlGroup`. Lead input has `Name = "Color"`.
- **Vertical alignment (Top/Center/Bottom):** 3 consecutive checkbox-style inputs → single radio-button widget.
- **Horizontal alignment (Left/Center/Right):** same pattern.
- **Emphasis (Strikeout + Underline):** 2 consecutive inputs with matching group → single button bar.

Pick any free integer. Don't reuse within the same effect unless you mean to merge.

## 2. `UserControls` — Adding New Controls

Declared inside any node:

```lua
SomeNode = NodeType {
    Inputs = { ... },
    UserControls = ordered() {
        ControlName = {
            INPID_InputControl = "SliderControl",   -- control type (REQUIRED)
            LINKID_DataType    = "Number",          -- data type of the value
            LINKS_Name         = "Display Label",
            ICS_ControlPage    = "Controls",
            INP_Default        = 0.5,
            INP_MinScale       = 0,
            INP_MaxScale       = 1,
            INP_Integer        = false,
            ICD_Width          = 0.5,
        },
    },
},
```

Once declared, the new control behaves like a real node input. You can read it from other nodes (`SourceOp = "SomeNode", Source = "ControlName"`) or re-expose it on the GroupOperator via an `InstanceInput`.

### Control Types (`INPID_InputControl`)

| Type | Use for | Key extra fields |
|------|---------|------------------|
| `SliderControl` | Numeric slider (float or int) | `INP_MinScale`, `INP_MaxScale`, `INP_Default`, `INP_Integer`, `IC_Steps` |
| `CheckboxControl` | On/off toggle | `INP_Default` (0 or 1), `CBC_TriState` |
| `ButtonControl` | Clickable button | `BTNCS_Execute` — Lua snippet run when clicked |
| `LabelControl` | Group label above a block of inputs (collapsible header) | `LBLC_DropDownButton = true`, `LBLC_NumInputs = N` — N is how many inputs below this label get grouped |
| `MultiButtonControl` | Radio group / tab bar | `MBTNC_StretchToFit`, `MBTNC_ShowName`, plus `[1]`, `[2]`, ... entries for each button's text |
| `ColorControl` | Color picker (single value) | `CLRC_ShowWheel`, `CLRC_ShowSliders` |
| `DropDownControl` / `ComboControl` | Dropdown menu | `CC_LabelPosition`, entries via `[1] = "...", [2] = "..."` |

**Always include:**

- `LINKID_DataType` — `"Number"` for scalar controls, `"Point"` for 2D, `"Text"` for strings, `"Image"` for image inputs.
- `LINKS_Name` — the display label.
- `ICS_ControlPage` — which inspector tab the control lives on (`"Controls"` is conventional).
- `INPID_InputControl` — the type itself.

### Width / Layout Fields

- **`ICD_Width`** — fraction 0..1 of the inspector row width. Two controls with `ICD_Width = 0.5` will sit side-by-side.
- **`Width`** (on `InstanceInput`) — same idea when layout is driven at the Group level.

### `ButtonControl` + `BTNCS_Execute`

Buttons run Lua snippets in Fusion's context. Common uses:

- **Preset buttons:** set several inputs at once.

  ```lua
  Button01 = {
      INPID_InputControl = "ButtonControl",
      LINKID_DataType    = "Number",
      LINKS_Name         = "Center",
      ICS_ControlPage    = "Controls",
      ICD_Width          = 0.33,
      BTNCS_Execute      = "tool:SetInput('Input9',{0.5,0.5})\n tool:SetInput('Input10',{1.0,0.5})",
  },
  ```

- **Reset to defaults:** set a bunch of inputs back to known values.
- **Copy values between slots:** read one input, write another.

`tool` in the snippet refers to the node the button lives on. Use `tool:SetInput("Name", value)` and `tool:GetInput("Name")`. For colors and points, pass a table: `{r, g, b, a}` or `{x, y}`.

### `LabelControl` Group Headers

```lua
UserControls = ordered() {
    ColorSection = {
        INPID_InputControl = "LabelControl",
        LINKID_DataType    = "Number",
        LINKS_Name         = "Color",
        LBLC_DropDownButton = true,      -- collapsible
        LBLC_NumInputs      = 4,         -- how many following inputs belong to this section
        INP_Integer         = false,
        INP_External        = false,
    },
},
```

Then expose the label and the next four `InstanceInput`s up to the Group — Resolve renders them as a collapsible section.

## 3. Exposing a `UserControls` Entry on the Group

Once declared, you address it just like a real input:

```lua
-- On the GroupOperator:
ColorSection = InstanceInput {
    SourceOp = "SomeNode",        -- the node that declared the UserControls entry
    Source   = "ColorSection",    -- the UserControls key
    Page     = "Controls",
},
```

## 4. Which Approach When

| Situation | Use |
|-----------|-----|
| You want to tweak a parameter that already exists on an internal node | `InstanceInput` |
| You want a color picker for an R/G/B/A set | 4× `InstanceInput` with same `ControlGroup` |
| You want a Top/Bottom/Center radio group | 3× `InstanceInput` with same `ControlGroup` on boolean params |
| You want a button that runs a Lua snippet | `UserControls { ButtonControl, BTNCS_Execute }` on a `Fuse.Wireless` carrier, then `InstanceInput` to expose |
| You want a section header | `UserControls { LabelControl, LBLC_NumInputs = N }` |
| You want a control whose value drives multiple nodes | Declare once in `UserControls`, then reference `SourceOp = "CarrierNode", Source = "ControlName"` from each internal node |
