# SEC-004: ReDoS in CSS Selector Parsing

## Vulnerability Type
Regular Expression Denial of Service (ReDoS) / CPU Exhaustion

## Severity
High

## Location
- **File**: `source/svgparser.cpp`, Lines 414-525
- **Component**: CSS selector parsing and matching

## Description
Complex CSS selectors can cause catastrophic backtracking in regex-based or recursive parsing, leading to CPU exhaustion and denial of service. The vulnerability occurs when matching complex selectors against many elements.

## Attack Vector
A malicious SVG file with:
- Pathological CSS selectors using nested combinators
- Multiple attribute selectors with wildcards
- Complex pseudo-class combinations
- Applied to document with many elements

Example pathological selector:
```css
div[class*='a'][class*='b'][class*='c'][class*='d'][class*='e'] div div div div div
```

## Expected Behavior

### Before Fix
- Parser hangs or takes excessive time (minutes to hours)
- CPU usage spikes to 100%
- Application becomes unresponsive
- No timeout mechanism

### After Fix
- Should implement parsing timeout (suggested: 1 second per selector)
- Should limit selector complexity (max depth, max components)
- Should fail gracefully with timeout error
- Should prevent CPU exhaustion

## Test Strategy
This test uses a complex selector with:
- Multiple nested descendant combinators
- Multiple attribute selectors with wildcards
- Pseudo-class combinations
- Applied to many elements (100 groups)

## Status
⚠️ **UNFIXED** - This vulnerability exists in current codebase

## Related Issues
- Common web security issue (OWASP)
- Requires timeout mechanism in selector matching
- Related to overall parsing timeout needs

## Reproduction
1. Load the test SVG file with pathological selector
2. Monitor CPU usage
3. Check for timeout or hang
4. Verify graceful failure with timeout

## Mitigation Priority
**P1 - Critical**: Fix before next release

## Notes
- Reasonable timeout: 1 second per selector
- Alternative: limit selector complexity (depth, components)
- Should track matching time, not just parsing time
- Consider selector complexity analysis before matching
