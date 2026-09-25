# Golden-image test corpus

Every directory below is one case, laid out exactly as the comparison engine
expects:

```
tests/cases/<group>/<case>/
    test.svg          # input
    baseline.png      # golden image (pass / known-fail cases only)
    description.md    # what the case exercises
```

`current.png` (a render artefact in the old out-of-tree prototype) is **not**
part of the corpus: `tests/tools/run_cases.py` renders into a temporary directory
and never writes into the source tree.

Per-case render size, background, tolerance and `expectedStatus` live in
`tests/data/manifest.json`. `tests/tools/run_cases.py` is the gated CTest test
(`wxlunasvg_cases`) that enforces them; `tests/tools/bless.py` regenerates
baselines:

```sh
python tests/tools/run_cases.py --list                 # status of every case
python tests/tools/run_cases.py --build-dir build      # run the corpus
python tests/tools/bless.py --build-dir build          # re-bless (Linux CI only)
```

## Baselines

The ported baselines are the prototype's, which were rendered on Windows. They
reproduce exactly against the current build on Windows, but baseline generation is
only canonical on **Linux CI** (plan decision 2b #12): re-bless the corpus there
before treating the images as canonical, and never bless on a developer box.

## Groups

| Group | Cases | Status | Notes |
|---|---|---|---|
| `bugs/` | 2 | pass | CSS selector pseudo-class bugs. Naming: `bug_NNN_<slug>`. |
| `features_svg12/filters/` | 12 | 11 pass, 1 skip | SVG 1.1 filter primitives (the in-flight filter work). |
| `features_svg20/` | 0 | — | The prototype group exists but is empty; nothing to port yet. |
| `filters/` | 4 | 1 pass, 3 skip | Flat prototype filter cases promoted to the standard layout. |
| `regression/` | 1 | pass | Broad mixed-content rendering guard. |
| `security/` | 9 | skip | Malicious inputs; ports of the prototype security vectors. |

"skip" means the case is tracked but never rendered. Two reasons exist:

- **Text vectors** (`<text>`) are excluded from the golden set (plan decision 2b
  #9): with `LUNASVG_DISABLE_LOAD_SYSTEM_FONTS` and no bundled-font-file API the
  output is not reproducible across platforms. The affected vectors are still
  vendored (with a description) so they can be enabled once a font API appears.
- **Security vectors** exercise crashes / hangs / file access and are not safe to
  render in CI; they are documented seeds for the hardening work.

## Adding a case

1. Create `tests/cases/<group>/bug_NNN_<slug>/` (bugs) or
   `tests/cases/<group>/<slug>/` (features/regression) with `test.svg` and
   `description.md`.
2. Add the path to the `cases` map of `tests/data/manifest.json` with an
   `expectedStatus`.
3. Render the case with `tests/tools/svgrender` and **bless the baseline on Linux
   CI** (plan decision 2b #12); do not bless on a developer box.
4. If the case is a known failure, set `"expectedStatus": "known-fail"` and record
   the issue reference (the runner fails an *unexpected pass* so the entry cannot
   rot silently).

## Not ported from the prototype

- `features_svg12/{bidi_text,css_blend_modes,css_media_queries,embedded_svg_in_image,letter_word_spacing,textpath,text_decoration,vertical_text}` and all of
  `features_svg20/*` are empty directories in `..\lunasvg-tests\test_cases`.
- `features_svg12/w3c_filters/` (the output of the prototype's
  `download_w3c_filter_tests.ps1`) was never generated; the W3C filter coverage
  instead lives in the report-only `tests/w3c/` subset.
- The unpaired `filters/test_*.svg` inputs have no baseline and no
  `description.md`; they are superseded by `features_svg12/filters/`.
