# features_svg12/

SVG 1.1 feature coverage. Today only `filters/` has cases.

## filters/

Twelve hand-written filter cases covering the SVG 1.1 filter primitives that the
in-flight filter work implements: `feGaussianBlur`, `feOffset`, `feBlend`,
`feColorMatrix`, `feComposite`, `feFlood`, `feMerge`, `feMorphology`,
`feTurbulence` and lighting.

Eleven are `pass` and use the `antialiased` tolerance policy (filter output has
soft edges). `filter_morphology_erode_dilate` is `skip` because it is a
**text vector** (`<text>` glyphs under erode/dilate) and text vectors are
excluded from the golden set (plan decision 2b #9).

The prototype's sibling directories (`bidi_text`, `css_blend_modes`,
`css_media_queries`, `embedded_svg_in_image`, `letter_word_spacing`, `textpath`,
`text_decoration`, `vertical_text`) and `w3c_filters/` are empty and were not
ported.
