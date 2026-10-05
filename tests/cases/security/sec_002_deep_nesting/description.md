# SEC-002: Stack Overflow in Nested Elements

## Vulnerability Type
Stack Overflow / Denial of Service

## Severity
High

## Location
- **File**: `source/svgparser.cpp`, Lines 830-1005
- **Component**: Element parsing and nesting

## Description
The SVG parser has no depth limit on nested elements. Deeply nested `<g>` (group), `<use>`, or `<svg>` elements can cause stack overflow through recursive parsing or rendering.

## Attack Vector
A malicious SVG file with:
- 150+ nested `<g>` elements
- Each nesting level consumes stack space
- Exceeds default stack size (~1MB on Windows, ~8MB on Linux)

## Expected Behavior

### Before Fix
- Stack overflow crash
- Application termination
- No graceful error handling

### After Fix
- Should implement maximum nesting depth (suggested: 100 levels)
- Should return parsing error when limit exceeded
- Should handle gracefully without crash

## Test Strategy
This test creates 150 nested `<g>` elements to trigger stack overflow:
- Nesting depth: 150 levels
- Simple structure to isolate nesting issue
- Small final rectangle to render

## Status
⚠️ **UNFIXED** - This vulnerability exists in current codebase

## Related Issues
- Related to SEC-005 (use recursion)
- Standard practice: limit nesting to 100-200 levels

## Reproduction
1. Load the test SVG file with 150 nested groups
2. Observe parser behavior
3. Check for stack overflow or crash
4. Verify error handling

## Mitigation Priority
**P1 - Critical**: Fix before next release

## Notes
- Browser implementations typically limit nesting to 100-200 levels
- Reasonable limit: 100 levels (sufficient for normal SVGs)
- Should track depth during parsing, not just rendering
