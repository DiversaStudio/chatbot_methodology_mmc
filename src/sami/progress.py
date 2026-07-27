"""Stage progress and timing for long pipeline runs.

A full run on CPU takes tens of minutes — most of it inside two silent model
calls. Without output people conclude the process has hung and kill it, so every
stage announces itself before it starts and reports its elapsed time after.

Output goes to stderr so piping the pipeline's stdout (the manifest table) stays
clean. No new dependency.
"""
from __future__ import annotations

import sys
import time
from contextlib import contextmanager


def fmt_duration(seconds: float) -> str:
    """'42s', '4m12s', '1h03m' — always two significant units, never '252.7s'."""
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


class Progress:
    """Numbered stage reporter. `total` is used only for the [i/n] counter."""

    def __init__(self, total: int, stream=None, enabled: bool = True):
        self.total = total
        self.stream = stream if stream is not None else sys.stderr
        self.enabled = enabled
        self.n = 0
        self._t0 = time.perf_counter()

    def _write(self, text: str) -> None:
        if self.enabled:
            print(text, file=self.stream, flush=True)

    def note(self, text: str) -> None:
        """A line that is not a stage (banners, warnings, hints)."""
        self._write(text)

    @contextmanager
    def stage(self, label: str):
        """Announce a stage, then report its elapsed time on exit.

        The label is printed *before* the work so a stage that hangs is
        identifiable; on failure the elapsed line still prints, marked, so a
        traceback is attributable to a specific stage.
        """
        self.n += 1
        prefix = f"[{self.n}/{self.total}]"
        self._write(f"{prefix} {label} ...")
        t0 = time.perf_counter()
        try:
            yield
        except BaseException:
            self._write(f"{prefix} {label} FAILED after {fmt_duration(time.perf_counter() - t0)}")
            raise
        self._write(f"{prefix} {label} done in {fmt_duration(time.perf_counter() - t0)}")

    def total_elapsed(self) -> str:
        return fmt_duration(time.perf_counter() - self._t0)
