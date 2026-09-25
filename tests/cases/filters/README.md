# filters/

The prototype's flat filter set (`..\lunasvg-tests\test_cases\filters\*.svg`
plus `.png` baselines), promoted to the standard
`<case>/{test.svg,baseline.png,description.md}` layout.

| Case | Status | Exercises |
|---|---|---|
| `drop_shadow` | pass | `feGaussianBlur` + `feOffset` + `feMerge` drop shadow. |
| `composite_ops` | skip | `feComposite` operators / `arithmetic`. |
| `color_matrix` | skip | `feColorMatrix` saturate / hueRotate / luminanceToAlpha. |
| `blend_modes` | skip | `feBlend` multiply / screen / darken / lighten. |

The three skipped vectors carry `<text>` labels and are therefore text vectors,
excluded from the golden set (plan decision 2b #9). Their baselines were rendered
with host fonts and were not vendored.

The prototype also contains eight unpaired `test_*.svg` inputs
(`test_turbulence`, `test_convolve`, `test_component_transfer`,
`test_displacement`, `test_diffuse_distant`, `test_diffuse_spotlight`,
`test_morphology`, `test_specular_point`). They have no baseline and no
description, are partly text vectors, and are superseded by
`features_svg12/filters/`; they were not ported. The in-flight filter work is
covered by `features_svg12/filters/` plus the report-only W3C filter cases in
`tests/w3c/`.
