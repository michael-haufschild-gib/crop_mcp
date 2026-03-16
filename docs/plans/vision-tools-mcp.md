# Plan: Vision Tools MCP Server

## Goal

A standalone MCP server that gives Claude Code image manipulation tools across all projects. Two tools at launch: `crop_image` (zoom into a screenshot region) and `extract_colors` (get exact hex values from an image region).

## Why

1. **Crop** is proven useful. The ui-review skill uses it heavily for screenshot analysis. But outside that skill, Claude has no way to zoom into image regions — useful during prototyping, agent-browser inspection, copying designs from reference screenshots.

2. **Color extraction** solves a known hallucination problem. Claude cannot reliably report hex color values from visual inspection alone. When copying a website's design into a prototype, exact CSS colors are needed. A tool that returns computed hex values eliminates guesswork.

## Scope

### In scope
- Python MCP server with stdio transport
- Two tools: `crop_image`, `extract_colors`
- Runs on a dedicated virtualenv with Pillow and numpy
- Global Claude Code configuration via `~/.claude/settings.json`
- Setup script for venv creation and dependency installation
- Tool descriptions written with prompt-write principles for optimal Claude tool selection

### Out of scope
- Changes to the ui-review skill (it keeps its own crop.py via Bash)
- Network transport, authentication, or multi-user concerns
- Image generation, annotation, OCR, or diffing tools (may be added later if needed)
- GUI or web interface

## Architecture

```
vision-tools-mcp/
  server.py          — MCP server entry point
  tools/
    crop.py          — crop_image implementation
    colors.py        — extract_colors implementation
  setup.sh           — venv creation + dependency install
  CLAUDE.md          — project instructions
  README.md          — usage and configuration docs
```

### Runtime

- **Transport:** stdio (Claude Code manages the subprocess lifecycle)
- **Python:** 3.9+ (same minimum as ui-review)
- **Venv:** `~/.vision-tools-env/` (separate from ui-review's venv — independent project, independent environment)
- **Dependencies:** `mcp` (MCP SDK), `Pillow` (image processing), `numpy` (color clustering)

### Configuration

Added to `~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "vision-tools": {
      "command": "/Users/Spare/.vision-tools-env/bin/python3",
      "args": ["/path/to/vision-tools-mcp/server.py"]
    }
  }
}
```

## Tool Specifications

### crop_image

**Purpose:** Crop a region from an image using normalized 0-1 coordinates. Returns the path to the saved crop.

**Parameters:**

| Name | Type | Required | Description |
|-|-|-|-|
| image_path | string | yes | Absolute path to the source image |
| x1 | number | yes | Left edge (0.0 = left, 1.0 = right) |
| y1 | number | yes | Top edge (0.0 = top, 1.0 = bottom) |
| x2 | number | yes | Right edge |
| y2 | number | yes | Bottom edge |
| output_path | string | no | Where to save the crop. Default: `{image_dir}/crop_{x1}_{y1}.png` |
| padding | integer | no | Extra pixels around the crop region. Default: 20 |

**Coordinate system:** Normalized 0-1 where (0,0) is top-left and (1,1) is bottom-right. Claude estimates relative positions naturally: "bottom quarter" ≈ y1=0.75, "center" ≈ 0.5.

**Returns:** `{ "output_path": "/path/to/crop.png", "width": 340, "height": 280 }`

**Validation:**
- All coordinates must be 0.0-1.0
- x1 < x2, y1 < y2
- image_path must exist and be a readable image

**Implementation:** Wraps the same logic as ui-review's crop.py — open with Pillow, convert normalized coords to pixels, apply padding clamped to image bounds, save as PNG.

### extract_colors

**Purpose:** Extract dominant colors from an image or image region as hex values. Solves the problem of Claude hallucinating color values when reading screenshots.

**Parameters:**

| Name | Type | Required | Description |
|-|-|-|-|
| image_path | string | yes | Absolute path to the source image |
| n_colors | integer | no | Number of dominant colors to extract. Default: 6 |
| x1 | number | no | Left edge of region (0-1). Omit all four to analyze the full image. |
| y1 | number | no | Top edge of region (0-1) |
| x2 | number | no | Right edge of region (0-1) |
| y2 | number | no | Bottom edge of region (0-1) |

**Returns:**
```json
{
  "colors": [
    { "hex": "#1A1A2E", "percentage": 42.3, "rgb": [26, 26, 46] },
    { "hex": "#E94560", "percentage": 18.7, "rgb": [233, 69, 96] },
    { "hex": "#FFFFFF", "percentage": 15.1, "rgb": [255, 255, 255] }
  ],
  "image_size": [1440, 900],
  "region_analyzed": "full image"
}
```

**Implementation:**
1. Open image with Pillow, crop to region if specified
2. Downsample to max 200x200 for performance (color clustering doesn't need full resolution)
3. Reshape pixels to (N, 3) array
4. K-means clustering with numpy (n_clusters = n_colors)
5. Sort clusters by pixel count descending
6. Return hex values with coverage percentages

**No scipy/sklearn dependency.** K-means can be implemented in ~30 lines of pure numpy. The dataset (200x200 = 40K pixels, 3 dimensions, 6 clusters) converges in <100ms.

## Implementation Steps

### 1. Project setup
- Initialize git repo
- Create directory structure
- Write CLAUDE.md with project instructions
- Write setup.sh for venv + dependencies

### 2. Implement crop_image tool
- Port logic from ui-review's crop.py (normalized coords, padding, validation)
- Wrap as MCP tool with proper schema and description
- Test with sample images

### 3. Implement extract_colors tool
- Write numpy k-means clustering (no sklearn dependency)
- Region support using the same normalized coordinate system as crop
- Test against known images with verifiable colors

### 4. MCP server integration
- Wire tools into MCP server using `mcp` Python package
- Stdio transport
- Error handling: return structured errors, never crash the server

### 5. Tool descriptions
- Use prompt-write skill to write tool descriptions that optimize Claude's tool selection
- Description must make clear WHEN to use each tool (crop: zoom into regions; colors: extract exact hex values)

### 6. Global configuration
- Add to `~/.claude/settings.json`
- Verify tools appear in Claude Code tool list
- Test both tools from a non-ui-review project

### 7. Documentation
- README.md: installation, configuration, usage examples
- Verify setup.sh works on clean system

## Testing

- **crop_image:** Crop known regions from a test image, verify output dimensions and content
- **extract_colors:** Extract colors from solid-color test images (red square → should return #FF0000), then from real screenshots (verify hex values match what Photoshop/browser devtools report)
- **Integration:** Start server via Claude Code, call both tools, verify structured output

## Future Expansion

Tools that may be added if proven useful (not in v1):

- **measure_region** — return pixel dimensions of a region (width, height, aspect ratio)
- **compare_images** — pixel-diff two screenshots, highlight changes
- **contrast_check** — WCAG contrast ratio between two hex colors or sampled from image regions
- **resize_image** — resize/optimize for different contexts

Each should only be added when there's a concrete, repeated use case — not speculatively.
