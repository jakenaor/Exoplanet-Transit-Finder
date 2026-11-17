"""Start the bundled server without recursively launching worker copies."""
#MARK: workers get first dibs
import multiprocessing as Multiprocessing

if __name__ == "__main__":
    Multiprocessing.freeze_support()

    import os as Os
    from pathlib import Path
    import signal as Signal
    import sys as Sys

    #MARK: the app bundle is not a place to put cache thingies
    Cache = Path(Os.environ.get("TRANSIT_FINDER_CACHE_DIR") or Path.home() / "Library/Caches/Exoplanet Transit Finder")
    Cache.mkdir(parents=True, exist_ok=True)
    Os.environ.setdefault("MPLCONFIGDIR", str(Cache / "matplotlib"))
    Os.environ.setdefault("NUMBA_CACHE_DIR", str(Cache / "numba"))
    for Key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "NUMBA_NUM_THREADS"):
        Os.environ.setdefault(Key, "1")
    for Stream in (Sys.stdout, Sys.stderr):
        if Stream is not None and hasattr(Stream, "reconfigure"):
            Stream.reconfigure(line_buffering=True)

    # quit from the launcher should still run the server's cleanup.
    def StopThing(Signum, Frame):
        raise KeyboardInterrupt

    Signal.signal(Signal.SIGTERM, StopThing)
    from main import RunApp
    RunApp()
