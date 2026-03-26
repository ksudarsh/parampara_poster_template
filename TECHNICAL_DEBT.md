# Technical Debt

## Rendering Performance

The current poster renderer is functional but underutilizes higher-end hardware. On machines with many CPU cores, large RAM, and a dedicated GPU, runtime still feels similar to a modest laptop because the implementation is primarily CPU-bound, mostly single-process, and does not use GPU acceleration.

### Current bottlenecks

- The rendering pipeline uses Pillow and NumPy only. It does not use CUDA or any GPU-aware rendering path.
- `render_with_auto_fit()` rerenders the full poster multiple times during binary search to find a fitting scale.
- Portrait processing work is repeated across rerenders:
  - image open/convert
  - resize
  - circular masking
  - shadow generation
  - alpha compositing
- Text layout work is repeated across rerenders:
  - caption wrapping
  - repeated `_text_size(...)` measurement calls
- A1 and A2 renders are done serially.
- Multiple selected languages are also rendered serially.

### Planned improvements

- Cache processed portraits keyed by source path and output dimensions.
- Cache text wrapping and text measurement results keyed by text/font/width.
- Reduce the number of full rerenders in `render_with_auto_fit()`:
  - use a coarser first-pass estimate
  - use fewer refinement passes
- Parallelize independent work:
  - A1 and A2 renders in separate processes
  - multiple selected languages in separate processes
- Reuse measurement helpers and avoid repeated small object creation in hot loops.

### Priority order

1. Add portrait/image-processing caches.
2. Reduce full-page rerenders in the auto-fit loop.
3. Parallelize A1/A2 and multi-language rendering.
4. Add text layout caching.

### Reminder for future changes

When making future changes to `generate_parampara_poster.py`, review this performance debt before adding more rendering work to the hot path.
