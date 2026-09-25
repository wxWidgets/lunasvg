# security/

Ports of the prototype's security vectors
(`..\lunasvg-tests\test_cases\security\`). Each directory holds `test.svg` and
`description.md`; there is deliberately no baseline.

**All nine cases are tracked as `skip`.** They exercise crashes, hangs, unbounded
allocation, recursion and local-file access, so rendering them in CI is unsafe
until the corresponding hardening lands. They are retained as documented,
runnable-on-demand seeds for that work: fix the bug, then move the case to
`known-fail` or `pass` (with a Linux-blessed baseline) in
`tests/data/manifest.json`.

| Case | Vulnerability |
|---|---|
| `sec_001_integer_overflow` | Canvas-size integer overflow. |
| `sec_002_deep_nesting` | Stack overflow from 150 nested elements. |
| `sec_003_excessive_path_data` | Memory exhaustion from a massive path. |
| `sec_004_redos_css` | ReDoS in CSS selector matching. |
| `sec_005_use_recursion` | Unbounded `<use>` recursion. |
| `sec_006_xxe_entity` | XXE / entity expansion. |
| `sec_007_base64_decoder` | Excessive base64 data allocation. |
| `sec_008_gradient_stops` | 1000+ gradient stops. |
| `sec_009_font_loading` | System font path information disclosure. |

Run one by hand with `tests/tools/svgrender` under a timeout and resource limit;
never wire them into an unconditional CI step.
