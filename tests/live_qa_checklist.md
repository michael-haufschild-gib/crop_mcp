# Live QA Checklist — Vision Tools MCP

Manual QA procedure for testing MCP tools from the AI consumer's perspective.
Run `make live-qa` first to generate test images.

Images are in `tests/live_qa_images/` (gitignored).

---

## Setup

```
make live-qa
```

Verify 3 images exist:
- `quadrants_400x400.png` — 4 solid-color quadrants
- `color_bars_600x100.png` — 6 vertical color stripes
- `large_markers_2000x1000.png` — white with 3 red marker squares

---

## Test 1: Grid overlay on quadrants

**Tool**: `get_image_coordinates_grid`
**Input**: `image_path` = absolute path to `quadrants_400x400.png`

**Expected result fields**:
- `width` = 400, `height` = 400
- `aspect_ratio` = 1.0
- `mode` = "RGB"
- `longer_axis` = "x" (square → x by convention)
- `grid_image` = path to a readable grid overlay PNG

**Visual check**: Read the `grid_image`. Confirm:
- Gridlines labeled `.1` through `.9` on both axes
- `.5` gridline bisects each axis (separating the 4 color quadrants)
- Labels are readable against the colored background

**Pass criteria**: All fields correct AND grid overlay is visually interpretable.

---

## Test 2: Crop top-left quadrant

**Tool**: `crop_to_magnify_image`
**Input**: `image_path` = `quadrants_400x400.png`, `x1=0, y1=0, x2=0.5, y2=0.5`, `padding=0`

**Expected result fields**:
- `source_width` = 400, `source_height` = 400
- `width` = 200, `height` = 200
- `crop_region_normalized` ≈ `{x1: 0.0, y1: 0.0, x2: 0.5, y2: 0.5}`
- `output_path` = path to cropped PNG

**Visual check**: Read the output image. It should be entirely red (#FF0000).

**Pass criteria**: Dimensions correct AND output is solid red.

---

## Test 3: Extract colors from crop output

**Tool**: `extract_colors`
**Input**: `image_path` = output_path from Test 2, `n_colors=1`

**Expected result fields**:
- `colors[0].hex` = "#FF0000" (or very close)
- `colors[0].rgb` = [255, 0, 0]
- `colors[0].percentage` ≈ 100.0

**Pass criteria**: Single dominant color is red.

---

## Test 4: Extract colors from full quadrants image

**Tool**: `extract_colors`
**Input**: `image_path` = `quadrants_400x400.png`, `n_colors=4`

**Expected result fields**:
- 4 colors returned
- Each ≈ 25% of image
- Hex values present (any order): `#FF0000`, `#00FF00`, `#0000FF`, `#FFFF00`

**Pass criteria**: All 4 quadrant colors detected, each near 25%.

---

## Test 5: Region-scoped color extraction

**Tool**: `extract_colors`
**Input**: `image_path` = `quadrants_400x400.png`, `n_colors=1`, `x1=0.5, y1=0.5, x2=1.0, y2=1.0`

**Expected result fields**:
- `colors[0].hex` = "#FFFF00" (or very close)
- `region_analyzed` indicates a sub-region, not "full image"

**Pass criteria**: Dominant color of bottom-right quadrant is yellow.

---

## Test 6: Color bars — multi-color extraction

**Tool**: `extract_colors`
**Input**: `image_path` = `color_bars_600x100.png`, `n_colors=6`

**Expected result fields**:
- 6 colors returned
- Expected hex values (any order): `#FF0000`, `#FF8000`, `#FFFF00`, `#008000`, `#0000FF`, `#8000FF`
- Each ≈ 16.7% of image

**Pass criteria**: All 6 bar colors detected with roughly equal percentages.

---

## Test 7: Check contrast — maximum contrast

**Tool**: `check_contrast`
**Input**: `foreground="#FFFFFF"`, `background="#000000"`

**Expected result fields**:
- `contrast_ratio` = 21.0
- `wcag_aa` = true
- `wcag_aaa` = true
- `foreground.hex` = "#FFFFFF", `foreground.rgb` = [255, 255, 255]
- `background.hex` = "#000000", `background.rgb` = [0, 0, 0]

**Pass criteria**: Ratio exactly 21.0, both AA and AAA pass.

---

## Test 8: Check contrast — failing pair

**Tool**: `check_contrast`
**Input**: `foreground="#777777"`, `background="#999999"`

**Expected result fields**:
- `contrast_ratio` < 3.0
- `wcag_aa` = false
- `wcag_aaa` = false

**Pass criteria**: Low contrast ratio, both AA and AAA fail.

---

## Test 9: Grid overlay on large image

**Tool**: `get_image_coordinates_grid`
**Input**: `image_path` = absolute path to `large_markers_2000x1000.png`

**Expected result fields**:
- `width` = 2000, `height` = 1000
- `aspect_ratio` = 2.0
- `longer_axis` = "x"
- `pixels_per_percent.x` = 20.0, `pixels_per_percent.y` = 10.0

**Visual check**: Read the `grid_image`. Confirm:
- Gridlines labeled `.1` through `.9`
- Red marker square visible near intersection of `.5`/`.5` gridlines (center)
- Two other markers visible near `.25`/`.25` and `.75`/`.75`
- Labels readable against white background

**Pass criteria**: All fields correct AND markers visible at expected grid positions.

---

## Test 10: Crop a marker from large image

**Tool**: `crop_to_magnify_image`
**Input**: `image_path` = `large_markers_2000x1000.png`, `x1=0.23, y1=0.23, x2=0.27, y2=0.27`, `padding=10`

**Expected result fields**:
- `output_path` = path to cropped PNG
- Crop region covers the top-left-quarter marker

**Visual check**: Read the output image. A red square should be visible against white background.

**Follow-up**: `extract_colors` on the crop with `n_colors=2`.
- Should return #FF0000 (red marker) and #FFFFFF (white background).

**Pass criteria**: Red marker visible in crop AND colors extracted correctly.

---

## Test 11: Pipeline chain — grid → crop → colors

Full workflow test combining all image tools.

1. Call `get_image_coordinates_grid` on `quadrants_400x400.png`.
2. Read the grid overlay image to identify where the green quadrant is.
3. Based on the grid, crop the green region (should be top-right: ~0.5,0,1.0,0.5).
4. Extract colors from the crop.
5. Verify the dominant color is #00FF00 (green).

**Pass criteria**: Correct color identified by following the grid → crop → colors workflow without prior knowledge of the quadrant layout.

---

## Test 12: Error handling — invalid path

**Tool**: `crop_to_magnify_image`
**Input**: `image_path="/tmp/nonexistent_abc123.png"`, `x1=0, y1=0, x2=1, y2=1`

**Expected**: Result contains `"error"` key with a message about the file not existing.

**Pass criteria**: Error returned gracefully, no server crash.

---

## Test 13: Error handling — invalid coordinates

**Tool**: `crop_to_magnify_image`
**Input**: `image_path` = `quadrants_400x400.png`, `x1=0.8, y1=0, x2=0.2, y2=1` (x1 > x2)

**Expected**: Result contains `"error"` key about invalid coordinates.

**Pass criteria**: Error returned gracefully with helpful message.

---

## Scoring

| Result | Meaning |
|-|-|
| 13/13 pass | All tools working correctly from AI consumer perspective |
| 11-12/13 | Minor issues — investigate failures |
| < 11/13 | Significant issues — fix before release |
