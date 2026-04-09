import numpy as np

from selfdrive.modeld.constants import ModelConstants, Plan
from selfdrive.modeld.semantic_fusion import apply_semantic_fusion


class FakeXYZT:
  def __init__(self, t, values):
    self.t = t.tolist()
    self.x = values[:, 0].tolist()
    self.y = values[:, 1].tolist()
    self.z = values[:, 2].tolist()


class FakeSemanticPlan:
  status = 1
  source = 1

  def __init__(self, values: np.ndarray, age: float = 0.1, confidence: float = 1.0, consistency: float = 1.0,
               consecutive_valid: int = 2, blend_hint: float = 1.0):
    t = np.asarray(ModelConstants.T_IDXS, dtype=np.float32)
    self.position = FakeXYZT(t, values[:, Plan.POSITION])
    self.velocity = FakeXYZT(t, values[:, Plan.VELOCITY])
    self.acceleration = FakeXYZT(t, values[:, Plan.ACCELERATION])
    self.orientation = FakeXYZT(t, values[:, Plan.T_FROM_CURRENT_EULER])
    self.orientationRate = FakeXYZT(t, values[:, Plan.ORIENTATION_RATE])
    self.age = age
    self.confidence = confidence
    self.consistency = consistency
    self.consecutiveValid = consecutive_valid
    self.blendHint = blend_hint


def build_stock_output(y_offset: float = 0.0) -> dict[str, np.ndarray]:
  plan = np.zeros((1, ModelConstants.IDX_N, Plan.ORIENTATION_RATE.stop), dtype=np.float32)
  plan[0, :, Plan.POSITION.start] = np.asarray(ModelConstants.T_IDXS, dtype=np.float32) * 5.0
  plan[0, :, Plan.POSITION.start + 1] = y_offset
  return {"plan": plan}


def test_semantic_fusion_uses_stale_plan_when_status_is_valid():
  stock_output = build_stock_output()
  semantic_values = stock_output["plan"][0].copy()
  semantic_values[:, Plan.POSITION.start + 1] = 1.5
  fused, result = apply_semantic_fusion(stock_output, FakeSemanticPlan(semantic_values, age=1.5))

  assert result.applied
  far_idxs = np.where(np.asarray(ModelConstants.T_IDXS, dtype=np.float32) >= 2.5)[0]
  np.testing.assert_allclose(fused["plan"][0, far_idxs, Plan.POSITION.start + 1], 1.5)


def test_semantic_fusion_preserves_near_horizon():
  stock_output = build_stock_output()
  semantic_values = stock_output["plan"][0].copy()
  semantic_values[:, Plan.POSITION.start + 1] = 1.5
  fused, result = apply_semantic_fusion(stock_output, FakeSemanticPlan(semantic_values))

  assert result.applied
  t = np.asarray(ModelConstants.T_IDXS, dtype=np.float32)
  near_idxs = np.where(t < 0.7)[0]
  np.testing.assert_allclose(fused["plan"][0, near_idxs, Plan.POSITION.start + 1], 0.0)


def test_semantic_fusion_biases_far_horizon():
  stock_output = build_stock_output()
  semantic_values = stock_output["plan"][0].copy()
  semantic_values[:, Plan.POSITION.start + 1] = 1.5
  fused, result = apply_semantic_fusion(stock_output, FakeSemanticPlan(semantic_values))

  assert result.applied
  t = np.asarray(ModelConstants.T_IDXS, dtype=np.float32)
  far_idxs = np.where(t >= 2.5)[0]
  assert np.all(fused["plan"][0, far_idxs, Plan.POSITION.start + 1] > 0.0)
  np.testing.assert_allclose(fused["plan"][0, far_idxs, Plan.POSITION.start + 1], 1.5)
