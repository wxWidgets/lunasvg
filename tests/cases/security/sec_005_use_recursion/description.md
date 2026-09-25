# SEC-005: Unbounded Recursion in `<use>` Elements

## Vulnerability Type
Stack Overflow / Denial of Service

## Severity
Medium

## Location
- **File**: `source/svgelement.cpp`, Lines 714-745
- **Component**: `<use>` element resolution

## Description
While circular `<use>` references are detected, there is no depth limit on `<use>` chains. Complex non-circular chains can still cause stack overflow through deep recursion.

The current implementation detects direct circular references:
```cpp
auto parent = parentElement();
while(parent) {
    auto attribute = parent->findAttribute(PropertyID::Id);
    if(!attribute.isEmpty() && attribute == idAttr)
        return;  // Circular reference detected
    parent = parent->parentElement();
}
```

However, complex chains like A→B→C→D→...→Z (depth 26) are not limited.

## Attack Vector
A malicious SVG file with:
- Chain of 50+ `<use>` elements
- Each referencing the next: `<use href="#level2"/>`, `<use id="level2" href="#level3"/>`, etc.
- Not circular, but very deep
- Each level consumes stack space during resolution

## Expected Behavior

### Before Fix
- Deep recursion consumes stack
- Stack overflow crash on deep chains
- No depth tracking

### After Fix
- Should implement maximum `<use>` depth (suggested: 50 levels)
- Should track recursion depth during resolution
- Should fail gracefully when limit exceeded
- Should return error without crash

## Test Strategy
This test creates a 50-level `<use>` chain:
- Each level references the next
- Not circular (passes circular check)
- Deep enough to be concerning
- Final element has simple content

## Status
⚠️ **UNFIXED** - This vulnerability exists in current codebase

## Related Issues
- Related to SEC-002 (deep nesting)
- Circular detection exists but not depth limiting
- Similar issue in most SVG implementations

## Reproduction
1. Load the test SVG file with 50-level `<use>` chain
2. Observe `<use>` resolution behavior
3. Check for stack overflow or crash
4. Verify depth limit enforcement

## Mitigation Priority
**P1 - Critical**: Fix before next release

## Notes
- Reasonable depth limit: 50 levels
- Most legitimate SVGs use < 5 levels
- Should track depth per resolution context
- Depth limit separate from general nesting limit
