import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import physical_ai_av
import scipy.spatial.transform as spt


CLIP_IDS_PATH = Path("/mnt/g/alpamayo1.5/notebooks/clip_ids.parquet")
OUT_PATH = Path("/mnt/g/alpamayo1.5/normal_driving_samples.json")

DEFAULT_T0_US = 5_100_000
DT = 0.1
NUM_HISTORY_STEPS = 16
NUM_FUTURE_STEPS = 64


def load_clip_ids(limit: int | None = None) -> list[str]:
    df = pd.read_parquet(CLIP_IDS_PATH)
    clip_ids = df["clip_id"].tolist()
    return clip_ids if limit is None else clip_ids[:limit]


def compute_local_future(
    avdi: physical_ai_av.PhysicalAIAVDatasetInterface,
    clip_id: str,
    t0_us: int,
) -> tuple[np.ndarray, np.ndarray]:
    egomotion = avdi.get_clip_feature(
        clip_id,
        avdi.features.LABELS.EGOMOTION,
        maybe_stream=True,
    )

    history_offsets_us = np.arange(
        -(NUM_HISTORY_STEPS - 1) * DT * 1_000_000,
        DT * 1_000_000 / 2,
        DT * 1_000_000,
    ).astype(np.int64)
    future_offsets_us = np.arange(
        DT * 1_000_000,
        (NUM_FUTURE_STEPS + 0.5) * DT * 1_000_000,
        DT * 1_000_000,
    ).astype(np.int64)

    history_timestamps = t0_us + history_offsets_us
    future_timestamps = t0_us + future_offsets_us

    ego_history = egomotion(history_timestamps)
    ego_future = egomotion(future_timestamps)

    ego_history_xyz = ego_history.pose.translation
    ego_history_quat = ego_history.pose.rotation.as_quat()
    ego_future_xyz = ego_future.pose.translation
    ego_future_quat = ego_future.pose.rotation.as_quat()

    t0_xyz = ego_history_xyz[-1].copy()
    t0_quat = ego_history_quat[-1].copy()
    t0_rot = spt.Rotation.from_quat(t0_quat)
    t0_rot_inv = t0_rot.inv()

    ego_future_xyz_local = t0_rot_inv.apply(ego_future_xyz - t0_xyz)
    ego_future_rot_local = (t0_rot_inv * spt.Rotation.from_quat(ego_future_quat)).as_matrix()
    return ego_future_xyz_local, ego_future_rot_local


def compute_metrics(future_xyz: np.ndarray, future_rot: np.ndarray) -> dict[str, float]:
    xy = future_xyz[:, :2]
    path_points = np.vstack([np.zeros((1, 2), dtype=np.float64), xy])
    deltas = np.diff(path_points, axis=0)
    segment_lengths = np.linalg.norm(deltas, axis=1)
    speeds = segment_lengths / DT
    accels = np.diff(speeds, prepend=speeds[0]) / DT

    yaws = np.unwrap(np.arctan2(future_rot[:, 1, 0], future_rot[:, 0, 0]))
    final_yaw_deg = math.degrees(abs(yaws[-1]))
    max_yaw_deg = math.degrees(np.max(np.abs(yaws)))

    end_x = float(future_xyz[-1, 0])
    end_y = float(future_xyz[-1, 1])
    path_length = float(segment_lengths.sum())
    straightness_ratio = path_length / max(end_x, 1e-3)

    return {
        "end_x_m": end_x,
        "end_y_m": end_y,
        "final_abs_y_m": float(abs(end_y)),
        "max_abs_y_m": float(np.max(np.abs(future_xyz[:, 1]))),
        "path_length_m": path_length,
        "straightness_ratio": float(straightness_ratio),
        "mean_speed_mps": float(speeds.mean()),
        "min_speed_mps": float(speeds.min()),
        "max_speed_mps": float(speeds.max()),
        "max_abs_accel_mps2": float(np.max(np.abs(accels))),
        "final_abs_yaw_deg": float(final_yaw_deg),
        "max_abs_yaw_deg": float(max_yaw_deg),
    }


def is_normal_driving(metrics: dict[str, float]) -> bool:
    return (
        metrics["end_x_m"] >= 30.0
        and metrics["final_abs_y_m"] <= 1.0
        and metrics["max_abs_y_m"] <= 2.0
        and metrics["final_abs_yaw_deg"] <= 4.0
        and metrics["max_abs_yaw_deg"] <= 5.0
        and 5.0 <= metrics["mean_speed_mps"] <= 15.0
        and metrics["min_speed_mps"] >= 3.0
        and metrics["max_abs_accel_mps2"] <= 2.5
        and metrics["straightness_ratio"] <= 1.05
    )


def normal_score(metrics: dict[str, float]) -> float:
    return (
        metrics["max_abs_y_m"] * 2.0
        + metrics["final_abs_y_m"] * 2.0
        + metrics["max_abs_yaw_deg"] * 0.35
        + abs(metrics["straightness_ratio"] - 1.0) * 30.0
        + abs(metrics["mean_speed_mps"] - 8.0) * 0.15
    )


def main() -> None:
    avdi = physical_ai_av.PhysicalAIAVDatasetInterface()
    clip_ids = load_clip_ids()

    candidates: list[dict] = []
    scanned = 0
    for clip_id in clip_ids:
        scanned += 1
        try:
            future_xyz, future_rot = compute_local_future(avdi, clip_id, DEFAULT_T0_US)
            metrics = compute_metrics(future_xyz, future_rot)
        except Exception as e:
            print(json.dumps({"clip_id": clip_id, "status": "skip", "error": type(e).__name__}), flush=True)
            continue

        if not is_normal_driving(metrics):
            continue

        sample = {
            "clip_id": clip_id,
            "t0_relative": DEFAULT_T0_US,
            "selection": "normal_driving_heuristic",
            "score": round(normal_score(metrics), 4),
            **{k: round(v, 4) for k, v in metrics.items()},
        }
        candidates.append(sample)
        print(json.dumps({"clip_id": clip_id, "status": "candidate", "score": sample["score"], "end_x_m": sample["end_x_m"], "max_abs_y_m": sample["max_abs_y_m"], "max_abs_yaw_deg": sample["max_abs_yaw_deg"]}), flush=True)

        if len(candidates) >= 20:
            break

    candidates.sort(key=lambda row: row["score"])
    chosen = candidates[:5]
    payload = {
        "selection_method": "egomotion straight/mild-driving heuristic at t0=5.1s",
        "scanned_clip_count": scanned,
        "candidate_count": len(candidates),
        "chosen_count": len(chosen),
        "chosen_samples": chosen,
        "all_candidates": candidates,
    }
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("OUT_PATH", str(OUT_PATH), flush=True)
    print("CHOSEN", json.dumps(chosen, indent=2), flush=True)


if __name__ == "__main__":
    main()
