# ADR-003 — Give each stdio session ownership of its image results

**Status** Accepted · **Decision implemented** 2026-11-19

Two clients can process large screenshots at the same time and consume each other's temporary output if they share a directory with a single eviction policy. Hosts on the same machine can also choose different temporary directories.

Keep one stdio process per client. Use the per-user cache for a shared image-work lock, and give each writing session a private result directory with its own ownership lock. Hold the image-work lock through decoding, saving and preview encoding. Contrast requests can proceed independently. [Runtime](../../tools/runtime.py) · [Process and file lifetime](../architecture.md#process-and-file-lifetime)

An active session retains complete result sets within its own quota. Normal shutdown removes them. After a process dies, another server using the same cache can reclaim its files once the OS releases the ownership lock. An explicit export is staged on the destination volume and published by atomic replacement. Its recovery record identifies the staging file even if the writing process is killed. The trade-off is that another image request can wait or receive a retryable busy error while the shared slot is occupied. [Parallel host and crash recovery tests](../../tests/test_cleanup.py)
