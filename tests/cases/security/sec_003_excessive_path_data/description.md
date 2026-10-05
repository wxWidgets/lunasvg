# SEC-003: Excessive Memory Allocation in Path Data

## Vulnerability Type
Memory Exhaustion / Denial of Service

## Severity
High

## Location
- **File**: `source/svgproperty.cpp` (SVGPath parsing)
- **Component**: Path data parsing and storage

## Description
The path data parser has no limit on the number of points or commands in a path. A malicious SVG can include extremely long path data with millions of points, causing:
- Excessive memory allocation
- Out-of-memory conditions
- Application hang or crash
- System instability

## Attack Vector
A malicious SVG file with:
- Path containing hundreds of thousands or millions of line segments
- Each segment requires memory for coordinates
- No validation before allocation

## Expected Behavior

### Before Fix
- Parser attempts to allocate unlimited memory
- Out-of-memory error or crash
- System may become unresponsive
- No user feedback about issue

### After Fix
- Should implement maximum point count (suggested: 1,000,000 points)
- Should return parsing error when limit exceeded
- Should fail gracefully with clear error message
- Should not allocate memory until validation passes

## Test Strategy
This test creates a path with 100,000 line segments (200,000 coordinates):
- Large but not extreme (to avoid test timeout)
- Demonstrates the principle without exhausting test system memory
- Actual attacks could use millions of points

## Status
⚠️ **UNFIXED** - This vulnerability exists in current codebase

## Related Issues
- Related to SEC-001 (integer overflow)
- Related to SEC-007 (base64 allocation)

## Reproduction
1. Load the test SVG file with massive path data
2. Monitor memory allocation
3. Check for out-of-memory handling
4. Verify graceful failure

## Mitigation Priority
**P1 - Critical**: Fix before next release

## Notes
- Reasonable limit: 1,000,000 points per path
- Most legitimate SVGs have < 10,000 points
- Should validate early, before allocation
- Consider progressive parsing for large but valid paths
