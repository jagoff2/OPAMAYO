import unittest

from selfdrive.alpamayo.server_stub import make_semantic_plan


def _xyzt():
  return {
    "t": [0.0, 1.0, 3.0],
    "x": [0.0, 10.0, 40.0],
    "y": [0.0, 0.0, 0.0],
    "z": [0.0, 0.0, 0.0],
  }


class TestAlpamayoServerStub(unittest.TestCase):
  def test_echo_mode_preserves_stock_plan(self):
    payload = {
      "stockPlan": {
        "position": _xyzt(),
        "orientation": _xyzt(),
        "velocity": _xyzt(),
        "orientationRate": _xyzt(),
        "acceleration": _xyzt(),
        "action": {
          "desiredCurvature": 0.01,
          "desiredAcceleration": 0.2,
          "shouldStop": False,
        },
      },
    }

    response = make_semantic_plan(payload, "echo")
    semantic = response["semanticPlan"]
    self.assertEqual(semantic["trajectory"]["position"]["x"], payload["stockPlan"]["position"]["x"])
    self.assertEqual(semantic["desiredAcceleration"], 0.2)

  def test_caution_mode_biases_far_horizon(self):
    payload = {
      "stockPlan": {
        "position": _xyzt(),
        "orientation": _xyzt(),
        "velocity": _xyzt(),
        "orientationRate": _xyzt(),
        "acceleration": _xyzt(),
        "action": {
          "desiredCurvature": 0.01,
          "desiredAcceleration": 0.2,
          "shouldStop": False,
        },
      },
    }

    response = make_semantic_plan(payload, "caution")
    semantic = response["semanticPlan"]
    self.assertLess(semantic["trajectory"]["velocity"]["x"][-1], payload["stockPlan"]["velocity"]["x"][-1])
    self.assertLessEqual(semantic["desiredAcceleration"], -0.1)


if __name__ == "__main__":
  unittest.main()
