# SEC-007: Base64 Decoder Buffer Issues

## Vulnerability Type
Memory Exhaustion / Buffer Overflow

## Severity
Medium

## Location
- **File**: `plutovg/source/plutovg-surface.c`, Lines 86-149
- **Component**: Base64 decoding in data URIs

## Description
The Base64 decoder allocates memory based on input length without proper validation:
```c
output_data = malloc(length);
```

A malicious data URI can:
1. Claim a very large decoded size through crafted base64
2. Cause malloc to allocate excessive memory
3. Trigger out-of-memory condition
4. Potentially cause buffer issues if size calculation is wrong

## Attack Vector
A malicious SVG file with:
- Data URI with extremely long base64 string
- Base64 data claiming to decode to huge size
- Invalid base64 that causes size miscalculation
- Causes memory exhaustion or buffer overflow

Example:
```svg
<image href="data:image/png;base64,iVBORw0KGgoAAAANSUh[... 1MB of base64 ...]"/>
```

## Expected Behavior

### Before Fix
- Allocates memory based on untrusted input length
- Out-of-memory crash on excessive size
- Potential buffer issues
- No size validation

### After Fix
- Should validate base64 data before allocation
- Should limit maximum data URI size (suggested: 10MB)
- Should validate decoded size is reasonable
- Should handle malloc failure gracefully
- Should reject invalid base64 early

## Test Strategy
This test uses a data URI with:
- Moderately large base64 data (~50KB encoded)
- Demonstrates principle without exhausting test memory
- Real attacks could use much larger data

## Status
⚠️ **UNFIXED** - This vulnerability exists in current codebase

## Related Issues
- Related to SEC-003 (excessive allocation)
- Common issue in base64 decoders
- Affects image loading via data URIs

## Reproduction
1. Load the test SVG file with large data URI
2. Monitor memory allocation
3. Check for validation before malloc
4. Verify graceful handling of large data

## Mitigation Priority
**P2 - High**: Fix in near-term release

## Notes
- Reasonable limit: 10MB decoded data
- Should validate base64 format first
- Should check decoded size before allocation
- Most legitimate data URIs are < 1MB
- Consider streaming decoder for large valid data
