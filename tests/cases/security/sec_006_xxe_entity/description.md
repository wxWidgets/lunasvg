# SEC-006: XML Entity Expansion (XXE)

## Vulnerability Type
XML External Entity (XXE) Attack / Information Disclosure / Denial of Service

## Severity
Medium-High

## Location
- **File**: `source/svgparser.cpp`, Lines 959-1005
- **Component**: XML DOCTYPE parsing

## Description
The parser may accept XML DOCTYPE declarations with external entities or entity expansion. This enables:
1. **XXE Attack**: Reading local files via external entity references
2. **Billion Laughs Attack**: Exponential entity expansion causing memory exhaustion
3. **SSRF**: Server-Side Request Forgery if external URLs are resolved

## Attack Vectors

### XXE (External Entity)
```xml
<!DOCTYPE svg [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<svg><text>&xxe;</text></svg>
```

### Billion Laughs (Entity Expansion)
```xml
<!DOCTYPE svg [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
<svg><text>&lol4;</text></svg>
```

## Expected Behavior

### Before Fix
- May resolve external entities
- May perform unbounded entity expansion
- May read local filesystem
- Memory exhaustion on billion laughs

### After Fix
- Should reject DOCTYPE with external entities
- Should disable external entity resolution entirely
- Should limit entity expansion depth (max 10 levels)
- Should limit entity expansion size (max 1MB)
- Should return parsing error for malicious DOCTYPE

## Test Strategy
This test includes:
- External entity reference (file:///etc/passwd on Linux, C:\Windows\win.ini on Windows)
- Entity expansion (simplified billion laughs)
- Should trigger XXE protection

## Status
⚠️ **UNFIXED** - This vulnerability may exist in current codebase

## Related Issues
- Classic XML security issue (OWASP Top 10)
- CVE-2013-1664 (Python), CVE-2017-5662 (Batik), etc.
- Requires XML parser configuration changes

## Reproduction
1. Load the test SVG file with XXE DOCTYPE
2. Check if external file is accessed
3. Monitor file system access (e.g., strace/Process Monitor)
4. Verify rejection of external entities

## Mitigation Priority
**P1 - Critical**: Fix before next release

## Notes
- Best practice: Disable DOCTYPE entirely for SVG
- Alternative: Disable external entity resolution
- Entity expansion limit: 10 levels, 1MB total
- Modern parsers (libxml2, expat) have config options
