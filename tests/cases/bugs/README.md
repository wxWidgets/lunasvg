# bugs/

Regression cases for fixed bugs. One directory per bug, named
`bug_NNN_<slug>`, each holding `test.svg`, `baseline.png` and `description.md`.

This is the convention that enforces "every fix ships a regression test": a
bug-fix PR must add a case here (plan Phase 8).

| Case | Exercises |
|---|---|
| `bug_001_pseudo_class_first_of_type` | `rect:first-of-type` CSS selector application. |
| `bug_002_pseudo_class_last_of_type` | `rect:last-of-type` CSS selector application. |

Both cases are flat geometry, so they are compared exactly
(`tolerance 0`, `maxDifferingPixelRatio 0`).
