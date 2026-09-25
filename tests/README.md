# wxlunasvg test suite

[![Tests](https://github.com/wxWidgets/lunasvg/actions/workflows/tests.yml/badge.svg)](https://github.com/wxWidgets/lunasvg/actions/workflows/tests.yml)

Self-contained, cross-platform tests for the wxlunasvg fork. The suite lives
inside the repository so `origin`'s CI can run it from a plain checkout; it is
invisible to wxWidgets' build because wxWidgets compiles the library from an
explicit source list (`build/cmake/lib/lunasvg.cmake`) and the tests are opt-in
and standalone-only.

> This file is seeded in Phase 3, extended in Phase 4 and Phase 5, and becomes
> the authoritative how-to in Phase 9.

## Running the suite

`ctest` is the canonical runner (what CI invokes); `tests/run_tests.py` is a thin
Python convenience wrapper.

```sh
cmake -S . -B build -DLUNASVG_BUILD_TESTS=ON
cmake --build build
ctest --test-dir build --output-on-failure
# or:
python tests/run_tests.py --configure
```

Catch2 v3 is fetched with `FetchContent` (never a submodule); point
`-DLUNASVG_CATCH2_DIR=<checkout>` at a pre-cloned copy for offline builds.

`ctest` runs two tests: `wxlunasvg_tests` (the Catch2 unit/structural suite) and
`wxlunasvg_cases` (the golden-image corpus, Phase 4). The corpus test is only
registered when CMake finds a Python 3 interpreter.

## Continuous integration

`.github/workflows/tests.yml` runs the suite on every PR to the `wx` integration
branch, nightly, and on demand:

| Job | What it does |
|---|---|
| `test` | OS x compiler x C++ standard matrix - `{ubuntu, macos, windows}` x `{gcc, clang, msvc}` (only the compilers each image actually has, via `exclude`) x `{C++17, C++20}`. Configures with `-DLUNASVG_BUILD_TESTS=ON`, builds, then runs `ctest --output-on-failure`. |
| `sanitizers` | ASAN + UBSAN on Linux/clang, building as C++20, mirroring wxWidgets' `--with-lunasvg --with-cxx=20` job (the knowledge-base sanitizer gate). |
| `structural-lint` | No build, no compiler - `scripts/post_merge.py --dry-run` idempotency (must report no changes), no legacy `namespace lunasvg` left under `include/` + `source/`, and the C++17 `#error` guard present in `include/lunasvg.h`. |

On failure every job uploads the ctest console log (`build/test_results.log`),
the CTest logs (`build/Testing/Temporary/**`) and the diff PNGs written by
`pngcompare` (`build/corpus-diffs/**`) as workflow artifacts. Rendered
`current.png`s are ephemeral - the corpus runner writes them to a temporary
directory and deletes them - so the diff PNGs are the durable failure evidence.

The matrix legs build unoptimised - the Windows (multi-config) legs select
`Debug`, the single-config legs use CMake's unoptimised default - to stay close
to the configuration used to bless the baselines. One caveat on the C++ standard
axis: the library target pins C++17 (`CXX_STANDARD 17` in the root
`CMakeLists.txt`), so `-DCMAKE_CXX_STANDARD=20` lifts the *test* sources and the
public header to C++20 while the library itself stays C++17 - which still
catches header/standard drift.

> **CI is a signal, not a merge gate.** `origin/wx` deliberately has no required
> status checks (plan decisions 2b #11 and 2b #13): the suite always *runs* on a
> PR, but a maintainer may merge even when it is red. Requesting branch
> protection is deferred, and no part of this project may assume a blocking
> status check exists.

Two further notes:

- **Baselines are blessed on Linux CI only** (plan decision 2b #12), so the Linux
  legs are the canonical signal; the Windows/macOS legs are advisory and exist to
  catch portability regressions early.
- **Fork vs same-repo PRs (GitHub nuance):** a PR opened from a branch of this
  repository runs the workflow from the PR's merge commit, whereas a PR from a
  different fork runs the workflow as it exists on the *base* branch. Changes to
  `tests.yml` therefore only take effect for same-repo PRs until they land on
  `wx`.

`.github/workflows/main.yml` stays the build-only workflow (meson + cmake); the
test suite is never wired into the meson path (plan decision #4).

## Golden-image comparison engine (Phase 3)

`tests/support/compare.{h,cpp}` decodes PNGs (vendored `stb_image.h`, see
`tests/data/provenance.md`) and compares **decoded pixels**, never PNG bytes.
This replaces the out-of-tree prototype's byte-exact `comparePNGs`, which was the
root cause of cross-platform flakiness. The semantics mirror wxWidgets'
`RGBSimilarTo` / `RGBASimilarTo` matchers in `tests/testimage.h`.

`CompareOptions`:

| Option | Meaning | wx equivalent |
|---|---|---|
| `tolerance` | per-channel absolute delta at or below which a channel is equal | tolerance argument of `RGBSimilarTo` |
| `check_alpha` | `false` compares RGB only; `true` compares RGBA | `RGBSimilarTo` vs `RGBASimilarTo` |
| `max_delta` | hard cap on the worst differing-channel delta (255 disables it) | — (extension) |
| `max_differing_pixel_ratio` | largest tolerated fraction of differing pixels (0.0 = wx behaviour) | — (extension) |

On failure the engine reports the **first mismatching pixel** wx-style
(`first mismatch is at (x, y) which has value 0x... instead of the expected 0x...`)
plus a summary (differing count, ratio, max channel delta, tolerance).

`tests/tools/pngcompare` is the CLI front-end (exit codes: `0` match, `1` usage,
`2` load failure, `4` mismatch) and writes a diff PNG via `--diff-out` when the
comparison fails.

### Tolerance policy

- **Flat fills and geometry: exact** (`tolerance 0`, `maxDifferingPixelRatio 0`).
- **Anti-aliased edges: small tolerance** (`tolerance 2`, `maxDelta 8`,
  `maxDifferingPixelRatio 0.002`) so a handful of edge pixels may differ while a
  whole-region regression still fails.

Named policies and per-case overrides live in `tests/data/manifest.json`.

## Corpus layout and manifest

Cases keep the prototype's layout:

```
tests/cases/<group>/<case>/
    test.svg          # input
    baseline.png      # golden image (committed; pass / known-fail cases only)
    description.md    # what the case exercises
```

`current.png` is never committed: the runner renders into a temporary directory.
The groups, their statuses and the "add a case" convention are documented in
`tests/cases/README.md` and the per-group `README.md` files.

`tests/data/manifest.json` holds defaults, the tolerance policies, and per-case
overrides (render size, background, tolerance, `expectedStatus`, `skipReason`).
Case keys are paths relative to the repository root. `expectedStatus` has three
values (plan Phase 4):

| Status | Meaning |
|---|---|
| `pass` | The render must match `baseline.png` within the case's tolerance. |
| `known-fail` | The render must **differ**; an unexpected match fails the run so the entry cannot rot. |
| `skip` | Tracked but never rendered (text vectors, malicious security inputs). |

`tests/tools/run_cases.py` enforces this as the CTest test `wxlunasvg_cases`
(registered when a Python 3 interpreter is found); `ctest` therefore runs both the
unit tests and the corpus. `bless.py` honours `expectedStatus` too and never
blesses a skipped case. To see the tracked state without running anything:

```sh
python tests/tools/run_cases.py --list
```

## W3C reference subset (report-only)

`tests/w3c/` vendors a curated slice of the W3C SVG 1.1 suite and tracks each
case as `pass` / `known-fail` / `skip` in `tests/w3c/expected_status.json`.
It is a **compliance progress tracker and never a merge gate** (plan decision
2b #13) and is not registered with CTest:

```sh
python tests/tools/run_w3c.py --build-dir build
```

See `tests/w3c/README.md` for the comparison policy (RGB-only, and why) and the
current baseline.

## Blessing baselines

```sh
python tests/tools/bless.py --build-dir build                 # bless every case
python tests/tools/bless.py --case tests/cases/bugs/bug_001_x # one case
python tests/tools/bless.py --dry-run                          # report only
```

Blessing is **only canonical on Linux CI** (plan decision 2b #12): the tool
refuses to run on other platforms unless `--allow-foreign-platform` is passed,
and every blessing prints `git status` / `git diff --stat` for the touched case
directories so the change is reviewable. Do not bless baselines on a Windows or
macOS developer box as canonical.

## Determinism and the current coverage gap

- The test build forces `LUNASVG_DISABLE_LOAD_SYSTEM_FONTS`, so the library never
  picks up host fonts (see the `LUNASVG_BUILD_TESTS` block in the root
  `CMakeLists.txt`).
- **Text-bearing vectors are excluded from the golden set** (plan decision 2b
  #9). Disabling system fonts makes rendering deterministic but leaves lunasvg
  with no bundled font-file API, so text output is not yet reproducible across
  platforms. This is a recorded coverage gap, not a blocker; it is revisited only
  if lunasvg gains an explicit font-file loading API.
