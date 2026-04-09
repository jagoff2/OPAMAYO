import json
import math
import time
from pathlib import Path

import numpy as np
import physical_ai_av
import torch

from alpamayo1_5 import helper
from alpamayo1_5.load_physical_aiavdataset import load_physical_aiavdataset
from alpamayo1_5.models.alpamayo1_5 import Alpamayo1_5
from timed_inference import build_model


SAMPLES_PATH = Path("/mnt/g/alpamayo1.5/notebooks/nav_demo_samples.json")
OUT_PATH = Path("/mnt/g/alpamayo1.5/compare_fast_vs_full_results.json")


def make_messages(data: dict, reasoning_mode: str) -> list[dict]:
    messages = helper.create_message(
        frames=data["image_frames"].flatten(0, 1),
        camera_indices=data["camera_indices"],
    )
    if reasoning_mode == "prefill_future_start":
        messages[1]["content"][-1]["text"] = messages[1]["content"][-1]["text"].replace(
            "output the chain-of-thought reasoning of the driving process, then output the future trajectory.",
            "output the future trajectory.",
        )
        messages[2]["content"] = [{"type": "text", "text": "<|traj_future_start|>"}]
    return messages


def prepare_inputs(model: Alpamayo1_5, data: dict, reasoning_mode: str) -> dict:
    helper.MIN_PIXELS = 65536
    helper.MAX_PIXELS = 65536
    processor = helper.get_processor(model.tokenizer)
    messages = make_messages(data, reasoning_mode)
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=False,
        continue_final_message=True,
        return_dict=True,
        return_tensors="pt",
    )
    model_inputs = {
        "tokenized_data": inputs,
        "ego_history_xyz": data["ego_history_xyz"],
        "ego_history_rot": data["ego_history_rot"],
    }
    return helper.to_device(model_inputs, model.device)


def extract_xy(pred_xyz: torch.Tensor) -> np.ndarray:
    return pred_xyz.detach().cpu().numpy()[0, 0, 0, :, :2]


def gt_xy(data: dict) -> np.ndarray:
    return data["ego_future_xyz"].cpu().numpy()[0, 0, :, :2]


def compute_minade(gt: np.ndarray, pred: np.ndarray) -> float:
    return float(np.linalg.norm(pred - gt, axis=1).mean())


def compare_paths(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    diff = np.linalg.norm(a - b, axis=1)
    return float(diff.mean()), float(diff[-1])


def sanity_metrics(model: Alpamayo1_5, data: dict, pred_xyz: torch.Tensor, pred_rot: torch.Tensor) -> dict:
    finite = bool(torch.isfinite(pred_xyz).all() and torch.isfinite(pred_rot).all())
    pred_xyz_single = pred_xyz[:, 0, 0]
    pred_rot_single = pred_rot[:, 0, 0]
    hist_xyz_single = data["ego_history_xyz"].to(pred_xyz.device)[:, 0]
    hist_rot_single = data["ego_history_rot"].to(pred_rot.device)[:, 0]
    action = model.action_space.traj_to_action(
        hist_xyz_single,
        hist_rot_single,
        pred_xyz_single,
        pred_rot_single,
    )
    accel = action[..., 0]
    curvature = action[..., 1]
    accel_max = float(accel.abs().max().detach().cpu().item())
    curvature_max = float(curvature.abs().max().detach().cpu().item())
    within_bounds = bool(model.action_space.is_within_bounds(action).all().detach().cpu().item())
    return {
        "finite": finite,
        "within_bounds": within_bounds,
        "accel_abs_max": accel_max,
        "curvature_abs_max": curvature_max,
    }


def run_mode(
    model: Alpamayo1_5,
    model_inputs: dict,
    reasoning_mode: str,
    seed: int,
) -> tuple[torch.Tensor, torch.Tensor, float]:
    torch.cuda.manual_seed_all(seed)
    start = time.perf_counter()
    with torch.inference_mode():
        with torch.autocast("cuda", dtype=torch.bfloat16):
            outputs = model.sample_trajectories_from_data_with_vlm_rollout(
                data=model_inputs,
                top_p=0.98,
                temperature=0.6,
                num_traj_samples=1,
                diffusion_kwargs={"inference_step": 6},
                skip_vlm_generation=(reasoning_mode == "prefill_future_start"),
            )
    elapsed = time.perf_counter() - start
    pred_xyz, pred_rot = outputs
    return pred_xyz, pred_rot, elapsed


def main() -> None:
    with SAMPLES_PATH.open("r", encoding="utf-8") as f:
        sample_rows = json.load(f)[:5]

    model = build_model(
        gpu_mem_gib=15,
        cpu_mem_gib=96,
        device_map_mode="manual_split",
        split_index=16,
        attn_implementation="flash_attention_2",
        expert_attn_implementation="eager",
    )
    avdi = physical_ai_av.PhysicalAIAVDatasetInterface()
    camera_features = [
        avdi.features.CAMERA.CAMERA_FRONT_WIDE_120FOV,
        avdi.features.CAMERA.CAMERA_FRONT_TELE_30FOV,
    ]

    results: list[dict] = []
    for idx, row in enumerate(sample_rows):
        data = load_physical_aiavdataset(
            row["clip_id"],
            t0_us=int(row["t0_relative"]),
            avdi=avdi,
            camera_features=camera_features,
            num_frames=2,
        )
        full_inputs = prepare_inputs(model, data, "full")
        fast_inputs = prepare_inputs(model, data, "prefill_future_start")

        full_xyz, full_rot, full_seconds = run_mode(model, full_inputs, "full", seed=1000 + idx)
        fast_xyz, fast_rot, fast_seconds = run_mode(
            model, fast_inputs, "prefill_future_start", seed=1000 + idx
        )

        full_xy = extract_xy(full_xyz)
        fast_xy = extract_xy(fast_xyz)
        gt = gt_xy(data)

        full_ade = compute_minade(gt, full_xy)
        fast_ade = compute_minade(gt, fast_xy)
        fast_vs_full_ade, fast_vs_full_fde = compare_paths(full_xy, fast_xy)

        result = {
            "clip_id": row["clip_id"],
            "t0_relative": int(row["t0_relative"]),
            "full_seconds": round(full_seconds, 4),
            "fast_seconds": round(fast_seconds, 4),
            "speedup_x": round(full_seconds / fast_seconds, 4),
            "full_ade_m": round(full_ade, 4),
            "fast_ade_m": round(fast_ade, 4),
            "ade_delta_m": round(fast_ade - full_ade, 4),
            "fast_vs_full_ade_m": round(fast_vs_full_ade, 4),
            "fast_vs_full_fde_m": round(fast_vs_full_fde, 4),
            "full_sanity": sanity_metrics(model, data, full_xyz, full_rot),
            "fast_sanity": sanity_metrics(model, data, fast_xyz, fast_rot),
        }
        print(json.dumps(result), flush=True)
        results.append(result)

    summary = {
        "num_samples": len(results),
        "mean_full_seconds": round(float(np.mean([r["full_seconds"] for r in results])), 4),
        "mean_fast_seconds": round(float(np.mean([r["fast_seconds"] for r in results])), 4),
        "mean_speedup_x": round(float(np.mean([r["speedup_x"] for r in results])), 4),
        "mean_full_ade_m": round(float(np.mean([r["full_ade_m"] for r in results])), 4),
        "mean_fast_ade_m": round(float(np.mean([r["fast_ade_m"] for r in results])), 4),
        "mean_ade_delta_m": round(float(np.mean([r["ade_delta_m"] for r in results])), 4),
        "mean_fast_vs_full_ade_m": round(
            float(np.mean([r["fast_vs_full_ade_m"] for r in results])), 4
        ),
        "mean_fast_vs_full_fde_m": round(
            float(np.mean([r["fast_vs_full_fde_m"] for r in results])), 4
        ),
        "all_fast_finite": all(r["fast_sanity"]["finite"] for r in results),
        "all_fast_within_bounds": all(r["fast_sanity"]["within_bounds"] for r in results),
    }

    payload = {"summary": summary, "results": results}
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("SUMMARY", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
