"""Tests for cleanup_temp_dir LRU eviction."""

from __future__ import annotations

import time
from pathlib import Path

from tools.validators import cleanup_temp_dir


class TestCleanupTempDir:
    """Tests for the LRU eviction utility."""

    def test_no_crash_on_nonexistent_dir(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        cleanup_temp_dir(nonexistent, max_mb=1)

    def test_no_crash_on_empty_dir(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        cleanup_temp_dir(empty_dir, max_mb=1)

    def test_under_limit_keeps_all_files(self, tmp_path: Path) -> None:
        d = tmp_path / "under"
        d.mkdir()
        for i in range(3):
            (d / f"file_{i}.txt").write_bytes(b"x" * 100)
        cleanup_temp_dir(d, max_mb=1)
        assert len(list(d.iterdir())) == 3

    def test_over_limit_evicts_oldest(self, tmp_path: Path) -> None:
        d = tmp_path / "over"
        d.mkdir()
        # Create 3 files, ~500 bytes each, total ~1500 bytes
        # Set max_mb very low so 1500 bytes exceeds it
        max_bytes = 1000
        max_mb = max_bytes / (1024 * 1024)

        oldest = d / "oldest.txt"
        oldest.write_bytes(b"x" * 500)
        # Ensure distinct mtime
        time.sleep(0.05)

        middle = d / "middle.txt"
        middle.write_bytes(b"x" * 500)
        time.sleep(0.05)

        newest = d / "newest.txt"
        newest.write_bytes(b"x" * 500)

        cleanup_temp_dir(d, max_mb=max_mb)

        remaining = {f.name for f in d.iterdir()}
        # Oldest file should have been evicted
        assert "oldest.txt" not in remaining
        # Newest file should survive
        assert "newest.txt" in remaining

    def test_evicts_down_to_half_limit(self, tmp_path: Path) -> None:
        d = tmp_path / "evict_half"
        d.mkdir()
        # 5 files, 200 bytes each = 1000 bytes total
        # Set limit to 800 bytes; target is 400 bytes
        # Should evict oldest until <= 400 bytes (keep 2 files)
        max_mb = 800 / (1024 * 1024)
        for i in range(5):
            f = d / f"file_{i:02d}.txt"
            f.write_bytes(b"x" * 200)
            time.sleep(0.05)

        cleanup_temp_dir(d, max_mb=max_mb)

        remaining = sorted(f.name for f in d.iterdir())
        assert len(remaining) == 2
        # The two newest files should survive
        assert remaining == ["file_03.txt", "file_04.txt"]

    def test_ignores_subdirectories(self, tmp_path: Path) -> None:
        d = tmp_path / "with_subdir"
        d.mkdir()
        (d / "subdir").mkdir()
        (d / "file.txt").write_bytes(b"x" * 100)
        cleanup_temp_dir(d, max_mb=0.0001)
        # Subdirectory should not be deleted (only files are cleaned)
        assert (d / "subdir").exists()
