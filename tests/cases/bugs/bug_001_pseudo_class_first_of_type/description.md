# Bug 001: `:first-of-type` Pseudo-Class Infinite Loop

**Source File:** `svgparser.cpp:390`

## Description
The CSS pseudo-class `:first-of-type` selector causes an infinite loop or incorrect styling when parsing SVG style rules. This prevents proper application of styles to the first element of a given type.

## Expected Behavior
- The first rectangle should be rendered in red
- The second rectangle should be rendered in blue
- The parser should correctly identify and style the first-of-type element

## Actual Behavior (Before Fix)
- Infinite loop during CSS parsing, or
- Incorrect styling application where both rectangles may appear blue
- Parser fails to properly evaluate the `:first-of-type` pseudo-class

## Test Purpose
This test verifies that the `:first-of-type` pseudo-class selector is correctly parsed and applied. After the fix, the first rectangle should display in red while the second displays in blue, demonstrating proper CSS selector functionality.

## Visual Verification
- Left rectangle: RED (80x80 at position 10,10)
- Right rectangle: BLUE (80x80 at position 110,10)
