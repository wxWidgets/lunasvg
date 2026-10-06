#!/usr/bin/env python3
"""
Regenerate golden-image baselines for the wxlunasvg test suite.

Renders each corpus case (``<case>/test.svg``) through the ``svgrender`` helper
using the per-case overrides in ``tests/data/manifest.json`` and replaces
``<case>/baseline.png``. Baseline regeneration is only canonical on Linux CI
(plan decision 2b #12), so this tool refuses to run anywhere else unless
``--allow-foreign-platform`` is passed explicitly.

Every blessing must surface as a reviewable diff, so after writing the tool runs
``git status`` and ``git diff --stat`` scoped to the touched case directories and
prints the result.

Typical use::

    python tests/tools/bless.py --build-dir build       # bless every case
    python tests/tools/bless.py --case tests/cases/bugs/bug_001_foo
    python tests/tools/bless.py --dry-run               # report only, write nothing

Python, not PowerShell (plan decision 2b #18).
"""

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_MANIFEST = REPO_ROOT / "tests" / "data" / "manifest.json"
DEFAULT_BUILD_DIR = REPO_ROOT / "build"

# Mirrors the render target's expected status values (see manifest.json).
EXPECTED_STATUS_VALUES = ("pass", "known-fail", "skip")

# pngcompare exit codes (tests/tools/pngcompare.cpp).
COMPARE_MATCH = 0
COMPARE_USAGE = 1
COMPARE_LOAD_FAILED = 2
COMPARE_DIFFERS = 4


def run(command: List[str], cwd: Path, echo: bool = True) -> subprocess.CompletedProcess:
    """Execute *command*, capturing its output; echo the command line unless *echo* is False."""
    if echo:
        print(f"+ {' '.join(command)}", flush=True)
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, check=False)


def find_tool(build_dir: Path, name: str) -> Optional[Path]:
    """Locate a built helper, tolerating single-config and multi-config trees."""
    suffixes = [""]
    if platform.system() == "Windows":
        suffixes.insert(0, ".exe")

    # add_subdirectory(tests) places the helpers under <build>/tests; a
    # multi-config generator (Visual Studio) nests them one level deeper.
    search_roots = [build_dir, build_dir / "bin", build_dir / "tests", build_dir / "bin" / "tests"]
    configs = ("", "Debug", "Release", "RelWithDebInfo", "MinSizeRel")

    for root in search_roots:
        for config in configs:
            directory = (root / config) if config else root
            for suffix in suffixes:
                candidate = directory / f"{name}{suffix}"
                if candidate.is_file():
                    return candidate

    return None


def load_manifest(manifest_path: Path) -> Dict:
    """Load and validate the corpus manifest."""
    if not manifest_path.is_file():
        raise SystemExit(f"error: manifest not found: {manifest_path}")

    with manifest_path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)

    if not isinstance(manifest.get("cases"), dict):
        raise SystemExit(f"error: manifest has no 'cases' object: {manifest_path}")
    return manifest


def case_options(case_entry: Dict, defaults: Dict) -> Dict:
    """Merge a case's overrides over the manifest defaults."""
    merged = dict(defaults)
    merged.update(case_entry or {})

    status = merged.get("expectedStatus", "pass")
    if status not in EXPECTED_STATUS_VALUES:
        raise SystemExit(f"error: invalid expectedStatus '{status}' (expected one of {EXPECTED_STATUS_VALUES})")
    return merged


def render_case(svgrender: Path, options: Dict, svg_path: Path, output_path: Path, echo: bool = True) -> None:
    """Render one case's SVG to *output_path* via the svgrender helper."""
    size = f"{int(options['width'])}x{int(options['height'])}"
    background = str(options["background"])
    command = [str(svgrender), str(svg_path), str(output_path), size, background]
    completed = run(command, REPO_ROOT, echo=echo)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "svgrender failed")


def baselines_differ(pngcompare: Path, options: Dict, baseline: Path, candidate: Path,
                     diff_path: Optional[Path] = None, echo: bool = True) -> Optional[bool]:
    """Return True if *baseline* and *candidate* differ, False if they match, None on error.

    When *diff_path* is given, pngcompare writes a reviewable diff PNG there on mismatch.
    """
    command = [
        str(pngcompare),
        str(baseline),
        str(candidate),
        "--tolerance",
        str(int(options["tolerance"])),
        "--max-ratio",
        str(float(options["maxDifferingPixelRatio"])),
        "--max-delta",
        str(int(options["maxDelta"])),
    ]
    if not options.get("checkAlpha", True):
        command.append("--no-alpha")
    if diff_path is not None:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        command += ["--diff-out", str(diff_path)]

    completed = run(command, REPO_ROOT, echo=echo)
    if completed.returncode == COMPARE_MATCH:
        return False
    if completed.returncode == COMPARE_DIFFERS:
        return True
    raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "pngcompare failed")


def surface_git_diff(directories: List[Path]) -> None:
    """Print the reviewable diff for the blessed cases."""
    if not directories:
        return

    scoped = [str(directory.relative_to(REPO_ROOT)) for directory in directories]
    print("\n--- reviewable diff ---")
    status = run(["git", "status", "--porcelain", "--", *scoped], REPO_ROOT)
    print(status.stdout.rstrip() or "(no changes)")
    diff = run(["git", "diff", "--stat", "--", *scoped], REPO_ROOT)
    if diff.stdout.strip():
        print(diff.stdout.rstrip())
    print("--- end reviewable diff ---")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="path to manifest.json")
    parser.add_argument("--build-dir", default=str(DEFAULT_BUILD_DIR), help="directory holding svgrender/pngcompare")
    parser.add_argument("--svgrender", default=None, help="explicit path to the svgrender helper")
    parser.add_argument("--pngcompare", default=None, help="explicit path to the pngcompare helper")
    parser.add_argument("--case", action="append", default=None, help="bless only this case key (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="report what would change without writing")
    parser.add_argument("--no-git-diff", action="store_true", help="suppress the trailing git diff")
    parser.add_argument(
        "--allow-foreign-platform",
        action="store_true",
        help="allow blessing off Linux; the result is NOT a canonical baseline",
    )
    args = parser.parse_args(argv)

    if platform.system() != "Linux" and not args.allow_foreign_platform:
        print(
            "error: baselines are only blessed on Linux CI (plan decision 2b #12); "
            f"this is {platform.system()}. Re-run with --allow-foreign-platform to override "
            "(the result must not be treated as canonical).",
            file=sys.stderr,
        )
        return 1

    manifest_path = Path(args.manifest).resolve()
    manifest = load_manifest(manifest_path)

    build_dir = Path(args.build_dir).resolve()
    svgrender = Path(args.svgrender).resolve() if args.svgrender else find_tool(build_dir, "svgrender")
    pngcompare = Path(args.pngcompare).resolve() if args.pngcompare else find_tool(build_dir, "pngcompare")
    if svgrender is None or not svgrender.is_file():
        print(f"error: svgrender not found under {build_dir}; build the tests first", file=sys.stderr)
        return 2
    if pngcompare is None or not pngcompare.is_file():
        print(f"error: pngcompare not found under {build_dir}; build the tests first", file=sys.stderr)
        return 2

    case_keys = args.case if args.case else sorted(manifest["cases"].keys())
    if not case_keys:
        print("No cases in the manifest yet. Nothing to bless.")
        return 0

    defaults = manifest.get("defaults", {})
    added: List[str] = []
    changed: List[str] = []
    unchanged: List[str] = []
    skipped: List[str] = []
    errors: List[str] = []
    touched: List[Path] = []

    with tempfile.TemporaryDirectory(prefix="wxlunasvg-bless-") as work_dir:
        work_path = Path(work_dir)
        for case_key in case_keys:
            options = case_options(manifest["cases"].get(case_key, {}), defaults)

            # Cases tracked as `skip` (text vectors, malicious security inputs,
            # ...) are never rendered by the runner, so they are never blessed
            # either; blessing them would create a golden image nothing consumes.
            if options["expectedStatus"] == "skip":
                skipped.append(case_key)
                print(f"skipped: {case_key} (expectedStatus=skip)")
                continue

            case_dir = (REPO_ROOT / case_key).resolve()
            svg_path = case_dir / "test.svg"
            baseline_path = case_dir / "baseline.png"

            if not svg_path.is_file():
                errors.append(f"{case_key}: missing {svg_path}")
                print(f"error: {case_key}: missing {svg_path}", file=sys.stderr)
                continue

            candidate_path = work_path / f"{case_dir.name}.png"

            try:
                render_case(svgrender, options, svg_path, candidate_path)
                if baseline_path.is_file():
                    differs = baselines_differ(pngcompare, options, baseline_path, candidate_path)
                    outcome = "changed" if differs else "unchanged"
                else:
                    outcome = "added"

                if args.dry_run:
                    print(f"[dry-run] {outcome}: {case_key}")
                elif outcome != "unchanged":
                    case_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(candidate_path, baseline_path)
                    print(f"{outcome}: {case_key}")
                else:
                    print(f"unchanged: {case_key}")

                if outcome == "added":
                    added.append(case_key)
                elif outcome == "changed":
                    changed.append(case_key)
                else:
                    unchanged.append(case_key)
                touched.append(case_dir)
            except RuntimeError as error:
                errors.append(f"{case_key}: {error}")
                print(f"error: {case_key}: {error}", file=sys.stderr)

    print(f"\nBlessed: {len(added)} added, {len(changed)} changed, {len(unchanged)} unchanged, "
          f"{len(skipped)} skipped, {len(errors)} error(s).")
    if args.dry_run:
        print("(dry-run: nothing was written)")

    if not args.no_git_diff and not args.dry_run:
        surface_git_diff(sorted(set(touched)))

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
