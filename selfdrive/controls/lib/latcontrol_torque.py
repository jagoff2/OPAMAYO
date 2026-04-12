import math
import numpy as np

from cereal import log
from opendbc.car.lateral import FRICTION_THRESHOLD, get_friction
from openpilot.common.constants import ACCELERATION_DUE_TO_GRAVITY
from openpilot.selfdrive.controls.lib.latcontrol import LatControl
from openpilot.common.pid import PIDController

from openpilot.sunnypilot.selfdrive.controls.lib.latcontrol_torque_ext import LatControlTorqueExt

# Controller loop timing; matches controls loop (100 Hz)
CONTROL_DT = 0.01  # s

# Low-speed curvature blending (will be faded to ~0 above ~12 m/s)
LOW_SPEED_X = [0, 10, 20, 30]          # m/s
LOW_SPEED_Y = [10, 8, 6, 3]            # unitless base, but we fade it out at speed

# Actuator-side jerk limit on commanded lateral acceleration (m/s^3)
JERK_LIMIT_X = [0.0, 10.0, 20.0, 30.0]  # m/s
JERK_LIMIT_Y = [10, 10, 2.5, 1.0]     # m/s^3

# Damping on measured lateral jerk to reduce snap-in and overshoot
BASE_JERK_DAMP_GAIN = 0.05  # unitless

# Lane-center feedback (previewed geometric error from curvature mismatch)
# Use only at low curvature/lat-acc where it helped; auto-fade elsewhere.
CENTER_PREVIEW_A = 4.5      # meters (base lookahead)
CENTER_PREVIEW_B = 0.25     # sec (meters per m/s)
K_Y   = 0.06                # s^-2  (reduced)
K_PSI = 0.025               # s^-1  (reduced)

# Apex guard + symmetric cut-prevention (nudges outward when tighter than plan)
K_APEX = 0.40               # dimensionless (stronger; symmetric)
K_CUT  = 0.60               # m/s^0 per (v^2 * delta_kappa) -> lat-acc reduction

# Aggressiveness scaling of PID error at high lat-acc (soften response)
AGGR_GAIN = 0.30            # 1/(1 + AGGR_GAIN*|a_lat_des|)

class LatControlTorque(LatControl):
  def __init__(self, CP, CP_SP, CI):
    super().__init__(CP, CP_SP, CI)
    self.torque_params = CP.lateralTuning.torque.as_builder()
    self.torque_from_lateral_accel = CI.torque_from_lateral_accel()
    self.lateral_accel_from_torque = CI.lateral_accel_from_torque()
    self.pid = PIDController(self.torque_params.kp, self.torque_params.ki,
                             k_f=self.torque_params.kf)
    self.update_limits()
    self.steering_angle_deadzone_deg = self.torque_params.steeringAngleDeadzoneDeg

    # sunnypilot extension remains fully supported
    self.extension = LatControlTorqueExt(self, CP, CP_SP, CI)

    # Internal state
    self._last_output_lataccel = 0.0
    self._last_actual_lataccel = 0.0
    self._last_error = 0.0
    self._last_desired_curvature = 0.0

  def update_live_torque_params(self, latAccelFactor, latAccelOffset, friction):
    self.torque_params.latAccelFactor = latAccelFactor
    self.torque_params.latAccelOffset = latAccelOffset
    self.torque_params.friction = friction
    self.update_limits()

  def update_limits(self):
    # Limit in lat-acc space (handles non-linear torque map correctly)
    self.pid.set_limits(self.lateral_accel_from_torque(self.steer_max, self.torque_params),
                        self.lateral_accel_from_torque(-self.steer_max, self.torque_params))

  def _apply_jerk_limit(self, target_lataccel, v_ego):
    """Slew-limit lateral acceleration by a speed-scaled jerk limit."""
    max_jerk = float(np.interp(v_ego, JERK_LIMIT_X, JERK_LIMIT_Y))
    max_delta = max_jerk * CONTROL_DT
    delta = np.clip(target_lataccel - self._last_output_lataccel, -max_delta, max_delta)
    return self._last_output_lataccel + delta

  @staticmethod
  def _deadzone(x, dz):
    if abs(x) <= dz:
      return 0.0
    return x - math.copysign(dz, x)

  def update(self, active, CS, VM, params, steer_limited_by_safety, desired_curvature, calibrated_pose, curvature_limited):
    pid_log = log.ControlsState.LateralTorqueState.new_message()
    if not active:
      output_torque = 0.0
      pid_log.active = False
      # Reset state to avoid stale rate limiting on resume
      self._last_output_lataccel = 0.0
      self._last_actual_lataccel = 0.0
      self._last_error = 0.0
      self._last_desired_curvature = 0.0
    else:
      # Curvature/lat-acc measurement
      actual_curvature = -VM.calc_curvature(math.radians(CS.steeringAngleDeg - params.angleOffsetDeg), CS.vEgo, params.roll)
      roll_compensation = params.roll * ACCELERATION_DUE_TO_GRAVITY
      curvature_deadzone = abs(VM.calc_curvature(math.radians(self.steering_angle_deadzone_deg), CS.vEgo, 0.0))

      # Base desired/actual lateral accelerations
      base_desired_latacc = desired_curvature * CS.vEgo ** 2
      actual_lateral_accel = actual_curvature * CS.vEgo ** 2
      lateral_accel_deadzone = curvature_deadzone * CS.vEgo ** 2

      # ---------- Lane-center preview (ONLY in easy regions) ----------
      # Use desired - actual so we pull toward the planner.
      Lp = CENTER_PREVIEW_A + CENTER_PREVIEW_B * CS.vEgo  # meters
      Lp = float(np.clip(Lp, 4.0, 20.0))

      e_kappa = (desired_curvature - actual_curvature)    # 1/m
      e_psi = e_kappa * Lp                                # rad (small-angle approx)
      e_y_preview = 0.5 * e_kappa * (Lp ** 2)             # m (previewed cross-track)

      # Fade preview strongly if the requested turn is tight or speed is high.
      # Thresholds chosen to keep preview out of high-lat regions.
      a_des_mag = abs(base_desired_latacc)
      tight_curve = abs(desired_curvature) * CS.vEgo > 0.25     # ~turn radius < ~40m at 10 m/s
      preview_enable = (a_des_mag < 1.5) and (not tight_curve)  # only when gentle

      if preview_enable:
        speed_scale = np.clip((CS.vEgo - 3.0) / 4.0, 0.0, 1.0)  # 0 @3 m/s ? 1 @7 m/s
        center_term = (K_Y * e_y_preview + K_PSI * CS.vEgo * e_psi) * speed_scale
        # = 20% of planner accel (+floor) to keep it truly "shaping"
        max_center = 0.20 * (a_des_mag + 0.5)
        center_term = float(np.clip(center_term, -max_center, max_center))
      else:
        center_term = 0.0

      desired_lateral_accel = base_desired_latacc + center_term

      # ---------- Symmetric cut-prevention (works both left & right) ----------
      # If |actual| > |desired|, reduce commanded lat-acc in the turn direction.
      # Stronger effect at higher speed (v^2) and larger inside excess.
      inside_excess = max(0.0, abs(actual_curvature) - abs(desired_curvature))
      if inside_excess > 0.0:
        cut_guard = -K_CUT * (CS.vEgo ** 2) * inside_excess * np.sign(desired_curvature)
        # Clamp guard to = 40% of planner accel (+floor)
        max_guard = 0.40 * (a_des_mag + 0.5)
        cut_guard = float(np.clip(cut_guard, -max_guard, max_guard))
        desired_lateral_accel += cut_guard

      # ---------- Apex guard (directional; only when tighter with same sign) ----------
      same_sign = (np.sign(desired_curvature) == np.sign(actual_curvature)) and (np.sign(desired_curvature) != 0.0)
      cutting_inside = same_sign and (abs(actual_curvature) > abs(desired_curvature))
      if cutting_inside:
        delta_k_in = (abs(actual_curvature) - abs(desired_curvature))  # =0
        apex_guard = -K_APEX * (CS.vEgo ** 2) * delta_k_in * np.sign(desired_curvature)
        guard_limit = 0.30 * (a_des_mag + 0.5)  # = 30% (apex guard is secondary to cut_guard)
        apex_guard = float(np.clip(apex_guard, -guard_limit, guard_limit))
        desired_lateral_accel += apex_guard

      # ---------- Low-speed curvature blending with fade-out ----------
      # Original low-speed helper caused bias at speed. Fade it to zero above ~12 m/s.
      low_speed_base = np.interp(CS.vEgo, LOW_SPEED_X, LOW_SPEED_Y) ** 2
      fade = 1.0 - np.clip((CS.vEgo - 8.0) / 4.0, 0.0, 1.0)  # 1 @=8 m/s ? 0 @=12 m/s
      low_speed_factor = low_speed_base * fade

      setpoint = desired_lateral_accel + low_speed_factor * desired_curvature
      measurement = actual_lateral_accel + low_speed_factor * actual_curvature
      gravity_adjusted_lateral_accel = desired_lateral_accel - roll_compensation

      # One-step latency prediction on measurement (no extra signals required)
      measured_jerk = (actual_lateral_accel - self._last_actual_lataccel) / CONTROL_DT
      pred_measurement = measurement + measured_jerk * CONTROL_DT

      # ---------- Aggressiveness scaling of PID error at high lat-acc ----------
      raw_error = float(setpoint - pred_measurement)
      aggr_scale = 1.0 / (1.0 + AGGR_GAIN * a_des_mag)
      raw_error *= aggr_scale

      # Error deadzone to avoid small oscillations near center
      error_dz = 0.5 * lateral_accel_deadzone
      pid_error = self._deadzone(raw_error, error_dz)

      # Feedforward: gravity + friction; add small jerk damping (acts on measurement)
      ff = gravity_adjusted_lateral_accel
      ff += get_friction(desired_lateral_accel - actual_lateral_accel,
                         lateral_accel_deadzone, FRICTION_THRESHOLD, self.torque_params)
      ff -= BASE_JERK_DAMP_GAIN * measured_jerk

      # Freeze I when limited, overridden, or very low speed
      freeze_integrator = steer_limited_by_safety or CS.steeringPressed or CS.vEgo < 5

      # Clamp integrator in tight/high-speed turns
      if abs(desired_curvature) > 0.02 and CS.vEgo > 15.0:  # ~R<50 m at 15 m/s
        self.pid.i = float(np.clip(self.pid.i, -0.15, 0.15))

      # Gentle integrator bleed to prevent "stacking up" after sign flip with small error
      if np.sign(self._last_error) != np.sign(pid_error) and abs(pid_error) < 2.0 * lateral_accel_deadzone:
        self.pid.i *= 0.9

      # PID in lat-acc space
      output_lataccel = self.pid.update(pid_error,
                                        feedforward=ff,
                                        speed=CS.vEgo,
                                        freeze_integrator=freeze_integrator)

      # Anticipatory jerk scaling based on desired curvature slew
      desired_curvature_rate = (desired_curvature - self._last_desired_curvature) / CONTROL_DT
      jerk_scale = 1.0 / (1.0 + 6.0 * abs(desired_curvature_rate))
      jerk_scale = float(np.clip(jerk_scale, 0.5, 1.0))

      # Actuator-side jerk limiting (complements planner s clip)
      output_lataccel = self._apply_jerk_limit(output_lataccel * jerk_scale, CS.vEgo) / max(jerk_scale, 1e-3)

      # Map desired lat-acc to torque
      output_torque = self.torque_from_lateral_accel(output_lataccel, self.torque_params)

      # sunnypilot extension can override error and torque if desired
      pid_log, output_torque = self.extension.update(
        CS, VM, self.pid, params, ff, pid_log,
        setpoint, pred_measurement, calibrated_pose, roll_compensation,
        desired_lateral_accel, actual_lateral_accel, lateral_accel_deadzone, gravity_adjusted_lateral_accel,
        desired_curvature, actual_curvature, steer_limited_by_safety, output_torque
      )

      # Logging
      pid_log.active = True
      pid_log.error = float(pid_error)
      pid_log.p = float(self.pid.p)
      pid_log.i = float(self.pid.i)
      pid_log.d = float(self.pid.d)
      pid_log.f = float(self.pid.f)
      pid_log.output = float(-output_torque)  # TODO: log lat accel?
      pid_log.actualLateralAccel = float(actual_lateral_accel)
      pid_log.desiredLateralAccel = float(desired_lateral_accel)
      pid_log.saturated = bool(self._check_saturation(self.steer_max - abs(output_torque) < 1e-3,
                                                      CS, steer_limited_by_safety, curvature_limited))

      # State update
      self._last_output_lataccel = output_lataccel
      self._last_actual_lataccel = actual_lateral_accel
      self._last_error = pid_error
      self._last_desired_curvature = desired_curvature

    # TODO left is positive in this convention
    return -output_torque, 0.0, pid_log
