# Testing Vision Tools

## Running tests

Run the narrowest check that covers the changed behavior. Use the checkout's development Python so pytest, Pillow and the server subprocess use the same environment.

On macOS or Linux, run `make setup` once. To run just the crop tests from the repository root:

```sh
.vision-tools-env/bin/python -m pytest -q tests/test_crop.py
```

On Windows, prepare development dependencies and run the same test file in PowerShell:

```powershell
py -3 server.py --setup --dev
.\.vision-tools-env\Scripts\python.exe -m pytest -q tests/test_crop.py
```

| Change | Check |
|---|---|
| Coordinates, fill, transparency or palette | The affected unit module, then [cross-tool tests](../tests/test_integration.py) if another tool consumes its output. |
| A tool name, signature, default or result block | [Stdio tests](../tests/test_server.py). Inspect the schema from `tools/list` and the public `tools/call` result. |
| Interpreter discovery or installation | [Bootstrap tests](../tests/test_bootstrap.py). Check stdout, the selected executable, the install lock and interrupted setup. |
| File retention, cancellation or shutdown | [Lifecycle tests](../tests/test_cleanup.py). Use two clients with the same cache and distinct temporary directories when testing contention. |
| A test assertion rule | [Linter tests](../tests/test_lint_tests.py). Cover a bad test the rule should reject and a valid one it must accept. |
| User-visible rendering | Generate the fixtures with `make live-qa`, then run the [13-case checklist](../tests/live_qa_checklist.md) against the server being changed. |

Use `make unit-test` and `make smoke-test` for their respective pytest layers. Before a commit, `make check` runs both linters, the formatter check, strict typing, the full suite with a 90% line-coverage floor, and the 750-line file limit. The [CI workflow](../.github/workflows/ci.yml) defines the platform matrix. When hosted checks are unavailable, record the local results and the platforms exercised.

## Writing a tool test

The `synthetic_image` fixture is 200 × 100 pixels, red on the left and blue on the right. This example would fail for an off-by-one edge, an unexpected padding default applied to an explicit zero, or a crop of the wrong half.

```python
from pathlib import Path

from PIL import Image

from tools.crop import crop_image


def test_left_half_preserves_red_pixels(synthetic_image: Path) -> None:
    result = crop_image(str(synthetic_image), 0, 0, 0.5, 1, padding=0)
    assert result["crop_region_px"] == {"x1": 0, "y1": 0, "x2": 100, "y2": 100}
    with Image.open(result["output_path"]) as output:
        assert output.getcolors() == [(10_000, (255, 0, 0))]
```

For invalid arguments, check the exception and the part of the message that helps the caller. At the MCP boundary, check `isError` and the JSON message in the text block. For a preview, decode the image block and compare dimensions or selected pixels with the expected result.

The [shared fixtures](../tests/conftest.py) give each test its own runtime root. Keep source files and explicit exports in `tmp_path`. The [stdio client](../tests/stdio_client.py) starts a separate server, correlates replies by request ID and checks process exit after closing its pipe. Mark these tests `@pytest.mark.integration`.

The assertion linter rejects placeholders and standalone checks that only confirm truthiness, type or presence. To check one module, run `python scripts/lint_tests.py tests/test_crop.py` with the development Python. [Linter implementation](../scripts/lint_tests.py)

## Blind screenshot geometry

Use the blind evaluation to measure how accurately a **model using the tools** locates a target. Pixel regressions in the renderer or edge tracing have deterministic [compositor tests](../tests/test_composite_geometry.py).

With the development Python active, render all nine composites and their answer key locally:

```sh
python -m tests.composite_geometry tests/live_qa_images/single-target
```

The renderer trims the foreground, drops resampling fringes below alpha 16, pastes it onto the background, and checks its visible RGB difference against the expected half-open box. The default render density is 1. Use `--density 2` or `--fit-5k` for the other recorded sizes. [Scene definitions](../tests/geometry_art/scenes.json) · [Renderer](../tests/composite_geometry.py)

An authenticated Codex CLI with image input is required to collect new model predictions. This example starts two fresh sessions for one native-resolution scene:

```sh
python -m tests.cold_geometry --scene ruins --density 1
```

The default evaluator arms are screenshot alone and the server in this checkout. Pass `--reference-server` with the path to a frozen server script to include a comparison implementation. The model receives the same composite in each arm, with the target description and no answer key. The evaluator emits one JSON object per prediction on stdout. It records the input hash and tool calls, rounds predicted edges to source pixels and scores them against the key. [Evaluator and scorer](../tests/cold_geometry.py)

The [single-target report](benchmarks/single-target.md) records the original three-resolution experiment. The [native-height follow-up](benchmarks/native-height.md) compares four conditions at native resolution. Each report links its raw evidence. Keep new runs separately labeled with their model, server revision, inputs and scoring rule.
