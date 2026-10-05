# Test data provenance

Source, revision, license, and retrieval date for test-only assets used by `tests/`.
These assets are test-only: none of them is compiled into or shipped with the library.

| Asset | Source | Revision | License | Retrieved (UTC) |
|---|---|---|---|---|
| W3C SVG 1.1 Second Edition test suite (SVG + reference PNGs) | https://www.w3.org/Graphics/SVG/Test/20110816/ (`svg/`, `png/`) | suite release `20110816` (static snapshot, no VCS revision) | W3C Test Suite License / W3C Document License — https://www.w3.org/Consortium/Legal/2008/04-testsuite-license | 2026-09-24 — curated subset vendored into `tests/w3c/cases/` (Phase 4), copied from the local snapshot `C:/rwCode/svg_w3c_tests` |
| WPT SVG reftests | https://github.com/web-platform-tests/wpt (`svg/` subtree) | not vendored | W3C 3-clause BSD (`LICENSE.md` in repo) | not vendored — the Phase 4 curated subset uses the W3C SVG 1.1 suite only |
| resvg reftests | https://github.com/linebender/resvg (`tests/` subtree; formerly RazrFalcon/resvg) | not vendored | MPL-2.0 (`LICENSE` in repo) | not vendored — the Phase 4 curated subset uses the W3C SVG 1.1 suite only |
| `stb_image.h` (PNG reader for tests, Phase 3) | https://github.com/nothings/stb (`stb_image.h`) | `v2.30` | public domain (MIT alternative) (`LICENSE` in repo; copy at vendoring) | 2026-09-24 — vendored from the in-tree v2.30 copy at `plutovg/source/plutovg-stb-image.h` |
| Catch2 v3 (test framework, Phase 2) | https://github.com/catchorg/Catch2 | tag TBD — pin at implementation (Phase 2) | BSL-1.0 (`LICENSE.txt` in repo) | not fetched; FetchContent at configure time (Phase 2) |

## Notes

- License files are copied into this directory (`tests/data/`) when each asset is vendored.
- Pre-existing local (non-repo) copies: `C:/rwCode/svg_w3c_tests` — W3C SVG 1.1 suite snapshot, last written 2026-05-17; consumed by `../lunasvg-tests/scripts/run_w3c_tests.ps1` and `../lunasvg-tests/scripts/download_w3c_filter_tests.ps1`. Contains no license file.
- `stb_image.h` `v2.30` matches the copy already present at `plutovg/source/plutovg-stb-image.h` (library-internal; separate from the test reader).
- `tests/support/stb_image.h` is a byte-for-byte copy of `plutovg/source/plutovg-stb-image.h` (stb_image v2.30, upstream release 2024-05-31); the upstream public-domain / MIT licence text is embedded at the end of the file, so no separate `LICENSE` copy is needed.
- Catch2 and all other test-only dependencies are obtained via CMake FetchContent, never as git submodules.
- Phase 4 vendored a curated W3C subset - 38 vectors plus reference PNGs (480x360) - into `tests/w3c/cases/`, tracked by `tests/w3c/expected_status.json` (report-only; see `tests/w3c/README.md`). Three `mustMatch` entries are recorded as `skip`: `struct-frag-01-t` (render failure) and `struct-image-01-t` / `struct-image-03-t` (they reference `../images/` auxiliary assets, which are not vendored). The W3C `images/` and `resources/` trees are deliberately not vendored.
- The `tests/cases/**` golden corpus (Phase 4) is ported from the out-of-tree prototype `..\lunasvg-tests\test_cases`; it is first-party test data, not vendored third-party material.
- wxWidgets has no written policy covering test data (`docs/contributing/how-to-update-third-party-library.md` covers code delivered as submodules only).
- Re-check trigger: revisit this assessment if a test asset is ever bundled into a shipped artifact. A submodule source tree is not a shipped artifact.
