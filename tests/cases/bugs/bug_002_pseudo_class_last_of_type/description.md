# Bug 002: `:last-of-type` Pseudo-Class Infinite Loop

**Source File:** `svgparser.cpp:401`

## Description
The CSS pseudo-class `:last-of-type` selector causes an infinite loop or incorrect styling when parsing SVG style rules. This prevents proper application of styles to the last element of a given type.

## Expected Behavior
- The first rectangle should be rendered in blue
- The second (last) rectangle should be rendered in green
- The parser should correctly identify and style the last-of-type element

## Actual Behavior (Before Fix)
- Infinite loop during CSS parsing, or
- Incorrect styling application where both rectangles may appear blue
- Parser fails to properly evaluate the `:last-of-type` pseudo-class

## Test Purpose
This test verifies that the `:last-of-type` pseudo-class selector is correctly parsed and applied. After the fix, the first rectangle should display in blue while the last rectangle displays in green, demonstrating proper CSS selector functionality.

## Visual Verification
- Left rectangle: BLUE (80x80 at position 10,10)
- Right rectangle: GREEN (80x80 at position 110,10)
