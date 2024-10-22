import logging
import multiprocessing as mp
import sched
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import InitVar, dataclass
from functools import partial
from queue import Empty, Full, Queue
from types import SimpleNamespace
from typing import Callable

from dill import dumps, loads
from vispy import app, scene

ContextFn = Callable[["Context"], None]

__all__ = [
    "Context",
    "TimeInfo",
    "schedule_fn",
    "RPCCanvas",
    "switch_canvas",
    "current_canvas",
    "close_all",
    "dt",
    "find_node",
]

_all_vis: list["RPCCanvas"] = []
_the_vis: "RPCCanvas" = None

_logger = logging.getLogger("rpcvispy")


class Context(SimpleNamespace):
    """Dict-like storage that supports dot syntax"""

    def __setitem__(self, key, value):
        self.__dict__.update({key: value})

    def __getitem__(self, key):
        return self.__dict__[key]

    def __contains__(self, item):
        return item in self.__dict__

    def ensure_get(self, key: str, create_fn):
        obj = None
        if key is None:
            obj = create_fn()
        elif key not in self:
            obj = create_fn()
            self[key] = obj
        else:
            obj = self[key]
        return obj


@dataclass
class TimeInfo:
    """Defines presentation time properties"""

    created: float | None = None
    pts: float | None = None
    max_queue_time: float = 1.0
    dt: InitVar[float | None] = None

    def __post_init__(self, dt):
        if self.created is None:
            self.created = time.perf_counter()
        if self.pts is None:
            self.pts = self.created

        if dt is not None:
            self.pts += dt


def dt(delta: float, **kwargs) -> TimeInfo:
    """Returns time-info for now+dt"""
    return TimeInfo(dt=delta, **kwargs)


def schedule_fn(queue: Queue, fn: ContextFn, ti: TimeInfo = None):
    """Schedule a draw function on the remote"""
    ti = ti or TimeInfo()
    try:
        queue.put((ti, dumps(fn)), timeout=ti.max_queue_time)
    except Full:
        _logger.warning("Queue full")


def _default_setup(ctx: Context, **kwargs):
    """Default canvas setup function"""
    canvas_kwargs = dict(show=True, keys="interactive")
    canvas_kwargs.update(kwargs)
    ctx.canvas = scene.SceneCanvas(**canvas_kwargs)
    ctx.view = ctx.canvas.central_widget.add_view()
    ctx.view.camera = kwargs.get("camera", "arcball")


def find_node(root: scene.Node, name: str):
    """Find node by key in scene graph."""
    if name is None:
        return root

    stack = deque()
    while len(stack) > 0:
        n = stack.popleft()
        if n.name is not None and n.name == name:
            return n
        for child in enumerate(n.children):
            stack.append(child)

    return None


def _worker(inq: Queue, **worker_kwargs):
    """Actual worker function running in separate process"""
    ctx = Context()
    ctx.rv = Context()
    ctx.rv.queue = inq
    ctx.rv.logger = logging.getLogger(
        f"rpcvispy.{mp.current_process().name}-{mp.current_process().ident}"
    )
    ctx.rv.scheduler = sched.scheduler(time.perf_counter, time.sleep)

    def process_closure(bytes):
        rpc = loads(bytes)
        rpc(ctx)

    def pop_queue(now: float):
        """Pops from queue and skips timeout elements"""
        n = 100
        try:
            while n > 0:
                t, code_bytes = inq.get_nowait()
                n = -1 if (now - t.created) <= t.max_queue_time else n - 1
            if n >= 0 and n < 100:
                ctx.rv.logger.info(f"Outdated more {100-n} elements")
            return t, code_bytes
        except Empty:
            pass
        return None

    def update(ev):
        """Update loop called by timer"""
        ctx.rv.dt = ev.dt
        ctx.rv.now = time.perf_counter()

        # read from queue
        read_tuple = pop_queue(ctx.rv.now)

        if read_tuple is not None:
            t, code_bytes = read_tuple
            if t.pts <= ctx.rv.now:
                # Drawing should already have happened
                process_closure(code_bytes)
            else:
                # Draw later (note: separate queue)
                ctx.rv.scheduler.enterabs(
                    t.pts, 1, process_closure, argument=(code_bytes,)
                )

        # Update scheduler for later draws
        ctx.rv.scheduler.run(blocking=False)

    # Call setup code
    _, bytes = inq.get(timeout=1.0)
    process_closure(bytes)

    # Link timer
    ctx.rv.timer = app.Timer(interval=1 / worker_kwargs.pop("fps", 60), start=False)
    ctx.rv.timer.connect(update)
    ctx.rv.timer.start()

    app.run()


class RPCCanvas:
    """Shallow interace for a remote vispy canvas."""

    def __init__(
        self,
        queue_size: int = 100,
        setup_fn: ContextFn = None,
        setup_kwargs=None,
        **worker_kwargs,
    ):
        self.queue = mp.Queue(maxsize=queue_size)
        if setup_fn is None:
            setup_kwargs = setup_kwargs or {}
            setup_fn = partial(_default_setup, **setup_kwargs)

        self.schedule(setup_fn)
        proc = mp.Process(
            target=_worker,
            name=worker_kwargs.get("name", "RPCCanvas"),
            args=(self.queue,),
            kwargs=worker_kwargs,
            daemon=False,
        )
        proc.start()
        _all_vis.append(self)

    @property
    def done(self):
        return len(self.queue) == 0

    def close(self):
        def _close(ctx):
            app.quit()

        self.schedule(_close, TimeInfo(max_queue_time=float("inf")))

    def schedule(self, closure: ContextFn, ti: TimeInfo = None):
        schedule_fn(self.queue, closure, ti)


@contextmanager
def switch_canvas(vis: RPCCanvas = None):
    """Context manager to switch default visualizer"""
    global _the_vis
    vis = vis or RPCCanvas()
    try:
        old = _the_vis
        _the_vis = vis
        yield vis
    finally:
        _the_vis = old


def current_canvas():
    """Lazy instantiate default visualizer"""
    global _the_vis
    if _the_vis is None:
        _the_vis = RPCCanvas()
    return _the_vis


def close_all():
    [v.close() for v in _all_vis]
