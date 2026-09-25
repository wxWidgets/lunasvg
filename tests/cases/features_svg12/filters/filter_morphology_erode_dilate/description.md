# filter_morphology_erode_dilate

feMorphology erode and dilate operators.

## What to verify
- The text "SVG" is rendered normally, then with erosion, and then with dilation.
- The eroded text has thinner strokes and the dilated text has thicker strokes.


> **Excluded from the golden set (skip).** The vector contains
> `<text>` glyphs; text vectors are excluded until lunasvg gains a
> font-file API (plan decision 2b #9). The recorded baseline was
> produced with host fonts and is not a valid golden image.

