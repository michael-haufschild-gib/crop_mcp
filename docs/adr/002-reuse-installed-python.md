# ADR-002 — Reuse a compatible installed Python

**Status** Accepted · **Decision implemented** 2026-11-19

A desktop MCP host launches a command over stdio. Its executable search path can differ from an interactive shell's, and users may already have Python and the required packages.

Use the invoking interpreter when its version and installed dependencies meet the project requirements. When the interpreter is too old, probe installed candidates. If setup needs dependencies, use a checkout-local virtual environment with the pinned constraints. Print absolute launch paths so clients can start from any working directory. Development setup installs the development tools into the checkout environment. [Bootstrap](../../bootstrap.py) · [Setup instructions](../../README.md#set-up-once)

This keeps an already compatible environment usable offline. The fallback needs a writable checkout and access to the packages for the first installation. A setup lock and an interrupted-install marker let concurrent launches share an installer and retry an incomplete installation. Installer output goes to stderr so the client retains its protocol stream. [Bootstrap tests](../../tests/test_bootstrap.py)
