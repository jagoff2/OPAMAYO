#!/usr/bin/env python3
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import numpy as np

from selfdrive.alpamayo.protocol import REQUEST_CONTENT_TYPE, RESPONSE_CONTENT_TYPE, decode_payload, encode_payload


def _copy_xyzt(payload: dict[str, Any]) -> dict[str, list[float]]:
  return {
    "t": list(payload["t"]),
    "x": list(payload["x"]),
    "y": list(payload["y"]),
    "z": list(payload["z"]),
  }


def _caution_trajectory(stock_plan: dict[str, Any]) -> dict[str, Any]:
  trajectory = {
    "position": _copy_xyzt(stock_plan["position"]),
    "orientation": _copy_xyzt(stock_plan["orientation"]),
    "velocity": _copy_xyzt(stock_plan["velocity"]),
    "orientationRate": _copy_xyzt(stock_plan["orientationRate"]),
    "acceleration": _copy_xyzt(stock_plan["acceleration"]),
  }

  t = np.asarray(trajectory["position"]["t"], dtype=np.float32)
  far_mask = t >= 2.5
  if far_mask.any():
    vx = np.asarray(trajectory["velocity"]["x"], dtype=np.float32)
    ax = np.asarray(trajectory["acceleration"]["x"], dtype=np.float32)
    px = np.asarray(trajectory["position"]["x"], dtype=np.float32)

    vx[far_mask] *= 0.92
    ax[far_mask] = np.minimum(ax[far_mask] - 0.15, ax[far_mask])

    far_idxs = np.flatnonzero(far_mask)
    if len(far_idxs):
      start_idx = int(far_idxs[0])
      for idx in far_idxs:
        dt = max(float(t[idx] - t[start_idx]), 0.0)
        px[idx] = min(px[idx], px[start_idx] + max(vx[idx], 0.0) * dt)

    trajectory["velocity"]["x"] = vx.tolist()
    trajectory["acceleration"]["x"] = ax.tolist()
    trajectory["position"]["x"] = px.tolist()

  return trajectory


def make_semantic_plan(payload: dict[str, Any], mode: str) -> dict[str, Any]:
  stock_plan = payload["stockPlan"]
  stock_action = stock_plan["action"]
  if mode == "caution":
    trajectory = _caution_trajectory(stock_plan)
    confidence = 0.7
    blend_hint = 0.55
    desired_accel = min(float(stock_action["desiredAcceleration"]), -0.1)
  else:
    trajectory = {
      "position": _copy_xyzt(stock_plan["position"]),
      "orientation": _copy_xyzt(stock_plan["orientation"]),
      "velocity": _copy_xyzt(stock_plan["velocity"]),
      "orientationRate": _copy_xyzt(stock_plan["orientationRate"]),
      "acceleration": _copy_xyzt(stock_plan["acceleration"]),
    }
    confidence = 0.6
    blend_hint = 0.25
    desired_accel = float(stock_action["desiredAcceleration"])

  return {
    "protocolVersion": payload.get("protocolVersion", 1),
    "semanticPlan": {
      "status": "valid",
      "source": "remoteServer",
      "age": 0.0,
      "confidence": confidence,
      "consistency": 1.0,
      "blendHint": blend_hint,
      "desiredCurvature": float(stock_action["desiredCurvature"]),
      "desiredAcceleration": desired_accel,
      "shouldStop": bool(stock_action["shouldStop"]),
      "trajectory": trajectory,
    },
  }


class SemanticPlanHandler(BaseHTTPRequestHandler):
  mode = "echo"

  def do_POST(self):
    try:
      content_length = int(self.headers.get("Content-Length", "0"))
      body = self.rfile.read(content_length)
      payload = decode_payload(body)
      response = make_semantic_plan(payload, self.mode)
      encoded = encode_payload(response)

      self.send_response(200)
      self.send_header("Content-Type", RESPONSE_CONTENT_TYPE)
      self.send_header("X-Alpamayo-Stub-Mode", self.mode)
      self.send_header("Content-Length", str(len(encoded)))
      self.end_headers()
      self.wfile.write(encoded)
    except Exception as exc:
      encoded = encode_payload({"error": str(exc), "status": "error"})
      self.send_response(400)
      self.send_header("Content-Type", RESPONSE_CONTENT_TYPE)
      self.send_header("Content-Length", str(len(encoded)))
      self.end_headers()
      self.wfile.write(encoded)

  def log_message(self, format: str, *args) -> None:
    return


def main():
  parser = argparse.ArgumentParser(description="Alpamayo semantic plan stub server")
  parser.add_argument("--host", default="0.0.0.0")
  parser.add_argument("--port", type=int, default=8081)
  parser.add_argument("--mode", choices=["echo", "caution"], default="echo")
  args = parser.parse_args()

  handler = type("SemanticPlanHandlerConfigured", (SemanticPlanHandler,), {"mode": args.mode})
  server = ThreadingHTTPServer((args.host, args.port), handler)
  print(f"alpamayo stub listening on http://{args.host}:{args.port} mode={args.mode} expects={REQUEST_CONTENT_TYPE}")
  server.serve_forever()


if __name__ == "__main__":
  main()
