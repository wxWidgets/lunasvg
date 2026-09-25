#!/usr/bin/env python3
"""Run the in-repo golden-image corpus (plan Phase 4).

For each case in ``tests/data/manifest.json`` this renders ``<case>/test.svg``
through the ``svgrender`` helper and compares the result with ``<case>/baseline.png``
through the tolerance-based ``pngcompare`` helper, then interprets the manifest's
``expectedStatus``:

* ``pass``      - the comparison must match; a mismatch fails the run;
* ``known-fail`` - the comparison must differ; an *unexpected* match also fails,
                   so a stale tracker entry cannot go unnoticed;
* ``skip``      - not rendered at all, reported for completeness.

This is the Phase 4 "ctest orchestration" of the manifest: ``tests/CMakeLists.txt``
registers it as the ``wxlunasvg_cases`` CTest test. It is Python, not PowerShell
(plan decision 2b #18). The W3C reference-PNG subset is *not* run here - it is
report-only and lives in ``tests/tools/run_w3c.py`` (plan decision 2b #13).

Typical use::

    python tests/tools/run_cases.py --build-dir build
    python tests/tools/run_cases.py --build-dir build --case tests/cases/bugs/bug_001_pseudo_class_first_of_type
    python tests/tools/run_cases.py --build-dir build --list
"""

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Reuse the Phase 3 tooling instead of duplicating render/compare logic.
from bless import (
    DEFAULT_MANIFEST,
    baselines_differ,
    case_options,
    find_tool,
    load_manifest,
    render_case,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

STATUS_PASS = "pass"
STATUS_KNOWN_FAIL = "known-fail"
STATUS_SKIP = "skip"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="path to manifest.json")
    parser.add_argument("--build-dir", default=str(REPO_ROOT / "build"), help="directory holding svgrender/pngcompare")
    parser.add_argument("--svgrender", default=None, help="explicit path to the svgrender helper")
    parser.add_argument("--pngcompare", default=None, help="explicit path to the pngcompare helper")
    parser.add_argument("--case", action="append", default=None, help="run only this case key (repeatable)")
    parser.add_argument("--diff-dir", default=None, help="where to write diff PNGs (default: <build-dir>/corpus-diffs)")
    parser.add_argument("--list", action="store_true", help="list the cases and their expected status, then exit")
    return parser.parse_args(argv)


def resolve_tools(args: argparse.Namespace) -> Optional[Dict[str, Path]]:
    build_dir = Path(args.build_dir).resolve()
    svgrender = Path(args.svgrender).resolve() if args.svgrender else find_tool(build_dir, "svgrender")
    pngcompare = Path(args.pngcompare).resolve() if args.pngcompare else find_tool(build_dir, "pngcompare")
    if svgrender is None or not svgrender.is_file():
        print(f"error: svgrender not found under {build_dir}; build the tests first", file=sys.stderr)
        return None
    if pngcompare is None or not pngcompare.is_file():
        print(f"error: pngcompare not found under {build_dir}; build the tests first", file=sys.stderr)
        return None
    return {"svgrender": svgrender, "pngcompare": pngcompare}


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    manifest = load_manifest(Path(args.manifest).resolve())
    defaults = manifest.get("defaults", {})
    cases: Dict[str, Dict] = manifest["cases"]

    case_keys = args.case if args.case else sorted(cases.keys())
    unknown = [key for key in case_keys if key not in cases]
    if unknown:
        print(f"error: unknown case key(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    if args.list:
        for key in case_keys:
            status = case_options(cases[key], defaults)["expectedStatus"]
            print(f"{status:10s} {key}")
        return 0

    tools = resolve_tools(args)
    if tools is None:
        return 2

    diff_dir = Path(args.diff_dir).resolve() if args.diff_dir else (Path(args.build_dir).resolve() / "corpus-diffs")

    passed = 0
    known_failed = 0
    skipped = 0
    failures: List[str] = []
    unexpected_passes: List[str] = []

    with tempfile.TemporaryDirectory(prefix="wxlunasvg-corpus-") as work_dir:
        work_path = Path(work_dir)
        for case_key in case_keys:
            options = case_options(cases[case_key], defaults)
            status = options["expectedStatus"]

            if status == STATUS_SKIP:
                skipped += 1
                print(f"SKIP      {case_key}: {options.get('skipReason', 'skipped')}")
                continue

            case_dir = (REPO_ROOT / case_key).resolve()
            svg_path = case_dir / "test.svg"
            baseline_path = case_dir / "baseline.png"
            if not svg_path.is_file():
                failures.append(f"{case_key}: missing {svg_path}")
                print(f"ERROR     {case_key}: missing {svg_path}", file=sys.stderr)
                continue
            if not baseline_path.is_file():
                failures.append(f"{case_key}: missing {baseline_path}")
                print(f"ERROR     {case_key}: missing {baseline_path}", file=sys.stderr)
                continue

            candidate_path = work_path / f"{case_dir.name}.png"
            diff_path = diff_dir / f"{case_dir.name}.diff.png"

            try:
                render_case(tools["svgrender"], options, svg_path, candidate_path, echo=False)
                differs = baselines_differ(tools["pngcompare"], options, baseline_path, candidate_path,
                                           diff_path if status == STATUS_PASS else None, echo=False)
            except RuntimeError as error:
                failures.append(f"{case_key}: {error}")
                print(f"ERROR     {case_key}: {error}", file=sys.stderr)
                continue

            if status == STATUS_PASS:
                if differs:
                    failures.append(case_key)
                    print(f"FAIL      {case_key}: render differs from baseline (diff: {diff_path})")
                else:
                    passed += 1
                    print(f"PASS      {case_key}")
            elif status == STATUS_KNOWN_FAIL:
                if differs:
                    known_failed += 1
                    print(f"XFAIL     {case_key} (expected: still failing)")
                else:
                    unexpected_passes.append(case_key)
                    print(f"XPASS     {case_key}: expected a known-fail but it now matches; update expectedStatus")

    print()
    print(f"corpus: {passed} pass, {known_failed} known-fail, {skipped} skip, "
          f"{len(failures)} failure(s), {len(unexpected_passes)} unexpected pass(es)")

    return 1 if failures or unexpected_passes else 0


if __name__ == "__main__":
    sys.exit(main())
