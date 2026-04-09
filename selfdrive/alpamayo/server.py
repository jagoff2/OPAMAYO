#!/usr/bin/env python3
import argparse
import base64
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np

from selfdrive.alpamayo.protocol import (
  FRAME_ENCODING_JPEG_BGR,
  FRAME_ENCODING_NV12,
  REQUEST_CONTENT_TYPE,
  RESPONSE_CONTENT_TYPE,
  decode_payload,
  encode_payload,
  parse_xyzt_dict,
  xyzt_to_dict,
)


STREAM_ORDER = ("wideRoad", "road")
STREAM_CAMERA_INDICES = {
  "wideRoad": 1,
  "road": 6,
}
DEFAULT_MIN_PIXELS = 65536
DEFAULT_MAX_PIXELS = 65536
DEFAULT_DIFFUSION_STEPS = 6
DEFAULT_NUM_TRAJ_SAMPLES = 1
DEFAULT_NUM_FRAMES = 2
DEFAULT_REASONING_MODE = "prefill_future_start"


def build_manual_split_device_map(split_index: int) -> dict[str, int]:
  device_map: dict[str, int] = {
    "vlm.model.visual": 0,
    "vlm.model.language_model.embed_tokens": 0,
    "vlm.model.language_model.norm": 1,
    "vlm.model.language_model.rotary_emb": 1,
    "vlm.lm_head": 1,
    "expert.norm": 1,
    "expert.rotary_emb": 1,
    "action_in_proj": 0,
    "action_out_proj": 1,
    "action_space": 0,
    "diffusion": 0,
  }
  for layer_idx in range(36):
    device = 0 if layer_idx < split_index else 1
    device_map[f"vlm.model.language_model.layers.{layer_idx}"] = device
    device_map[f"expert.layers.{layer_idx}"] = device
  return device_map


def set_module_attention_implementation(module, attn_implementation: str) -> None:
  for submodule in module.modules():
    config = getattr(submodule, "config", None)
    if config is not None:
      setattr(config, "_attn_implementation", attn_implementation)
      if hasattr(config, "attn_implementation"):
        setattr(config, "attn_implementation", attn_implementation)


def _resolve_alpamayo_repo(repo_path: str | None) -> Path:
  candidates = [
    Path(repo_path) if repo_path else None,
    Path(os.getenv("ALPAMAYO_REPO", "")) if os.getenv("ALPAMAYO_REPO") else None,
    Path(__file__).resolve().parents[3] / "alpamayo1.5",
    Path.cwd() / "alpamayo1.5",
  ]
  for candidate in candidates:
    if candidate is not None and candidate.exists():
      return candidate.resolve()
  raise FileNotFoundError("Unable to locate alpamayo1.5 repo. Set --alpamayo-repo or ALPAMAYO_REPO.")


def _ensure_alpamayo_importable(repo_path: Path) -> None:
  repo_str = str(repo_path)
  if repo_str not in sys.path:
    sys.path.insert(0, repo_str)


def _yaw_from_rotations(rotations: np.ndarray) -> np.ndarray:
  return np.unwrap(np.arctan2(rotations[:, 1, 0], rotations[:, 0, 0]).astype(np.float32))


def _interp_with_stock_tail(stock_t: np.ndarray, dense_t: np.ndarray, dense_values: np.ndarray, stock_values: np.ndarray) -> np.ndarray:
  out = stock_values.copy()
  active_mask = stock_t <= dense_t[-1]
  if active_mask.any():
    for axis in range(dense_values.shape[1]):
      out[active_mask, axis] = np.interp(stock_t[active_mask], dense_t, dense_values[:, axis])
  return out.astype(np.float32)


def _interp_scalar_with_stock_tail(stock_t: np.ndarray, dense_t: np.ndarray, dense_values: np.ndarray, stock_values: np.ndarray) -> np.ndarray:
  out = stock_values.copy()
  active_mask = stock_t <= dense_t[-1]
  if active_mask.any():
    out[active_mask] = np.interp(stock_t[active_mask], dense_t, dense_values)
  return out.astype(np.float32)


def _decode_nv12_rgb(frame_payload: dict[str, Any]) -> np.ndarray:
  import cv2

  width = int(frame_payload["width"])
  height = int(frame_payload["height"])
  stride = int(frame_payload["stride"])
  payload = base64.b64decode(frame_payload["dataBase64"])
  expected_bytes = stride * height * 3 // 2
  if len(payload) < expected_bytes:
    raise ValueError(f"Frame payload too short: got={len(payload)} expected>={expected_bytes}")

  nv12 = np.frombuffer(payload[:expected_bytes], dtype=np.uint8).reshape((height + height // 2, stride))
  rgb = cv2.cvtColor(nv12[:, :width], cv2.COLOR_YUV2RGB_NV12)
  return np.transpose(rgb, (2, 0, 1)).copy()


def _decode_jpeg_bgr_rgb(frame_payload: dict[str, Any]) -> np.ndarray:
  import cv2

  payload = base64.b64decode(frame_payload["dataBase64"])
  compressed = np.frombuffer(payload, dtype=np.uint8)
  bgr = cv2.imdecode(compressed, cv2.IMREAD_COLOR)
  if bgr is None:
    raise ValueError("Failed to decode JPEG transport frame")
  rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
  return np.transpose(rgb, (2, 0, 1)).copy()


def _decode_frame_rgb(frame_payload: dict[str, Any]) -> np.ndarray:
  encoding = frame_payload.get("encoding", FRAME_ENCODING_NV12)
  if encoding == FRAME_ENCODING_NV12:
    return _decode_nv12_rgb(frame_payload)
  if encoding == FRAME_ENCODING_JPEG_BGR:
    return _decode_jpeg_bgr_rgb(frame_payload)
  raise ValueError(f"Unsupported frame encoding: {encoding}")


def _group_frames(frame_payloads: list[dict[str, Any]], frames_per_camera: int) -> dict[str, list[dict[str, Any]]]:
  grouped: dict[str, list[dict[str, Any]]] = {name: [] for name in STREAM_ORDER}
  for frame_payload in frame_payloads:
    stream = frame_payload.get("stream")
    if stream in grouped:
      grouped[stream].append(frame_payload)

  for stream_name in STREAM_ORDER:
    grouped[stream_name].sort(key=lambda payload: int(payload.get("timestampEof", 0)))
    if len(grouped[stream_name]) < frames_per_camera:
      raise ValueError(f"Missing {frames_per_camera} frames for stream={stream_name}")
    grouped[stream_name] = grouped[stream_name][-frames_per_camera:]
  return grouped


def _stack_image_frames(grouped_frames: dict[str, list[dict[str, Any]]], torch_module) -> tuple[Any, Any]:
  image_frames = []
  camera_indices = []
  for stream_name in STREAM_ORDER:
    stream_tensors = [torch_module.from_numpy(_decode_frame_rgb(frame_payload)) for frame_payload in grouped_frames[stream_name]]
    image_frames.append(torch_module.stack(stream_tensors, dim=0))
    camera_indices.append(STREAM_CAMERA_INDICES[stream_name])
  return torch_module.stack(image_frames, dim=0), torch_module.tensor(camera_indices, dtype=torch_module.int64)


def _build_nav_text(navigation_payload: dict[str, Any] | None) -> str | None:
  if not isinstance(navigation_payload, dict):
    return None
  text = str(navigation_payload.get("text", "")).strip()
  if text:
    return text

  primary = str(navigation_payload.get("maneuverPrimaryText", "")).strip()
  secondary = str(navigation_payload.get("maneuverSecondaryText", "")).strip()
  distance_m = float(navigation_payload.get("maneuverDistance", 0.0) or 0.0)
  parts = [part for part in (primary, secondary) if part]
  if distance_m > 0.0:
    parts.append(f"in {int(round(distance_m))}m")
  return " ".join(parts) if parts else None


def _make_messages(helper_module, image_frames, camera_indices, num_frames: int, reasoning_mode: str, nav_text: str | None) -> list[dict[str, Any]]:
  messages = helper_module.create_message(
    frames=image_frames.flatten(0, 1),
    camera_indices=camera_indices,
    num_frames_per_camera=num_frames,
    nav_text=nav_text,
  )
  if reasoning_mode == DEFAULT_REASONING_MODE:
    prompt = "output the chain-of-thought reasoning of the driving process, then output the future trajectory."
    messages[1]["content"][-1]["text"] = messages[1]["content"][-1]["text"].replace(prompt, "output the future trajectory.")
    messages[2]["content"] = [{"type": "text", "text": "<|traj_future_start|>"}]
  return messages


def _parse_stock_component(stock_plan: dict[str, Any], key: str, default_t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
  parsed = parse_xyzt_dict(stock_plan[key], default_t)
  if parsed is None:
    raise ValueError(f"Invalid stock plan component: {key}")
  return parsed


def _build_semantic_trajectory(stock_plan: dict[str, Any], pred_xyz: np.ndarray, pred_rot: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray]]:
  stock_t, stock_position = _parse_stock_component(stock_plan, "position", np.asarray(stock_plan["position"]["t"], dtype=np.float32))
  _, stock_orientation = _parse_stock_component(stock_plan, "orientation", stock_t)
  _, stock_velocity = _parse_stock_component(stock_plan, "velocity", stock_t)
  _, stock_orientation_rate = _parse_stock_component(stock_plan, "orientationRate", stock_t)
  _, stock_acceleration = _parse_stock_component(stock_plan, "acceleration", stock_t)

  dense_t = np.concatenate(([0.0], np.arange(0.1, 0.1 * len(pred_xyz) + 1e-6, 0.1, dtype=np.float32))).astype(np.float32)
  dense_position_xy = np.vstack([np.zeros((1, 2), dtype=np.float32), pred_xyz[:, :2].astype(np.float32)])
  dense_velocity_xy = np.gradient(dense_position_xy, dense_t, axis=0, edge_order=2).astype(np.float32)
  dense_acceleration_xy = np.gradient(dense_velocity_xy, dense_t, axis=0, edge_order=2).astype(np.float32)
  dense_yaw = np.concatenate(([0.0], _yaw_from_rotations(pred_rot))).astype(np.float32)
  dense_yaw_rate = np.gradient(dense_yaw, dense_t, edge_order=2).astype(np.float32)

  semantic_position = stock_position.copy()
  semantic_position[:, :2] = _interp_with_stock_tail(stock_t, dense_t, dense_position_xy, stock_position[:, :2])

  semantic_orientation = stock_orientation.copy()
  semantic_orientation[:, 2] = _interp_scalar_with_stock_tail(stock_t, dense_t, dense_yaw, stock_orientation[:, 2])

  semantic_velocity = stock_velocity.copy()
  semantic_velocity[:, :2] = _interp_with_stock_tail(stock_t, dense_t, dense_velocity_xy, stock_velocity[:, :2])

  semantic_acceleration = stock_acceleration.copy()
  semantic_acceleration[:, :2] = _interp_with_stock_tail(stock_t, dense_t, dense_acceleration_xy, stock_acceleration[:, :2])

  semantic_orientation_rate = stock_orientation_rate.copy()
  semantic_orientation_rate[:, 2] = _interp_scalar_with_stock_tail(stock_t, dense_t, dense_yaw_rate, stock_orientation_rate[:, 2])

  return stock_t.astype(np.float32), {
    "position": semantic_position.astype(np.float32),
    "orientation": semantic_orientation.astype(np.float32),
    "velocity": semantic_velocity.astype(np.float32),
    "orientationRate": semantic_orientation_rate.astype(np.float32),
    "acceleration": semantic_acceleration.astype(np.float32),
  }


class FastAlpamayoRuntime:
  def __init__(self, args: argparse.Namespace):
    self.args = args
    self.model_lock = threading.Lock()

    repo_path = _resolve_alpamayo_repo(args.alpamayo_repo)
    _ensure_alpamayo_importable(repo_path)

    import torch
    from alpamayo1_5 import helper
    from alpamayo1_5.models.alpamayo1_5 import Alpamayo1_5

    self.repo_path = repo_path
    self.torch = torch
    self.helper = helper
    self.Alpamayo1_5 = Alpamayo1_5

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    self.helper.MIN_PIXELS = args.min_pixels
    self.helper.MAX_PIXELS = args.max_pixels
    self.model = self._build_model()
    self.processor = self.helper.get_processor(self.model.tokenizer)

  def _build_model(self):
    torch = self.torch
    gpu_count = torch.cuda.device_count()
    if gpu_count < 2:
      raise RuntimeError(f"Current proven Alpamayo server config requires 2 CUDA GPUs, found={gpu_count}")

    max_memory = {idx: f"{self.args.gpu_mem_gib}GiB" for idx in range(gpu_count)}
    max_memory["cpu"] = f"{self.args.cpu_mem_gib}GiB"
    device_map = build_manual_split_device_map(self.args.split_index)
    model = self.Alpamayo1_5.from_pretrained(
      "nvidia/Alpamayo-1.5-10B",
      dtype=torch.bfloat16,
      attn_implementation=self.args.attn_implementation,
      device_map=device_map,
      max_memory=max_memory,
      low_cpu_mem_usage=True,
    )
    if self.args.expert_attn_implementation:
      set_module_attention_implementation(model.expert, self.args.expert_attn_implementation)
    return model

  def infer(self, payload: dict[str, Any]) -> dict[str, Any]:
    torch = self.torch

    decode_start = time.perf_counter()
    camera_bundle = payload.get("cameraBundle") or {}
    frames_per_camera = int(camera_bundle.get("framesPerCamera", DEFAULT_NUM_FRAMES))
    grouped_frames = _group_frames(payload["frames"], frames_per_camera)
    image_frames, camera_indices = _stack_image_frames(grouped_frames, torch)
    ego_history_payload = payload["egoHistory"]
    ego_history_xyz = torch.tensor(ego_history_payload["xyz"], dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    ego_history_rot = torch.tensor(ego_history_payload["rot"], dtype=torch.float32).unsqueeze(0).unsqueeze(0)
    nav_text = _build_nav_text(payload.get("navigation"))
    decode_seconds = time.perf_counter() - decode_start

    message_start = time.perf_counter()
    messages = _make_messages(self.helper, image_frames, camera_indices, frames_per_camera, self.args.reasoning_mode, nav_text)
    inputs = self.processor.apply_chat_template(
      messages,
      tokenize=True,
      add_generation_prompt=False,
      continue_final_message=True,
      return_dict=True,
      return_tensors="pt",
    )
    model_inputs = {
      "tokenized_data": inputs,
      "ego_history_xyz": ego_history_xyz,
      "ego_history_rot": ego_history_rot,
    }
    model_inputs = self.helper.to_device(model_inputs, self.model.device)
    message_seconds = time.perf_counter() - message_start

    with self.model_lock:
      torch.cuda.manual_seed_all(self.args.seed)
      runtime_profile: dict[str, float | int] = {}
      infer_start = time.perf_counter()
      with torch.inference_mode():
        with torch.autocast("cuda", dtype=torch.bfloat16):
          pred_xyz, pred_rot = self.model.sample_trajectories_from_data_with_vlm_rollout(
            data=model_inputs,
            top_p=self.args.top_p,
            temperature=self.args.temperature,
            num_traj_samples=self.args.num_traj_samples,
            diffusion_kwargs={"inference_step": self.args.diffusion_steps},
            runtime_profile=runtime_profile,
            skip_vlm_generation=(self.args.reasoning_mode == DEFAULT_REASONING_MODE),
          )
      inference_seconds = time.perf_counter() - infer_start

    pred_xyz_np = pred_xyz.detach().cpu().numpy()[0, 0, 0]
    pred_rot_np = pred_rot.detach().cpu().numpy()[0, 0, 0]
    stock_t, semantic = _build_semantic_trajectory(payload["stockPlan"], pred_xyz_np, pred_rot_np)

    action = payload["stockPlan"].get("action", {})
    curvature_index = int(np.searchsorted(stock_t, 0.5, side="left"))
    curvature_index = min(curvature_index, len(stock_t) - 1)
    semantic_vx = float(semantic["velocity"][curvature_index, 0])
    semantic_yaw_rate = float(semantic["orientationRate"][curvature_index, 2])
    desired_curvature = float(semantic_yaw_rate / max(abs(semantic_vx), 0.1))
    desired_acceleration = float(semantic["acceleration"][curvature_index, 0])

    return {
      "protocolVersion": int(payload.get("protocolVersion", 1)),
      "semanticPlan": {
        "status": "valid",
        "source": self.args.source,
        "age": 0.0,
        "confidence": 0.85,
        "consistency": 1.0,
        "blendHint": 1.0,
        "desiredCurvature": desired_curvature,
        "desiredAcceleration": desired_acceleration,
        "shouldStop": bool(action.get("shouldStop", False)),
        "trajectory": {
          "position": xyzt_to_dict(stock_t, semantic["position"]),
          "orientation": xyzt_to_dict(stock_t, semantic["orientation"]),
          "velocity": xyzt_to_dict(stock_t, semantic["velocity"]),
          "orientationRate": xyzt_to_dict(stock_t, semantic["orientationRate"]),
          "acceleration": xyzt_to_dict(stock_t, semantic["acceleration"]),
        },
      },
      "runtime": {
        "decodeSeconds": round(decode_seconds, 4),
        "messageSeconds": round(message_seconds, 4),
        "inferenceSeconds": round(inference_seconds, 4),
        "runtimeProfile": runtime_profile,
      },
    }


class SemanticPlanHandler(BaseHTTPRequestHandler):
  runtime: FastAlpamayoRuntime | None = None

  def do_GET(self):
    if self.path != "/_health":
      self.send_response(404)
      self.end_headers()
      return

    encoded = encode_payload({"ready": self.runtime is not None})
    self.send_response(200)
    self.send_header("Content-Type", RESPONSE_CONTENT_TYPE)
    self.send_header("Content-Length", str(len(encoded)))
    self.end_headers()
    self.wfile.write(encoded)

  def do_POST(self):
    if self.runtime is None:
      encoded = encode_payload({"error": "runtime not initialized"})
      self.send_response(503)
      self.send_header("Content-Type", RESPONSE_CONTENT_TYPE)
      self.send_header("Content-Length", str(len(encoded)))
      self.end_headers()
      self.wfile.write(encoded)
      return

    request_id = time.time_ns() & 0xFFFFFFFF
    request_start = time.perf_counter()
    try:
      content_length = int(self.headers.get("Content-Length", "0"))
      body = self.rfile.read(content_length)
      read_seconds = time.perf_counter() - request_start
      decode_start = time.perf_counter()
      payload = decode_payload(body)
      decode_seconds = time.perf_counter() - decode_start
      infer_start = time.perf_counter()
      response = self.runtime.infer(payload)
      infer_seconds = time.perf_counter() - infer_start
      encode_start = time.perf_counter()
      encoded = encode_payload(response)
      encode_seconds = time.perf_counter() - encode_start
      self.send_response(200)
      self.send_header("Content-Type", RESPONSE_CONTENT_TYPE)
      self.send_header("Content-Length", str(len(encoded)))
      self.end_headers()
      self.wfile.write(encoded)
      total_seconds = time.perf_counter() - request_start
      semantic = response.get("semanticPlan", {})
      runtime = response.get("runtime", {})
      print(
        f"alpamayo request ok id={request_id} in={content_length} out={len(encoded)} "
        f"read={read_seconds:.3f}s decode={decode_seconds:.3f}s infer={infer_seconds:.3f}s "
        f"encode={encode_seconds:.3f}s total={total_seconds:.3f}s "
        f"status={semantic.get('status')} source={semantic.get('source')} "
        f"server_decode={runtime.get('decodeSeconds')} message={runtime.get('messageSeconds')} "
        f"inference={runtime.get('inferenceSeconds')}",
        flush=True,
      )
    except Exception as exc:
      total_seconds = time.perf_counter() - request_start
      encoded = encode_payload({"status": "error", "error": str(exc)})
      self.send_response(500)
      self.send_header("Content-Type", RESPONSE_CONTENT_TYPE)
      self.send_header("Content-Length", str(len(encoded)))
      self.end_headers()
      self.wfile.write(encoded)
      print(f"alpamayo request error id={request_id} total={total_seconds:.3f}s error={exc}", flush=True)
      traceback.print_exc()

  def log_message(self, format: str, *args) -> None:
    return


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Real Alpamayo semantic-plan server")
  parser.add_argument("--host", default="0.0.0.0")
  parser.add_argument("--port", type=int, default=8081)
  parser.add_argument("--alpamayo-repo", default=None)
  parser.add_argument("--gpu-mem-gib", type=int, default=15)
  parser.add_argument("--cpu-mem-gib", type=int, default=96)
  parser.add_argument("--split-index", type=int, default=16)
  parser.add_argument("--min-pixels", type=int, default=DEFAULT_MIN_PIXELS)
  parser.add_argument("--max-pixels", type=int, default=DEFAULT_MAX_PIXELS)
  parser.add_argument("--diffusion-steps", type=int, default=DEFAULT_DIFFUSION_STEPS)
  parser.add_argument("--num-traj-samples", type=int, default=DEFAULT_NUM_TRAJ_SAMPLES)
  parser.add_argument("--attn-implementation", choices=["eager", "sdpa", "flash_attention_2"], default="flash_attention_2")
  parser.add_argument("--expert-attn-implementation", choices=["eager", "sdpa", "flash_attention_2"], default="eager")
  parser.add_argument("--reasoning-mode", choices=["full", "prefill_future_start"], default=DEFAULT_REASONING_MODE)
  parser.add_argument("--top-p", type=float, default=0.98)
  parser.add_argument("--temperature", type=float, default=0.6)
  parser.add_argument("--seed", type=int, default=42)
  parser.add_argument("--source", choices=["remoteServer", "localEgpu"], default="remoteServer")
  return parser.parse_args()


def main():
  args = parse_args()
  handler = type("SemanticPlanHandlerConfigured", (SemanticPlanHandler,), {})
  handler.runtime = FastAlpamayoRuntime(args)
  server = ThreadingHTTPServer((args.host, args.port), handler)
  print(
    f"alpamayo server listening on http://{args.host}:{args.port} "
    f"content-type={REQUEST_CONTENT_TYPE} repo={handler.runtime.repo_path}",
    flush=True,
  )
  server.serve_forever()


if __name__ == "__main__":
  main()
