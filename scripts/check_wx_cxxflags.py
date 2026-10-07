#!/usr/bin/env python3
"""Compile every wxlunasvg library source under wxWidgets' warning flags.

wxWidgets builds this fork in-tree (``--with-lunasvg --with-cxx=20``) with its
own ``WXLUNASVG_CXXFLAGS`` plus ``-Werror``, so any warning the fork emits is
fatal downstream. This script reproduces that compile locally, before a warning
ever reaches a wxWidgets build.

Regression this guards
----------------------
Bumping the ``wx`` submodule dropped the fork's spellings in
``source/svgelement.cpp``::

    std::unique_ptr<SVGNode> SVGTextNode::clone(bool /* deep unused */) const
    void SVGElement::render(SVGRenderState& /* state */) const

Restoring plain ``bool deep`` / ``SVGRenderState& state`` makes
``-Wunused-parameter`` + ``-Werror`` fatal in the wx job above; this checker
reproduces that failure locally.

Flag provenance
---------------
The exact flags are wxWidgets' ``WXLUNASVG_CXXFLAGS`` from
``build/bakefiles/common.bkl`` plus the CI ``-Werror``::

    -std=gnu++20
    -Wall -Wundef -Wunused-parameter -Wno-ctor-dtor-privacy -Woverloaded-virtual
    -DwxENABLE_EXTRA_WARNINGS <override-flag> -Werror -Wno-error=cpp

``<override-flag>`` is ``-Wsuggest-override`` for GNU (GCC) and
``-Winconsistent-missing-override`` for clang. The include roots wx compiles the
submodule with are ``-Iinclude -Iplutovg/include -Iplutovg/source``.

Exit codes
----------
``0`` every source compiled clean; ``1`` one or more sources failed (a warning
was treated as an error) - this is the guard tripping; ``2`` could not run (no
compiler, or no sources found).

This script is the single source of truth invoked by BOTH the ``wx-warnings``
GitHub job (``.github/workflows/tests.yml``) and ``scripts/sync_upstream.py``.
"""

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent

# Environment variables that inject foreign C++ include/link paths into a plain
# g++/clang++ invocation. An inherited CPATH/CPLUS_INCLUDE_PATH (e.g. Intel
# oneAPI plus an msys2 clang64 libc++ tree on the developer machine) makes the
# check fail spuriously with errors like "'aligned_alloc' has not been declared
# in '::'". wxWidgets compiles the submodule in a normal environment with only
# the -I roots below, so clear these to keep the check reproducible.
SANITISE_ENV_KEYS = {
    "CPATH",
    "C_INCLUDE_PATH",
    "CPLUS_INCLUDE_PATH",
    "LIBRARY_PATH",
    "GCC_EXEC_PREFIX",
    "OBJC_INCLUDE_PATH",
}


def base_flags(compiler: str) -> List[str]:
    """Return wxWidgets' warning flags, picking the override flag by family."""
    try:
        version = subprocess.run(
            [compiler, "--version"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        version = None

    output = ""
    if version is not None:
        output = (version.stdout or "") + (version.stderr or "")
    is_clang = "clang" in output.lower()

    override_flag = "-Winconsistent-missing-override" if is_clang else "-Wsuggest-override"

    return [
        "-std=gnu++20",
        "-Wall",
        "-Wundef",
        "-Wunused-parameter",
        "-Wno-ctor-dtor-privacy",
        "-Woverloaded-virtual",
        "-DwxENABLE_EXTRA_WARNINGS",
        override_flag,
        "-Werror",
        "-Wno-error=cpp",
    ]


def include_flags() -> List[str]:
    """The include roots wxWidgets compiles the submodule with."""
    return ["-Iinclude", "-Iplutovg/include", "-Iplutovg/source"]


def clean_env(keep_environment: bool) -> dict:
    """Return the child environment with foreign include paths removed."""
    if keep_environment:
        return dict(os.environ)
    return {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in SANITISE_ENV_KEYS
    }


# GitHub workflow-command error annotations are parsed from this shape:
#   source/svgelement.cpp:88:50: error: unused parameter 'deep' [-Werror=...]
#   source\svgelement.cpp:88:50: error: ...   (Windows separators are fine)
ERROR_LINE_PATTERN = re.compile(
    r"^(?P<file>[^:\s][^:]*?):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
    r"(?P<sev>error|fatal error)\s*:\s*(?P<msg>.*)$"
)


def github_escape(text: str) -> str:
    """Escape a message for a GitHub workflow command (``%`` and CR/LF)."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def github_annotations(stderr_text: str) -> List[str]:
    """Return ``::error`` annotations parsed from captured compiler stderr."""
    annotations: List[str] = []
    for output_line in stderr_text.splitlines():
        match = ERROR_LINE_PATTERN.match(output_line)
        if match is None:
            continue
        location = f"file={match.group('file')},line={match.group('line')}"
        column = match.group("col")
        if column is not None:
            location += f",col={column}"
        annotations.append(f"::error {location}::{github_escape(match.group('msg'))}")
    return annotations


def print_captured_stderr(stderr_text: str) -> None:
    """Print captured compiler stderr indented beneath its failing source."""
    for output_line in stderr_text.splitlines():
        print(f"    {output_line}", file=sys.stderr)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--cxx",
        default="g++",
        help="C++ compiler to invoke (default: g++)",
    )
    parser.add_argument(
        "--keep-environment",
        action="store_true",
        help="do not strip CPATH/CPLUS_INCLUDE_PATH/etc from the child environment",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)

    args = parse_args(argv)

    sources = sorted(glob.glob(str(REPO_ROOT / "source" / "*.cpp")))
    if not sources:
        print(f"error: no sources found under {REPO_ROOT / 'source'}", file=sys.stderr)
        return 2

    cxx = shutil.which(args.cxx)
    if cxx is None:
        print(
            f"error: compiler '{args.cxx}' was not found on PATH; pass --cxx",
            file=sys.stderr,
        )
        return 2

    flags = base_flags(cxx) + include_flags()
    print(f"compiler      : {cxx}")
    print(f"flags         : {' '.join(flags)}")

    env = clean_env(args.keep_environment)
    failed: List[Tuple[str, str]] = []

    with tempfile.TemporaryDirectory() as temp_dir:
        for source in sources:
            relative_source = os.path.relpath(source, REPO_ROOT)
            object_path = os.path.join(temp_dir, Path(source).stem + ".o")
            print(f"compiling {relative_source}")

            result = subprocess.run(
                [cxx, *flags, "-c", relative_source, "-o", object_path],
                cwd=str(REPO_ROOT),
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                failed.append((relative_source, result.stderr or ""))

    total = len(sources)
    if failed:
        print(
            f"FAILED: {len(failed)}/{total} sources failed under wxWidgets' warning flags",
            file=sys.stderr,
        )
        for relative_source, captured_stderr in failed:
            print(f"\n{relative_source}", file=sys.stderr)
            if captured_stderr:
                print_captured_stderr(captured_stderr)
            print(
                f"    (reproduce: {' '.join([cxx, *flags, '-c', relative_source])})",
                file=sys.stderr,
            )

        if os.environ.get("GITHUB_ACTIONS"):
            for _, captured_stderr in failed:
                for annotation in github_annotations(captured_stderr):
                    print(annotation, file=sys.stderr)
        return 1

    print(f"OK: {total}/{total} sources compile cleanly under wxWidgets' warning flags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
