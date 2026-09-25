# filters/composite_ops

`feComposite` Porter-Duff operators (`over`, `in`, `out`, `atop`, `xor`) plus
`arithmetic`, each compositing the source graphic with a red `feFlood`.

> **Excluded from the golden set (skip).** The vector contains `<text>` labels;
> text vectors are excluded until lunasvg gains a font-file API (plan decision 2b #9).
