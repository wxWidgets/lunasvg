# SEC-001: Integer Overflow in Canvas Creation

## Vulnerability Type
Integer Overflow / Memory Corruption

## Severity
High

## Location
- **File**: `source/graphics.cpp`, Lines 497-503
- **Component**: Canvas creation

## Description
The maximum size check (`kMaxSize = 32768`) can be bypassed through integer overflow when combining large coordinates with width/height values. The vulnerability occurs when `x`, `y`, `width`, and `height` values are used in arithmetic operations that can overflow:

```cpp
constexpr int kMaxSize = 1 << 15;  // 32768
if(width <= 0 || height <= 0 || width >= kMaxSize || height >= kMaxSize)
    return std::shared_ptr<Canvas>(new Canvas(0, 0, 1, 1));
auto l = static_cast<int>(std::floor(x));
auto t = static_cast<int>(std::floor(y));
auto r = static_cast<int>(std::ceil(x + width));   // Overflow here!
auto b = static_cast<int>(std::ceil(y + height));  // And here!
```

## Attack Vector
A malicious SVG file with:
- Large `x` or `y` offsets (e.g., 32700)
- Combined with large `width`/`height` values (e.g., 32700)
- When added together: `32700 + 32700 = 65400` (overflows 32-bit signed int range when properly checked)

## Expected Behavior

### Before Fix
- May allocate incorrect canvas size
- Potential memory corruption
- Could crash or behave unpredictably

### After Fix
- Should detect overflow condition
- Should reject SVG or clamp to safe values
- Should return error or use fallback dimensions

## Test Strategy
This test uses extreme coordinate values that should trigger overflow protection:
- `viewBox="32700 32700 32700 32700"` 
- Large offsets combined with large dimensions

## Status
⚠️ **UNFIXED** - This vulnerability exists in current codebase

## Related Issues
- CVE-TBD (pending security fix)
- Related to SEC-003 (excessive memory allocation)

## Reproduction
1. Load the test SVG file
2. Observe whether overflow is detected
3. Check memory allocation patterns
4. Verify no crash or corruption occurs

## Mitigation Priority
**P1 - Critical**: Fix before next release
