import struct

import numpy as np


def parse_pointcloud2_xyz(msg) -> np.ndarray:
    """Extract (N, 3) float32 XYZ array from a sensor_msgs/PointCloud2."""
    field_offsets = {f.name: f.byte_offset for f in msg.fields}
    x_off = field_offsets["x"]
    y_off = field_offsets["y"]
    z_off = field_offsets["z"]
    point_step = msg.point_step
    n_points = msg.width * msg.height

    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(n_points, point_step)

    xs = np.frombuffer(raw[:, x_off : x_off + 4].tobytes(), dtype=np.float32)
    ys = np.frombuffer(raw[:, y_off : y_off + 4].tobytes(), dtype=np.float32)
    zs = np.frombuffer(raw[:, z_off : z_off + 4].tobytes(), dtype=np.float32)

    xyz = np.stack([xs, ys, zs], axis=1)
    valid = np.isfinite(xyz).all(axis=1)
    return xyz[valid]


def downsample_stride(xyz: np.ndarray, keep_every: int) -> np.ndarray:
    """Return every keep_every-th point."""
    return xyz[::keep_every]


def transform_nwu_to_threejs(xyz: np.ndarray) -> np.ndarray:
    """
    Convert ROS NWU (X=Forward, Y=Left, Z=Up) to Three.js Y-Up right-handed
    (X=Right, Y=Up, Z=toward viewer).

    Mapping:
      Three.js X =  -ROS Y
      Three.js Y =   ROS Z
      Three.js Z =  -ROS X
    """
    out = np.empty_like(xyz)
    out[:, 0] = -xyz[:, 1]
    out[:, 1] = xyz[:, 2]
    out[:, 2] = -xyz[:, 0]
    return out


def pack_xyz_binary(xyz: np.ndarray) -> bytes:
    """Flatten (N, 3) float32 to raw bytes for the WebSocket wire format."""
    return xyz.astype(np.float32, copy=False).tobytes()
