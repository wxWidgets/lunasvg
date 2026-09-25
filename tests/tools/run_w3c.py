#!/usr/bin/env python3
"""Report-only W3C SVG 1.1 reference-image tracker (plan Phase 4).

Renders every vendored case in ``tests/w3c/cases/`` through the ``svgrender``
helper and compares the result with the external W3C reference PNG through the
tolerance-based ``pngcompare`` helper, interpreting the per-case status in
``tests/w3c/expected_status.json``:

* ``pass``       - expected to match the reference within the policy tolerance;
* ``known-fail`` - expected to differ; it is the recorded *compliance gap*;
* ``skip``       - no vendored case (render failure, missing auxiliary assets).

**This is a progress tracker, not a gate.** W3C results are report-only (plan
decision 2b #13): a failure never blocks a merge, known-fail entries never fail a
build, and this tool therefore exits 0 by default. Pass ``--strict`` to turn an
unexpected *pass* (a known-fail that now matches) or a regressed ``pass`` into a
non-zero exit code for ad-hoc use; CI must not rely on that without a decision
change.

The comparison policy intentionally ignores alpha (``checkAlpha: false``). The
W3C reference rasters were produced by a browser and encode viewport-clipping /
stroke anti-aliasing in the alpha channel that lunasvg reproduces differently;
comparing RGB within the standard anti-aliased tolerance still catches colour and
geometry regressions. See ``tests/w3c/README.md``.

Typical use::

    python tests/tools/run_w3c.py --build-dir build
    python tests/tools/run_w3c.py --build-dir build --only-failing
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Reuse the Phase 3 tooling instead of duplicating render/compare logic.
from bless import find_tool, render_case

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATUS_FILE = REPO_ROOT / "tests" / "w3c" / "expected_status.json"
CASES_DIR = REPO_ROOT / "tests" / "w3c" / "cases"

STATUS_PASS = "pass"
STATUS_KNOWN_FAIL = "known-fail"
STATUS_SKIP = "skip"

TOOLING_ERROR = 2


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--status-file", default=str(DEFAULT_STATUS_FILE), help="path to expected_status.json")
    parser.add_argument("--build-dir", default=str(REPO_ROOT / "build"), help="directory holding svgrender/pngcompare")
    parser.add_argument("--svgrender", default=None, help="explicit path to the svgrender helper")
    parser.add_argument("--pngcompare", default=None, help="explicit path to the pngcompare helper")
    parser.add_argument("--case", action="append", default=None, help="run only this case (repeatable)")
    parser.add_argument("--only-failing", action="store_true", help="print only non-passing entries")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on a regressed pass or an unexpected pass")
    return parser.parse_args(argv)


def load_status(path: Path) -> Dict:
    if not path.is_file():
        raise SystemExit(f"error: status file not found: {path}")
    with path.open("r", encoding="utf-8") as stream:
        status = json.load(stream)
    if not isinstance(status.get("cases"), dict):
        raise SystemExit(f"error: status file has no 'cases' object: {path}")
    return status


def compare_command(pngcompare: Path, reference: Path, candidate: Path, policy: Dict) -> List[str]:
    command = [
        str(pngcompare),
        str(reference),
        str(candidate),
        "--tolerance", str(int(policy["tolerance"])),
        "--max-delta", str(int(policy["maxDelta"])),
        "--max-ratio", str(float(policy["maxDifferingPixelRatio"])),
    ]
    if not policy.get("checkAlpha", True):
        command.append("--no-alpha")
    return command


def main(argv: Optional[List[str]] = None) -> int:
    import subprocess

    args = parse_args(argv)
    status = load_status(Path(args.status_file).resolve())
    policy = status.get("policy", {})
    cases: Dict[str, Dict] = status["cases"]

    case_names = args.case if args.case else sorted(cases.keys())
    unknown = [name for name in case_names if name not in cases]
    if unknown:
        print(f"error: unknown case(s): {', '.join(unknown)}", file=sys.stderr)
        return TOOLING_ERROR

    build_dir = Path(args.build_dir).resolve()
    svgrender = Path(args.svgrender).resolve() if args.svgrender else find_tool(build_dir, "svgrender")
    pngcompare = Path(args.pngcompare).resolve() if args.pngcompare else find_tool(build_dir, "pngcompare")
    if svgrender is None or not svgrender.is_file():
        print(f"error: svgrender not found under {build_dir}; build the tests first", file=sys.stderr)
        return TOOLING_ERROR
    if pngcompare is None or not pngcompare.is_file():
        print(f"error: pngcompare not found under {build_dir}; build the tests first", file=sys.stderr)
        return TOOLING_ERROR

    counts = {STATUS_PASS: 0, STATUS_KNOWN_FAIL: 0, STATUS_SKIP: 0}
    regressed: List[str] = []
    unexpected_pass: List[str] = []
    errors: List[str] = []

    with tempfile.TemporaryDirectory(prefix="wxlunasvg-w3c-") as work_dir:
        work_path = Path(work_dir)
        for name in case_names:
            entry = cases[name]
            expected = entry.get("status", STATUS_KNOWN_FAIL)

            if expected == STATUS_SKIP:
                counts[STATUS_SKIP] += 1
                if not args.only_failing:
                    print(f"SKIP      {name}: {entry.get('note', 'not vendored')}")
                continue

            svg_path = CASES_DIR / name / "test.svg"
            reference_path = CASES_DIR / name / "reference.png"
            if not svg_path.is_file() or not reference_path.is_file():
                errors.append(name)
                print(f"ERROR     {name}: vendored case is incomplete", file=sys.stderr)
                continue

            candidate_path = work_path / f"{name}.png"
            try:
                render_case(svgrender, _render_options(policy), svg_path, candidate_path, echo=False)
                completed = subprocess.run(compare_command(pngcompare, reference_path, candidate_path, policy),
                                           capture_output=True, text=True, check=False)
            except RuntimeError as error:
                errors.append(name)
                print(f"ERROR     {name}: {error}", file=sys.stderr)
                continue

            matches = completed.returncode == 0
            if expected == STATUS_PASS:
                if matches:
                    counts[STATUS_PASS] += 1
                    if not args.only_failing:
                        print(f"PASS      {name}")
                else:
                    regressed.append(name)
                    print(f"REGRESSED {name}: expected pass but now differs from the reference")
            elif matches:
                counts[STATUS_KNOWN_FAIL] += 1
                unexpected_pass.append(name)
                print(f"XPASS     {name}: known-fail now matches the reference; update expected_status.json")
            else:
                counts[STATUS_KNOWN_FAIL] += 1
                if not args.only_failing:
                    print(f"XFAIL     {name}")

    total = counts[STATUS_PASS] + counts[STATUS_KNOWN_FAIL] + counts[STATUS_SKIP]
    print()
    print("W3C SVG 1.1 tracker (report-only; never a merge gate - plan decision 2b #13)")
    print(f"  pass:       {counts[STATUS_PASS]}")
    print(f"  known-fail: {counts[STATUS_KNOWN_FAIL]}")
    print(f"  skip:       {counts[STATUS_SKIP]}")
    print(f"  total:      {total}")
    if regressed:
        print(f"  regressed passes: {', '.join(regressed)}")
    if unexpected_pass:
        print(f"  unexpected passes: {', '.join(unexpected_pass)}")
    if errors:
        print(f"  errors: {', '.join(errors)}")

    if args.strict and (regressed or unexpected_pass or errors):
        return 1
    return 0


def _render_options(policy: Dict) -> Dict:
    """Adapt the W3C policy block to the shape ``bless.render_case`` expects."""
    return {
        "width": policy["width"],
        "height": policy["height"],
        "background": policy["background"],
    }


if __name__ == "__main__":
    sys.exit(main())
