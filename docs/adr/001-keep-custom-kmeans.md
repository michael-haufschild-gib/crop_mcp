# ADR-001: Keep Custom k-means for Color Extraction

**Status:** Accepted
**Date:** 2026-03-17
**Deciders:** Project maintainer
**Context:** L7+ quality audit flagged the custom `_kmeans` in `tools/colors.py` as a naive choice vs. Pillow's built-in `Image.quantize()`.

## Decision

Retain the custom numpy k-means implementation. Do not replace with `Image.quantize()`.

## Context

`tools/colors.py` implements k-means clustering from scratch using numpy to extract dominant colors from images. An audit suggested replacing it with Pillow's `Image.quantize()`, which uses median-cut or octree quantization internally, is faster, and would potentially eliminate the numpy runtime dependency.

The question: is the custom implementation justified, or is it unnecessary complexity?

## Evaluation

### Option A: Replace with `Image.quantize()` (Rejected)

Pros:
- Zero custom algorithm code to maintain
- Faster (C-level implementation)
- Could theoretically remove numpy from runtime deps

Cons:
- **numpy cannot be removed.** Test suite uses `np.full`, `np.vstack`, `np.testing.assert_array_almost_equal` throughout `test_colors.py` and `test_grid.py`. Moving numpy to dev-only deps saves nothing — it's still installed in the venv.
- **Different algorithm, different results.** Median-cut partitions color space by splitting the longest axis; k-means minimizes within-cluster variance. For images with overlapping color distributions, these produce measurably different cluster centers. Existing tests assert exact hex values (`#FF0000`, `#0000FF`) against synthetic images — these would need revalidation.
- **Percentage breakdown requires extra work.** `Image.quantize()` returns a palette image. Computing per-color percentages requires counting pixels in the quantized result — roughly the same complexity as the current `_centers_to_color_list`.
- **k-means++ initialization is non-trivial.** The current implementation uses k-means++ seeding (lines 52-70) for better convergence. This is a deliberate algorithmic choice, not a naive implementation.

### Option B: Keep custom k-means (Accepted)

Pros:
- **Performance is already bounded.** Images are thumbnailed to 200x200 (`MAX_ANALYSIS_DIM`) before clustering. At 40K pixels and k=20, the distance matrix is ~18MB per iteration. Typical runtime: <30ms.
- **Well-tested.** 14 tests in `test_colors.py` cover: single color, two colors, k > unique colors, deterministic seeding, label distribution, region extraction, downsampling, percentage sums, and color entry structure.
- **Full control over output format.** The function returns `(centers, labels)` directly, which feeds cleanly into `_centers_to_color_list` for percentage computation. No intermediate palette conversion.
- **Deterministic.** Fixed seed (`rng = np.random.default_rng(42)`) ensures identical results across runs, which matters for test stability.

Cons:
- ~100 lines of algorithm code to maintain
- O(N·k) memory per iteration (bounded by thumbnail + max k=20)

## Consequences

- `tools/colors.py` retains `_kmeans` as the clustering backend.
- numpy remains a runtime dependency.
- If a future use case requires processing images without thumbnailing (e.g., pixel-accurate color mapping), the memory profile should be re-evaluated at that time.
- If numpy is ever removed from the test suite, this decision should be revisited since the primary blocker would be eliminated.
