import logging
import numpy as np
import rpcvispy as rv

from vispy import app


def basic():

    # Scatter random points
    rv.primitives.xyz_axis(scale=0.25, key="world")

    # Scale to 1.0 after 1.0 sec
    rv.primitives.xyz_axis(scale=1.0, key="world", ti=rv.dt(1.0))

    xyz = np.random.randn(10, 3)
    rv.primitives.scatter(
        xyz,
        "green",
        key="x",
    )
    rv.primitives.scatter(
        np.random.randn(10, 3),
        "red",
        key="y",
        ti=rv.dt(2.0),
    )

    for i in range(30):
        rv.primitives.scatter(
            xyz + (i * 0.01, 0.0, 0.0),
            "green",
            key="x",
            ti=rv.dt(i * 0.01),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.use_app("glfw")
    basic()
