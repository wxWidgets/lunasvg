# SEC-009: Font Loading from Arbitrary Paths

## Vulnerability Type
Information Disclosure (Low Risk)

## Severity
Low

## Location
- **File**: `source/graphics.cpp`, Lines 411-435
- **Component**: Font loading

## Description
The font loading code attempts to load fonts from hardcoded system paths:
- Windows: `C:/Windows/Fonts/`
- System font directories

While this is generally low risk, it could potentially:
1. Disclose information about file system structure
2. Be used to probe for font file existence
3. Leak information about installed fonts
4. Cause issues in sandboxed environments

## Attack Vector
Limited attack surface:
- Font loading is triggered by `font-family` attribute
- Attempts to access system font directories
- Could probe for specific font files
- May fail in sandboxed environments

## Expected Behavior

### Before Fix
- Loads fonts from hardcoded system paths
- May expose file system structure
- Works in normal environments
- May fail or cause issues in sandboxed environments

### After Fix
- Should consider font access restrictions
- Could implement font sandboxing
- Could use only embedded/safe fonts
- Should handle font loading failures gracefully

## Test Strategy
This test uses various font families to trigger font loading:
- System fonts (Arial, Times New Roman)
- Potentially non-existent fonts
- Observes font loading behavior

## Status
⚠️ **UNFIXED** - This is a minor issue in current codebase

## Related Issues
- Generally low risk in most deployments
- More relevant for sandboxed/server environments
- Similar to other file system access patterns

## Reproduction
1. Load the test SVG file with various fonts
2. Monitor file system access (strace/Process Monitor)
3. Observe font loading attempts
4. Check behavior in sandboxed environment

## Mitigation Priority
**P3 - Low**: Address in future release or as needed

## Notes
- Not a critical vulnerability for most use cases
- More of a defense-in-depth consideration
- Relevant if library used in web service/sandbox
- Consider allowing font directory configuration
- May want to restrict to specific font directories
- Handle missing fonts gracefully
