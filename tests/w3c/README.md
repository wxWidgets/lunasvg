# W3C SVG 1.1 reference-image subset (report-only)

A curated slice of the [W3C SVG 1.1 Second Edition Test Suite][suite] rendered by
wxlunasvg and compared against the suite's **external reference PNGs**.

> **This is a progress tracker, not a gate.** W3C results are report-only and
> never block a merge, and `known-fail` entries never fail a build (plan decision
> 2b #13). Nothing here is registered with CTest.

[suite]: https://www.w3.org/Graphics/SVG/Test/20110816/

## Layout

```
tests/w3c/
    expected_status.json      # per-case status + comparison policy
    cases/<name>/
        test.svg              # the W3C test vector (renamed from <name>.svg)
        reference.png         # the W3C reference raster (renamed from <name>.png)
```

The reference PNGs are always **480x360**; the vectors set
`width="100%" height="100%" viewBox="0 0 480 360"`.

## Running

```sh
python tests/tools/run_w3c.py --build-dir build                 # full report
python tests/tools/run_w3c.py --build-dir build --only-failing   # gaps only
python tests/tools/run_w3c.py --build-dir build --strict         # opt-in non-zero exit
```

The tool exits `0` by default: an `XFAIL` (a `known-fail` that still differs) and
even a `REGRESSED` pass do not fail the run. `--strict` is for ad-hoc use only; CI
must not depend on it without revisiting decision 2b #13.

## Status model

`expected_status.json` records one entry per case (see `issueField` in the file):

| `status` | Meaning |
|---|---|
| `pass` | Must match the reference within the policy tolerance. |
| `known-fail` | Expected to differ - the recorded compliance gap. `issue` is reserved for a tracker reference. |
| `skip` | Not vendored (render failure, or needs auxiliary assets we do not ship). |

`seenIn` records where the case came from in the prototype: `mustMatch` (the
`w3c_ignore.json` regression list) or `filters` (the filter tests the prototype's
`download_w3c_filter_tests.ps1` fetched).

### Current baseline

| Status | Count |
|---|---|
| `pass` | 5 (`coords-trans-02-t` .. `coords-trans-06-t`) |
| `known-fail` | 33 |
| `skip` | 3 |

### Comparison policy, and why alpha is ignored

Every W3C vector draws a 1px `<rect id="test-frame">` border at the viewport edge
and embeds a `$Revision: ... $` string, and the suite's reference rasters were
rasterised by a browser. Against lunasvg:

- the frame's stroke is anti-aliased differently, and its coverage is clipped at
  the viewport edge, so the **alpha channel differs systematically**;
- the revision text cannot be rendered at all - `LUNASVG_DISABLE_LOAD_SYSTEM_FONTS`
  is set and lunasvg has no bundled-font-file API.

The reference rasters therefore do not match alpha-for-alpha, and comparing RGBA
would mark every case as failing, hiding the real signal. The policy compares
**RGB** within the standard anti-aliased tolerance
(`tolerance 2`, `maxDelta 8`, `maxDifferingPixelRatio 0.002`) - strict enough that
a colour or geometry regression still fails. This is the reason
`tests/w3c/README.md` exists and why the policy is stored in the JSON rather than
hard-coded.

### Text vectors

The *golden* corpus (`tests/cases/`) excludes text vectors (plan decision 2b #9)
because the golden images must be deterministic. The W3C subset deliberately keeps
them: it is report-only, so text non-determinism only adds to `known-fail`, and
excluding every vector with `<text>` would leave almost no W3C coverage.

## Updating

- A test that has been fixed becomes `"status": "pass"`; a regression flips it
  back to `"known-fail"` with a note.
- To add more W3C tests, copy `<name>.svg` and `<name>.png` from the local suite
  snapshot (`C:/rwCode/svg_w3c_tests`) into `cases/<name>/` as `test.svg` /
  `reference.png`, add an entry, and record the change in
  `tests/data/provenance.md` if the suite revision changes.
- Do **not** vendor vectors that need `../images/` or other auxiliary assets; mark
  them `skip` with the reason (this keeps the subset lean and self-contained).

## Provenance

Source, revision and licence are recorded in `tests/data/provenance.md`. The suite
snapshot carries no separate licence file; the W3C Test Suite Licence applies.
