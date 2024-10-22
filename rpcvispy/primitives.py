import numpy as np
from . import core


def scatter(
    xyz: np.ndarray,
    color: np.ndarray = None,
    key: str = None,
    parent_key: str = None,
    ti: core.TimeInfo = None,
    v: core.RPCCanvas = None,
    marker_kwargs: dict = None,
):
    """Plot or update a set n-dimensional points"""

    key = key or "_default"
    marker_kwargs = marker_kwargs or {}

    def _scatter(ctx: core.Context):
        # called in remote context
        from vispy.scene.visuals import Markers

        markers = ctx.ensure_get(
            key,
            lambda: Markers(
                parent=core.find_node(ctx.view.scene, parent_key),
                name=key,
            ),
        )

        markers.set_data(
            pos=xyz,
            edge_color=color,
            face_color=color,
            **marker_kwargs,
        )

    v = v or core.current_canvas()
    v.schedule(_scatter, ti)
