# filter_chained_primitives

Multi-step filter chain: blur then color matrix then offset.

## What to verify
- A blue star is shown with a filtered duplicate offset from the original.
- The duplicate is blurred, hue-rotated, and shifted by the offset in sequence.
