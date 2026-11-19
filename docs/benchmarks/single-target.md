# Screenshot position and size accuracy

2026-11-19 · Codex CLI 0.167.1 · `gpt-6.2-astra` · medium reasoning effort.

At 2×, the updated MCP matched all six held-out targets exactly. Across all nine targets the mean absolute edge error was 1.42 pixels unaided, 0.61 with the previous MCP and 0.06 with the updated MCP. Native resolution remained harder for the updated MCP. It underestimated the key’s height by five pixels and the drone’s by eight.

Each prediction came from a fresh Codex session given one target description and one full composite PNG. The model never saw the standalone foreground, pristine background, placement coordinates or answer key. Each pair used identical PNG bytes. The reference server used the previous fourfold zoom with normalized lines and labels drawn on the crop. The updated server puts original pixel and normalized rulers in the margins and magnifies tight crops up to eightfold.

Passing requires every edge to fall within two source pixels of the visible target. The position-and-size column applies the same two-pixel tolerance to x, y, width and height separately. Opposite edge errors can accumulate in a dimension. Exact requires all four edges to match. X and Y are the top-left corner. All error columns below are mean absolute errors in source pixels except “Worst edge”, which is the largest absolute error across that row. Width and height are differences between the rounded edges.

## All nine scenes

| Density | Condition | Edges within 2 px | Position and size within 2 px | Exact | X | Y | Width | Height | Edge | Worst edge |
|---|---|---|---|---|---|---|---|---|---|---|
| 2× | Screenshot alone | 7/9 | 4/9 | 0/9 | 0.89 | 2.89 | 1.78 | 3.67 | 1.42 | 16 |
| 2× | Previous MCP | 8/9 | 8/9 | 7/9 | 0.11 | 1.89 | 0.33 | 2.11 | 0.61 | 17 |
| 2× | Updated MCP | 9/9 | 9/9 | 8/9 | 0.11 | 0.00 | 0.11 | 0.11 | 0.06 | 1 |
| 1× | Screenshot alone | 6/9 | 6/9 | 2/9 | 0.56 | 1.78 | 1.00 | 2.33 | 0.83 | 7 |
| 1× | Updated MCP | 7/9 | 7/9 | 6/9 | 0.11 | 1.44 | 0.22 | 1.56 | 0.44 | 8 |
| 5K fit | Screenshot alone | 5/9 | 3/9 | 0/9 | 1.44 | 4.00 | 2.44 | 4.89 | 2.00 | 23 |
| 5K fit | Updated MCP | 9/9 | 9/9 | 6/9 | 0.44 | 0.00 | 0.22 | 0.00 | 0.17 | 2 |

The 1× images use the generated backgrounds at their original resolution. The 2× condition resizes each background and places a freshly rasterized foreground at twice the coordinates and width. The supplemental 5K condition scales the same assets to fit inside 5120 × 2880 pixels, preserving aspect ratio. It was added after the 2× result. All nine placements, the model, the prompts and the two-pixel thresholds were kept fixed. Each condition has one prediction per scene. Small differences between individual runs can reflect model variability.

## Held-out scenes

The railway ticket, RPG key and eyedropper were used during development. The other six scenes were held out until the update was in place.

| Density | Condition | Edges within 2 px | Position and size within 2 px | Exact | X | Y | Width | Height | Edge | Worst edge |
|---|---|---|---|---|---|---|---|---|---|---|
| 2× | Screenshot alone | 5/6 | 3/6 | 0/6 | 1.17 | 2.83 | 2.17 | 3.33 | 1.46 | 16 |
| 2× | Previous MCP | 5/6 | 5/6 | 5/6 | 0.00 | 2.83 | 0.17 | 3.00 | 0.79 | 17 |
| 2× | Updated MCP | 6/6 | 6/6 | 6/6 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0 |
| 1× | Screenshot alone | 4/6 | 4/6 | 2/6 | 0.33 | 2.00 | 0.67 | 2.33 | 0.75 | 7 |
| 1× | Updated MCP | 5/6 | 5/6 | 4/6 | 0.00 | 1.50 | 0.00 | 1.50 | 0.38 | 8 |
| 5K fit | Screenshot alone | 3/6 | 2/6 | 0/6 | 1.67 | 4.33 | 2.83 | 5.17 | 2.25 | 23 |
| 5K fit | Updated MCP | 6/6 | 6/6 | 5/6 | 0.33 | 0.00 | 0.00 | 0.00 | 0.17 | 2 |

## Results by target

Each tuple is the signed error in (x, y, width, height), in pixels. Positive numbers mean farther right, farther down, wider, or taller.

### 2× screenshots

| Target | True (x, y, width, height) | Screenshot alone | Previous MCP | Updated MCP |
|---|---|---|---|---|
| illustrated Mountain Pass railway ticket | (148, 848, 302, 72) | (0, -1, 0, 2) | (0, 0, 0, 0) | (0, 0, 0, 0) |
| dropped brass skeleton key on the stone ground, including the teeth and bow | (1442, 1252, 164, 126) | (0, 7, 0, -8) | (1, 0, -2, -1) | (1, 0, -1, -1) |
| entire eyedropper cursor over the photograph, from bulb to tip | (1914, 1074, 78, 85) | (-1, -1, 3, 3) | (0, 0, 0, 0) | (0, 0, 0, 0) |
| open brass compass next to the backpack, including its hinged lid | (1686, 956, 148, 175) | (-1, -1, 2, 2) | (0, 0, 0, 0) | (0, 0, 0, 0) |
| orange maintenance drone in the hangar, including its rotor guards | (2062, 704, 234, 149) | (-1, 16, 3, -15) | (0, 17, 1, -18) | (0, 0, 0, 0) |
| italic Col des Aiguilles map label, including its narrow lettering outline | (2096, 722, 256, 44) | (-2, 0, 2, 0) | (0, 0, 0, 0) | (0, 0, 0, 0) |
| red Chef’s pick menu stamp, including its oval border | (1010, 2580, 224, 115) | (-2, 0, 3, 1) | (0, 0, 0, 0) | (0, 0, 0, 0) |
| pale green luna moth above the bridge, including its antennae and wing tails | (1180, 710, 126, 95) | (-1, 0, 3, 1) | (0, 0, 0, 0) | (0, 0, 0, 0) |
| yellow roadside course marshal flag, including the pole | (1568, 606, 84, 90) | (0, 0, 0, -1) | (0, 0, 0, 0) | (0, 0, 0, 0) |

### 1× screenshots

| Target | True (x, y, width, height) | Screenshot alone | Updated MCP |
|---|---|---|---|
| illustrated Mountain Pass railway ticket | (74, 424, 151, 36) | (1, 0, -1, 1) | (0, 0, 0, 0) |
| dropped brass skeleton key on the stone ground, including the teeth and bow | (721, 626, 82, 63) | (-2, 4, 3, -6) | (1, 4, -2, -5) |
| entire eyedropper cursor over the photograph, from bulb to tip | (957, 537, 39, 42) | (0, 0, 1, 0) | (0, 0, 0, 0) |
| open brass compass next to the backpack, including its hinged lid | (843, 478, 74, 87) | (-1, 0, 2, 1) | (0, 0, 0, 0) |
| orange maintenance drone in the hangar, including its rotor guards | (1031, 352, 117, 75) | (0, 7, 1, -7) | (0, 8, 0, -8) |
| italic Col des Aiguilles map label, including its narrow lettering outline | (1048, 361, 128, 22) | (-1, -1, 1, 2) | (0, 0, 0, 0) |
| red Chef’s pick menu stamp, including its oval border | (505, 1290, 112, 58) | (0, 0, 0, 0) | (0, 0, 0, 0) |
| pale green luna moth above the bridge, including its antennae and wing tails | (590, 355, 63, 48) | (0, -4, 0, 4) | (0, 0, 0, 0) |
| yellow roadside course marshal flag, including the pole | (784, 303, 42, 45) | (0, 0, 0, 0) | (0, -1, 0, 1) |

### 5K fit screenshots

| Target | True (x, y, width, height) | Screenshot alone | Updated MCP |
|---|---|---|---|
| illustrated Mountain Pass railway ticket | (212, 1217, 434, 103) | (0, -1, 0, 3) | (1, 0, -1, 0) |
| dropped brass skeleton key on the stone ground, including the teeth and bow | (2093, 1817, 238, 182) | (-2, 8, 3, -9) | (1, 0, -1, 0) |
| entire eyedropper cursor over the photograph, from bulb to tip | (2778, 1559, 113, 123) | (-1, -1, 2, 1) | (0, 0, 0, 0) |
| open brass compass next to the backpack, including its hinged lid | (2447, 1388, 215, 254) | (-3, -1, 5, 2) | (0, 0, 0, 0) |
| orange maintenance drone in the hangar, including its rotor guards | (2993, 1022, 340, 217) | (-2, 23, 4, -23) | (0, 0, 0, 0) |
| italic Col des Aiguilles map label, including its narrow lettering outline | (3043, 1048, 372, 63) | (-1, 0, 0, -1) | (-2, 0, 0, 0) |
| red Chef’s pick menu stamp, including its oval border | (820, 2094, 182, 94) | (-2, 0, 3, 0) | (0, 0, 0, 0) |
| pale green luna moth above the bridge, including its antennae and wing tails | (1806, 1087, 193, 146) | (-2, 2, 4, 4) | (0, 0, 0, 0) |
| yellow roadside course marshal flag, including the pole | (2399, 927, 129, 139) | (0, 0, 1, 1) | (0, 0, 0, 0) |

The [raw predictions and tool calls](single-target.jsonl) include each input hash, expected and predicted bounds, and signed edge errors. The [rendering and scoring procedure](../testing.md#blind-screenshot-geometry) and [scene definitions](../../tests/geometry_art/scenes.json) reproduce the inputs.
