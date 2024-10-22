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


def xyz_axis(
    scale: float = 1.0,
    key: str = None,
    parent_key: str = None,
    ti: core.TimeInfo = None,
    v: core.RPCCanvas = None,
):
    """Set XYZ indication"""

    def _axis(ctx: core.Context):
        # called in remote context
        from vispy.scene.visuals import XYZAxis
        from vispy.scene import MatrixTransform

        axis = ctx.ensure_get(
            key,
            lambda: XYZAxis(
                parent=core.find_node(ctx.view.scene, parent_key),
                name=key,
            ),
        )
        axis.transform = MatrixTransform()
        axis.transform.scale([scale] * 3)

    v = v or core.current_canvas()
    v.schedule(_axis, ti)


def transform(
    key: str = None,
    t_parent_child: np.ndarray = None,
    ti: core.TimeInfo = None,
    v: core.RPCCanvas = None,
):
    """Set the node transform"""

    t_parent_child = t_parent_child if t_parent_child is not None else np.eye(4)

    def _transform(ctx: core.Context):
        from vispy.scene import MatrixTransform

        node = core.find_node(ctx.view.scene, key)
        node.transform = MatrixTransform()
        node.transform.matrix = t_parent_child.T
        node.update()

    v = v or core.current_canvas()
    v.schedule(_transform, ti)


def empty(
    key: str = None,
    parent_key: str = None,
    t_parent_child: np.ndarray = None,
    ti: core.TimeInfo = None,
    v: core.RPCCanvas = None,
):
    """Add an empty placeholder node"""

    t_parent_child = t_parent_child if t_parent_child is not None else np.eye(4)

    def _empty(ctx: core.Context):
        from vispy.scene import Node
        from vispy.scene import MatrixTransform

        empty = ctx.ensure_get(
            key,
            lambda: Node(
                parent=core.find_node(ctx.view.scene, parent_key),
                name=key,
            ),
        )
        empty.transform = MatrixTransform()
        empty.transform.matrix = t_parent_child.T
        empty.update()

    v = v or core.current_canvas()
    v.schedule(_empty, ti)
