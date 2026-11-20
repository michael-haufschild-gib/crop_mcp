# Python style guide

Use the existing tool signature, result types and tests as the starting point for a change. Ruff settings live in [pyproject.toml](../../pyproject.toml). The file-length check lives in [lint.sh](../../lint.sh).

## Types, names and imports

- Write runtime code for the minimum supported Python declared in the project metadata. Keep the interpreter-discovery path importable by the older Pythons listed in the README.
- Use `from __future__ import annotations` for new modules. Annotate parameters and return values. Use a `TypedDict` for structured tool results and `NotRequired` for fields that are present only when the caller requests them.
- In public signatures, keep types that `get_type_hints` resolves at runtime available in the defining module. Move type-only imports elsewhere under `TYPE_CHECKING`. See [schema generation](../../server.py).
- Group imports into standard library, third-party and local modules. Import numerical dependencies inside the operations that need them when an eager import would make every idle client pay for them.
- Use `snake_case` for modules and functions, a leading underscore for private helpers, and upper case for constants. Include units where callers could confuse them, as in `traced_edges_px` and `traced_edges_normalized`.
- Give public functions a docstring. Use Google-style `Args` and `Returns` sections to document coordinate systems, defaults, units and optional fields on public image functions. Comments should explain choices that affect the result, such as preserving integer edges on a normalized round trip.

## Boundaries and errors

| Where the code runs | Convention |
|---|---|
| Image implementation | Validate caller input explicitly. Raise `ValueError` with the offending input and a useful correction. Production checks must still run under `python -O`. |
| MCP adapter | Return the JSON result in a text content block. For errors set `isError` and serialize the message in that block. Log unexpected exceptions to stderr and keep internal exception details out of the client reply. |
| Diagnostics | Use a module logger and pass values as logging arguments. Use f-strings for user-facing messages. Keep stdout available for the protocol. |
| Dependencies | Keep transport, interpreter setup and test imports out of image code. See the [import boundary rules](../../tools/ruff.toml). |

## Image and file ownership

Use the shared validators and the session runtime when adding an image operation. A path supplied by the caller can outlive the MCP process. Session-generated files follow the retention rules in the [architecture guide](../architecture.md#process-and-file-lifetime).

Keep precision until display. For example, the contrast verdict compares the unrounded luminance ratio to the WCAG threshold. A geometry test should assert the returned source box or image pixels. The [testing guide](../testing.md#writing-a-tool-test) contains a working example.
