import json
import time
from copy import deepcopy
from pathlib import Path

import numpy as np
import physical_ai_av
import torch
import torch.nn.functional as F
from transformers.models.qwen2_vl.image_processing_qwen2_vl import smart_resize

from alpamayo1_5 import helper
from alpamayo1_5.load_physical_aiavdataset import load_physical_aiavdataset
from alpamayo1_5.models.alpamayo1_5 import Alpamayo1_5
from timed_inference import build_model


SAMPLES_PATH = Path("/mnt/g/alpamayo1.5/notebooks/nav_demo_samples.json")
OUT_PATH = Path("/mnt/g/alpamayo1.5/compare_camera_budget_profiles_results.json")

CAMERA_FRONT_WIDE = 1
CAMERA_FRONT_TELE = 6

PROFILES = [
    {
        "name": "equal_64k",
        "camera_target_pixels": {
            CAMERA_FRONT_WIDE: 65536,
            CAMERA_FRONT_TELE: 65536,
        },
    },
    {
        "name": "wide_80k_tele_48k",
        "camera_target_pixels": {
            CAMERA_FRONT_WIDE: 81920,
            CAMERA_FRONT_TELE: 49152,
        },
    },
    {
        "name": "wide_96k_tele_32k",
        "camera_target_pixels": {
            CAMERA_FRONT_WIDE: 98304,
            CAMERA_FRONT_TELE: 32768,
        },
    },
    {
        "name": "wide_112k_tele_16k",
        "camera_target_pixels": {
            CAMERA_FRONT_WIDE: 114688,
            CAMERA_FRONT_TELE: 16384,
        },
    },
]


def build_image_content(
    frames: list[torch.Tensor],
    camera_indices: torch.Tensor,
    num_frames_per_camera: int,
) -> list[dict]:
    expanded_cam_ids = camera_indices.repeat_interleave(num_frames_per_camera)
    content: list[dict] = []
    prev_cam_id = None
    frame_idx = 0
    for i, frame in enumerate(frames):
        cam_id = expanded_cam_ids[i].item()
        if prev_cam_id is not None and cam_id != prev_cam_id:
            frame_idx = 0
        if frame_idx == 0:
            cam_name = helper.CAMERA_DISPLAY_NAMES.get(cam_id, f"Camera {cam_id}")
            content.append({"type": "text", "text": f"{cam_name}: "})
        content.append({"type": "text", "text": f"frame {frame_idx} "})
        content.append({"type": "image", "image": frame})
        prev_cam_id = cam_id
        frame_idx += 1
    return content


def make_messages(
    frames: list[torch.Tensor],
    camera_indices: torch.Tensor,
    num_frames_per_camera: int,
) -> list[dict]:
    num_traj_token = 48
    hist_traj_placeholder = (
        f"<|traj_history_start|>{'<|traj_history|>' * num_traj_token}<|traj_history_end|>"
    )
    prompt_text = "output the future trajectory."
    user_text = f"{hist_traj_placeholder}{prompt_text}"
    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are a driving assistant that generates safe and accurate actions.",
                }
            ],
        },
        {
            "role": "user",
            "content": build_image_content(frames, camera_indices, num_frames_per_camera)
            + [{"type": "text", "text": user_text}],
        },
        {
            "role": "assistant",
            "content": [{"type": "text", "text": "<|traj_future_start|>"}],
        },
    ]
    messages[1]["content"][-1]["text"] = messages[1]["content"][-1]["text"].replace(
        "output the chain-of-thought reasoning of the driving process, then output the future trajectory.",
        "output the future trajectory.",
    )
    return messages


def resize_frames_by_camera_budget(
    image_frames: torch.Tensor,
    camera_indices: torch.Tensor,
    camera_target_pixels: dict[int, int],
) -> tuple[torch.Tensor, list[dict]]:
    resized_frames: list[torch.Tensor] = []
    resize_stats: list[dict] = []
    for cam_pos, cam_idx in enumerate(camera_indices.tolist()):
        frames = image_frames[cam_pos]
        original_h = int(frames.shape[-2])
        original_w = int(frames.shape[-1])
        target_pixels = camera_target_pixels.get(cam_idx, original_h * original_w)
        resized_h, resized_w = smart_resize(
            original_h,
            original_w,
            factor=28,
            min_pixels=target_pixels,
            max_pixels=target_pixels,
        )
        if resized_h == original_h and resized_w == original_w:
            resized = frames.clone()
        else:
            resized = F.interpolate(
                frames.float(),
                size=(resized_h, resized_w),
                mode="bilinear",
                align_corners=False,
                antialias=True,
            ).round().clamp(0, 255)
            resized = resized.to(dtype=frames.dtype)
        resized_frames.append(resized)
        resize_stats.append(
            {
                "camera_index": cam_idx,
                "input_hw": [original_h, original_w],
                "output_hw": [resized_h, resized_w],
                "target_pixels": int(target_pixels),
                "output_pixels": int(resized_h * resized_w),
            }
        )
    return resized_frames, resize_stats


def prepare_inputs(
    model: Alpamayo1_5,
    data: dict,
    camera_target_pixels: dict[int, int],
) -> tuple[dict, dict]:
    working = deepcopy(data)
    resized_by_camera, resize_stats = resize_frames_by_camera_budget(
        working["image_frames"],
        working["camera_indices"],
        camera_target_pixels,
    )
    num_frames_per_camera = int(working["image_frames"].shape[1])
    flat_frames = [frame for cam_frames in resized_by_camera for frame in cam_frames]

    helper.MIN_PIXELS = min(camera_target_pixels.values())
    helper.MAX_PIXELS = max(camera_target_pixels.values())
    processor = helper.get_processor(model.tokenizer)
    messages = make_messages(
        flat_frames,
        working["camera_indices"],
        num_frames_per_camera=num_frames_per_camera,
    )
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=False,
        continue_final_message=True,
        return_dict=True,
        return_tensors="pt",
    )
    merge_length = processor.image_processor.merge_size**2
    image_grid_thw = inputs["image_grid_thw"].detach().cpu()
    image_tokens = int((image_grid_thw.prod(dim=1) // merge_length).sum().item())
    prep_info = {
        "resize_stats": resize_stats,
        "image_grid_thw": image_grid_thw.tolist(),
        "image_tokens": image_tokens,
        "input_ids_shape": list(inputs["input_ids"].shape),
    }
    model_inputs = {
        "tokenized_data": inputs,
        "ego_history_xyz": working["ego_history_xyz"],
        "ego_history_rot": working["ego_history_rot"],
    }
    return helper.to_device(model_inputs, model.device), prep_info


def extract_xy(pred_xyz: torch.Tensor) -> np.ndarray:
    return pred_xyz.detach().cpu().numpy()[0, 0, 0, :, :2]


def gt_xy(data: dict) -> np.ndarray:
    return data["ego_future_xyz"].cpu().numpy()[0, 0, :, :2]


def compute_ade(gt: np.ndarray, pred: np.ndarray) -> float:
    return float(np.linalg.norm(pred - gt, axis=1).mean())


def compute_axis_metrics(gt: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    delta = pred - gt
    abs_delta = np.abs(delta)
    return {
        "longitudinal_mae_m": float(abs_delta[:, 0].mean()),
        "lateral_mae_m": float(abs_delta[:, 1].mean()),
        "endpoint_longitudinal_abs_m": float(abs(delta[-1, 0])),
        "endpoint_lateral_abs_m": float(abs(delta[-1, 1])),
    }


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
    return {
        "finite": finite,
        "within_bounds": bool(model.action_space.is_within_bounds(action).all().detach().cpu().item()),
        "accel_abs_max": float(accel.abs().max().detach().cpu().item()),
        "curvature_abs_max": float(curvature.abs().max().detach().cpu().item()),
    }


def run_fast_mode(
    model: Alpamayo1_5,
    model_inputs: dict,
    seed: int,
) -> tuple[torch.Tensor, torch.Tensor, float, dict[str, float | int]]:
    runtime_profile: dict[str, float | int] = {}
    torch.cuda.manual_seed_all(seed)
    torch.cuda.synchronize()
    start = time.perf_counter()
    with torch.inference_mode():
        with torch.autocast("cuda", dtype=torch.bfloat16):
            pred_xyz, pred_rot = model.sample_trajectories_from_data_with_vlm_rollout(
                data=model_inputs,
                top_p=0.98,
                temperature=0.6,
                num_traj_samples=1,
                diffusion_kwargs={"inference_step": 6},
                runtime_profile=runtime_profile,
                skip_vlm_generation=True,
            )
    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    return pred_xyz, pred_rot, elapsed, runtime_profile


def summarize_profile_results(rows: list[dict]) -> dict:
    return {
        "num_samples": len(rows),
        "mean_seconds": round(float(np.mean([r["seconds"] for r in rows])), 4),
        "mean_image_tokens": round(float(np.mean([r["image_tokens"] for r in rows])), 2),
        "mean_ade_m": round(float(np.mean([r["ade_m"] for r in rows])), 4),
        "mean_longitudinal_mae_m": round(float(np.mean([r["longitudinal_mae_m"] for r in rows])), 4),
        "mean_lateral_mae_m": round(float(np.mean([r["lateral_mae_m"] for r in rows])), 4),
        "mean_endpoint_longitudinal_abs_m": round(
            float(np.mean([r["endpoint_longitudinal_abs_m"] for r in rows])),
            4,
        ),
        "mean_endpoint_lateral_abs_m": round(
            float(np.mean([r["endpoint_lateral_abs_m"] for r in rows])),
            4,
        ),
        "all_finite": all(r["sanity"]["finite"] for r in rows),
        "all_within_bounds": all(r["sanity"]["within_bounds"] for r in rows),
    }


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

    by_profile: dict[str, list[dict]] = {profile["name"]: [] for profile in PROFILES}

    warmup_data = load_physical_aiavdataset(
        sample_rows[0]["clip_id"],
        t0_us=int(sample_rows[0]["t0_relative"]),
        avdi=avdi,
        camera_features=camera_features,
        num_frames=2,
    )
    warmup_inputs, _ = prepare_inputs(model, warmup_data, PROFILES[0]["camera_target_pixels"])
    run_fast_mode(model, warmup_inputs, seed=999)

    for sample_idx, row in enumerate(sample_rows):
        data = load_physical_aiavdataset(
            row["clip_id"],
            t0_us=int(row["t0_relative"]),
            avdi=avdi,
            camera_features=camera_features,
            num_frames=2,
        )
        gt = gt_xy(data)
        rotation = sample_idx % len(PROFILES)
        ordered_profiles = PROFILES[rotation:] + PROFILES[:rotation]
        for order_idx, profile in enumerate(ordered_profiles):
            model_inputs, prep_info = prepare_inputs(model, data, profile["camera_target_pixels"])
            pred_xyz, pred_rot, seconds, runtime_profile = run_fast_mode(
                model,
                model_inputs,
                seed=2000 + (sample_idx * 10) + order_idx,
            )
            pred = extract_xy(pred_xyz)
            axis_metrics = compute_axis_metrics(gt, pred)
            result = {
                "profile": profile["name"],
                "clip_id": row["clip_id"],
                "t0_relative": int(row["t0_relative"]),
                "seconds": round(seconds, 4),
                "image_tokens": prep_info["image_tokens"],
                "ade_m": round(compute_ade(gt, pred), 4),
                "longitudinal_mae_m": round(axis_metrics["longitudinal_mae_m"], 4),
                "lateral_mae_m": round(axis_metrics["lateral_mae_m"], 4),
                "endpoint_longitudinal_abs_m": round(axis_metrics["endpoint_longitudinal_abs_m"], 4),
                "endpoint_lateral_abs_m": round(axis_metrics["endpoint_lateral_abs_m"], 4),
                "resize_stats": prep_info["resize_stats"],
                "image_grid_thw": prep_info["image_grid_thw"],
                "input_ids_shape": prep_info["input_ids_shape"],
                "runtime_profile": runtime_profile,
                "sanity": sanity_metrics(model, data, pred_xyz, pred_rot),
            }
            print(json.dumps(result), flush=True)
            by_profile[profile["name"]].append(result)

    summary = {name: summarize_profile_results(rows) for name, rows in by_profile.items()}
    payload = {"summary": summary, "results_by_profile": by_profile}
    with OUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("SUMMARY", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
