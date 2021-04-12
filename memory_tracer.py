import gc
import logging
import tracemalloc

L = logging.getLogger(__name__)


class MemoryTracer:
    """
    Usage:
        with MemoryTracer() as mt:
            <some code>
            mt.update()
            <other code>
            mt.update()
            ...
    """

    def __init__(self, top=20, trace=1, nframe=25, gccollect=True, log=None, disabled=False):
        """Init the memory tracer.

        Args:
            top (int): Limit the number of lines when printing the statistics.
            trace (int): Limit the number of printed tracebacks.
            nframe (int): Collected tracebacks of traces will be limited to nframe frames.
            gccollect (bool): True to execute gc.collect() before taking each snapshot.
            log: logger function to be used to to print the information.
            disabled (bool): True to disable the tracer to temporarily turn off the debugging.
        """
        self.top = top
        self.trace = trace
        self.nframe = nframe
        self.gccollect = gccollect
        self.log = log or L.info
        self.disabled = disabled
        self._start = None  # starting snapshot
        self._prev = None  # last saved snapshot

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        if self.disabled:
            return self
        if tracemalloc.is_tracing():
            raise RuntimeError("Cannot start to trace when already tracing")
        self.log("Starting memory tracer")
        tracemalloc.start(self.nframe)
        self._start = tracemalloc.take_snapshot()
        self._prev = self._start

    def stop(self):
        if self.disabled:
            return
        self._start = None
        self._prev = None
        tracemalloc.stop()
        self.log("Stopped memory tracer")

    def _format_stats(self, stats):
        return "\n".join(f"{i:-2}: {s}" for i, s in enumerate(stats, 1))

    def update(self):
        if self.disabled:
            return
        if self.gccollect:
            gc.collect()
        current = tracemalloc.take_snapshot()

        # compare the current snapshot to the starting snapshot
        cumulative_stats = current.compare_to(self._start, "filename")
        # compare the current snapshot to the previous snapshot
        incremental_stats = current.compare_to(self._prev, "lineno")

        lines = self._format_stats(cumulative_stats[: self.top])
        self.log("Top cumulative stats since start:\n%s", lines)

        lines = self._format_stats(incremental_stats[: self.top])
        self.log("Top incremental stats since previous:\n%s", lines)

        lines = self._format_stats(current.statistics("filename")[: self.top])
        self.log("Top current stats:\n%s", lines)

        # get traceback for the current snapshot
        traces = current.statistics("traceback")
        for stat in traces[: self.trace]:
            lines = "\n".join(stat.traceback.format())
            self.log("memory_blocks=%s size_KiB=%.1f\n%s", stat.count, stat.size / 1024, lines)

        # set previous snapshot to current snapshot
        self._prev = current
