#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import copy
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))

from selfdrive.controls.reasoned.pathsynth import BasePlan
from selfdrive.controls.reasoned.planner import ReasonedPlanner, ReasonedPlannerConfig
from selfdrive.controls.reasoned.side_semantics import (
  construction_avoidance_metadrive_lateral_for_hazard_side,
  construction_avoidance_metadrive_side_valid,
  construction_avoidance_route_side_valid,
  construction_hazard_metadrive_lateral_for_side,
  construction_hazard_side_from_avoid_token,
  lateral_side_metadrive,
  lateral_side_openpilot,
  lateral_side_route,
  metadrive_lateral_for_side,
  metadrive_to_openpilot_lateral_m,
  openpilot_to_metadrive_lateral_m,
  openpilot_to_route_lateral_m,
  route_lateral_for_openpilot_side,
  route_to_openpilot_lateral_m,
)
from selfdrive.controls.reasoned.ui_scene_board import OverlayGeometry, UiSceneBoardRenderer
from selfdrive.controls.reasoned.vlm import StaticRtpEngine, build_rtp_engine
from tools.reasoned_trajectory_poc.run_local_demo import SCENARIOS


ALPAMAYO_CONTRACT_BENCH = REPO_ROOT.parent / "openpilot_alpamayo" / "openpilot" / "tools" / "alpamayo_speed" / "bench_alpamayo_metadrive_contract.py"
AVOID_ZONE_RE = re.compile(
  r"^(?P<side>left_edge|right_edge|corridor_object|lead_vehicle|cut_in_vehicle|crossing_vehicle)_s"
  r"(?P<start>\d+(?:\.\d+)?)_(?P<end>\d+(?:\.\d+)?)"
  r"(?:_margin(?P<margin>\d+(?:\.\d+)?))?$"
)
STOP_LINE_RE = re.compile(r"^stop_line_s(?P<distance>\d+(?:\.\d+)?)$")
VEHICLE_SCENES = {
  "true_moving_lead",
  "slower_lead",
  "braking_lead",
  "stopped_lead",
  "cut_in_vehicle",
  "crossing_vehicle",
  "irrelevant_vehicle",
}
CONSTRUCTION_SCENES = {"construction", "construction_left", "construction_right"}
VEHICLE_KIND_TOKENS = ("lead_vehicle", "cut_in_vehicle", "crossing_vehicle", "irrelevant_vehicle")
ROUTE_VEHICLE_MODEL_CLASSES = ("DefaultVehicle", "LVehicle", "MVehicle", "SVehicle", "XLVehicle")
ROUTE_VEHICLE_MODEL_CLASS = "DefaultVehicle"
ROUTE_VEHICLE_USE_SPECIAL_COLOR = False
# Keep the visual heading equal to the physical route heading. The DefaultVehicle
# mesh gives the clearest rear-view same-direction lead car in the driver board.
ROUTE_VEHICLE_VISUAL_HEADING_OFFSET_RAD = 0.0
DEFAULT_ROUTE_LATERAL_SIGN_TO_OPENPILOT = -1.0


def wrap_angle(angle: float) -> float:
  return (angle + math.pi) % (2.0 * math.pi) - math.pi


def route_vehicle_visual_heading(route_heading: float, visual_heading_offset_rad: float = ROUTE_VEHICLE_VISUAL_HEADING_OFFSET_RAD) -> float:
  return wrap_angle(float(route_heading) + float(visual_heading_offset_rad))


def route_vehicle_heading_error_rad(route_heading: float, actual_heading: float) -> float:
  return wrap_angle(float(actual_heading) - float(route_heading))


def route_vehicle_heading_alignment_cos(route_heading: float, actual_heading: float) -> float:
  return math.cos(route_vehicle_heading_error_rad(route_heading, actual_heading))


def route_vehicle_heading_same_direction(route_heading: float, actual_heading: float) -> bool:
  return route_vehicle_heading_alignment_cos(route_heading, actual_heading) >= 0.0


def object_heading_theta(obj, fallback_heading: float) -> float:
  try:
    value = float(obj.heading_theta)
  except Exception:
    value = float(fallback_heading)
  return value if math.isfinite(value) else float(fallback_heading)


def route_vehicle_class_from_name(name: str):
  from metadrive.component.vehicle.vehicle_type import DefaultVehicle, LVehicle, MVehicle, SVehicle, XLVehicle

  classes = {
    "DefaultVehicle": DefaultVehicle,
    "LVehicle": LVehicle,
    "MVehicle": MVehicle,
    "SVehicle": SVehicle,
    "XLVehicle": XLVehicle,
  }
  try:
    return classes[name]
  except KeyError as exc:
    raise ValueError(f"unknown route vehicle model class: {name}") from exc


def percentile(values: list[float], pct: float) -> float:
  if not values:
    return 0.0
  ordered = sorted(values)
  idx = min(len(ordered) - 1, max(0, round((pct / 100.0) * (len(ordered) - 1))))
  return ordered[idx]


def construction_scene_side(scene_name: str) -> str:
  if scene_name == "construction_left":
    return "left"
  if scene_name in {"construction", "construction_right"}:
    return "right"
  return ""


def make_base_plan(frame_id: int, speed_mps: float, curvature: float = 0.0, xy: tuple[tuple[float, ...], tuple[float, ...]] | None = None, desired_speed_mps: float | None = None) -> BasePlan:
  if xy is None:
    xs = np.linspace(0.5, 80.0, 33)
    ys = 0.5 * curvature * xs * xs
  else:
    xs = np.asarray(xy[0], dtype=np.float32)
    ys = np.asarray(xy[1], dtype=np.float32)
  desired_speed = float(speed_mps if desired_speed_mps is None else desired_speed_mps)
  return BasePlan(
    frame_id=frame_id,
    model_log_mono_time_ns=frame_id * 50_000_000,
    t=tuple(float(i) * 0.2 for i in range(len(xs))),
    x=tuple(float(x) for x in xs),
    y=tuple(float(y) for y in ys),
    speeds=tuple(desired_speed for _ in xs),
    desired_curvature=float(curvature),
    v_ego=float(speed_mps),
  )


def make_base_plan_from_route(env, frame_id: int, speed_mps: float, desired_speed_mps: float | None = None) -> BasePlan:
  distances = np.linspace(0.5, 80.0, 33)
  xs: list[float] = []
  ys: list[float] = []
  for dist in distances:
    point = route_world_point(env, float(dist), 0.0)
    forward, left = world_to_ego(env, point)
    xs.append(max(0.1, forward))
    ys.append(left)

  curvature = 0.0
  for x, y in zip(xs, ys):
    if x >= 12.0:
      curvature = float(np.clip(2.0 * y / max(x * x, 1.0), -0.2, 0.2))
      break
  return make_base_plan(frame_id, speed_mps, curvature, (tuple(xs), tuple(ys)), desired_speed_mps)


def load_alpamayo_contract_bench():
  if not ALPAMAYO_CONTRACT_BENCH.exists():
    raise FileNotFoundError(f"missing Alpamayo contract benchmark module: {ALPAMAYO_CONTRACT_BENCH}")
  spec = importlib.util.spec_from_file_location("_alpamayo_contract_bench", ALPAMAYO_CONTRACT_BENCH)
  if spec is None or spec.loader is None:
    raise ImportError(f"failed to load Alpamayo contract benchmark module: {ALPAMAYO_CONTRACT_BENCH}")
  module = importlib.util.module_from_spec(spec)
  sys.modules.setdefault("_alpamayo_contract_bench", module)
  spec.loader.exec_module(module)
  return module


def make_env(args: argparse.Namespace):
  from panda3d.core import Vec3
  from metadrive.component.sensors.rgb_camera import RGBCamera
  from metadrive.envs.metadrive_env import MetaDriveEnv
  map_arg: int | str
  map_arg = int(args.map) if str(args.map).isdigit() else args.map

  sensors: dict[str, tuple[Any, int, int]] = {"rgb_road": (RGBCamera, args.camera_width, args.camera_height)}
  if bool(getattr(args, "_alpamayofast_dual_cameras", False)):
    from panda3d.core import GraphicsOutput, Texture

    class CopyRamRGBCamera(RGBCamera):
      def __init__(self, *cam_args, **cam_kwargs):
        super().__init__(*cam_args, **cam_kwargs)
        self.cpu_texture = Texture()
        self.buffer.addRenderTexture(self.cpu_texture, GraphicsOutput.RTMCopyRam)

      def get_rgb_array_cpu(self) -> np.ndarray:
        origin_img = self.cpu_texture
        img = np.frombuffer(origin_img.getRamImage().getData(), dtype=np.uint8)
        img = img.reshape((origin_img.getYSize(), origin_img.getXSize(), -1))
        img = img[:, :, :3]
        return img[::-1].copy()

    class RGBCameraWide(CopyRamRGBCamera):
      def __init__(self, *cam_args, **cam_kwargs):
        super().__init__(*cam_args, **cam_kwargs)
        lens = self.get_lens()
        lens.setFov(120)
        lens.setNear(0.1)

    class RGBCameraRoad(CopyRamRGBCamera):
      def __init__(self, *cam_args, **cam_kwargs):
        super().__init__(*cam_args, **cam_kwargs)
        lens = self.get_lens()
        lens.setFov(40)
        lens.setNear(0.1)

    sensors = {
      "rgb_wide": (RGBCameraWide, args.camera_width, args.camera_height),
      "rgb_road": (RGBCameraRoad, args.camera_width, args.camera_height),
    }

  config = {
    "use_render": False,
    "image_observation": True,
    "sensors": sensors,
    "vehicle_config": {"image_source": "rgb_road"},
    "interface_panel": [],
    "traffic_density": 0.0,
    "manual_control": False,
    "show_logo": False,
    "show_fps": False,
    "start_seed": args.seed,
    "num_scenarios": 1,
    "map": map_arg,
    "crash_vehicle_done": False,
    "crash_object_done": False,
    "out_of_route_done": False,
    "on_continuous_line_done": False,
  }
  env = MetaDriveEnv(config)
  env.reset(seed=args.seed)
  env._rtp_camera_color_order = str(getattr(args, "camera_color_order", "bgr"))
  env._rtp_route_vehicle_visual_heading_offset_rad = math.radians(float(getattr(
    args,
    "route_vehicle_visual_heading_offset_deg",
    math.degrees(ROUTE_VEHICLE_VISUAL_HEADING_OFFSET_RAD),
  )))
  for sensor_name in sensors:
    cam = env.engine.sensors[sensor_name]
    cam.get_cam().reparentTo(env.vehicle.origin)
    cam.get_cam().setPos(Vec3(0.0, 0.0, 1.22))
    cam.get_cam().setHpr(Vec3(0.0, 0.0, 0.0))
  return env


def spawn_novel_scene(env, args: argparse.Namespace) -> list[dict[str, float | str]]:
  scene_name = args.novel_scene
  spawned: list[dict[str, float | str]] = []
  env._rtp_moving_pedestrians = []
  env._rtp_controlled_vehicles = []
  env._rtp_vehicle_track_history = {}
  env._rtp_phase_traffic_lights = []
  lane = route_lane_for_vehicle(env)
  lane_heading = float(lane.heading_theta_at(max(0.0, lane.local_coordinates(env.vehicle.position)[0])))

  def spawn_at(kind: str, ahead_m: float, lateral_m: float, cls, **kwargs) -> None:
    route_s_m = current_route_longitudinal_m(env) + float(ahead_m)
    point = route_world_point(env, ahead_m, lateral_m)
    obj = env.engine.spawn_object(
      cls,
      position=[float(point[0]), float(point[1])],
      heading_theta=lane_heading,
      force_spawn=True,
      **kwargs,
    )
    spawned.append({
      "kind": kind,
      "route_s_m": float(route_s_m),
      "ahead_m": float(ahead_m),
      "lateral_m": float(lateral_m),
      "x": float(point[0]),
      "y": float(point[1]),
      "id": str(getattr(obj, "id", "")),
    })

  if scene_name == "none":
    pass
  elif scene_name in CONSTRUCTION_SCENES:
    from metadrive.component.static_object.traffic_object import TrafficBarrier, TrafficCone
    side = construction_scene_side(scene_name)
    for ahead_m in (14.0, 20.0, 26.0, 32.0):
      spawn_at(f"traffic_cone_{side}_edge", ahead_m, route_lateral_for_side_from_args(args, side, 1.35), TrafficCone, static=True)
    spawn_at(f"traffic_barrier_{side}_edge", 24.0, route_lateral_for_side_from_args(args, side, 1.20), TrafficBarrier, static=True)
  elif scene_name == "pedestrian":
    from metadrive.component.traffic_participants.pedestrian import Pedestrian
    spawn_at("pedestrian_center_lane", 24.0, 0.0, Pedestrian, random_seed=3)
  elif scene_name == "traffic_light":
    _spawn_phase_traffic_light(env, lane, args, spawned)
  elif scene_name == "stop_sign":
    point = route_world_point(env, 18.0, -1.15)
    _spawn_stop_sign_billboard(env, float(point[0]), float(point[1]), lane_heading)
    from metadrive.component.traffic_light.base_traffic_light import BaseTrafficLight
    light_point = route_world_point(env, 18.0, 0.0)
    light = env.engine.spawn_object(
      BaseTrafficLight,
      lane=lane,
      position=[float(light_point[0]), float(light_point[1])],
      force_spawn=True,
      show_model=True,
    )
    light.set_red()
    env._rtp_phase_traffic_lights = [{"light": light}]
    env._rtp_traffic_light_state = "red"
    spawned.append({
      "kind": "stop_sign_billboard",
      "ahead_m": 18.0,
      "lateral_m": -1.15,
      "x": float(point[0]),
      "y": float(point[1]),
      "id": "billboard",
    })
    spawned.append({
      "kind": "red_stop_light",
      "ahead_m": 18.0,
      "lateral_m": 0.0,
      "x": float(light_point[0]),
      "y": float(light_point[1]),
      "id": str(getattr(light, "id", "")),
    })
  elif scene_name == "random_mixed":
    _spawn_random_mixed_scene(env, args, spawned)
  elif scene_name in VEHICLE_SCENES:
    _spawn_vehicle_interaction_scene(env, args, scene_name, spawned)
  else:
    raise ValueError(f"unknown novel scene: {scene_name}")

  if args.include_traffic_light and scene_name not in {"traffic_light", "stop_sign"}:
    _spawn_phase_traffic_light(env, lane, args, spawned)

  # Advance one render step so newly spawned objects are visible to the camera sensor.
  env.step([0.0, 0.0])
  return spawned


def _spawn_phase_traffic_light(env, lane, args: argparse.Namespace, spawned: list[dict[str, float | str]]) -> None:
  controller, record = _spawn_controlled_traffic_light(
    env,
    lane,
    route_s_m=args.traffic_light_route_s,
    lateral_m=args.traffic_light_lateral_m,
    initial_state="red",
  )
  env._rtp_phase_traffic_lights = list(getattr(env, "_rtp_phase_traffic_lights", [])) + [controller]
  env._rtp_traffic_light_state = "red"
  spawned.append(record)


def _spawn_controlled_traffic_light(env, lane, route_s_m: float, lateral_m: float, initial_state: str) -> tuple[dict, dict[str, float | str]]:
  from metadrive.component.traffic_light.base_traffic_light import BaseTrafficLight

  point, heading = route_point_at_s(env, route_s_m, lateral_m)
  light = env.engine.spawn_object(
    BaseTrafficLight,
    lane=lane,
    position=[float(point[0]), float(point[1])],
    force_spawn=True,
    show_model=False,
  )
  try:
    light.origin.setScale(0.95, 1.8, 1.8)
  except Exception:
    pass
  billboard = _spawn_traffic_light_billboard(env, float(point[0]), float(point[1]), heading, initial_state)
  controller = {"light": light, "billboard": billboard}
  _set_controlled_traffic_light_state(env, controller, initial_state)
  return controller, {
    "kind": "controlled_traffic_light",
    "route_s_m": float(route_s_m),
    "ahead_m": float(route_s_m),
    "lateral_m": float(lateral_m),
    "x": float(point[0]),
    "y": float(point[1]),
    "id": str(getattr(light, "id", "")),
    "initial_state": initial_state,
  }


def update_phase_traffic_lights(env, frame_id: int, args: argparse.Namespace) -> None:
  lights = getattr(env, "_rtp_phase_traffic_lights", [])
  if not lights:
    return
  if args.traffic_light_cycle:
    red_frames = max(1, int(args.traffic_light_red_frames))
    green_frames = max(1, int(args.traffic_light_green_frames))
    phase_frame = frame_id % (red_frames + green_frames)
    state = "red" if phase_frame < red_frames else "green"
  else:
    state = "green" if frame_id >= args.traffic_light_green_frame else "red"
  if getattr(env, "_rtp_traffic_light_state", None) == state:
    return
  for controller in lights:
    _set_controlled_traffic_light_state(env, controller, state)
  env._rtp_traffic_light_state = state


def _set_controlled_traffic_light_state(env, controller: dict, state: str) -> None:
  light = controller.get("light")
  if light is not None:
    if state == "green":
      light.set_green()
    else:
      light.set_red()
  billboard = controller.get("billboard")
  if billboard is not None:
    billboard["card"].setColor(*_traffic_signal_color(state))


def _route_lanes(env):
  nav = env.vehicle.navigation
  lane_id = getattr(getattr(env.vehicle, "lane", None), "index", (None, None, 0))[2]
  lane_id = lane_id if isinstance(lane_id, int) else 0
  lanes = []
  net = nav.map.road_network
  for start, end in zip(nav.checkpoints[:-1], nav.checkpoints[1:]):
    road_lanes = net.graph.get(start, {}).get(end, [])
    if not road_lanes:
      continue
    lanes.append(road_lanes[min(max(lane_id, 0), len(road_lanes) - 1)])
  return lanes


def route_point_at_s(env, route_s_m: float, lateral_offset_m: float) -> tuple[np.ndarray, float]:
  remaining = max(0.0, float(route_s_m))
  lanes = _route_lanes(env)
  if not lanes:
    return route_world_point(env, route_s_m, lateral_offset_m), 0.0
  lane = lanes[-1]
  local_s = min(remaining, lane.length)
  for candidate in lanes:
    lane = candidate
    if remaining <= candidate.length:
      local_s = remaining
      break
    remaining -= candidate.length
  local_s = min(max(0.0, local_s), lane.length)
  half_width = max(0.1, float(lane.width_at(local_s)) * 0.5 - 0.45)
  point = np.asarray(lane.position(local_s, float(np.clip(lateral_offset_m, -half_width, half_width))), dtype=np.float32)
  heading = float(lane.heading_theta_at(local_s))
  return point, heading


def route_total_length_m(env) -> float:
  return float(sum(lane.length for lane in _route_lanes(env)))


def route_coordinates_for_position(env, position) -> tuple[float, float]:
  lanes = _route_lanes(env)
  if not lanes:
    lane = route_lane_for_vehicle(env)
    long_m, lateral_m = lane.local_coordinates(position)
    return float(long_m), float(lateral_m)

  cumulative = 0.0
  best_s = 0.0
  best_lateral_m = 0.0
  best_score = float("inf")
  for lane in lanes:
    long_m, lateral_m = lane.local_coordinates(position)
    clamped_long = float(np.clip(long_m, 0.0, lane.length))
    overshoot = max(0.0, -float(long_m), float(long_m) - float(lane.length))
    score = abs(float(lateral_m)) + overshoot * 2.0
    if score < best_score:
      best_score = score
      best_s = cumulative + clamped_long
      best_lateral_m = float(lateral_m)
    cumulative += float(lane.length)
  return float(best_s), float(best_lateral_m)


def route_lateral_sign_to_openpilot(env, *, ahead_m: float = 12.0, probe_m: float = 1.0) -> float:
  """Return the sign that converts route-lane lateral into ego/openpilot lateral.

  MetaDrive lane-local lateral sign is not a production interface. Calibrate it
  from the current ego pose so simulated objects, rendered boards, Qwen state
  text, and control targets all share the openpilot convention: positive means
  ego-left.
  """
  probe = max(0.1, abs(float(probe_m)))
  try:
    left_for_plus = world_to_ego(env, route_world_point(env, ahead_m, probe))[1]
    left_for_minus = world_to_ego(env, route_world_point(env, ahead_m, -probe))[1]
  except Exception:
    return DEFAULT_ROUTE_LATERAL_SIGN_TO_OPENPILOT
  if not (math.isfinite(left_for_plus) and math.isfinite(left_for_minus)):
    return DEFAULT_ROUTE_LATERAL_SIGN_TO_OPENPILOT
  if abs(left_for_plus - left_for_minus) < 1e-3:
    return DEFAULT_ROUTE_LATERAL_SIGN_TO_OPENPILOT
  return 1.0 if left_for_plus > left_for_minus else -1.0


def _route_lateral_sign_from_args(args: argparse.Namespace | None) -> float:
  if args is None:
    return DEFAULT_ROUTE_LATERAL_SIGN_TO_OPENPILOT
  try:
    sign = float(getattr(args, "route_lateral_sign_to_openpilot", DEFAULT_ROUTE_LATERAL_SIGN_TO_OPENPILOT))
  except (TypeError, ValueError):
    return DEFAULT_ROUTE_LATERAL_SIGN_TO_OPENPILOT
  return 1.0 if sign >= 0.0 else -1.0


def route_to_openpilot_lateral_m_from_args(args: argparse.Namespace | None, route_lateral_m: float | None) -> float | None:
  if route_lateral_m is None:
    return None
  return route_to_openpilot_lateral_m(route_lateral_m, _route_lateral_sign_from_args(args))


def openpilot_to_route_lateral_m_from_args(args: argparse.Namespace | None, openpilot_lateral_m: float | None) -> float | None:
  if openpilot_lateral_m is None:
    return None
  return openpilot_to_route_lateral_m(openpilot_lateral_m, _route_lateral_sign_from_args(args))


def route_lateral_for_side_from_args(args: argparse.Namespace | None, side: str, magnitude_m: float) -> float:
  return route_lateral_for_openpilot_side(side, magnitude_m, _route_lateral_sign_from_args(args))


def lateral_side_route_openpilot(args: argparse.Namespace | None, route_lateral_m: float | None) -> str:
  return lateral_side_route(route_lateral_m, _route_lateral_sign_from_args(args))


def _spawn_route_vehicle(
  env,
  spawned: list[dict[str, float | str]],
  *,
  kind: str,
  route_s_m: float,
  lateral_m: float,
  speed_mps: float,
  expected_lead_class: str,
  target_lateral_m: float | None = None,
  lateral_rate_mps: float = 0.0,
  accel_mps2: float = 0.0,
  min_speed_mps: float = 0.0,
  max_speed_mps: float | None = None,
  model_class_name: str = ROUTE_VEHICLE_MODEL_CLASS,
  use_special_color: bool = ROUTE_VEHICLE_USE_SPECIAL_COLOR,
) -> None:
  VehicleClass = route_vehicle_class_from_name(model_class_name)
  point, heading = route_point_at_s(env, route_s_m, lateral_m)
  visual_heading_offset_rad = float(getattr(env, "_rtp_route_vehicle_visual_heading_offset_rad", ROUTE_VEHICLE_VISUAL_HEADING_OFFSET_RAD))
  visual_heading = route_vehicle_visual_heading(heading, visual_heading_offset_rad)
  vehicle_config = dict(env.engine.global_config["vehicle_config"])
  vehicle_config["use_special_color"] = bool(use_special_color)
  obj = env.engine.spawn_object(
    VehicleClass,
    vehicle_config=vehicle_config,
    position=[float(point[0]), float(point[1])],
    heading=visual_heading,
    force_spawn=True,
  )
  try:
    obj.set_velocity([math.cos(heading), math.sin(heading)], float(speed_mps))
  except Exception:
    pass
  actual_heading = object_heading_theta(obj, visual_heading)
  heading_error = route_vehicle_heading_error_rad(heading, actual_heading)
  heading_alignment = math.cos(heading_error)
  record = {
    "kind": kind,
    "route_s_m": float(route_s_m),
    "ahead_m": float(route_s_m),
    "lateral_m": float(lateral_m),
    "lateral_openpilot_m": float(route_to_openpilot_lateral_m_from_args(getattr(env, "_rtp_route_lateral_args", None), lateral_m)),
    "target_lateral_m": float(lateral_m if target_lateral_m is None else target_lateral_m),
    "x": float(point[0]),
    "y": float(point[1]),
    "route_heading_theta": float(heading),
    "visual_heading_theta": float(visual_heading),
    "actual_heading_theta": float(actual_heading),
    "route_heading_error_rad": float(heading_error),
    "route_heading_alignment_cos": float(heading_alignment),
    "route_heading_same_direction": bool(heading_alignment >= 0.0),
    "visual_heading_offset_rad": float(visual_heading_offset_rad),
    "model_class": str(model_class_name),
    "use_special_color": bool(use_special_color),
    "id": str(getattr(obj, "id", "")),
    "speed_mps": float(speed_mps),
    "accel_mps2": float(accel_mps2),
    "lateral_rate_mps": float(lateral_rate_mps),
    "expected_lead_class": expected_lead_class,
  }
  spawned.append(record)
  env._rtp_controlled_vehicles = list(getattr(env, "_rtp_controlled_vehicles", [])) + [{
    "obj": obj,
    "record": record,
    "route_s_m": float(route_s_m),
    "lateral_m": float(lateral_m),
    "target_lateral_m": float(lateral_m if target_lateral_m is None else target_lateral_m),
    "lateral_rate_mps": float(lateral_rate_mps),
    "speed_mps": float(speed_mps),
    "accel_mps2": float(accel_mps2),
    "min_speed_mps": float(min_speed_mps),
    "max_speed_mps": None if max_speed_mps is None else float(max_speed_mps),
  }]


def _spawn_vehicle_interaction_scene(env, args: argparse.Namespace, scene_name: str, spawned: list[dict[str, float | str]]) -> None:
  route_s = float(args.vehicle_scene_route_s)
  desired = max(0.0, float(args.speed_mps))
  route_vehicle_kwargs = {
    "model_class_name": str(getattr(args, "route_vehicle_model", ROUTE_VEHICLE_MODEL_CLASS)),
    "use_special_color": bool(getattr(args, "route_vehicle_special_color", ROUTE_VEHICLE_USE_SPECIAL_COLOR)),
  }
  if scene_name == "true_moving_lead":
    _spawn_route_vehicle(
      env,
      spawned,
      kind="lead_vehicle_true_moving",
      route_s_m=route_s,
      lateral_m=0.0,
      speed_mps=desired,
      expected_lead_class="true_moving_lead",
      min_speed_mps=desired,
      max_speed_mps=desired,
      **route_vehicle_kwargs,
    )
  elif scene_name == "slower_lead":
    _spawn_route_vehicle(
      env,
      spawned,
      kind="lead_vehicle_slower",
      route_s_m=route_s,
      lateral_m=0.0,
      speed_mps=desired * float(args.slower_lead_speed_scale),
      expected_lead_class="slower_lead",
      min_speed_mps=0.0,
      max_speed_mps=desired * float(args.slower_lead_speed_scale),
      **route_vehicle_kwargs,
    )
  elif scene_name == "braking_lead":
    _spawn_route_vehicle(
      env,
      spawned,
      kind="lead_vehicle_braking",
      route_s_m=route_s,
      lateral_m=0.0,
      speed_mps=desired * float(args.braking_lead_initial_speed_scale),
      accel_mps2=-abs(float(args.braking_lead_decel_mps2)),
      min_speed_mps=0.0,
      expected_lead_class="braking_lead",
      **route_vehicle_kwargs,
    )
  elif scene_name == "stopped_lead":
    _spawn_route_vehicle(
      env,
      spawned,
      kind="lead_vehicle_stopped",
      route_s_m=route_s,
      lateral_m=0.0,
      speed_mps=0.0,
      expected_lead_class="stopped_lead",
      **route_vehicle_kwargs,
    )
  elif scene_name == "cut_in_vehicle":
    start_lateral = float(args.cut_in_start_lateral_m)
    _spawn_route_vehicle(
      env,
      spawned,
      kind="cut_in_vehicle_entering",
      route_s_m=route_s,
      lateral_m=start_lateral,
      target_lateral_m=0.0,
      lateral_rate_mps=abs(float(args.cut_in_lateral_rate_mps)),
      speed_mps=desired * float(args.cut_in_speed_scale),
      expected_lead_class="cut_in_vehicle",
      **route_vehicle_kwargs,
    )
  elif scene_name == "crossing_vehicle":
    start_lateral = float(args.crossing_vehicle_start_lateral_m)
    _spawn_route_vehicle(
      env,
      spawned,
      kind="crossing_vehicle_conflict",
      route_s_m=route_s,
      lateral_m=start_lateral,
      target_lateral_m=-start_lateral,
      lateral_rate_mps=abs(float(args.crossing_vehicle_lateral_rate_mps)),
      speed_mps=desired * float(args.crossing_vehicle_longitudinal_speed_scale),
      expected_lead_class="crossing_vehicle",
      **route_vehicle_kwargs,
    )
  elif scene_name == "irrelevant_vehicle":
    lateral = float(args.irrelevant_vehicle_lateral_m)
    _spawn_route_vehicle(
      env,
      spawned,
      kind="irrelevant_vehicle",
      route_s_m=route_s,
      lateral_m=lateral,
      speed_mps=desired,
      expected_lead_class="irrelevant_vehicle",
      min_speed_mps=desired,
      max_speed_mps=desired,
      **route_vehicle_kwargs,
    )
  else:
    raise ValueError(f"unknown vehicle scene: {scene_name}")


def _spawn_random_mixed_scene(env, args: argparse.Namespace, spawned: list[dict[str, float | str]]) -> None:
  from metadrive.component.static_object.traffic_object import TrafficBarrier, TrafficCone
  from metadrive.component.traffic_participants.pedestrian import Pedestrian

  rng = np.random.default_rng(args.random_scene_seed)
  route_len = route_total_length_m(env)
  if route_len <= 1.0:
    route_len = args.random_scene_route_m
  end_s = min(route_len - 8.0, args.random_scene_route_m)
  start_s = 14.0

  construction_s = start_s
  cluster_id = 0
  while construction_s < end_s:
    side = "right" if rng.random() < args.random_construction_right_probability else "left"
    base_lateral = route_lateral_for_side_from_args(args, side, float(rng.uniform(1.05, 1.45)))
    cluster_len = int(rng.integers(2, args.random_construction_max_objects + 1))
    for idx in range(cluster_len):
      route_s = min(end_s, construction_s + idx * float(rng.uniform(4.0, 7.0)))
      lateral = base_lateral + float(rng.normal(0.0, 0.08))
      point, heading = route_point_at_s(env, route_s, lateral)
      cls = TrafficBarrier if idx == cluster_len // 2 and rng.random() < 0.45 else TrafficCone
      obj = env.engine.spawn_object(
        cls,
        position=[float(point[0]), float(point[1])],
        heading_theta=heading,
        force_spawn=True,
        static=True,
      )
      kind = "random_traffic_barrier" if cls is TrafficBarrier else "random_traffic_cone"
      spawned.append({
        "kind": kind,
        "route_s_m": float(route_s),
        "ahead_m": float(route_s),
        "lateral_m": float(lateral),
        "x": float(point[0]),
        "y": float(point[1]),
        "id": str(getattr(obj, "id", "")),
        "cluster": str(cluster_id),
      })
    construction_s += float(rng.uniform(args.random_construction_spacing_min_m, args.random_construction_spacing_max_m))
    cluster_id += 1

  pedestrians = []
  pedestrian_s = start_s + 8.0
  pedestrian_id = 0
  while pedestrian_s < end_s:
    start_side = "left" if rng.random() < 0.5 else "right"
    target_side = "right" if start_side == "left" else "left"
    start_lateral = route_lateral_for_side_from_args(args, start_side, float(rng.uniform(1.35, 1.75)))
    target_lateral = route_lateral_for_side_from_args(args, target_side, float(rng.uniform(1.20, 1.65)))
    start_sign = 1.0 if start_lateral >= 0.0 else -1.0
    start_point, heading = route_point_at_s(env, pedestrian_s, start_lateral)
    end_point, _ = route_point_at_s(env, pedestrian_s + float(rng.uniform(-1.5, 2.0)), target_lateral)
    direction = np.asarray(end_point - start_point, dtype=np.float32)
    if float(np.linalg.norm(direction)) < 1e-3:
      direction = np.asarray([0.0, -start_sign], dtype=np.float32)
    speed = float(rng.uniform(args.random_pedestrian_speed_min_mps, args.random_pedestrian_speed_max_mps))
    ped = env.engine.spawn_object(
      Pedestrian,
      position=[float(start_point[0]), float(start_point[1])],
      heading_theta=heading + (math.pi / 2.0) * -start_sign,
      force_spawn=True,
      random_seed=int(rng.integers(0, 2**31 - 1)),
    )
    ped.set_velocity(direction.tolist(), speed)
    record = {
      "kind": "moving_pedestrian_crossing",
      "route_s_m": float(pedestrian_s),
      "ahead_m": float(pedestrian_s),
      "lateral_m": float(start_lateral),
      "target_lateral_m": float(target_lateral),
      "x": float(start_point[0]),
      "y": float(start_point[1]),
      "id": str(getattr(ped, "id", "")),
      "speed_mps": speed,
      "pedestrian": str(pedestrian_id),
    }
    spawned.append(record)
    pedestrians.append({
      "obj": ped,
      "direction": (float(direction[0]), float(direction[1])),
      "speed_mps": speed,
      "target_lateral_m": float(target_lateral),
      "record": record,
    })
    pedestrian_s += float(rng.uniform(args.random_pedestrian_spacing_min_m, args.random_pedestrian_spacing_max_m))
    pedestrian_id += 1

  env._rtp_moving_pedestrians = pedestrians
  env._rtp_random_scene_route_len_m = route_len


def update_moving_pedestrians(env) -> None:
  movers = getattr(env, "_rtp_moving_pedestrians", [])
  if not movers:
    return
  current_long_m = current_route_longitudinal_m(env)
  for mover in movers:
    try:
      ped = mover["obj"]
      ped.set_velocity(list(mover["direction"]), float(mover["speed_mps"]))
      record = mover["record"]
      record["x"] = float(ped.position[0])
      record["y"] = float(ped.position[1])
      route_s_m, lateral_m = route_coordinates_for_position(env, ped.position)
      record["route_s_m"] = float(route_s_m)
      record["ahead_m"] = float(route_s_m - current_long_m)
      record["lateral_m"] = float(lateral_m)
    except Exception:
      continue


def update_controlled_vehicles(env, dt: float) -> None:
  vehicles = getattr(env, "_rtp_controlled_vehicles", [])
  if not vehicles:
    return
  dt = max(0.0, float(dt))
  current_long_m = current_route_longitudinal_m(env)
  for vehicle in vehicles:
    try:
      speed = float(vehicle["speed_mps"]) + float(vehicle["accel_mps2"]) * dt
      speed = max(float(vehicle["min_speed_mps"]), speed)
      max_speed = vehicle.get("max_speed_mps")
      if max_speed is not None:
        speed = min(float(max_speed), speed)
      route_s_m = float(vehicle["route_s_m"]) + speed * dt
      lateral_m = float(vehicle["lateral_m"])
      target_lateral_m = float(vehicle["target_lateral_m"])
      lateral_rate = abs(float(vehicle["lateral_rate_mps"]))
      if lateral_rate > 0.0:
        lateral_m = _slew(lateral_m, target_lateral_m, lateral_rate * dt)

      point, heading = route_point_at_s(env, route_s_m, lateral_m)
      visual_heading_offset_rad = float(getattr(env, "_rtp_route_vehicle_visual_heading_offset_rad", ROUTE_VEHICLE_VISUAL_HEADING_OFFSET_RAD))
      visual_heading = route_vehicle_visual_heading(heading, visual_heading_offset_rad)
      obj = vehicle["obj"]
      obj.set_position([float(point[0]), float(point[1])])
      obj.set_heading_theta(visual_heading)
      try:
        obj.set_velocity([math.cos(heading), math.sin(heading)], speed)
      except Exception:
        pass
      actual_heading = object_heading_theta(obj, visual_heading)
      heading_error = route_vehicle_heading_error_rad(heading, actual_heading)
      heading_alignment = math.cos(heading_error)

      vehicle["speed_mps"] = speed
      vehicle["route_s_m"] = route_s_m
      vehicle["lateral_m"] = lateral_m
      record = vehicle["record"]
      record["route_s_m"] = float(route_s_m)
      record["ahead_m"] = float(route_s_m - current_long_m)
      record["lateral_m"] = float(lateral_m)
      record["lateral_openpilot_m"] = float(route_to_openpilot_lateral_m_from_args(getattr(env, "_rtp_route_lateral_args", None), lateral_m))
      record["x"] = float(point[0])
      record["y"] = float(point[1])
      record["route_heading_theta"] = float(heading)
      record["visual_heading_theta"] = float(visual_heading)
      record["actual_heading_theta"] = float(actual_heading)
      record["route_heading_error_rad"] = float(heading_error)
      record["route_heading_alignment_cos"] = float(heading_alignment)
      record["route_heading_same_direction"] = bool(heading_alignment >= 0.0)
      record["visual_heading_offset_rad"] = float(visual_heading_offset_rad)
      record["speed_mps"] = float(speed)
    except Exception:
      continue


def _finite_float(value) -> float | None:
  try:
    result = float(value)
  except (TypeError, ValueError):
    return None
  return result if math.isfinite(result) else None


def nearest_route_vehicle_state(
  spawned_scene: list[dict[str, float | str]],
  current_long_m: float,
  ego_speed_mps: float,
  *,
  track_history: dict[str, dict[str, float]] | None = None,
  dt: float | None = None,
  route_lateral_sign_to_openpilot: float = 1.0,
  max_ahead_m: float = 90.0,
  max_behind_m: float = 3.0,
  max_lateral_m: float = 4.0,
) -> dict[str, float | int | str | None]:
  """Return production-style physical lead cues without copying sim labels.

  The keys mirror signals a road build can derive from model/radar/track fusion.
  This deliberately ignores expected_lead_class and object kind semantics except
  for selecting vehicle-like tracks from the sim harness.
  """
  empty: dict[str, float | int | str | None] = {
    "lead_present": 0,
    "lead_source": "none",
    "lead_distance_m": None,
    "lead_lateral_m": None,
    "lead_speed_mps": None,
    "lead_rel_speed_mps": None,
    "lead_closing_mps": None,
    "lead_accel_mps2": None,
    "lead_lateral_velocity_mps": None,
    "lead_route_heading_theta": None,
    "lead_actual_heading_theta": None,
    "lead_heading_error_rad": None,
    "lead_heading_alignment_cos": None,
    "lead_heading_same_direction": None,
  }
  candidates: list[tuple[float, dict[str, float | str], float, float, float, float, float | None, float | None, float | None, float | None, int | None]] = []
  history = track_history if track_history is not None else {}
  next_history: dict[str, dict[str, float]] = {}
  dt_s = max(0.0, float(dt or 0.0))
  lateral_sign = 1.0 if float(route_lateral_sign_to_openpilot) >= 0.0 else -1.0
  for idx, item in enumerate(spawned_scene):
    if not _spawned_kind_matches(item, VEHICLE_KIND_TOKENS):
      continue
    route_s_m = _finite_float(item.get("route_s_m"))
    lateral_m = _finite_float(item.get("lateral_m"))
    if route_s_m is None or lateral_m is None:
      continue
    track_key = str(item.get("id") or f"{idx}:{item.get('kind', 'vehicle')}")
    prev = history.get(track_key)
    if prev is not None and dt_s > 1e-4:
      speed_mps = (route_s_m - prev["route_s_m"]) / dt_s
      lateral_velocity_mps = (lateral_m - prev["lateral_m"]) / dt_s
      prev_speed_mps = prev.get("speed_mps", math.nan)
      accel_mps2 = (speed_mps - prev_speed_mps) / dt_s if math.isfinite(prev_speed_mps) else 0.0
    else:
      speed_mps = _finite_float(item.get("speed_mps"))
      if speed_mps is None:
        next_history[track_key] = {
          "route_s_m": float(route_s_m),
          "lateral_m": float(lateral_m),
          "speed_mps": math.nan,
        }
        continue
      lateral_velocity_mps = _finite_float(item.get("lateral_rate_mps"))
      accel_mps2 = _finite_float(item.get("accel_mps2"))
      lateral_velocity_mps = 0.0 if lateral_velocity_mps is None else lateral_velocity_mps
      accel_mps2 = 0.0 if accel_mps2 is None else accel_mps2
    next_history[track_key] = {
      "route_s_m": float(route_s_m),
      "lateral_m": float(lateral_m),
      "speed_mps": float(speed_mps),
    }
    ahead_m = route_s_m - float(current_long_m)
    if ahead_m < -float(max_behind_m) or ahead_m > float(max_ahead_m):
      continue
    lateral_openpilot_m = lateral_sign * lateral_m
    if abs(lateral_openpilot_m) > float(max_lateral_m):
      continue
    route_heading = _finite_float(item.get("route_heading_theta"))
    actual_heading = _finite_float(item.get("actual_heading_theta"))
    if actual_heading is None:
      actual_heading = _finite_float(item.get("visual_heading_theta"))
    heading_error = None
    heading_alignment = None
    same_direction = None
    if route_heading is not None and actual_heading is not None:
      heading_error = route_vehicle_heading_error_rad(route_heading, actual_heading)
      heading_alignment = math.cos(heading_error)
      same_direction = 1 if heading_alignment >= 0.0 else 0
    candidates.append((
      ahead_m,
      item,
      lateral_openpilot_m,
      speed_mps,
      accel_mps2,
      lateral_sign * lateral_velocity_mps,
      route_heading,
      actual_heading,
      heading_error,
      heading_alignment,
      same_direction,
    ))

  if track_history is not None:
    track_history.clear()
    track_history.update(next_history)

  if not candidates:
    return empty

  (
    ahead_m,
    _,
    lateral_m,
    lead_speed_mps,
    accel_mps2,
    lateral_velocity_mps,
    route_heading,
    actual_heading,
    heading_error,
    heading_alignment,
    same_direction,
  ) = min(candidates, key=lambda row: (row[0] < 0.0, abs(row[0])))
  rel_speed_mps = lead_speed_mps - float(ego_speed_mps)
  return {
    "lead_present": 1,
    "lead_source": "track",
    "lead_distance_m": float(ahead_m),
    "lead_lateral_m": float(lateral_m),
    "lead_speed_mps": float(lead_speed_mps),
    "lead_rel_speed_mps": float(rel_speed_mps),
    "lead_closing_mps": float(-rel_speed_mps),
    "lead_accel_mps2": float(accel_mps2),
    "lead_lateral_velocity_mps": float(lateral_velocity_mps),
    "lead_route_heading_theta": None if route_heading is None else float(route_heading),
    "lead_actual_heading_theta": None if actual_heading is None else float(actual_heading),
    "lead_heading_error_rad": None if heading_error is None else float(heading_error),
    "lead_heading_alignment_cos": None if heading_alignment is None else float(heading_alignment),
    "lead_heading_same_direction": None if same_direction is None else int(same_direction),
  }


def _spawn_stop_sign_billboard(env, x: float, y: float, lane_heading: float) -> None:
  from panda3d.core import CardMaker, TextNode

  root = env.engine.render.attachNewNode("rtp_stop_sign")
  root.setPos(x, y, 1.70)
  root.setHpr(math.degrees(lane_heading) + 90.0, 0.0, 0.0)
  root.setScale(1.10)

  card_maker = CardMaker("rtp_stop_sign_card")
  card_maker.setFrame(-1.0, 1.0, -1.0, 1.0)
  card = root.attachNewNode(card_maker.generate())
  card.setTwoSided(True)
  card.setLightOff(1)
  card.setTexture(_stop_sign_texture(env), 1)

  text_node = TextNode("rtp_stop_sign_billboard_text")
  text_node.setText("STOP")
  text_node.setAlign(TextNode.ACenter)
  text_node.setTextColor(1.0, 1.0, 1.0, 1.0)
  text = env.engine.render.attachNewNode(text_node)
  text.setPos(x, y - 0.05, 1.62)
  text.setScale(0.58)
  text.setLightOff(1)
  text.setBillboardPointEye()


def _spawn_traffic_light_billboard(env, x: float, y: float, lane_heading: float, state: str) -> dict:
  from panda3d.core import CardMaker, TransparencyAttrib

  root = env.engine.render.attachNewNode("rtp_controlled_traffic_light")
  root.setPos(x, y, 1.85)
  root.setHpr(math.degrees(lane_heading) + 90.0, 0.0, 0.0)
  root.setScale(1.35)

  card_maker = CardMaker("rtp_controlled_traffic_light_card")
  card_maker.setFrame(-1.0, 1.0, -1.0, 1.0)
  card = root.attachNewNode(card_maker.generate())
  card.setTwoSided(True)
  card.setLightOff(1)
  card.setTransparency(TransparencyAttrib.MAlpha)
  card.setColor(*_traffic_signal_color(state))
  card.setBillboardPointEye()
  return {"root": root, "card": card}


def _traffic_signal_color(state: str) -> tuple[float, float, float, float]:
  if state == "green":
    return 0.0, 1.0, 0.12, 1.0
  return 1.0, 0.0, 0.0, 1.0


def _stop_sign_texture(env):
  from panda3d.core import Filename, Texture
  from PIL import Image, ImageDraw, ImageFont

  texture_path = REPO_ROOT / "artifacts" / "reasoned_trajectory_poc" / "stop_sign_texture_opaque.png"
  if not texture_path.exists():
    texture_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (256, 256), (160, 0, 0))
    draw = ImageDraw.Draw(image)
    points = [
      (96, 10), (160, 10), (246, 96), (246, 160),
      (160, 246), (96, 246), (10, 160), (10, 96),
    ]
    draw.polygon(points, fill=(205, 0, 0), outline=(255, 255, 255))
    try:
      font = ImageFont.truetype("arial.ttf", 64)
    except Exception:
      font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "STOP", font=font)
    draw.text(((256 - (bbox[2] - bbox[0])) / 2, (256 - (bbox[3] - bbox[1])) / 2 - 8), "STOP", font=font, fill=(255, 255, 255))
    image.save(texture_path)
  texture = env.engine.loader.loadTexture(Filename.fromOsSpecific(str(texture_path)))
  texture.setMinfilter(Texture.FTLinear)
  texture.setMagfilter(Texture.FTLinear)
  return texture


def _traffic_signal_texture(env, state: str):
  from panda3d.core import Filename, Texture
  from PIL import Image, ImageDraw

  normalized = "green" if state == "green" else "red"
  texture_path = REPO_ROOT / "artifacts" / "reasoned_trajectory_poc" / f"traffic_signal_clean_v3_{normalized}.png"
  texture_path.parent.mkdir(parents=True, exist_ok=True)
  bg = (245, 245, 245)
  image = Image.new("RGB", (256, 256), bg)
  draw = ImageDraw.Draw(image)
  fill = (255, 0, 0) if normalized == "red" else (0, 235, 50)
  outline = (40, 40, 40)
  draw.rounded_rectangle((8, 8, 248, 248), radius=28, fill=bg, outline=outline, width=8)
  draw.ellipse((42, 42, 214, 214), fill=fill, outline=outline, width=6)
  image.save(texture_path)
  texture = env.engine.loader.loadTexture(Filename.fromOsSpecific(str(texture_path)))
  texture.setMinfilter(Texture.FTLinear)
  texture.setMagfilter(Texture.FTLinear)
  return texture


def camera_frame(env) -> np.ndarray:
  cam = env.engine.sensors["rgb_road"]
  frame = cam.perceive(to_float=False)
  if not isinstance(frame, np.ndarray):
    frame = frame.get()
  return _convert_camera_frame_color(frame, str(getattr(env, "_rtp_camera_color_order", "bgr")))


def _convert_camera_frame_color(frame: np.ndarray, camera_color_order: str) -> np.ndarray:
  frame = frame.astype(np.uint8, copy=False)
  if str(camera_color_order).lower() == "bgr":
    return frame[:, :, :3][:, :, ::-1].copy()
  return frame


def _traffic_light_visual_overlay(env, frame: np.ndarray, args: argparse.Namespace) -> np.ndarray:
  if args.disable_traffic_light_visual_overlay or not getattr(env, "_rtp_phase_traffic_lights", []):
    return frame
  state = str(getattr(env, "_rtp_traffic_light_state", ""))
  if state not in {"red", "green"}:
    return frame
  remaining_m = float(args.traffic_light_route_s) - current_route_longitudinal_m(env)
  if remaining_m < -8.0:
    return frame

  out = np.array(frame, copy=True)
  height, width = out.shape[:2]
  # Draw the simulated traffic signal as a clean UI-visible object instead of
  # using MetaDrive's dark 3D signal body, which the VLM misclassified as an obstacle.
  x = int(round(width * float(args.traffic_light_overlay_x_frac)))
  y_far = height * float(args.traffic_light_overlay_y_far_frac)
  y_near = height * float(args.traffic_light_overlay_y_near_frac)
  approach = 1.0 - np.clip(remaining_m / max(float(args.traffic_light_route_s), 1.0), 0.0, 1.0)
  y = int(round((1.0 - approach) * y_far + approach * y_near))
  radius = int(round(args.traffic_light_overlay_radius_px * (0.85 + 0.35 * approach)))
  radius = max(8, min(radius, width // 10, height // 10))

  body_w = int(round(radius * 2.6))
  body_h = int(round(radius * 6.0))
  body_x0 = max(0, x - body_w // 2)
  body_x1 = min(width, x + body_w // 2)
  body_y0 = max(0, y - body_h // 2)
  body_y1 = min(height, y + body_h // 2)
  out[body_y0:body_y1, body_x0:body_x1] = (
    0.65 * out[body_y0:body_y1, body_x0:body_x1].astype(np.float32) +
    0.35 * np.array((42, 48, 52), dtype=np.float32)
  ).astype(np.uint8)
  border = max(2, radius // 6)
  out[body_y0:min(height, body_y0 + border), body_x0:body_x1] = (230, 235, 238)
  out[max(0, body_y1 - border):body_y1, body_x0:body_x1] = (230, 235, 238)
  out[body_y0:body_y1, body_x0:min(width, body_x0 + border)] = (230, 235, 238)
  out[body_y0:body_y1, max(0, body_x1 - border):body_x1] = (230, 235, 238)

  yy, xx = np.ogrid[:height, :width]
  lamp_r = max(5, int(round(radius * 0.72)))
  lamp_spacing = max(lamp_r * 2 + 3, int(round(radius * 1.72)))
  active = {
    "red": np.array((238, 20, 20), dtype=np.uint8),
    "yellow": np.array((240, 188, 20), dtype=np.uint8),
    "green": np.array((20, 224, 60), dtype=np.uint8),
  }
  inactive = np.array((38, 43, 46), dtype=np.uint8)
  for idx, lamp_name in enumerate(("red", "yellow", "green")):
    cy = y + (idx - 1) * lamp_spacing
    dist2 = (xx - x) * (xx - x) + (yy - cy) * (yy - cy)
    outer = dist2 <= (lamp_r + 3) * (lamp_r + 3)
    inner = dist2 <= lamp_r * lamp_r
    out[outer] = np.array((245, 248, 250), dtype=np.uint8)
    out[inner] = active[lamp_name] if lamp_name == state else inactive
  return out


def _visual_traffic_signal_label_from_frame(frame: np.ndarray) -> str | None:
  arr = np.asarray(frame, dtype=np.int16)
  if arr.ndim != 3 or arr.shape[2] < 3:
    return None
  h, w = arr.shape[:2]
  roi = arr[int(h * 0.04):int(h * 0.50), int(w * 0.30):int(w * 0.74), :3]
  if roi.size == 0:
    return None
  red = (roi[:, :, 0] > 185) & (roi[:, :, 1] < 95) & (roi[:, :, 2] < 95)
  green = (roi[:, :, 1] > 170) & (roi[:, :, 0] < 95) & (roi[:, :, 2] < 140)
  red_count = int(red.sum())
  green_count = int(green.sum())
  min_pixels = 70
  if red_count >= min_pixels and red_count > green_count * 1.35:
    return "red_stop_light"
  if green_count >= min_pixels and green_count > red_count * 1.35:
    return "green_go_light"
  return None


def speed_mps(env) -> float:
  return float(np.linalg.norm(np.asarray(env.vehicle.velocity, dtype=np.float32)))


def route_lane_for_vehicle(env):
  vehicle = env.vehicle
  nav = getattr(vehicle, "navigation", None)
  ref_lanes = getattr(nav, "current_ref_lanes", None)
  if ref_lanes:
    if getattr(vehicle, "lane", None) in ref_lanes:
      return vehicle.lane
    lane_id = getattr(getattr(vehicle, "lane", None), "index", (None, None, 0))[2]
    if isinstance(lane_id, int) and 0 <= lane_id < len(ref_lanes):
      return ref_lanes[lane_id]
    return ref_lanes[0]
  return vehicle.lane


def next_route_lane(env, current_lane):
  nav = getattr(env.vehicle, "navigation", None)
  next_lanes = getattr(nav, "next_ref_lanes", None)
  if not next_lanes:
    return None
  lane_id = getattr(current_lane, "index", (None, None, 0))[2]
  if isinstance(lane_id, int) and 0 <= lane_id < len(next_lanes):
    return next_lanes[lane_id]
  return next_lanes[0]


def route_world_point(env, ahead_m: float, lateral_offset_m: float) -> np.ndarray:
  lane = route_lane_for_vehicle(env)
  long_m, _ = lane.local_coordinates(env.vehicle.position)
  target_long = long_m + ahead_m
  target_lane = lane
  if target_long > lane.length:
    overflow = target_long - lane.length
    next_lane = next_route_lane(env, lane)
    if next_lane is not None:
      target_lane = next_lane
      target_long = min(max(0.0, overflow), next_lane.length)
    else:
      target_long = lane.length
  else:
    target_long = min(max(0.0, target_long), lane.length)

  half_width = max(0.1, float(target_lane.width_at(target_long)) * 0.5 - 0.45)
  return np.asarray(target_lane.position(target_long, float(np.clip(lateral_offset_m, -half_width, half_width))), dtype=np.float32)


def world_to_ego(env, point: np.ndarray) -> tuple[float, float]:
  vehicle = env.vehicle
  dx = float(point[0] - vehicle.position[0])
  dy = float(point[1] - vehicle.position[1])
  heading = float(vehicle.heading_theta)
  cos_h = math.cos(heading)
  sin_h = math.sin(heading)
  forward = dx * cos_h + dy * sin_h
  left = -dx * sin_h + dy * cos_h
  return forward, left


def selected_lateral_offset_m(synth) -> float:
  if synth is None:
    return 0.0
  for candidate in synth.candidates:
    if candidate.name == synth.selected_candidate:
      return float(candidate.lateral_offset_m)
  return 0.0


construction_hazard_side_from_token = construction_hazard_side_from_avoid_token
construction_avoidance_side_valid = construction_avoidance_metadrive_side_valid


@dataclass
class DurableAvoidance:
  start_long_m: float
  end_long_m: float
  ramp_in_start_long_m: float
  ramp_out_end_long_m: float
  offset_m: float
  source_token: str
  source_meta: str
  confidence: float

  def active(self, current_long_m: float) -> bool:
    return current_long_m <= self.ramp_out_end_long_m

  def target_offset(self, current_long_m: float) -> float:
    if current_long_m < self.ramp_in_start_long_m or current_long_m > self.ramp_out_end_long_m:
      return 0.0
    if current_long_m < self.start_long_m:
      span = max(0.1, self.start_long_m - self.ramp_in_start_long_m)
      return self.offset_m * _smoothstep((current_long_m - self.ramp_in_start_long_m) / span)
    if current_long_m <= self.end_long_m:
      return self.offset_m
    span = max(0.1, self.ramp_out_end_long_m - self.end_long_m)
    return self.offset_m * (1.0 - _smoothstep((current_long_m - self.end_long_m) / span))


@dataclass
class DurableLateralOverrideState:
  pending_source_token: str = ""
  pending_sign: int = 0
  pending_count: int = 0
  pending_observation_id: int | None = None

  def reset(self) -> None:
    self.pending_source_token = ""
    self.pending_sign = 0
    self.pending_count = 0
    self.pending_observation_id = None


@dataclass
class DurableSpeedPlan:
  start_long_m: float
  end_long_m: float
  ramp_out_end_long_m: float
  speed_cap_mps: float
  stop_s: float | None
  source_token: str
  source_meta: str
  confidence: float

  def active(self, current_long_m: float) -> bool:
    return current_long_m <= self.ramp_out_end_long_m

  def target_speed_cap(self, current_long_m: float, nominal_speed_mps: float) -> float:
    if self.stop_s is not None:
      stop_cap = _distance_aware_stop_speed_cap(
        self.start_long_m,
        current_long_m,
        float(self.stop_s),
        nominal_speed_mps,
      )
      if self.speed_cap_mps > 1e-3:
        stop_cap = min(stop_cap, self.speed_cap_mps)
      return stop_cap
    if current_long_m > self.ramp_out_end_long_m:
      return nominal_speed_mps
    if current_long_m <= self.end_long_m:
      return self.speed_cap_mps
    span = max(0.1, self.ramp_out_end_long_m - self.end_long_m)
    blend = _smoothstep((current_long_m - self.end_long_m) / span)
    return self.speed_cap_mps + (nominal_speed_mps - self.speed_cap_mps) * blend


def _smoothstep(raw: float) -> float:
  x = float(np.clip(raw, 0.0, 1.0))
  return x * x * (3.0 - 2.0 * x)


GENERIC_STOP_HOLD_RADIUS_M = 4.0
GENERIC_STOP_COMFORT_DECEL_MPS2 = 1.1


def _distance_aware_stop_speed_cap(start_long_m: float, current_long_m: float, stop_s: float, nominal_speed_mps: float) -> float:
  stop_long_m = start_long_m + max(0.0, stop_s)
  remaining_m = stop_long_m - current_long_m
  hold_radius_m = GENERIC_STOP_HOLD_RADIUS_M
  if remaining_m <= hold_radius_m:
    return 0.0
  decel_mps2 = max(0.1, GENERIC_STOP_COMFORT_DECEL_MPS2)
  stopping_cap = math.sqrt(max(0.0, 2.0 * decel_mps2 * (remaining_m - hold_radius_m)))
  return float(np.clip(stopping_cap, 0.0, nominal_speed_mps))


def _slew(current: float, target: float, max_delta: float) -> float:
  return float(current + np.clip(target - current, -max_delta, max_delta))


def current_route_longitudinal_m(env) -> float:
  route_s_m, _ = route_coordinates_for_position(env, env.vehicle.position)
  return route_s_m


def durable_avoidance_from_program(program, current_long_m: float, selected_offset_m: float, args: argparse.Namespace) -> DurableAvoidance | None:
  if program is None or not program.avoid:
    return None

  for token in program.avoid:
    match = AVOID_ZONE_RE.match(token)
    if match is None:
      continue
    side = match.group("side")
    start_s = float(match.group("start"))
    end_s = float(match.group("end"))
    if end_s <= start_s:
      continue

    if side == "corridor_object" and abs(selected_offset_m) <= 1e-3:
      continue

    margin_raw = match.group("margin")
    requested_margin = float(margin_raw) if margin_raw is not None else abs(selected_offset_m)
    offset_mag = max(abs(selected_offset_m), requested_margin, args.min_construction_offset_m)
    offset_mag = min(offset_mag, args.max_durable_offset_m)

    hazard_side = construction_hazard_side_from_token(token)
    if hazard_side in {"left", "right"}:
      target_side = "left" if hazard_side == "right" else "right"
      offset_m = route_lateral_for_side_from_args(args, target_side, offset_mag)
    else:
      offset_m = float(openpilot_to_route_lateral_m_from_args(args, selected_offset_m)) if abs(selected_offset_m) > 1e-3 else 0.0

    plan = DurableAvoidance(
      start_long_m=current_long_m + start_s,
      end_long_m=current_long_m + end_s,
      ramp_in_start_long_m=current_long_m + max(0.0, start_s - args.avoid_lead_m),
      ramp_out_end_long_m=current_long_m + end_s + args.avoid_recover_m,
      offset_m=offset_m,
      source_token=token,
      source_meta=str(getattr(program, "meta", "")),
      confidence=float(getattr(program, "confidence", 0.0)),
    )
    return plan if durable_avoidance_sign_valid_for_args(plan, args) else None
  return None


def durable_speed_plan_from_program(program, current_long_m: float, args: argparse.Namespace) -> DurableSpeedPlan | None:
  if program is None or not _program_requests_durable_speed(program):
    return None

  cap = args.speed_mps
  has_explicit_speed_cap = getattr(program, "speed_scale", None) is not None or program.speed_cap_mps is not None
  if getattr(program, "speed_scale", None) is not None:
    cap = min(cap, args.speed_mps * float(np.clip(program.speed_scale, 0.0, 1.0)))
  if program.speed_cap_mps is not None:
    cap = min(cap, float(program.speed_cap_mps))
  elif not has_explicit_speed_cap and getattr(program, "meta", "") in {"STOP", "YIELD"}:
    cap = 0.0
  elif not has_explicit_speed_cap and getattr(program, "meta", "") in {"SLOW", "BIAS_LEFT_AND_SLOW", "BIAS_RIGHT_AND_SLOW", "OCCLUSION_CAUTION", "EMERGENCY_CAUTION"}:
    cap = min(cap, args.speed_mps * float(np.clip(args.durable_slow_speed_scale, 0.0, 1.0)))

  if program.stop_s is not None:
    cap = min(cap, _stop_speed_cap_for_demo(float(program.stop_s), args.speed_mps))

  if cap >= args.speed_mps - 1e-3 and program.stop_s is None:
    return None

  source_token, start_s, end_s = _speed_plan_interval(program, args)
  if program.stop_s is not None:
    end_s = max(end_s, float(program.stop_s))
  end_s = max(end_s, args.durable_speed_min_horizon_m)

  return DurableSpeedPlan(
    start_long_m=current_long_m,
    end_long_m=current_long_m + end_s,
    ramp_out_end_long_m=current_long_m + end_s + args.durable_speed_recover_m,
    speed_cap_mps=float(np.clip(cap, 0.0, args.speed_mps)),
    stop_s=None if program.stop_s is None else float(program.stop_s),
    source_token=source_token,
    source_meta=str(getattr(program, "meta", "")),
    confidence=float(getattr(program, "confidence", 0.0)),
  )


def _merge_durable_avoidance(existing: DurableAvoidance, new: DurableAvoidance) -> DurableAvoidance:
  offset_m = existing.offset_m
  if _lateral_sign(existing.offset_m) != _lateral_sign(new.offset_m):
    offset_m = new.offset_m
  elif abs(new.offset_m) > abs(existing.offset_m):
    offset_m = new.offset_m
  return DurableAvoidance(
    start_long_m=min(existing.start_long_m, new.start_long_m),
    end_long_m=max(existing.end_long_m, new.end_long_m),
    ramp_in_start_long_m=min(existing.ramp_in_start_long_m, new.ramp_in_start_long_m),
    ramp_out_end_long_m=max(existing.ramp_out_end_long_m, new.ramp_out_end_long_m),
    offset_m=offset_m,
    source_token=existing.source_token,
    source_meta=new.source_meta,
    confidence=max(existing.confidence, new.confidence),
  )


def _merge_durable_speed_plan(existing: DurableSpeedPlan, new: DurableSpeedPlan) -> DurableSpeedPlan:
  # Same-source speed plans represent updated judgement about the same hazard.
  # Keep the broader spatial interval, but let the newest cap/stop decision replace
  # a stale stricter one so a transient YIELD cannot pin the car at zero forever.
  return DurableSpeedPlan(
    start_long_m=min(existing.start_long_m, new.start_long_m),
    end_long_m=max(existing.end_long_m, new.end_long_m),
    ramp_out_end_long_m=max(existing.ramp_out_end_long_m, new.ramp_out_end_long_m),
    speed_cap_mps=new.speed_cap_mps,
    stop_s=new.stop_s,
    source_token=existing.source_token,
    source_meta=new.source_meta,
    confidence=max(existing.confidence, new.confidence),
  )


def _lateral_conflict_override_allowed(
  updated: dict[str, DurableAvoidance],
  new: DurableAvoidance,
  args: argparse.Namespace,
  override_state: DurableLateralOverrideState | None,
  rtp_source_frame_id: int | None = None,
) -> bool:
  conflicts = [plan for plan in updated.values() if _lateral_plans_conflict(plan, new)]
  if not conflicts:
    activation_confidence = float(getattr(args, "durable_lateral_activation_confidence", getattr(args, "durable_override_confidence", 0.70)))
    if new.confidence < activation_confidence:
      if override_state is not None:
        override_state.reset()
      return False
    activation_immediate_confidence = float(getattr(args, "durable_lateral_activation_immediate_confidence", 0.95))
    if new.confidence >= activation_immediate_confidence:
      if override_state is not None:
        override_state.reset()
      return True
    required_activation_count = max(1, int(getattr(args, "durable_lateral_activation_confirm_frames", 2)))
    if required_activation_count > 1 and override_state is not None:
      new_sign = _lateral_sign(new.offset_m)
      if override_state.pending_source_token == new.source_token and override_state.pending_sign == new_sign:
        if rtp_source_frame_id is None or override_state.pending_observation_id != rtp_source_frame_id:
          override_state.pending_count += 1
          override_state.pending_observation_id = rtp_source_frame_id
      else:
        override_state.pending_source_token = new.source_token
        override_state.pending_sign = new_sign
        override_state.pending_count = 1
        override_state.pending_observation_id = rtp_source_frame_id
      if override_state.pending_count < required_activation_count:
        return False
    if override_state is not None:
      override_state.reset()
    return True

  immediate_confidence = float(getattr(args, "durable_conflict_immediate_confidence", 0.95))
  if _construction_lateral_conflict(conflicts, new):
    immediate_confidence = float(getattr(args, "durable_construction_conflict_immediate_confidence", max(immediate_confidence, 0.95)))
  if new.confidence >= immediate_confidence:
    if override_state is not None:
      override_state.reset()
    return True

  conflict_confidence = float(getattr(args, "durable_conflict_override_confidence", 0.80))
  if new.confidence < conflict_confidence:
    if override_state is not None:
      override_state.reset()
    return False

  required_count = max(1, int(getattr(args, "durable_conflict_confirm_frames", 3)))
  if required_count <= 1 or override_state is None:
    if override_state is not None:
      override_state.reset()
    return True

  new_sign = _lateral_sign(new.offset_m)
  if override_state.pending_source_token == new.source_token and override_state.pending_sign == new_sign:
    if rtp_source_frame_id is None or override_state.pending_observation_id != rtp_source_frame_id:
      override_state.pending_count += 1
      override_state.pending_observation_id = rtp_source_frame_id
  else:
    override_state.pending_source_token = new.source_token
    override_state.pending_sign = new_sign
    override_state.pending_count = 1
    override_state.pending_observation_id = rtp_source_frame_id

  if override_state.pending_count >= required_count:
    override_state.reset()
    return True
  return False


def update_durable_lateral_plans(
  plans: dict[str, DurableAvoidance],
  new: DurableAvoidance | None,
  program,
  current_long_m: float,
  args: argparse.Namespace,
  override_state: DurableLateralOverrideState | None = None,
  rtp_source_frame_id: int | None = None,
) -> dict[str, DurableAvoidance]:
  updated = {
    key: plan for key, plan in plans.items()
    if plan.active(current_long_m) and durable_avoidance_sign_valid_for_args(plan, args)
  }
  if _program_clears_lateral(program) and _program_confidence(program) > args.durable_override_confidence:
    updated.clear()
    if override_state is not None:
      override_state.reset()

  if new is None:
    if override_state is not None:
      override_state.reset()
    return updated

  if not _lateral_conflict_override_allowed(updated, new, args, override_state, rtp_source_frame_id):
    return updated

  if _program_confidence(program) >= args.durable_override_confidence:
    if new.offset_m > 0.0:
      updated = {key: plan for key, plan in updated.items() if plan.offset_m >= 0.0}
    elif new.offset_m < 0.0:
      updated = {key: plan for key, plan in updated.items() if plan.offset_m <= 0.0}
  elif new.confidence >= args.durable_conflict_override_confidence:
    updated = {
      key: plan for key, plan in updated.items()
      if not _lateral_plans_conflict(plan, new)
    }

  existing = updated.get(new.source_token)
  updated[new.source_token] = new if existing is None else _merge_durable_avoidance(existing, new)
  return updated


def update_durable_speed_plans(plans: dict[str, DurableSpeedPlan], new: DurableSpeedPlan | None, program, current_long_m: float, args: argparse.Namespace) -> dict[str, DurableSpeedPlan]:
  updated = {key: plan for key, plan in plans.items() if plan.active(current_long_m)}
  signal_clear_confidence = float(getattr(args, "durable_signal_clear_confidence", args.durable_override_confidence))
  if _program_clears_signal_stop(program) and _program_confidence(program) >= signal_clear_confidence:
    updated = {
      key: plan for key, plan in updated.items()
      if key != "traffic_light_stop" and not key.startswith("stop_line_s")
    }
  if _program_clears_agent_speed(program) and _program_confidence(program) >= args.durable_conflict_override_confidence:
    updated = {
      key: plan for key, plan in updated.items()
      if not _is_agent_speed_source(key)
    }
  elif _program_clears_speed(program) and _program_confidence(program) >= args.durable_override_confidence:
    updated = {
      key: plan for key, plan in updated.items()
      if key == "traffic_light_stop" or key.startswith("stop_line_s")
    }

  if new is None:
    return updated

  if new.source_token == "traffic_light_stop":
    updated.clear()

  existing = updated.get(new.source_token)
  updated[new.source_token] = new if existing is None else _merge_durable_speed_plan(existing, new)
  return updated


def _clear_signal_speed_plans(plans: dict[str, DurableSpeedPlan]) -> dict[str, DurableSpeedPlan]:
  return {
    key: plan for key, plan in plans.items()
    if key != "traffic_light_stop" and not key.startswith("stop_line_s")
  }


def _is_agent_speed_source(source_token: str) -> bool:
  return source_token.startswith(("corridor_object", "lead_vehicle", "cut_in_vehicle", "crossing_vehicle"))


def _is_lead_speed_source(source_token: str) -> bool:
  return source_token.startswith("lead_vehicle")


def _clear_lead_speed_plans(plans: dict[str, DurableSpeedPlan]) -> dict[str, DurableSpeedPlan]:
  return {
    key: plan for key, plan in plans.items()
    if not _is_lead_speed_source(key)
  }


def _physical_lead_clear_reason(lead_state: dict[str, float | int | str | None], args: argparse.Namespace, *, allow_true_moving_clear: bool) -> str:
  if int(lead_state.get("lead_present") or 0) != 1:
    return "no_lead_track"

  distance_m = _finite_float(lead_state.get("lead_distance_m"))
  lateral_m = _finite_float(lead_state.get("lead_lateral_m"))
  if distance_m is None or distance_m < -0.5:
    return "lead_not_ahead"
  if lateral_m is None:
    return "lead_lateral_unknown"
  if abs(lateral_m) > float(getattr(args, "lead_clear_path_lateral_m", 1.35)):
    return "lead_outside_path"
  if not allow_true_moving_clear:
    return ""

  rel_speed_mps = _finite_float(lead_state.get("lead_rel_speed_mps"))
  closing_mps = _finite_float(lead_state.get("lead_closing_mps"))
  accel_mps2 = _finite_float(lead_state.get("lead_accel_mps2"))
  if rel_speed_mps is None or closing_mps is None or accel_mps2 is None:
    return ""
  max_true_lead_closing = float(getattr(args, "lead_clear_true_moving_closing_mps", 0.35))
  max_true_lead_rel_loss = float(getattr(args, "lead_clear_true_moving_rel_loss_mps", 0.35))
  min_non_braking_accel = -abs(float(getattr(args, "lead_clear_non_braking_accel_mps2", 0.60)))
  if (
    closing_mps <= max_true_lead_closing and
    rel_speed_mps >= -max_true_lead_rel_loss and
    accel_mps2 >= min_non_braking_accel
  ):
    return "true_moving_or_opening_lead"
  return ""


def _apply_current_lead_state_guard(
  plans: dict[str, DurableSpeedPlan],
  lead_state: dict[str, float | int | str | None],
  args: argparse.Namespace,
  *,
  allow_true_moving_clear: bool,
) -> dict[str, DurableSpeedPlan]:
  reason = _physical_lead_clear_reason(lead_state, args, allow_true_moving_clear=allow_true_moving_clear)
  if not reason:
    return plans
  return _clear_lead_speed_plans(plans)


def _apply_current_visual_signal_guard(
  plans: dict[str, DurableSpeedPlan],
  visual_signal_label: str | None,
  current_long_m: float,
  args: argparse.Namespace,
) -> dict[str, DurableSpeedPlan]:
  if _passed_traffic_light_stop(current_long_m, args):
    return _clear_signal_speed_plans(plans)
  if visual_signal_label == "green_go_light":
    return _clear_signal_speed_plans(plans)
  if visual_signal_label != "red_stop_light" or args.disable_vlm_speed_control:
    return plans

  visual_red_program = argparse.Namespace(
    meta="STOP",
    evidence=("red_signal_for_path",),
    confidence=max(args.durable_conflict_override_confidence, 0.74),
  )
  visual_red_plan = _adjust_signal_speed_plan(None, visual_red_program, current_long_m, args)
  if visual_red_plan is None:
    return plans
  return update_durable_speed_plans(plans, visual_red_plan, visual_red_program, current_long_m, args)


def _should_apply_visual_signal_guard(mode: str, args: argparse.Namespace, visual_signal_label: str | None) -> bool:
  return (
    mode == "vlm"
    and bool(getattr(args, "enable_visual_signal_guard", False))
    and not bool(getattr(args, "disable_vlm_speed_control", False))
    and visual_signal_label in {"red_stop_light", "green_go_light"}
  )


def _adjust_signal_speed_plan(new: DurableSpeedPlan | None, program, current_long_m: float, args: argparse.Namespace) -> DurableSpeedPlan | None:
  if program is None or not _traffic_light_enabled(args) or getattr(program, "meta", "") != "STOP":
    return new
  if "red_signal_for_path" not in tuple(getattr(program, "evidence", ())):
    return new

  stop_long_m = _traffic_light_stop_line_m(args)
  remaining_m = stop_long_m - current_long_m
  if remaining_m < -_traffic_light_passed_ignore_m(args):
    return None
  hold_radius_m = max(0.0, float(getattr(args, "traffic_light_stop_hold_radius_m", 0.75)))
  full_stop_m = max(hold_radius_m, float(getattr(args, "traffic_light_full_stop_m", hold_radius_m)))
  decel_distance_m = max(full_stop_m + 0.1, float(args.traffic_light_decel_distance_m))
  if remaining_m <= full_stop_m:
    cap = 0.0
  elif remaining_m >= decel_distance_m:
    cap = args.speed_mps
  else:
    span = decel_distance_m - full_stop_m
    linear_cap = args.speed_mps * (remaining_m - full_stop_m) / span
    decel_mps2 = max(0.1, float(getattr(args, "traffic_light_comfort_decel_mps2", 1.1)))
    stopping_cap = math.sqrt(max(0.0, 2.0 * decel_mps2 * (remaining_m - full_stop_m)))
    cap = min(linear_cap, stopping_cap)

  return DurableSpeedPlan(
    start_long_m=current_long_m,
    end_long_m=max(stop_long_m, current_long_m + (args.durable_speed_min_horizon_m if remaining_m <= full_stop_m else 0.0)),
    ramp_out_end_long_m=max(stop_long_m, current_long_m + (args.durable_speed_min_horizon_m if remaining_m <= full_stop_m else 0.0)) + args.durable_speed_recover_m,
    speed_cap_mps=float(np.clip(cap, 0.0, args.speed_mps)),
    stop_s=max(0.0, remaining_m),
    source_token="traffic_light_stop",
    source_meta="STOP",
    confidence=float(getattr(program, "confidence", 0.0)),
  )


def _traffic_light_enabled(args: argparse.Namespace) -> bool:
  return bool(args.include_traffic_light or args.novel_scene in {"traffic_light", "stop_sign"})


def _traffic_light_stop_line_m(args: argparse.Namespace) -> float:
  return max(0.0, float(args.traffic_light_route_s) - float(args.traffic_light_stop_before_m))


def _traffic_light_passed_ignore_m(args: argparse.Namespace) -> float:
  return max(0.0, float(getattr(args, "traffic_light_passed_ignore_m", 2.0)))


def _passed_traffic_light_stop(current_long_m: float, args: argparse.Namespace) -> bool:
  return _traffic_light_enabled(args) and current_long_m > _traffic_light_stop_line_m(args) + _traffic_light_passed_ignore_m(args)


def _traffic_light_first_green_frame(args: argparse.Namespace) -> int:
  return int(args.traffic_light_red_frames if args.traffic_light_cycle else args.traffic_light_green_frame)


def active_lateral_plans(plans: dict[str, DurableAvoidance], current_long_m: float) -> list[DurableAvoidance]:
  return [plan for plan in plans.values() if plan.active(current_long_m)]


def active_speed_plans(plans: dict[str, DurableSpeedPlan], current_long_m: float) -> list[DurableSpeedPlan]:
  return [plan for plan in plans.values() if plan.active(current_long_m)]


def _lateral_sign(offset_m: float) -> int:
  if offset_m > 1e-3:
    return 1
  if offset_m < -1e-3:
    return -1
  return 0


def _lateral_plans_conflict(existing: DurableAvoidance, new: DurableAvoidance) -> bool:
  existing_sign = _lateral_sign(existing.offset_m)
  new_sign = _lateral_sign(new.offset_m)
  return existing_sign != 0 and new_sign != 0 and existing_sign != new_sign


def _is_construction_edge_token(source_token: str) -> bool:
  return source_token.startswith(("right_edge_", "left_edge_"))


def _construction_lateral_conflict(conflicts: Sequence[DurableAvoidance], new: DurableAvoidance) -> bool:
  return _is_construction_edge_token(new.source_token) and any(_is_construction_edge_token(plan.source_token) for plan in conflicts)


def durable_avoidance_sign_valid(plan: DurableAvoidance) -> bool:
  """Validate that a MetaDrive lateral target moves away from its avoid edge."""
  return construction_avoidance_side_valid(plan.source_token, plan.offset_m)


def durable_avoidance_sign_valid_for_args(plan: DurableAvoidance, args: argparse.Namespace | None) -> bool:
  """Validate route-lane target side after converting through the calibrated adapter."""
  return construction_avoidance_route_side_valid(plan.source_token, plan.offset_m, _route_lateral_sign_from_args(args))


def compose_lateral_offset(plans: dict[str, DurableAvoidance], current_long_m: float, max_offset_m: float) -> float:
  offsets = [plan.target_offset(current_long_m) for plan in active_lateral_plans(plans, current_long_m)]
  offsets = [offset for offset in offsets if abs(offset) > 1e-3]
  if not offsets:
    return 0.0
  strongest = max(offsets, key=abs)
  return float(np.clip(strongest, -max_offset_m, max_offset_m))


def compose_lateral_offset_after_publish(
  plans: dict[str, DurableAvoidance],
  current_long_m: float,
  max_offset_m: float,
  compiled_lateral_offset_openpilot_m: float | None,
  args: argparse.Namespace,
) -> tuple[float, bool]:
  durable_offset_m = compose_lateral_offset(plans, current_long_m, max_offset_m)
  if plans or abs(durable_offset_m) > 1e-3:
    return durable_offset_m, False
  if compiled_lateral_offset_openpilot_m is None or not bool(getattr(args, "allow_compiled_lateral_fallback", False)):
    return durable_offset_m, False
  return float(openpilot_to_route_lateral_m_from_args(args, compiled_lateral_offset_openpilot_m)), True


def compose_speed_cap(plans: dict[str, DurableSpeedPlan], current_long_m: float, nominal_speed_mps: float) -> float | None:
  caps = [plan.target_speed_cap(current_long_m, nominal_speed_mps) for plan in active_speed_plans(plans, current_long_m)]
  caps = [float(np.clip(cap, 0.0, nominal_speed_mps)) for cap in caps if cap < nominal_speed_mps - 1e-3]
  return min(caps) if caps else None


def _program_requests_durable_speed(program) -> bool:
  if program is None:
    return False
  return (
    getattr(program, "speed_cap_mps", None) is not None
    or getattr(program, "speed_scale", None) is not None
    or getattr(program, "stop_s", None) is not None
    or getattr(program, "meta", "") in {
      "BIAS_LEFT_AND_SLOW",
      "BIAS_RIGHT_AND_SLOW",
      "SLOW",
      "YIELD",
      "STOP",
      "OCCLUSION_CAUTION",
      "EMERGENCY_CAUTION",
    }
  )


def _program_clears_lateral(program) -> bool:
  if program is None:
    return False
  scene = str(getattr(program, "scene", ""))
  evidence = tuple(str(item) for item in getattr(program, "evidence", ()))
  if scene == "construction_presence_unknown" or any("cones_barrier" in item or "construction" in item for item in evidence):
    return False
  return (
    getattr(program, "meta", "") == "BASE"
    and not getattr(program, "avoid", ())
    and abs(float(getattr(program, "lat_bias_m", 0.0))) <= 1e-3
  )


def _program_clears_speed(program) -> bool:
  if program is None:
    return False
  return (
    getattr(program, "meta", "") == "BASE"
    and not getattr(program, "avoid", ())
    and getattr(program, "speed_cap_mps", None) is None
    and getattr(program, "speed_scale", None) is None
    and getattr(program, "stop_s", None) is None
  )


def _program_clears_agent_speed(program) -> bool:
  if program is None:
    return False
  avoid = tuple(getattr(program, "avoid", ()))
  evidence = tuple(str(item) for item in getattr(program, "evidence", ()))
  if any(item in {"true_moving_lead", "irrelevant_vehicle"} for item in evidence):
    return True
  has_agent_evidence = any(
    token in item
    for item in evidence
    for token in ("agent", "pedestrian", "vehicle", "animal", "slower_lead", "braking_lead", "stopped_lead", "cut_in", "crossing")
  )
  return (
    getattr(program, "meta", "") not in {"STOP", "YIELD"}
    and getattr(program, "stop_s", None) is None
    and not any(_is_agent_speed_source(str(token)) for token in avoid)
    and not has_agent_evidence
  )


def _program_clears_signal_stop(program) -> bool:
  if program is None:
    return False
  evidence = tuple(str(item) for item in getattr(program, "evidence", ()))
  return (
    "green_signal_for_path" in evidence
    and "red_signal_for_path" not in evidence
    and "stop_sign_for_path" not in evidence
  )


def _speed_plan_interval(program, args: argparse.Namespace) -> tuple[str, float, float]:
  avoid = tuple(getattr(program, "avoid", ()))
  preferred_sides: tuple[str, ...]
  if getattr(program, "meta", "") in {"STOP", "YIELD"} or getattr(program, "stop_s", None) is not None:
    preferred_sides = ("stop_line", "lead_vehicle", "cut_in_vehicle", "crossing_vehicle", "corridor_object", "right_edge", "left_edge")
  else:
    preferred_sides = ("lead_vehicle", "cut_in_vehicle", "crossing_vehicle", "right_edge", "left_edge", "corridor_object", "stop_line")

  parsed: list[tuple[str, str, float, float]] = []
  for token in avoid:
    interval = _parse_plan_interval_token(token)
    if interval is not None:
      side, start_s, end_s = interval
      parsed.append((token, side, start_s, end_s))

  for side in preferred_sides:
    for token, parsed_side, start_s, end_s in parsed:
      if parsed_side == side:
        return token, start_s, end_s

  if getattr(program, "stop_s", None) is not None:
    stop_s = float(program.stop_s)
    return f"stop_s{stop_s:.1f}", max(0.0, stop_s - args.avoid_lead_m), stop_s + args.avoid_recover_m

  return str(getattr(program, "meta", "speed")), 0.0, args.durable_speed_min_horizon_m


def _parse_plan_interval_token(token: str) -> tuple[str, float, float] | None:
  match = AVOID_ZONE_RE.match(token)
  if match is not None:
    start_s = float(match.group("start"))
    end_s = float(match.group("end"))
    if end_s > start_s:
      return match.group("side"), start_s, end_s

  stop_match = STOP_LINE_RE.match(token)
  if stop_match is not None:
    distance = float(stop_match.group("distance"))
    return "stop_line", max(0.0, distance - 4.0), distance + 6.0

  return None


def _stop_speed_cap_for_demo(stop_s: float, desired_speed_mps: float) -> float:
  if stop_s <= 20.0:
    return 0.0
  if stop_s <= 40.0:
    return desired_speed_mps * 0.2
  return desired_speed_mps * 0.4


def _program_confidence(program) -> float:
  return 0.0 if program is None else float(getattr(program, "confidence", 0.0))


def _lead_class_from_program(program) -> str:
  if program is None:
    return ""
  evidence = set(str(item) for item in getattr(program, "evidence", ()))
  for label in (
    "true_moving_lead",
    "slower_lead_closing",
    "braking_lead_closing",
    "stopped_lead_in_path",
    "cut_in_vehicle_entering_path",
    "crossing_vehicle_conflict",
    "irrelevant_vehicle",
  ):
    if label in evidence:
      return label
  scene = str(getattr(program, "scene", ""))
  for label in ("true_moving_lead", "slower_lead", "braking_lead", "stopped_lead", "cut_in_vehicle", "crossing_vehicle", "irrelevant_vehicle"):
    if label in scene:
      return label
  return ""


def _expected_lead_class_from_spawned(spawned_scene: list[dict[str, float | str]]) -> str:
  for item in spawned_scene:
    expected = str(item.get("expected_lead_class", ""))
    if expected:
      return expected
  return ""


def _spawned_kind_matches(item: dict[str, float | str], kind_tokens: tuple[str, ...] | None) -> bool:
  if kind_tokens is None:
    return True
  kind = str(item.get("kind", "")).lower()
  return any(token in kind for token in kind_tokens)


def spawned_min_distance_m(env, spawned_scene: list[dict[str, float | str]], kind_tokens: tuple[str, ...] | None = None) -> float | None:
  vehicle_pos = np.asarray(env.vehicle.position, dtype=np.float32)
  distances = []
  for item in spawned_scene:
    if not _spawned_kind_matches(item, kind_tokens):
      continue
    if "x" in item and "y" in item:
      obj_pos = np.asarray([float(item["x"]), float(item["y"])], dtype=np.float32)
      distances.append(float(np.linalg.norm(vehicle_pos - obj_pos)))
  return min(distances) if distances else None


def spawned_route_clearance_m(
  spawned_scene: list[dict[str, float | str]],
  current_route_long_m: float,
  current_lateral_m: float,
  kind_tokens: tuple[str, ...],
) -> float | None:
  distances = []
  for item in spawned_scene:
    if not _spawned_kind_matches(item, kind_tokens) or "route_s_m" not in item or "lateral_m" not in item:
      continue
    ds = float(item["route_s_m"]) - current_route_long_m
    dl = float(item["lateral_m"]) - current_lateral_m
    distances.append(float(math.hypot(ds, dl)))
  return min(distances) if distances else None


def spawned_route_proximity(
  spawned_scene: list[dict[str, float | str]],
  current_route_long_m: float,
  current_lateral_m: float,
  kind_tokens: tuple[str, ...],
) -> dict[str, float | str | None]:
  nearest: tuple[float, dict[str, float | str], float, float] | None = None
  for item in spawned_scene:
    if not _spawned_kind_matches(item, kind_tokens) or "route_s_m" not in item or "lateral_m" not in item:
      continue
    ahead_m = float(item["route_s_m"]) - current_route_long_m
    lateral_delta_m = float(item["lateral_m"]) - current_lateral_m
    route_distance_m = float(math.hypot(ahead_m, lateral_delta_m))
    if nearest is None or route_distance_m < nearest[0]:
      nearest = (route_distance_m, item, ahead_m, lateral_delta_m)

  if nearest is None:
    return {
      "route_distance_m": None,
      "ahead_m": None,
      "lateral_delta_m": None,
      "object_lateral_m": None,
      "object_route_s_m": None,
      "kind": "",
    }

  route_distance_m, item, ahead_m, lateral_delta_m = nearest
  return {
    "route_distance_m": route_distance_m,
    "ahead_m": ahead_m,
    "lateral_delta_m": lateral_delta_m,
    "object_lateral_m": float(item["lateral_m"]),
    "object_route_s_m": float(item["route_s_m"]),
    "kind": str(item.get("kind", "")),
  }


def _jsonable_info_flags(info) -> dict[str, bool | float | int | str]:
  if not isinstance(info, dict):
    return {}
  out: dict[str, bool | float | int | str] = {}
  for key, value in info.items():
    if isinstance(value, (bool, str)):
      out[str(key)] = value
    elif isinstance(value, (int, float, np.integer, np.floating)):
      out[str(key)] = float(value)
  return out


class MetaDriveRouteFollower:
  def __init__(self, max_steer: float = 0.75, max_steer_rate_per_s: float = 0.9, steer_smoothing_alpha: float = 0.35):
    self.max_steer = max_steer
    self.max_steer_rate_per_s = max_steer_rate_per_s
    self.steer_smoothing_alpha = steer_smoothing_alpha
    self.last_steer = 0.0

  def action(self, env, target_speed_mps: float, lateral_offset_m: float, dt: float) -> tuple[float, float, dict[str, float]]:
    vehicle = env.vehicle
    speed = speed_mps(env)
    lane = route_lane_for_vehicle(env)
    long_m, current_lateral_m = lane.local_coordinates(vehicle.position)
    lookahead_m = float(np.clip(6.0 + speed * 1.65, 8.0, 28.0))
    target = route_world_point(env, lookahead_m, lateral_offset_m)
    dx = float(target[0] - vehicle.position[0])
    dy = float(target[1] - vehicle.position[1])
    desired_heading = math.atan2(dy, dx)
    heading_error = wrap_angle(desired_heading - float(vehicle.heading_theta))
    lateral_error = float(current_lateral_m - lateral_offset_m)

    raw_steer = float(np.clip(1.45 * heading_error + 0.04 * lateral_error, -self.max_steer, self.max_steer))
    filtered_steer = self.last_steer + self.steer_smoothing_alpha * (raw_steer - self.last_steer)
    steer = _slew(self.last_steer, filtered_steer, self.max_steer_rate_per_s * max(dt, 1e-3))
    steer = float(np.clip(steer, -self.max_steer, self.max_steer))
    self.last_steer = steer

    speed_error = target_speed_mps - speed
    speed_gain = 0.45 if target_speed_mps <= 0.5 and speed_error < 0.0 else 0.16
    gas = float(np.clip(speed_gain * speed_error, -0.65, 0.55))
    return steer, gas, {
      "lane_longitudinal_m": float(long_m),
      "lane_lateral_m": float(current_lateral_m),
      "target_lateral_m": float(lateral_offset_m),
      "lookahead_m": lookahead_m,
      "heading_error_rad": float(heading_error),
      "raw_steer": raw_steer,
    }


def make_planner(args: argparse.Namespace, engine_name: str) -> ReasonedPlanner | None:
  if engine_name == "stock":
    return None
  if engine_name == "static":
    engine = StaticRtpEngine(SCENARIOS[args.scenario])
  else:
    if args.async_vlm:
      os.environ["RTP_VLM_ASYNC"] = "1"
      os.environ["RTP_VLM_ASYNC_PERIOD_FRAMES"] = str(args.vlm_period_frames)
      os.environ["RTP_VLM_ASYNC_MAX_AGE_FRAMES"] = str(args.vlm_max_age_frames)
      if args.vlm_latest_only:
        os.environ["RTP_VLM_ASYNC_LATEST_ONLY"] = "1"
      if args.vlm_drop_stale_results:
        os.environ["RTP_VLM_ASYNC_DROP_STALE_RESULTS"] = "1"
        os.environ["RTP_VLM_ASYNC_MAX_RESULT_AGE_FRAMES"] = str(args.vlm_max_result_age_frames)
    engine = build_rtp_engine()
  return ReasonedPlanner(
    config=ReasonedPlannerConfig(
      deadline_ms=args.deadline_ms,
      allow_async_rtp=args.async_vlm,
      max_async_age_frames=args.vlm_max_age_frames,
    ),
    renderer=scene_board_renderer_for_args(args),
    engine=engine,
  )


def scene_board_renderer_for_args(args: argparse.Namespace) -> UiSceneBoardRenderer:
  candidate_offset = float(args.candidate_guide_offset_m) if bool(getattr(args, "scene_board_candidate_guides", False)) else 0.0
  geometry = OverlayGeometry(
    planned_corridor_half_width_m=float(getattr(args, "scene_board_corridor_half_width_m", OverlayGeometry.planned_corridor_half_width_m)),
    focus_corridor_extra_width_m=float(getattr(args, "scene_board_focus_extra_width_m", OverlayGeometry.focus_corridor_extra_width_m)),
    dim_outside_corridor=bool(getattr(args, "scene_board_dim_outside_corridor", OverlayGeometry.dim_outside_corridor)),
    outside_corridor_dim_alpha=int(getattr(args, "scene_board_dim_alpha", OverlayGeometry.outside_corridor_dim_alpha)),
    candidate_lateral_offset_m=max(0.0, candidate_offset),
    draw_candidate_labels=bool(getattr(args, "scene_board_candidate_labels", OverlayGeometry.draw_candidate_labels)),
    draw_base_path_reference=bool(getattr(args, "scene_board_base_path_reference", OverlayGeometry.draw_base_path_reference)),
    draw_corridor_side_guides=bool(getattr(args, "scene_board_corridor_side_guides", OverlayGeometry.draw_corridor_side_guides)),
    draw_corridor_side_fill=bool(getattr(args, "scene_board_corridor_side_fill", OverlayGeometry.draw_corridor_side_fill)),
    draw_corridor_side_labels=bool(getattr(args, "scene_board_corridor_side_labels", OverlayGeometry.draw_corridor_side_labels)),
    draw_edge_insets=bool(getattr(args, "scene_board_edge_insets", OverlayGeometry.draw_edge_insets)),
    draw_candidate_obstruction_boards=bool(getattr(args, "scene_board_candidate_obstruction_boards", OverlayGeometry.draw_candidate_obstruction_boards)),
    candidate_obstruction_offset_m=float(getattr(args, "scene_board_candidate_obstruction_offset_m", OverlayGeometry.candidate_obstruction_offset_m)),
  )
  return UiSceneBoardRenderer(args.board_width, args.board_height, geometry=geometry)


def run_episode(args: argparse.Namespace, mode: str) -> dict:
  env = make_env(args)
  args.route_lateral_sign_to_openpilot = route_lateral_sign_to_openpilot(env)
  env._rtp_route_lateral_args = args
  spawned_scene = spawn_novel_scene(env, args)
  out_dir = args.out / mode
  out_dir.mkdir(parents=True, exist_ok=True)
  if mode == "vlm" and args.async_vlm:
    os.environ["RTP_VLM_ASYNC_LOG_PATH"] = str(out_dir / "async_vlm_events.jsonl")
  planner = make_planner(args, mode)
  records = []
  controller = MetaDriveRouteFollower(max_steer_rate_per_s=args.max_steer_rate_per_s, steer_smoothing_alpha=args.steer_smoothing_alpha)
  active_lateral_offset_m = 0.0
  desired_lateral_offset_m = 0.0
  durable_lateral_plans: dict[str, DurableAvoidance] = {}
  durable_lateral_override_state = DurableLateralOverrideState()
  durable_speed_plans: dict[str, DurableSpeedPlan] = {}
  model_frame_id_offset = 0

  try:
    if planner is not None and mode == "vlm" and args.async_vlm and args.prewarm_seconds > 0:
      warm_until = time.perf_counter() + args.prewarm_seconds
      warm_frame_id = 0
      while time.perf_counter() < warm_until:
        warm_road = _traffic_light_visual_overlay(env, camera_frame(env), args)
        warm_plan = make_base_plan(warm_frame_id, speed_mps(env), curvature=0.0, desired_speed_mps=args.speed_mps)
        planner.step(warm_plan, {"v_ego": warm_plan.current_speed, "road_frame": warm_road, "status": "WARM"})
        warm_frame_id += 1
        time.sleep(0.05)
      wait_idle = getattr(planner.engine, "wait_idle", None)
      if callable(wait_idle) and not wait_idle(max(2.0, args.prewarm_seconds)):
        raise RuntimeError("async VLM prewarm did not become idle before episode start")
      if args.prewarm_reset_runtime_state:
        reset_runtime_state = getattr(planner.engine, "reset_runtime_state", None)
        if callable(reset_runtime_state):
          reset_runtime_state()
      else:
        # Real openpilot frame ids are monotonic across pre-engagement warmup
        # and active planning. Keep the model clock monotonic when retaining
        # the warmed VLM state so async age checks remain meaningful.
        model_frame_id_offset = warm_frame_id

    for frame_id in range(args.frames):
      model_frame_id = frame_id + model_frame_id_offset
      frame_start = time.perf_counter()
      ctrl_dt = args.tick_sec if args.tick_sec > 0 else 0.05
      update_phase_traffic_lights(env, frame_id, args)
      current_long_m = current_route_longitudinal_m(env)
      durable_lateral_plans = {key: plan for key, plan in durable_lateral_plans.items() if plan.active(current_long_m)}
      durable_speed_plans = {key: plan for key, plan in durable_speed_plans.items() if plan.active(current_long_m)}
      if _passed_traffic_light_stop(current_long_m, args):
        durable_speed_plans = _clear_signal_speed_plans(durable_speed_plans)
      desired_lateral_offset_m = compose_lateral_offset(durable_lateral_plans, current_long_m, args.max_durable_offset_m)
      active_lateral_offset_m = _slew(active_lateral_offset_m, desired_lateral_offset_m, args.max_lateral_offset_rate_mps * ctrl_dt)
      current_speed = speed_mps(env)
      active_speed_cap_mps = None if args.disable_vlm_speed_control else compose_speed_cap(durable_speed_plans, current_long_m, args.speed_mps)
      target_speed = min(args.speed_mps, active_speed_cap_mps) if active_speed_cap_mps is not None else args.speed_mps
      steer_cmd, gas, control_debug = controller.action(env, target_speed, active_lateral_offset_m, ctrl_dt)
      _, reward, terminated, truncated, info = env.step([steer_cmd, gas])
      update_moving_pedestrians(env)
      update_controlled_vehicles(env, ctrl_dt)
      road = _traffic_light_visual_overlay(env, camera_frame(env), args)
      current_visual_signal_label = _visual_traffic_signal_label_from_frame(road) if _traffic_light_enabled(args) else None
      current_speed = speed_mps(env)
      current_long_m = current_route_longitudinal_m(env)
      base_plan = make_base_plan_from_route(env, model_frame_id, current_speed, args.speed_mps)
      lead_state = nearest_route_vehicle_state(
        spawned_scene,
        current_long_m,
        current_speed,
        track_history=getattr(env, "_rtp_vehicle_track_history", None),
        dt=ctrl_dt,
        route_lateral_sign_to_openpilot=_route_lateral_sign_from_args(args),
      )
      scene_board_state = {
        "v_ego": current_speed,
        "road_frame": road,
        "path_lateral_offset_m": route_to_openpilot_lateral_m_from_args(args, active_lateral_offset_m),
        "status": "VLM" if mode == "vlm" else "RTP",
        **lead_state,
      }
      lead_guard_cleared_speed_sources: list[str] = []
      if not args.disable_vlm_speed_control:
        before_lead_guard = set(durable_speed_plans)
        durable_speed_plans = _apply_current_lead_state_guard(
          durable_speed_plans,
          lead_state,
          args,
          allow_true_moving_clear=True,
        )
        lead_guard_cleared_speed_sources.extend(sorted(before_lead_guard - set(durable_speed_plans)))

      result = None
      compiled_lateral_offset_openpilot_m = None
      compiled_lateral_offset_metadrive_m = None
      new_durable_avoidance_sign_valid = None
      compiled_lateral_fallback_used = False
      if planner is not None:
        result = planner.step(base_plan, scene_board_state)
        if frame_id % args.save_every == 0 and result.board is not None:
          result.board.save(out_dir / f"vlm_input_{frame_id:04d}.png")
          for aux_name, aux_png in sorted(result.board.aux_pngs.items()):
            safe_aux_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in aux_name)
            (out_dir / f"vlm_input_{frame_id:04d}_{safe_aux_name}.png").write_bytes(bytes(aux_png))
        if result.should_publish and result.synth is not None:
          compiled_lateral_offset_m = float(np.clip(selected_lateral_offset_m(result.synth), -args.max_durable_offset_m, args.max_durable_offset_m))
          compiled_lateral_offset_openpilot_m = compiled_lateral_offset_m
          compiled_lateral_offset_metadrive_m = openpilot_to_route_lateral_m_from_args(args, compiled_lateral_offset_m)
          new_durable_avoidance = durable_avoidance_from_program(result.program, current_long_m, compiled_lateral_offset_m, args)
          new_durable_avoidance_sign_valid = None if new_durable_avoidance is None else durable_avoidance_sign_valid_for_args(new_durable_avoidance, args)
          new_speed_plan = None if args.disable_vlm_speed_control else durable_speed_plan_from_program(result.program, current_long_m, args)
          new_speed_plan = _adjust_signal_speed_plan(new_speed_plan, result.program, current_long_m, args)
          durable_lateral_plans = update_durable_lateral_plans(
            durable_lateral_plans,
            new_durable_avoidance,
            result.program,
            current_long_m,
            args,
            override_state=durable_lateral_override_state,
            rtp_source_frame_id=result.rtp_source_frame_id,
          )
          durable_speed_plans = update_durable_speed_plans(durable_speed_plans, new_speed_plan, result.program, current_long_m, args)
          if not args.disable_vlm_speed_control:
            before_lead_guard = set(durable_speed_plans)
            durable_speed_plans = _apply_current_lead_state_guard(
              durable_speed_plans,
              lead_state,
              args,
              allow_true_moving_clear=False,
            )
            lead_guard_cleared_speed_sources.extend(sorted(before_lead_guard - set(durable_speed_plans)))

          desired_lateral_offset_m, compiled_lateral_fallback_used = compose_lateral_offset_after_publish(
            durable_lateral_plans,
            current_long_m,
            args.max_durable_offset_m,
            compiled_lateral_offset_m,
            args,
          )
          active_speed_cap_mps = None if args.disable_vlm_speed_control else compose_speed_cap(durable_speed_plans, current_long_m, args.speed_mps)
      elif frame_id % args.save_every == 0:
        board = scene_board_renderer_for_args(args).render(
          base_plan,
          {"v_ego": current_speed, "road_frame": road, "path_lateral_offset_m": 0.0, "status": "STOCK", **lead_state},
        )
        board.save(out_dir / f"stock_overlay_{frame_id:04d}.png")

      if _should_apply_visual_signal_guard(mode, args, current_visual_signal_label):
        durable_speed_plans = _apply_current_visual_signal_guard(durable_speed_plans, current_visual_signal_label, current_long_m, args)

      min_spawned_distance_m = spawned_min_distance_m(env, spawned_scene)
      min_construction_distance_m = spawned_min_distance_m(env, spawned_scene, ("construction", "traffic_cone", "traffic_barrier"))
      min_pedestrian_distance_m = spawned_min_distance_m(env, spawned_scene, ("pedestrian",))
      min_vehicle_distance_m = spawned_min_distance_m(env, spawned_scene, VEHICLE_KIND_TOKENS)
      active_lateral_plan_records = active_lateral_plans(durable_lateral_plans, current_long_m)
      active_speed_plan_records = active_speed_plans(durable_speed_plans, current_long_m)
      strongest_lateral_plan = max(active_lateral_plan_records, key=lambda plan: abs(plan.target_offset(current_long_m)), default=None)
      active_lateral_plan_details = [
        {
          "source_token": plan.source_token,
          "source_meta": plan.source_meta,
          "target_offset_metadrive_m": plan.target_offset(current_long_m),
          "target_offset_openpilot_m": route_to_openpilot_lateral_m_from_args(args, plan.target_offset(current_long_m)),
          "hazard_side": construction_hazard_side_from_token(plan.source_token),
          "target_side_metadrive": lateral_side_metadrive(plan.target_offset(current_long_m)),
          "target_side_openpilot": lateral_side_route_openpilot(args, plan.target_offset(current_long_m)),
          "confidence": plan.confidence,
          "sign_valid": durable_avoidance_sign_valid_for_args(plan, args),
        }
        for plan in active_lateral_plan_records
      ]
      record_speed_cap_mps = None if args.disable_vlm_speed_control else compose_speed_cap(durable_speed_plans, current_long_m, args.speed_mps)
      lane_lateral_m = float(control_debug.get("lane_lateral_m", 0.0))
      scene_board_path_lateral_offset_m = route_to_openpilot_lateral_m_from_args(args, active_lateral_offset_m)
      strongest_lateral_target_metadrive_m = None if strongest_lateral_plan is None else strongest_lateral_plan.target_offset(current_long_m)
      strongest_lateral_source_token = "" if strongest_lateral_plan is None else strongest_lateral_plan.source_token
      min_construction_route_clearance_m = spawned_route_clearance_m(
        spawned_scene,
        current_long_m,
        lane_lateral_m,
        ("construction", "traffic_cone", "traffic_barrier"),
      )
      construction_route_proximity = spawned_route_proximity(
        spawned_scene,
        current_long_m,
        lane_lateral_m,
        ("construction", "traffic_cone", "traffic_barrier"),
      )
      min_pedestrian_route_clearance_m = spawned_route_clearance_m(
        spawned_scene,
        current_long_m,
        lane_lateral_m,
        ("pedestrian",),
      )
      pedestrian_route_proximity = spawned_route_proximity(
        spawned_scene,
        current_long_m,
        lane_lateral_m,
        ("pedestrian",),
      )
      min_vehicle_route_clearance_m = spawned_route_clearance_m(
        spawned_scene,
        current_long_m,
        lane_lateral_m,
        VEHICLE_KIND_TOKENS,
      )
      vehicle_route_proximity = spawned_route_proximity(
        spawned_scene,
        current_long_m,
        lane_lateral_m,
        VEHICLE_KIND_TOKENS,
      )
      records.append({
        "frame_id": frame_id,
        "model_frame_id": model_frame_id,
        "mode": mode,
        "speed_mps": current_speed,
        "desired_speed_mps": args.speed_mps,
        "gas": gas,
        "steer_cmd": steer_cmd,
        "active_lateral_offset_m": active_lateral_offset_m,
        "desired_lateral_offset_m": desired_lateral_offset_m,
        "target_speed_mps": target_speed,
        "vlm_speed_control_enabled": not args.disable_vlm_speed_control,
        "control_debug": control_debug,
        "lead_state": lead_state,
        "lead_present": lead_state["lead_present"],
        "lead_source": lead_state["lead_source"],
        "lead_distance_m": lead_state["lead_distance_m"],
        "lead_lateral_m": lead_state["lead_lateral_m"],
        "lead_speed_mps": lead_state["lead_speed_mps"],
        "lead_rel_speed_mps": lead_state["lead_rel_speed_mps"],
        "lead_closing_mps": lead_state["lead_closing_mps"],
        "lead_accel_mps2": lead_state["lead_accel_mps2"],
        "lead_lateral_velocity_mps": lead_state["lead_lateral_velocity_mps"],
        "lead_route_heading_theta": lead_state["lead_route_heading_theta"],
        "lead_actual_heading_theta": lead_state["lead_actual_heading_theta"],
        "lead_heading_error_rad": lead_state["lead_heading_error_rad"],
        "lead_heading_alignment_cos": lead_state["lead_heading_alignment_cos"],
        "lead_heading_same_direction": lead_state["lead_heading_same_direction"],
        "lead_speed_guard_clear_reason": "" if args.disable_vlm_speed_control else _physical_lead_clear_reason(lead_state, args, allow_true_moving_clear=True),
        "lead_speed_guard_cleared_sources": lead_guard_cleared_speed_sources,
        "reward": float(reward),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "info_flags": _jsonable_info_flags(info),
        "route_lateral_sign_to_openpilot": _route_lateral_sign_from_args(args),
        "active_lateral_offset_metadrive_m": active_lateral_offset_m,
        "active_lateral_offset_openpilot_m": route_to_openpilot_lateral_m_from_args(args, active_lateral_offset_m),
        "active_lateral_side_metadrive": lateral_side_metadrive(active_lateral_offset_m),
        "active_lateral_side_openpilot": lateral_side_route_openpilot(args, active_lateral_offset_m),
        "desired_lateral_offset_metadrive_m": desired_lateral_offset_m,
        "desired_lateral_offset_openpilot_m": route_to_openpilot_lateral_m_from_args(args, desired_lateral_offset_m),
        "desired_lateral_side_metadrive": lateral_side_metadrive(desired_lateral_offset_m),
        "desired_lateral_side_openpilot": lateral_side_route_openpilot(args, desired_lateral_offset_m),
        "compiled_lateral_fallback_used": compiled_lateral_fallback_used,
        "compiled_lateral_offset_openpilot_m": compiled_lateral_offset_openpilot_m,
        "compiled_lateral_offset_metadrive_m": compiled_lateral_offset_metadrive_m,
        "compiled_lateral_side_openpilot": lateral_side_openpilot(compiled_lateral_offset_openpilot_m),
        "compiled_lateral_side_metadrive": lateral_side_metadrive(compiled_lateral_offset_metadrive_m),
        "new_durable_avoidance_sign_valid": new_durable_avoidance_sign_valid,
        "min_spawned_object_distance_m": min_spawned_distance_m,
        "min_construction_object_distance_m": min_construction_distance_m,
        "min_pedestrian_object_distance_m": min_pedestrian_distance_m,
        "min_vehicle_object_distance_m": min_vehicle_distance_m,
        "min_construction_route_clearance_m": min_construction_route_clearance_m,
        "construction_nearest_ahead_m": construction_route_proximity["ahead_m"],
        "construction_nearest_lateral_delta_m": construction_route_proximity["lateral_delta_m"],
        "construction_nearest_object_lateral_m": construction_route_proximity["object_lateral_m"],
        "construction_nearest_kind": construction_route_proximity["kind"],
        "min_pedestrian_route_clearance_m": min_pedestrian_route_clearance_m,
        "pedestrian_nearest_ahead_m": pedestrian_route_proximity["ahead_m"],
        "pedestrian_nearest_lateral_delta_m": pedestrian_route_proximity["lateral_delta_m"],
        "pedestrian_nearest_object_lateral_m": pedestrian_route_proximity["object_lateral_m"],
        "pedestrian_nearest_kind": pedestrian_route_proximity["kind"],
        "min_vehicle_route_clearance_m": min_vehicle_route_clearance_m,
        "vehicle_nearest_ahead_m": vehicle_route_proximity["ahead_m"],
        "vehicle_nearest_lateral_delta_m": vehicle_route_proximity["lateral_delta_m"],
        "vehicle_nearest_object_lateral_m": vehicle_route_proximity["object_lateral_m"],
        "vehicle_nearest_kind": vehicle_route_proximity["kind"],
        "durable_avoidance_active": bool(active_lateral_plan_records),
        "durable_avoidance_offset_m": 0.0 if strongest_lateral_target_metadrive_m is None else strongest_lateral_target_metadrive_m,
        "durable_avoidance_start_long_m": None if strongest_lateral_plan is None else strongest_lateral_plan.start_long_m,
        "durable_avoidance_end_long_m": None if strongest_lateral_plan is None else strongest_lateral_plan.end_long_m,
        "durable_avoidance_source": strongest_lateral_source_token,
        "durable_avoidance_source_meta": "" if strongest_lateral_plan is None else strongest_lateral_plan.source_meta,
        "durable_avoidance_confidence": 0.0 if strongest_lateral_plan is None else strongest_lateral_plan.confidence,
        "durable_avoidance_hazard_side": construction_hazard_side_from_token(strongest_lateral_source_token),
        "durable_avoidance_target_side_metadrive": lateral_side_metadrive(strongest_lateral_target_metadrive_m),
        "durable_avoidance_target_side_openpilot": lateral_side_route_openpilot(args, strongest_lateral_target_metadrive_m),
        "durable_lateral_plan_count": len(active_lateral_plan_records),
        "durable_lateral_plan_sources": [plan.source_token for plan in active_lateral_plan_records],
        "durable_lateral_plan_details": active_lateral_plan_details,
        "durable_lateral_plan_sign_valid_all": all(item["sign_valid"] for item in active_lateral_plan_details),
        "durable_lateral_pending_source": durable_lateral_override_state.pending_source_token,
        "durable_lateral_pending_sign": durable_lateral_override_state.pending_sign,
        "durable_lateral_pending_count": durable_lateral_override_state.pending_count,
        "durable_lateral_pending_observation_id": durable_lateral_override_state.pending_observation_id,
        "durable_speed_plan_count": len(active_speed_plan_records),
        "durable_speed_plan_sources": [plan.source_token for plan in active_speed_plan_records],
        "durable_speed_cap_mps": record_speed_cap_mps,
        "traffic_light_state": str(getattr(env, "_rtp_traffic_light_state", "")),
        "visual_signal_label": current_visual_signal_label,
        "visual_signal_guard_enabled": bool(args.enable_visual_signal_guard and mode == "vlm"),
        "traffic_light_green_frame": _traffic_light_first_green_frame(args),
        "route_longitudinal_m": current_long_m,
        "scene_board_path_lateral_offset_m": scene_board_path_lateral_offset_m,
        "green_path_offset_openpilot_m": scene_board_path_lateral_offset_m,
        "green_path_matches_tracked_path": abs(scene_board_path_lateral_offset_m - route_to_openpilot_lateral_m_from_args(args, active_lateral_offset_m)) <= 1e-6,
        "scene_board_state_text": "" if result is None or result.board is None else result.board.state_text,
        "scene_board_aux_keys": [] if result is None or result.board is None else sorted(result.board.aux_pngs),
        "traffic_light_stop_line_m": None if not _traffic_light_enabled(args) else _traffic_light_stop_line_m(args),
        "traffic_light_remaining_to_stop_m": None if not _traffic_light_enabled(args) else _traffic_light_stop_line_m(args) - current_long_m,
        "route_completion": float(info.get("route_completion", 0.0)) if isinstance(info, dict) else 0.0,
        "reasoned_should_publish": False if result is None else result.should_publish,
        "reasoned_valid": False if result is None else result.valid,
        "reasoned_deadline_met": True if result is None else result.deadline_met,
        "reasoned_latency_ms": 0.0 if result is None else result.timings.publish_age_ms,
        "camera_to_scene_board_ms": 0.0 if result is None else result.timings.camera_to_scene_board_ms,
        "scene_board_to_vlm_prefill_ms": 0.0 if result is None else result.timings.scene_board_to_vlm_prefill_ms,
        "vlm_decode_ms": 0.0 if result is None else result.timings.vlm_decode_ms,
        "rtp_parse_ms": 0.0 if result is None else result.timings.rtp_parse_ms,
        "path_synth_ms": 0.0 if result is None else result.timings.path_synth_ms,
        "rtp_source_frame_id": None if result is None else result.rtp_source_frame_id,
        "rtp_age_frames": None if result is None else result.rtp_age_frames,
        "control_consumed_age_frames": None if result is None else result.rtp_age_frames,
        "qwen_labels": [] if result is None else list(result.labels),
        "qwen_label_scores": {} if result is None else result.label_scores,
        "qwen_raw_labels": [] if result is None else list(result.raw_labels),
        "qwen_raw_label_scores": {} if result is None else result.raw_label_scores,
        "qwen_labels_scored_this_request": [] if result is None else list(result.labels_scored_this_request),
        "qwen_score_group_index": None if result is None else result.score_group_index,
        "qwen_label_state_debug": None if result is None else result.label_state_debug,
        "qwen_choice": None if result is None else result.choice,
        "lead_class": "" if result is None else _lead_class_from_program(result.program),
        "expected_lead_class": _expected_lead_class_from_spawned(spawned_scene),
        "vlm_backend": "" if result is None else result.vlm_backend,
        "selected_candidate": None if result is None or result.synth is None else result.synth.selected_candidate,
        "path_delta_m": 0.0 if result is None or result.synth is None else result.synth.vlm_changed_path_meters,
        "speed_delta_mps": 0.0 if result is None or result.synth is None else result.synth.vlm_changed_speed_mps,
        "invalid_reason": "" if result is None else result.invalid_reason,
        "rtp_text": "" if result is None else result.rtp_text,
        "spawned_scene": spawned_scene,
      })
      if terminated or truncated:
        break
      if args.tick_sec > 0:
        time.sleep(max(0.0, args.tick_sec - (time.perf_counter() - frame_start)))
  finally:
    if planner is not None:
      planner.engine.close()
    env.close()

  latencies = [r["reasoned_latency_ms"] for r in records if mode != "stock"]
  published = [r for r in records if r["reasoned_should_publish"]]
  rtp_ages = [int(r["rtp_age_frames"]) for r in records if r["rtp_age_frames"] is not None]
  same_frame_records = [
    r for r in records
    if r["rtp_source_frame_id"] is not None and int(r["rtp_source_frame_id"]) == int(r.get("model_frame_id", r["frame_id"]))
  ]
  summary = {
    "mode": mode,
    "frames": len(records),
    "nominal_speed_mps": args.speed_mps,
    "desired_speed_mps": args.speed_mps,
    "publish_count": len(published),
    "valid_count": sum(1 for r in records if r["reasoned_valid"]),
    "deadline_miss_count": sum(1 for r in records if not r["reasoned_deadline_met"]),
    "mean_speed_mps": statistics.fmean([r["speed_mps"] for r in records]) if records else 0.0,
    "mean_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
    "p90_latency_ms": percentile(latencies, 90),
    "p99_latency_ms": percentile(latencies, 99),
    "p999_latency_ms": percentile(latencies, 99.9),
    "max_latency_ms": max(latencies) if latencies else 0.0,
    "same_frame_count": len(same_frame_records),
    "same_frame_all": len(same_frame_records) == len(records) if mode != "stock" else True,
    "max_rtp_age_frames": max(rtp_ages) if rtp_ages else 0,
    "mean_path_delta_m": statistics.fmean([r["path_delta_m"] for r in published]) if published else 0.0,
    "mean_speed_delta_mps": statistics.fmean([r["speed_delta_mps"] for r in published]) if published else 0.0,
    "expected_lead_class": _expected_lead_class_from_spawned(spawned_scene),
    "qwen_lead_classes": sorted(set(str(r["lead_class"]) for r in records if r.get("lead_class"))),
    "min_construction_route_clearance_m": min((r["min_construction_route_clearance_m"] for r in records if r["min_construction_route_clearance_m"] is not None), default=None),
    "min_pedestrian_route_clearance_m": min((r["min_pedestrian_route_clearance_m"] for r in records if r["min_pedestrian_route_clearance_m"] is not None), default=None),
    "min_vehicle_route_clearance_m": min((r["min_vehicle_route_clearance_m"] for r in records if r["min_vehicle_route_clearance_m"] is not None), default=None),
    "records": records,
  }
  (out_dir / "episode.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
  return summary


def run_alpamayofast_episode(args: argparse.Namespace) -> dict:
  from PIL import Image

  bench = load_alpamayo_contract_bench()
  out_dir = args.out / "vlm"
  out_dir.mkdir(parents=True, exist_ok=True)

  previous_dual_camera = bool(getattr(args, "_alpamayofast_dual_cameras", False))
  args._alpamayofast_dual_cameras = True
  env = make_env(args)
  args._alpamayofast_dual_cameras = previous_dual_camera

  route_controller = MetaDriveRouteFollower(
    max_steer_rate_per_s=args.max_steer_rate_per_s,
    steer_smoothing_alpha=args.steer_smoothing_alpha,
  )
  alpamayo_controller = bench.AlpamayoTrajectoryController(
    max_steer=args.alpamayo_max_steer,
    max_steer_rate_per_s=args.max_steer_rate_per_s,
  )
  spawned_scene = spawn_novel_scene(env, args)

  sample_dt_s = max(float(args.alpamayo_model_step_sec), 1e-6)
  query_interval_sec = sample_dt_s * max(1, int(args.alpamayo_query_every))
  frame_step_ns = int(sample_dt_s * 1e9)
  warmup_stock_frames = args.alpamayo_warmup_stock_frames
  if warmup_stock_frames is None:
    warmup_stock_frames = int(math.ceil(bench.HISTORY_STEPS * sample_dt_s / max(args.tick_sec, 1e-6)))
  warmup_stock_frames = max(0, int(warmup_stock_frames))
  frame_buffer_size = max(
    int(args.alpamayo_num_frames) + 4,
    int(math.ceil((sample_dt_s * max(1, int(args.alpamayo_num_frames) - 1)) / max(args.tick_sec, 1e-6)) + 4),
    warmup_stock_frames,
    args.frames + int(args.alpamayo_num_frames) + 4,
  )
  ego_history = bench.EgoHistory(bench.HISTORY_STEPS, sample_dt_s=sample_dt_s)
  frame_buffers = {stream: deque(maxlen=frame_buffer_size) for stream in bench.STREAMS}

  records: list[dict[str, Any]] = []
  endpoint_latencies: list[float] = []
  endpoint_errors: list[str] = []
  endpoint_attempts = 0
  endpoint_successes = 0
  endpoint_valid_successes = 0
  latest_plan_frame_id: int | None = None
  latest_plan_latency_ms: float | None = None
  latest_endpoint_status_code: int | None = None
  latest_endpoint_latency_ms: float | None = None
  latest_response_status = ""
  latest_response_error = ""
  last_semantic: dict[str, Any] | None = None
  last_response_payload: dict[str, Any] | None = None
  endpoint_executor: concurrent.futures.ThreadPoolExecutor | None = None
  endpoint_future: concurrent.futures.Future[tuple[int, dict[str, Any], float]] | None = None
  endpoint_request_frame_id: int | None = None
  endpoint_response_index = 0
  last_request_t0_ns: int | None = None
  prev_speed: float | None = None
  next_query_time_s = args.tick_sec * warmup_stock_frames
  terminated = False
  truncated = False
  episode_wall_start = time.perf_counter()
  response_reasoning_log_path = out_dir / "alpamayo_response_reasoning.jsonl"

  if not args.alpamayo_sync_endpoint:
    endpoint_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

  def reasoning_text_candidates(payload: dict[str, Any] | None, semantic: dict[str, Any]) -> list[str]:
    candidates: list[str] = []

    def collect_from(mapping: dict[str, Any] | None) -> None:
      if not isinstance(mapping, dict):
        return
      for key in ("reasoningText", "cotText", "cot", "reasoning", "reasoningPreview", "cotPreview", "planReasoning"):
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
          candidates.append(value.strip())
      debug = mapping.get("debug")
      if isinstance(debug, dict):
        for key in ("reasoningText", "cotText", "cot", "cotPreview", "reasoning", "reasoningPreview", "planReasoning"):
          value = debug.get(key)
          if isinstance(value, str) and value.strip():
            candidates.append(value.strip())

    collect_from(semantic)
    if isinstance(payload, dict):
      collect_from(payload.get("semanticPlan"))
      collect_from(payload.get("debug"))
      collect_from(payload)
    return candidates

  def full_reasoning_text(payload: dict[str, Any] | None, semantic: dict[str, Any]) -> str:
    candidates = reasoning_text_candidates(payload, semantic)
    return " ".join(candidates[0].split()) if candidates else ""

  def log_endpoint_reasoning_response(
    status_code: int,
    payload: dict[str, Any],
    latency_ms: float,
    request_frame_id_for_plan: int | None,
  ) -> None:
    nonlocal endpoint_response_index
    semantic = payload.get("semanticPlan", {}) if isinstance(payload, dict) else {}
    reasoning_text = full_reasoning_text(payload, semantic if isinstance(semantic, dict) else {})
    debug = semantic.get("debug", {}) if isinstance(semantic, dict) else {}
    endpoint_response_index += 1
    row = {
      "response_index": endpoint_response_index,
      "request_frame_id": request_frame_id_for_plan,
      "status_code": status_code,
      "semantic_status": bench.semantic_status(payload),
      "latency_ms": latency_ms,
      "reasoning_text": reasoning_text,
      "reasoning_text_len": len(reasoning_text),
      "cot_preview": str(debug.get("cotPreview", "")) if isinstance(debug, dict) else "",
      "reasoning_generated_tokens": debug.get("reasoningGeneratedTokens") if isinstance(debug, dict) else None,
      "streaming_reuse_mode": ((debug.get("frameCacheStats", {}) or {}).get("vlmPrefixCache", {}) or {}).get("streamingReuseMode", "") if isinstance(debug, dict) else "",
      "streaming_reuse_unverified": bool(((debug.get("frameCacheStats", {}) or {}).get("vlmPrefixCache", {}) or {}).get("streamingReuseUnverified", False)) if isinstance(debug, dict) else False,
    }
    with response_reasoning_log_path.open("a", encoding="utf-8") as f:
      f.write(json.dumps(row, separators=(",", ":")) + "\n")

  def consume_endpoint_result(
    status_code: int,
    payload: dict[str, Any],
    latency_ms: float,
    request_frame_id_for_plan: int | None,
  ) -> None:
    nonlocal endpoint_successes, endpoint_valid_successes, last_response_payload, last_semantic
    nonlocal latest_endpoint_status_code, latest_endpoint_latency_ms, latest_response_status, latest_response_error
    nonlocal latest_plan_frame_id, latest_plan_latency_ms
    endpoint_successes += 1
    endpoint_latencies.append(latency_ms)
    latest_endpoint_status_code = status_code
    latest_endpoint_latency_ms = latency_ms
    latest_response_status = bench.semantic_status(payload)
    last_response_payload = payload
    try:
      log_endpoint_reasoning_response(status_code, payload, latency_ms, request_frame_id_for_plan)
    except Exception:
      pass
    if bench.semantic_valid(payload):
      endpoint_valid_successes += 1
      latest_response_error = ""
      last_semantic = payload.get("semanticPlan", {})
      if request_frame_id_for_plan is not None:
        latest_plan_frame_id = request_frame_id_for_plan
        latest_plan_latency_ms = latency_ms
    else:
      latest_response_error = str(payload.get("semanticPlan", {}).get("error", "invalid semanticPlan"))
      endpoint_errors.append(latest_response_error)

  def semantic_for_metadrive_control(semantic: dict[str, Any]) -> dict[str, Any]:
    steer_sign = float(args.alpamayo_steer_sign)
    if steer_sign >= 0.0:
      return semantic
    converted = copy.deepcopy(semantic)
    trajectory = converted.get("trajectory")
    if isinstance(trajectory, dict):
      for group_name, value_name in (("position", "y"), ("velocity", "y"), ("orientation", "z")):
        group = trajectory.get(group_name)
        if isinstance(group, dict) and isinstance(group.get(value_name), list):
          group[value_name] = [-float(value) for value in group[value_name]]
    if isinstance(converted.get("desiredCurvature"), (int, float)):
      converted["desiredCurvature"] = -float(converted["desiredCurvature"])
    return converted

  def planner_bridge_target_from_semantic(semantic: dict[str, Any]) -> tuple[float, dict[str, float]]:
    trajectory = semantic.get("trajectory", {})
    position = trajectory.get("position", {}) if isinstance(trajectory, dict) else {}
    xs = np.asarray(position.get("x", ()), dtype=np.float32)
    ys = np.asarray(position.get("y", ()), dtype=np.float32)
    if xs.size < 2 or ys.size < 2:
      return 0.0, {
        "alpamayo_planner_bridge": 1.0,
        "alpamayo_path_valid": 0.0,
        "alpamayo_route_lateral_target_m": 0.0,
      }
    count = min(int(xs.size), int(ys.size))
    xs = xs[:count]
    ys = ys[:count]
    finite = np.isfinite(xs) & np.isfinite(ys)
    xs = xs[finite]
    ys = ys[finite]
    positive = xs > 0.1
    xs = xs[positive]
    ys = ys[positive]
    if xs.size < 2:
      return 0.0, {
        "alpamayo_planner_bridge": 1.0,
        "alpamayo_path_valid": 0.0,
        "alpamayo_route_lateral_target_m": 0.0,
      }
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    preview_m = float(args.alpamayo_lateral_preview_m)
    raw_y = float(np.interp(preview_m, xs, ys))
    route_lateral_m = float(args.alpamayo_steer_sign) * raw_y * float(args.alpamayo_lateral_gain)
    max_offset_m = max(0.0, float(args.alpamayo_max_lateral_offset_m))
    clipped_lateral_m = float(np.clip(route_lateral_m, -max_offset_m, max_offset_m))
    return clipped_lateral_m, {
      "alpamayo_planner_bridge": 1.0,
      "alpamayo_path_valid": 1.0,
      "alpamayo_bridge_preview_m": preview_m,
      "alpamayo_path_raw_y_at_preview_m": raw_y,
      "alpamayo_route_lateral_before_clip_m": route_lateral_m,
      "alpamayo_route_lateral_target_m": clipped_lateral_m,
      "alpamayo_lateral_gain": float(args.alpamayo_lateral_gain),
      "alpamayo_max_lateral_offset_m": max_offset_m,
      "alpamayo_lateral_sign": float(args.alpamayo_steer_sign),
    }

  def alpamayo_reasoning_overlay_text(payload: dict[str, Any] | None, semantic: dict[str, Any]) -> str:
    if not bool(args.alpamayo_reasoning_overlay):
      return ""
    text = full_reasoning_text(payload, semantic)
    if not text:
      return ""
    max_chars = max(0, int(args.alpamayo_reasoning_overlay_chars))
    return text[:max_chars]

  def append_wrapped_reasoning_lines(video_lines: list[str], reasoning_text: str) -> None:
    if not reasoning_text:
      return
    line_chars = max(12, int(args.alpamayo_reasoning_overlay_line_chars))
    remaining = reasoning_text
    first = True
    while remaining:
      chunk = remaining[:line_chars]
      remaining = remaining[line_chars:]
      video_lines.append(("reason " if first else "       ") + chunk)
      first = False

  try:
    for frame_id in range(args.frames):
      frame_start = time.perf_counter()
      timestamp_s = float(frame_id) * args.tick_sec
      timestamp_eof_ns = int(round(timestamp_s * 1e9))
      ego_history.append_from_env_if_due(env, timestamp_s)

      current_speed_before_step = bench.speed_mps(env)
      a_ego = 0.0 if prev_speed is None else (current_speed_before_step - prev_speed) / max(args.tick_sec, 1e-3)
      vehicle_state = {
        "vEgo": current_speed_before_step,
        "aEgo": a_ego,
        "standstill": current_speed_before_step < 0.01,
        "steeringAngleDeg": float(getattr(env.vehicle, "steering", 0.0) * getattr(env.vehicle, "MAX_STEERING", 1.0)),
      }
      captured = bench.capture_frames(env, frame_id, timestamp_eof_ns, args.alpamayo_jpeg_quality, args.tick_sec)
      for stream, frame in captured.items():
        frame_buffers[stream].append(frame)

      in_flight = endpoint_future is not None and not endpoint_future.done()
      request_frame_id = None

      if endpoint_future is not None and endpoint_future.done():
        completed_request_frame_id = endpoint_request_frame_id
        endpoint_request_frame_id = None
        try:
          status_code, payload, latency_ms = endpoint_future.result()
          consume_endpoint_result(status_code, payload, latency_ms, completed_request_frame_id)
        except Exception as exc:
          latest_response_status = "error"
          latest_response_error = f"{type(exc).__name__}: {exc}"
          endpoint_errors.append(latest_response_error)
          latest_endpoint_status_code = None
          latest_endpoint_latency_ms = None
        endpoint_future = None
        in_flight = False

      can_query = (
        frame_id >= warmup_stock_frames
        and (timestamp_s + 1e-9) >= next_query_time_s
        and not in_flight
        and ego_history.has_sufficient_samples(allow_backfill=args.alpamayo_backfill_ego_history)
      )
      if can_query:
        latest_available_t0_ns = min(int(frame_buffers[name][-1]["timestampEof"]) for name in bench.STREAMS)
        target_t0_ns = None
        if not args.alpamayo_sync_endpoint and last_request_t0_ns is not None and last_request_t0_ns < latest_available_t0_ns:
          target_t0_ns = min(
            latest_available_t0_ns,
            last_request_t0_ns + frame_step_ns * max(1, int(args.alpamayo_catchup_stride_steps)),
          )
        request_pair = bench.build_request(
          frame_buffers,
          ego_history,
          vehicle_state,
          frame_id,
          frame_step_ns=frame_step_ns,
          num_frames=int(args.alpamayo_num_frames),
          allow_backfill=args.alpamayo_backfill_ego_history,
          target_t0_ns=target_t0_ns,
        )
        if request_pair is not None:
          request_payload, request_frame_id, request_t0_ns = request_pair
          last_request_t0_ns = request_t0_ns
          endpoint_attempts += 1
          next_query_time_s += query_interval_sec
          force_sync_first_plan = bool(args.alpamayo_wait_first_plan and last_semantic is None)
          if args.alpamayo_sync_endpoint or force_sync_first_plan:
            try:
              status_code, payload, latency_ms = bench.post_alpamayo(
                args.alpamayo_endpoint_url,
                request_payload,
                args.alpamayo_endpoint_timeout_s,
              )
              consume_endpoint_result(status_code, payload, latency_ms, request_frame_id)
            except Exception as exc:
              latest_response_status = "error"
              latest_response_error = f"{type(exc).__name__}: {exc}"
              endpoint_errors.append(latest_response_error)
              latest_endpoint_status_code = None
              latest_endpoint_latency_ms = None
          elif endpoint_executor is not None:
            endpoint_future = endpoint_executor.submit(
              bench.post_alpamayo,
              args.alpamayo_endpoint_url,
              request_payload,
              args.alpamayo_endpoint_timeout_s,
            )
            endpoint_request_frame_id = request_frame_id
            in_flight = True

      stock_steer, stock_gas, stock_debug = route_controller.action(env, args.speed_mps, 0.0, args.tick_sec)
      steer_cmd = stock_steer
      gas = stock_gas
      control_source = "stock_route_follower"
      alpamayo_debug: dict[str, float] = {}
      if last_semantic is not None:
        try:
          if args.alpamayo_control_mode == "planner_bridge":
            lateral_target_m, alpamayo_debug = planner_bridge_target_from_semantic(last_semantic)
            steer_cmd, gas, stable_debug = route_controller.action(env, args.speed_mps, lateral_target_m, args.tick_sec)
            alpamayo_debug.update({
              "alpamayo_control_mode_planner_bridge": 1.0,
              "alpamayo_actuator_steer": float(steer_cmd),
              "alpamayo_actuator_gas": float(gas),
              "alpamayo_actuator_speed_target_mps": float(args.speed_mps),
              "alpamayo_actuator_lane_lateral_m": float(stable_debug.get("lane_lateral_m", 0.0)),
              "alpamayo_actuator_raw_steer": float(stable_debug.get("raw_steer", 0.0)),
            })
            control_source = "alpamayo_planner_bridge"
          else:
            steer_cmd, gas, alpamayo_debug = alpamayo_controller.action(semantic_for_metadrive_control(last_semantic), bench.speed_mps(env), args.tick_sec)
            alpamayo_debug["alpamayo_steer_sign"] = float(args.alpamayo_steer_sign)
            control_source = "alpamayo_trajectory"
        except Exception as exc:
          latest_response_error = latest_response_error or f"Alpamayo control decode failed: {exc}"
          endpoint_errors.append(latest_response_error)

      step_start = time.perf_counter()
      _, reward, terminated, truncated, info = env.step([steer_cmd, gas])
      sim_step_ms = (time.perf_counter() - step_start) * 1000.0
      lane = route_lane_for_vehicle(env)
      route_long_m, route_lateral_m = lane.local_coordinates(env.vehicle.position)
      route_long_m = float(route_long_m)
      route_lateral_m = float(route_lateral_m)
      current_speed = bench.speed_mps(env)
      prev_speed = current_speed
      latest_plan_age_frames = frame_id - latest_plan_frame_id if latest_plan_frame_id is not None else None
      semantic = last_semantic or {}
      reasoning_overlay_text = alpamayo_reasoning_overlay_text(last_response_payload, semantic)
      trajectory = semantic.get("trajectory", {})
      position = trajectory.get("position", {})
      min_spawned_distance_m = spawned_min_distance_m(env, spawned_scene)
      record = {
        "frame_id": frame_id,
        "mode": "alpamayofast",
        "control_source": control_source,
        "speed_mps": current_speed,
        "route_longitudinal_m": route_long_m,
        "route_lateral_m": route_lateral_m,
        "steer_cmd": float(steer_cmd),
        "gas": float(gas),
        "stock_steer": float(stock_steer),
        "stock_gas": float(stock_gas),
        "reward": float(reward),
        "terminated": bool(terminated),
        "truncated": bool(truncated),
        "sim_step_ms": sim_step_ms,
        "frame_wall_ms": (time.perf_counter() - frame_start) * 1000.0,
        "endpoint_status_code": latest_endpoint_status_code,
        "endpoint_latency_ms": latest_endpoint_latency_ms,
        "semantic_status": latest_response_status,
        "semantic_error": latest_response_error,
        "semantic_source": semantic.get("source", ""),
        "trajectory_len": len(position.get("x", [])),
        "desired_curvature": semantic.get("desiredCurvature"),
        "desired_acceleration": semantic.get("desiredAcceleration"),
        "cot_preview": str(semantic.get("cot", ""))[:160],
        "reasoning_overlay_text": reasoning_overlay_text,
        "stock_debug": stock_debug,
        "alpamayo_debug": alpamayo_debug,
        "model_step_sec": sample_dt_s,
        "warmup_stock_frames": warmup_stock_frames,
        "request_frame_id": request_frame_id,
        "latest_plan_frame_id": latest_plan_frame_id,
        "latest_plan_age_frames": latest_plan_age_frames,
        "latest_plan_latency_ms": latest_plan_latency_ms,
        "in_flight": endpoint_future is not None and not endpoint_future.done(),
        "min_spawned_distance_m": min_spawned_distance_m,
      }
      records.append(record)

      if frame_id % args.save_every == 0:
        video_lines = [
          f"ALPAMAYOFAST frame {frame_id}",
          f"src {control_source}",
          f"v {current_speed:.2f} m/s lat {route_lateral_m:.2f} m",
          f"steer {float(steer_cmd):+.3f} gas {float(gas):+.3f}",
        ]
        if latest_response_status:
          status_line = f"endpoint {latest_endpoint_status_code or '-'} {latest_response_status}"
          if latest_endpoint_latency_ms is not None:
            status_line += f" {latest_endpoint_latency_ms:.0f}ms"
          video_lines.append(status_line)
        if latest_response_error:
          video_lines.append(latest_response_error[:54])
        if latest_plan_frame_id is not None:
          video_lines.append(f"plan id {latest_plan_frame_id} age {latest_plan_age_frames} lat {latest_plan_latency_ms or 0:.0f}ms")
        append_wrapped_reasoning_lines(video_lines, reasoning_overlay_text)
        frame = bench.draw_label_block(captured["road"]["_rgb"], video_lines)
        Image.fromarray(frame).save(out_dir / f"vlm_input_{frame_id:04d}.png")

      if terminated or truncated:
        break
      if args.tick_sec > 0:
        time.sleep(max(0.0, args.tick_sec - (time.perf_counter() - frame_start)))
  finally:
    env.close()
    if endpoint_future is not None and not endpoint_future.done():
      endpoint_future.cancel()
    if endpoint_executor is not None:
      endpoint_executor.shutdown(wait=False, cancel_futures=True)

  lane_abs = [abs(float(r["route_lateral_m"])) for r in records]
  speeds = [float(r["speed_mps"]) for r in records]
  route_distance = float(records[-1]["route_longitudinal_m"] - records[0]["route_longitudinal_m"]) if records else 0.0
  alpamayo_control_frames = sum(1 for r in records if str(r.get("control_source", "")).startswith("alpamayo_"))
  stock_control_frames = sum(1 for r in records if r.get("control_source") == "stock_route_follower")
  deadline_miss_count = sum(1 for value in endpoint_latencies if float(value) > float(args.deadline_ms))
  summary = {
    "mode": "alpamayofast",
    "frames": len(records),
    "nominal_speed_mps": args.speed_mps,
    "desired_speed_mps": args.speed_mps,
    "publish_count": endpoint_valid_successes,
    "valid_count": endpoint_valid_successes,
    "deadline_miss_count": deadline_miss_count,
    "endpoint_calls": endpoint_successes,
    "endpoint_attempts": endpoint_attempts,
    "valid_endpoint_responses": endpoint_valid_successes,
    "endpoint_error_count": len(endpoint_errors),
    "endpoint_errors": endpoint_errors[:10],
    "endpoint_latency_ms": {
      "mean": statistics.fmean(endpoint_latencies) if endpoint_latencies else None,
      "p95": percentile(endpoint_latencies, 95) if endpoint_latencies else None,
      "p99": percentile(endpoint_latencies, 99) if endpoint_latencies else None,
      "max": max(endpoint_latencies) if endpoint_latencies else None,
    },
    "response_reasoning_log": str(response_reasoning_log_path),
    "alpamayo_control_frames": alpamayo_control_frames,
    "stock_route_follower_frames": stock_control_frames,
    "mean_speed_mps": statistics.fmean(speeds) if speeds else 0.0,
    "final_speed_mps": speeds[-1] if speeds else 0.0,
    "route_distance_m": route_distance,
    "max_abs_route_lateral_m": max(lane_abs) if lane_abs else 0.0,
    "terminated": bool(terminated),
    "truncated": bool(truncated),
    "expected_lead_class": _expected_lead_class_from_spawned(spawned_scene),
    "records": records,
    "last_response_payload": last_response_payload,
  }
  (out_dir / "episode_alpamayofast_records.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
  return summary


def main() -> None:
  parser = argparse.ArgumentParser(description="Run an actual MetaDrive camera-frame demo with UI-style VLM overlays.")
  parser.add_argument("--frames", type=int, default=60)
  parser.add_argument("--speed-mps", type=float, default=10.0)
  parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="construction")
  parser.add_argument("--engine", choices=("static", "vlm", "alpamayofast"), default="static")
  parser.add_argument("--async-vlm", action="store_true")
  parser.add_argument("--vlm-period-frames", type=int, default=2)
  parser.add_argument("--vlm-max-age-frames", type=int, default=8)
  parser.add_argument("--vlm-latest-only", action="store_true")
  parser.add_argument("--vlm-drop-stale-results", action="store_true")
  parser.add_argument("--vlm-max-result-age-frames", type=int, default=8)
  parser.add_argument("--alpamayo-endpoint-url", default="http://127.0.0.1:8765/alpamayo")
  parser.add_argument("--alpamayo-endpoint-timeout-s", type=float, default=300.0)
  parser.add_argument("--alpamayo-model-step-sec", type=float, default=0.1)
  parser.add_argument("--alpamayo-num-frames", type=int, default=4)
  parser.add_argument("--alpamayo-query-every", type=int, default=2)
  parser.add_argument("--alpamayo-catchup-stride-steps", type=int, default=1)
  parser.add_argument("--alpamayo-warmup-stock-frames", type=int, default=None)
  parser.add_argument("--alpamayo-backfill-ego-history", action="store_true")
  parser.add_argument("--alpamayo-jpeg-quality", type=int, default=85)
  parser.add_argument("--alpamayo-sync-endpoint", action="store_true")
  parser.add_argument("--alpamayo-wait-first-plan", action=argparse.BooleanOptionalAction, default=True)
  parser.add_argument("--alpamayo-max-steer", type=float, default=0.75)
  parser.add_argument("--alpamayo-control-mode", choices=("planner_bridge", "trajectory"), default="planner_bridge", help="planner_bridge treats Alpamayo semanticPlan as planner output and uses the MetaDrive route follower as the actuator layer; trajectory is the direct low-level diagnostic path.")
  parser.add_argument("--alpamayo-lateral-preview-m", type=float, default=12.0)
  parser.add_argument("--alpamayo-lateral-gain", type=float, default=1.0)
  parser.add_argument("--alpamayo-max-lateral-offset-m", type=float, default=0.8)
  parser.add_argument("--alpamayo-steer-sign", type=float, choices=(-1.0, 1.0), default=-1.0, help="Lateral sign applied when mapping Alpamayo ego-frame path y into MetaDrive route lateral target.")
  parser.add_argument("--alpamayo-reasoning-overlay", action=argparse.BooleanOptionalAction, default=True, help="Append Alpamayo reasoning/cot preview text to the existing video overlay.")
  parser.add_argument("--alpamayo-reasoning-overlay-chars", type=int, default=180)
  parser.add_argument("--alpamayo-reasoning-overlay-line-chars", type=int, default=54)
  parser.add_argument("--prewarm-seconds", type=float, default=90.0)
  parser.add_argument("--prewarm-reset-runtime-state", action=argparse.BooleanOptionalAction, default=True, help="Reset rotating VLM state after async prewarm. Disable to model real pre-engagement warm state with monotonic model frame ids.")
  parser.add_argument("--deadline-ms", type=float, default=50.0)
  parser.add_argument("--tick-sec", type=float, default=0.05)
  parser.add_argument("--map", default="3")
  parser.add_argument(
    "--novel-scene",
    choices=("none", *sorted(CONSTRUCTION_SCENES), "pedestrian", "traffic_light", "stop_sign", "random_mixed", *sorted(VEHICLE_SCENES)),
    default="none",
  )
  parser.add_argument("--camera-width", type=int, default=512)
  parser.add_argument("--camera-height", type=int, default=320)
  parser.add_argument("--camera-color-order", choices=("bgr", "rgb"), default="bgr")
  parser.add_argument("--board-width", type=int, default=320)
  parser.add_argument("--board-height", type=int, default=200)
  parser.add_argument("--scene-board-candidate-guides", action=argparse.BooleanOptionalAction, default=False)
  parser.add_argument("--candidate-guide-offset-m", type=float, default=1.25)
  parser.add_argument("--scene-board-corridor-half-width-m", type=float, default=OverlayGeometry.planned_corridor_half_width_m)
  parser.add_argument("--scene-board-focus-extra-width-m", type=float, default=OverlayGeometry.focus_corridor_extra_width_m)
  parser.add_argument("--scene-board-dim-outside-corridor", action=argparse.BooleanOptionalAction, default=OverlayGeometry.dim_outside_corridor)
  parser.add_argument("--scene-board-dim-alpha", type=int, default=OverlayGeometry.outside_corridor_dim_alpha)
  parser.add_argument("--scene-board-corridor-side-guides", action=argparse.BooleanOptionalAction, default=OverlayGeometry.draw_corridor_side_guides)
  parser.add_argument("--scene-board-corridor-side-fill", action=argparse.BooleanOptionalAction, default=OverlayGeometry.draw_corridor_side_fill)
  parser.add_argument("--scene-board-corridor-side-labels", action=argparse.BooleanOptionalAction, default=OverlayGeometry.draw_corridor_side_labels)
  parser.add_argument("--scene-board-base-path-reference", action=argparse.BooleanOptionalAction, default=OverlayGeometry.draw_base_path_reference)
  parser.add_argument("--scene-board-candidate-labels", action=argparse.BooleanOptionalAction, default=OverlayGeometry.draw_candidate_labels)
  parser.add_argument("--scene-board-edge-insets", action=argparse.BooleanOptionalAction, default=OverlayGeometry.draw_edge_insets)
  parser.add_argument("--scene-board-candidate-obstruction-boards", action=argparse.BooleanOptionalAction, default=OverlayGeometry.draw_candidate_obstruction_boards)
  parser.add_argument("--scene-board-candidate-obstruction-offset-m", type=float, default=OverlayGeometry.candidate_obstruction_offset_m)
  parser.add_argument("--save-every", type=int, default=5)
  parser.add_argument("--seed", type=int, default=7)
  parser.add_argument("--avoid-lead-m", type=float, default=10.0)
  parser.add_argument("--avoid-recover-m", type=float, default=10.0)
  parser.add_argument("--min-construction-offset-m", type=float, default=1.25)
  parser.add_argument("--max-durable-offset-m", type=float, default=1.3)
  parser.add_argument("--max-lateral-offset-rate-mps", type=float, default=0.55)
  parser.add_argument("--max-steer-rate-per-s", type=float, default=0.9)
  parser.add_argument("--steer-smoothing-alpha", type=float, default=0.35)
  parser.add_argument("--durable-override-confidence", type=float, default=0.70)
  parser.add_argument("--durable-lateral-activation-confidence", type=float, default=0.80)
  parser.add_argument("--durable-lateral-activation-confirm-frames", type=int, default=3)
  parser.add_argument("--durable-lateral-activation-immediate-confidence", type=float, default=0.95)
  parser.add_argument("--durable-conflict-override-confidence", type=float, default=0.90)
  parser.add_argument("--durable-signal-clear-confidence", type=float, default=0.80, help="Confidence threshold for a current green-signal RTP to clear stale signal-stop plans.")
  parser.add_argument("--durable-conflict-confirm-frames", type=int, default=3)
  parser.add_argument("--durable-conflict-immediate-confidence", type=float, default=0.95)
  parser.add_argument("--durable-construction-conflict-immediate-confidence", type=float, default=0.95, help="Immediate-confidence threshold for reversing an active construction lateral plan after the Qwen side state machine has accepted a contradictory side.")
  parser.add_argument("--allow-compiled-lateral-fallback", action=argparse.BooleanOptionalAction, default=False, help="Opt back into directly tracking a just-compiled one-frame lateral offset when no durable lateral plan activated. Default is off so repeated-activation guards cannot be bypassed.")
  parser.add_argument("--disable-vlm-speed-control", action="store_true")
  parser.add_argument("--durable-slow-speed-scale", type=float, default=0.25)
  parser.add_argument("--durable-speed-min-horizon-m", type=float, default=10.0)
  parser.add_argument("--durable-speed-recover-m", type=float, default=3.0)
  parser.add_argument("--random-scene-seed", type=int, default=42)
  parser.add_argument("--random-scene-route-m", type=float, default=180.0)
  parser.add_argument("--random-construction-start-s", type=float, default=14.0)
  parser.add_argument("--random-construction-spacing-min-m", type=float, default=22.0)
  parser.add_argument("--random-construction-spacing-max-m", type=float, default=34.0)
  parser.add_argument("--random-construction-max-objects", type=int, default=4)
  parser.add_argument("--random-construction-right-probability", type=float, default=0.7)
  parser.add_argument("--random-pedestrian-start-s", type=float, default=24.0)
  parser.add_argument("--random-pedestrian-spacing-min-m", type=float, default=32.0)
  parser.add_argument("--random-pedestrian-spacing-max-m", type=float, default=48.0)
  parser.add_argument("--random-pedestrian-speed-min-mps", type=float, default=0.8)
  parser.add_argument("--random-pedestrian-speed-max-mps", type=float, default=1.6)
  parser.add_argument("--vehicle-scene-route-s", type=float, default=24.0)
  parser.add_argument("--route-vehicle-model", choices=ROUTE_VEHICLE_MODEL_CLASSES, default=ROUTE_VEHICLE_MODEL_CLASS)
  parser.add_argument("--route-vehicle-special-color", action=argparse.BooleanOptionalAction, default=ROUTE_VEHICLE_USE_SPECIAL_COLOR)
  parser.add_argument("--route-vehicle-visual-heading-offset-deg", type=float, default=math.degrees(ROUTE_VEHICLE_VISUAL_HEADING_OFFSET_RAD))
  parser.add_argument("--slower-lead-speed-scale", type=float, default=0.55)
  parser.add_argument("--braking-lead-initial-speed-scale", type=float, default=0.85)
  parser.add_argument("--braking-lead-decel-mps2", type=float, default=1.4)
  parser.add_argument("--lead-clear-path-lateral-m", type=float, default=1.35, help="Physical lead-track lateral bound used to clear stale lead speed plans when a tracked vehicle is outside the ego path.")
  parser.add_argument("--lead-clear-true-moving-closing-mps", type=float, default=0.35, help="Maximum closing speed treated as stable/opening for clearing stale lead slow plans between VLM updates.")
  parser.add_argument("--lead-clear-true-moving-rel-loss-mps", type=float, default=0.35, help="Maximum negative relative speed still treated as true-moving for stale lead slow-plan clearing.")
  parser.add_argument("--lead-clear-non-braking-accel-mps2", type=float, default=0.60, help="Acceleration magnitude below which the physical lead track is not considered braking for stale slow-plan clearing.")
  parser.add_argument("--cut-in-start-lateral-m", type=float, default=1.65)
  parser.add_argument("--cut-in-lateral-rate-mps", type=float, default=0.75)
  parser.add_argument("--cut-in-speed-scale", type=float, default=0.75)
  parser.add_argument("--crossing-vehicle-start-lateral-m", type=float, default=-1.75)
  parser.add_argument("--crossing-vehicle-lateral-rate-mps", type=float, default=1.20)
  parser.add_argument("--crossing-vehicle-longitudinal-speed-scale", type=float, default=0.10)
  parser.add_argument("--irrelevant-vehicle-lateral-m", type=float, default=2.00)
  parser.add_argument("--include-traffic-light", action=argparse.BooleanOptionalAction, default=False)
  parser.add_argument("--traffic-light-route-s", type=float, default=48.0)
  parser.add_argument("--traffic-light-lateral-m", type=float, default=0.0)
  parser.add_argument("--traffic-light-green-frame", type=int, default=140)
  parser.add_argument("--traffic-light-cycle", action=argparse.BooleanOptionalAction, default=False)
  parser.add_argument("--traffic-light-red-frames", type=int, default=140)
  parser.add_argument("--traffic-light-green-frames", type=int, default=140)
  parser.add_argument("--traffic-light-stop-before-m", type=float, default=5.0)
  parser.add_argument("--traffic-light-decel-distance-m", type=float, default=28.0)
  parser.add_argument("--traffic-light-full-stop-m", type=float, default=4.0)
  parser.add_argument("--traffic-light-stop-hold-radius-m", type=float, default=0.75)
  parser.add_argument("--traffic-light-comfort-decel-mps2", type=float, default=1.1)
  parser.add_argument("--traffic-light-passed-ignore-m", type=float, default=2.0)
  parser.add_argument("--enable-visual-signal-guard", action=argparse.BooleanOptionalAction, default=False, help="Demo-only rendered-pixel signal guard. Keep disabled for Qwen-only production-path evaluation.")
  parser.add_argument("--disable-traffic-light-visual-overlay", action="store_true")
  parser.add_argument("--traffic-light-overlay-x-frac", type=float, default=0.56)
  parser.add_argument("--traffic-light-overlay-y-far-frac", type=float, default=0.22)
  parser.add_argument("--traffic-light-overlay-y-near-frac", type=float, default=0.32)
  parser.add_argument("--traffic-light-overlay-radius-px", type=int, default=16)
  parser.add_argument("--out", type=Path, default=REPO_ROOT / "artifacts" / "reasoned_trajectory_poc" / "metadrive_overlay_demo")
  args = parser.parse_args()

  args.out.mkdir(parents=True, exist_ok=True)
  started = time.perf_counter()
  stock = run_episode(args, "stock")
  reasoned = run_alpamayofast_episode(args) if args.engine == "alpamayofast" else run_episode(args, args.engine)
  comparison = {
    "engine": args.engine,
    "async_vlm": args.async_vlm,
    "elapsed_sec": time.perf_counter() - started,
    "stock": {k: v for k, v in stock.items() if k != "records"},
    "reasoned": {k: v for k, v in reasoned.items() if k != "records"},
    "delta_mean_speed_mps": reasoned["mean_speed_mps"] - stock["mean_speed_mps"],
    "delta_publish_count": reasoned["publish_count"] - stock["publish_count"],
  }
  out_path = args.out / f"comparison_{args.engine}.json"
  out_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
  print(json.dumps(comparison, indent=2))
  print(f"artifacts={args.out}")


if __name__ == "__main__":
  main()
