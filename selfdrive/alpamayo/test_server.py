import unittest

import numpy as np

from selfdrive.alpamayo.server import _build_nav_text, _build_semantic_trajectory


def _xyzt(t, x, y, z):
  return {
    "t": list(t),
    "x": list(x),
    "y": list(y),
    "z": list(z),
  }


def _yaw_matrix(yaw: float) -> np.ndarray:
  c = float(np.cos(yaw))
  s = float(np.sin(yaw))
  return np.array([
    [c, -s, 0.0],
    [s, c, 0.0],
    [0.0, 0.0, 1.0],
  ], dtype=np.float32)


class TestAlpamayoServer(unittest.TestCase):
  def test_build_nav_text_prefers_explicit_text(self):
    self.assertEqual(_build_nav_text({"text": "Turn right in 50m"}), "Turn right in 50m")

  def test_build_nav_text_formats_primary_secondary(self):
    payload = {
      "maneuverPrimaryText": "Turn left",
      "maneuverSecondaryText": "onto Main St",
      "maneuverDistance": 42.0,
    }
    self.assertEqual(_build_nav_text(payload), "Turn left onto Main St in 42m")

  def test_build_semantic_trajectory_uses_stock_tail(self):
    stock_t = [0.0, 0.1, 0.2, 7.0]
    stock_position = _xyzt(stock_t, [0.0, 0.5, 1.0, 99.0], [0.0, 0.0, 0.0, 7.0], [0.0, 0.0, 0.0, 0.0])
    stock_orientation = _xyzt(stock_t, [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.7])
    stock_velocity = _xyzt(stock_t, [0.0, 1.0, 1.0, 4.0], [0.0, 0.0, 0.0, 0.5], [0.0, 0.0, 0.0, 0.0])
    stock_orientation_rate = _xyzt(stock_t, [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.2])
    stock_acceleration = _xyzt(stock_t, [0.0, 0.2, 0.1, -0.3], [0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 0.0])
    stock_plan = {
      "position": stock_position,
      "orientation": stock_orientation,
      "velocity": stock_velocity,
      "orientationRate": stock_orientation_rate,
      "acceleration": stock_acceleration,
    }

    pred_xyz = np.array([
      [1.0, 0.1, 0.0],
      [2.0, 0.3, 0.0],
    ], dtype=np.float32)
    pred_rot = np.stack([_yaw_matrix(0.05), _yaw_matrix(0.1)], axis=0)

    t, semantic = _build_semantic_trajectory(stock_plan, pred_xyz, pred_rot)

    np.testing.assert_allclose(t, np.asarray(stock_t, dtype=np.float32))
    self.assertAlmostEqual(float(semantic["position"][1, 0]), 1.0, places=4)
    self.assertAlmostEqual(float(semantic["position"][2, 0]), 2.0, places=4)
    self.assertAlmostEqual(float(semantic["position"][-1, 0]), 99.0, places=4)
    self.assertAlmostEqual(float(semantic["position"][-1, 1]), 7.0, places=4)
    self.assertAlmostEqual(float(semantic["orientation"][-1, 2]), 0.7, places=4)
    self.assertAlmostEqual(float(semantic["orientation"][1, 2]), 0.05, places=3)
    self.assertAlmostEqual(float(semantic["orientation"][2, 2]), 0.1, places=3)


if __name__ == "__main__":
  unittest.main()
