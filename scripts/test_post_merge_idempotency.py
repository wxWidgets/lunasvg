#!/usr/bin/env python3
"""Idempotency test for ``scripts/post_merge.py`` (plan section 6, Phase 6).

The upstream-sync gate (``scripts/sync_upstream.py``) and the structural-lint CI
job both depend on one property: once ``post_merge.py`` has normalised a tree, a
*second* run must have nothing left to do. If it did not, every sync would keep
re-introducing namespace/guard churn and the checkout would never be
"post_merge clean".

The test is self-contained. It builds a small fixture tree that exercises all
three transforms (the C++17 ``#error`` guard, the WX defines, and the namespace
rewrite), applies ``post_merge.py`` once, and asserts that a subsequent
``--dry-run`` - and a second real run - report no changes. It also pins the
invariants the rewrite must preserve: prose comments and string literals that
merely mention the legacy name are left verbatim.

Run directly (this is what the structural-lint CI job invokes) or under
unittest::

    python scripts/test_post_merge_idempotency.py
    python -m unittest scripts.test_post_merge_idempotency

Python, not PowerShell (plan decision 2b #18).
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

POST_MERGE = Path(__file__).resolve().with_name("post_merge.py")

# Un-normalised fixtures: the legacy namespace, no C++17 guard, no WX defines.
HEADER_FIXTURE = """\
#ifndef LUNASVG_H
#define LUNASVG_H

#include <cstdint>

namespace lunasvg {

class Document {};

} // namespace lunasvg

extern "C" {
void lunasvg_destroy(Document* document);
}

#endif
"""

SOURCE_FIXTURE = """\
#include "lunasvg.h"

using namespace lunasvg;

// lunasvg is the legacy name; this comment mentions it as prose and must survive.
static const char* kLegacyName = "lunasvg";

namespace lunasvg {

int example() { return 1; }

} // namespace lunasvg
"""

PROSE_COMMENT = "// lunasvg is the legacy name; this comment mentions it as prose and must survive."
STRING_LITERAL = 'static const char* kLegacyName = "lunasvg";'

NO_CHANGES = "No changes needed."
CHANGES_MADE = "change(s) made"


class PostMergeIdempotencyTest(unittest.TestCase):
    """``post_merge.py`` must be a no-op the second time it runs."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="wxlunasvg-postmerge-")
        self.root = Path(self._tmp.name)
        (self.root / "include").mkdir()
        (self.root / "source").mkdir()
        self.header = self.root / "include" / "lunasvg.h"
        self.source = self.root / "source" / "example.cpp"
        self.header.write_text(HEADER_FIXTURE, encoding="utf-8")
        self.source.write_text(SOURCE_FIXTURE, encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_post_merge(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(POST_MERGE), "--root", str(self.root), *extra],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_first_run_changes_then_dry_run_is_noop(self) -> None:
        first = self.run_post_merge()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn(CHANGES_MADE, first.stdout, "the fixture should need normalising")

        second = self.run_post_merge("--dry-run")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn(NO_CHANGES, second.stdout, "a second --dry-run must report no changes")
        self.assertNotIn(CHANGES_MADE, second.stdout)

    def test_second_real_run_is_noop(self) -> None:
        self.assertEqual(self.run_post_merge().returncode, 0)
        second = self.run_post_merge()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn(NO_CHANGES, second.stdout)

    def test_rewrite_applies_guards_and_preserves_prose(self) -> None:
        self.assertEqual(self.run_post_merge().returncode, 0)

        header = self.header.read_text(encoding="utf-8")
        self.assertIn("201703L", header)
        self.assertIn("C++17 or later is required", header)
        self.assertIn("WXBUILDING", header)
        self.assertIn("namespace wxlunasvg", header)
        self.assertNotIn("namespace lunasvg", header)

        source = self.source.read_text(encoding="utf-8")
        self.assertIn("namespace wxlunasvg", source)
        self.assertIn("using namespace wxlunasvg;", source)
        self.assertNotIn("namespace lunasvg", source)
        # Prose and literals that merely mention the legacy name are not rewritten.
        self.assertIn(PROSE_COMMENT, source)
        self.assertIn(STRING_LITERAL, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
