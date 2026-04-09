import argparse
import time

import numpy as np
import physical_ai_av
import torch

from alpamayo1_5 import helper
from alpamayo1_5.load_physical_aiavdataset import load_physical_aiavdataset
from alpamayo1_5.models.alpamayo1_5 import Alpamayo1_5


DEFAULT_CLIP_ID = "030c760c-ae38-49aa-9ad8-f5650a545d26"
DEFAULT_T0_US = 5_100_000


def gpu_stats() -> dict[int, dict[str, float]]:
    stats: dict[int, dict[str, float]] = {}
    for idx in range(torch.cuda.device_count()):
        free_bytes, total_bytes = torch.cuda.mem_get_info(idx)
        stats[idx] = {
            "used_gib": round((total_bytes - free_bytes) / (1024**3), 2),
            "free_gib": round(free_bytes / (1024**3), 2),
            "total_gib": round(total_bytes / (1024**3), 2),
        }
    return stats


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


def set_module_attention_implementation(module: torch.nn.Module, attn_implementation: str) -> None:
    for submodule in module.modules():
        config = getattr(submodule, "config", None)
        if config is not None:
            setattr(config, "_attn_implementation", attn_implementation)
            if hasattr(config, "attn_implementation"):
                setattr(config, "attn_implementation", attn_implementation)


def build_model(
    gpu_mem_gib: int,
    cpu_mem_gib: int,
    device_map_mode: str,
    split_index: int,
    attn_implementation: str,
    expert_attn_implementation: str | None,
) -> Alpamayo1_5:
    max_memory = {idx: f"{gpu_mem_gib}GiB" for idx in range(torch.cuda.device_count())}
    max_memory["cpu"] = f"{cpu_mem_gib}GiB"
    device_map: str | dict[str, int]
    if device_map_mode == "auto":
        device_map = "auto"
    elif device_map_mode == "manual_split":
        device_map = build_manual_split_device_map(split_index)
    else:
        raise ValueError(f"Unsupported device_map_mode={device_map_mode}")
    model = Alpamayo1_5.from_pretrained(
        "nvidia/Alpamayo-1.5-10B",
        dtype=torch.bfloat16,
        attn_implementation=attn_implementation,
        device_map=device_map,
        max_memory=max_memory,
        low_cpu_mem_usage=True,
    )
    if expert_attn_implementation is not None:
        set_module_attention_implementation(model.expert, expert_attn_implementation)
    return model


def summarize_min_ade(data: dict, pred_xyz: torch.Tensor) -> float:
    gt_xy = data["ego_future_xyz"].cpu()[0, 0, :, :2].T.numpy()
    pred_xy = pred_xyz.cpu().numpy()[0, 0, :, :, :2].transpose(0, 2, 1)
    diff = np.linalg.norm(pred_xy - gt_xy[None, ...], axis=1).mean(-1)
    return float(diff.min())


def select_camera_features(
    avdi: physical_ai_av.PhysicalAIAVDatasetInterface, camera_mode: str
) -> list[str] | None:
    if camera_mode == "full":
        return None
    if camera_mode == "front2":
        return [
            avdi.features.CAMERA.CAMERA_FRONT_WIDE_120FOV,
            avdi.features.CAMERA.CAMERA_FRONT_TELE_30FOV,
        ]
    if camera_mode == "front1":
        return [avdi.features.CAMERA.CAMERA_FRONT_WIDE_120FOV]
    raise ValueError(f"Unsupported camera_mode={camera_mode}")


def timed_run(
    clip_id: str,
    t0_us: int,
    num_traj_samples: int,
    max_generation_length: int,
    seed: int,
    camera_mode: str,
    num_frames: int,
    gpu_mem_gib: int,
    cpu_mem_gib: int,
    min_pixels: int,
    max_pixels: int,
    device_map_mode: str,
    split_index: int,
    repeat_infer: int,
    diffusion_steps: int | None,
    attn_implementation: str,
    expert_attn_implementation: str | None,
    reasoning_mode: str,
) -> None:
    overall_start = time.perf_counter()

    stage_start = time.perf_counter()
    avdi = physical_ai_av.PhysicalAIAVDatasetInterface()
    camera_features = select_camera_features(avdi, camera_mode)
    data = load_physical_aiavdataset(
        clip_id,
        t0_us=t0_us,
        avdi=avdi,
        camera_features=camera_features,
        num_frames=num_frames,
    )
    dataset_seconds = time.perf_counter() - stage_start
    print("dataset_seconds", round(dataset_seconds, 2), flush=True)
    print("image_frames_shape", tuple(data["image_frames"].shape), flush=True)
    print("camera_indices", data["camera_indices"].tolist(), flush=True)

    stage_start = time.perf_counter()
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
    messages_seconds = time.perf_counter() - stage_start
    print("messages_seconds", round(messages_seconds, 2), flush=True)

    stage_start = time.perf_counter()
    model = build_model(
        gpu_mem_gib=gpu_mem_gib,
        cpu_mem_gib=cpu_mem_gib,
        device_map_mode=device_map_mode,
        split_index=split_index,
        attn_implementation=attn_implementation,
        expert_attn_implementation=expert_attn_implementation,
    )
    model_load_seconds = time.perf_counter() - stage_start
    print("model_load_seconds", round(model_load_seconds, 2), flush=True)
    print("model_device", model.device, flush=True)
    print("hf_device_map", model.hf_device_map, flush=True)
    print("gpu_post_load", gpu_stats(), flush=True)

    stage_start = time.perf_counter()
    helper.MIN_PIXELS = min_pixels
    helper.MAX_PIXELS = max_pixels
    processor = helper.get_processor(model.tokenizer)
    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=False,
        continue_final_message=True,
        return_dict=True,
        return_tensors="pt",
    )
    processor_seconds = time.perf_counter() - stage_start
    print("processor_seconds", round(processor_seconds, 2), flush=True)
    print("input_ids_shape", tuple(inputs["input_ids"].shape), flush=True)

    stage_start = time.perf_counter()
    model_inputs = {
        "tokenized_data": inputs,
        "ego_history_xyz": data["ego_history_xyz"],
        "ego_history_rot": data["ego_history_rot"],
    }
    model_inputs = helper.to_device(model_inputs, model.device)
    move_inputs_seconds = time.perf_counter() - stage_start
    print("move_inputs_seconds", round(move_inputs_seconds, 2), flush=True)
    print("gpu_pre_infer", gpu_stats(), flush=True)

    infer_seconds_list: list[float] = []
    runtime_profiles: list[dict[str, float | int]] = []
    pred_xyz = pred_rot = extra = None
    with torch.inference_mode():
        with torch.autocast("cuda", dtype=torch.bfloat16):
            for infer_idx in range(repeat_infer):
                torch.cuda.manual_seed_all(seed + infer_idx)
                infer_start = time.perf_counter()
                runtime_profile: dict[str, float | int] = {}
                diffusion_kwargs = {}
                if diffusion_steps is not None:
                    diffusion_kwargs["inference_step"] = diffusion_steps
                outputs = model.sample_trajectories_from_data_with_vlm_rollout(
                    data=model_inputs,
                    top_p=0.98,
                    temperature=0.6,
                    num_traj_samples=num_traj_samples,
                    max_generation_length=max_generation_length,
                    return_extra=(reasoning_mode == "full"),
                    diffusion_kwargs=diffusion_kwargs or None,
                    runtime_profile=runtime_profile,
                    skip_vlm_generation=(reasoning_mode == "prefill_future_start"),
                )
                if reasoning_mode == "full":
                    pred_xyz, pred_rot, extra = outputs
                else:
                    pred_xyz, pred_rot = outputs
                    extra = None
                infer_seconds = time.perf_counter() - infer_start
                infer_seconds_list.append(infer_seconds)
                runtime_profiles.append(runtime_profile)
                print(f"infer_seconds_{infer_idx}", round(infer_seconds, 2), flush=True)
                print(f"runtime_profile_{infer_idx}", runtime_profile, flush=True)
    print("infer_seconds_mean", round(sum(infer_seconds_list) / len(infer_seconds_list), 2), flush=True)
    print("gpu_post_infer", gpu_stats(), flush=True)

    assert pred_xyz is not None and pred_rot is not None
    min_ade = summarize_min_ade(data, pred_xyz)
    print("min_ade_m", round(min_ade, 4), flush=True)
    print("pred_xyz_shape", tuple(pred_xyz.shape), flush=True)
    print("pred_rot_shape", tuple(pred_rot.shape), flush=True)
    if extra is not None:
        cot = extra["cot"][0, 0, 0]
        print("cot_chars", len(cot), flush=True)
        print("cot_preview", cot[:600].replace("\n", " "), flush=True)
    else:
        print("cot_chars", 0, flush=True)
        print("cot_preview", "<not generated>", flush=True)
    print("overall_seconds", round(time.perf_counter() - overall_start, 2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip-id", default=DEFAULT_CLIP_ID)
    parser.add_argument("--t0-us", type=int, default=DEFAULT_T0_US)
    parser.add_argument("--num-traj-samples", type=int, default=1)
    parser.add_argument("--max-generation-length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--camera-mode", choices=["full", "front2", "front1"], default="full")
    parser.add_argument("--num-frames", type=int, default=4)
    parser.add_argument("--gpu-mem-gib", type=int, default=15)
    parser.add_argument("--cpu-mem-gib", type=int, default=96)
    parser.add_argument("--min-pixels", type=int, default=helper.MIN_PIXELS)
    parser.add_argument("--max-pixels", type=int, default=helper.MAX_PIXELS)
    parser.add_argument("--device-map-mode", choices=["auto", "manual_split"], default="auto")
    parser.add_argument("--split-index", type=int, default=20)
    parser.add_argument("--repeat-infer", type=int, default=1)
    parser.add_argument("--diffusion-steps", type=int, default=None)
    parser.add_argument("--attn-implementation", choices=["eager", "sdpa", "flash_attention_2"], default="eager")
    parser.add_argument("--expert-attn-implementation", choices=["eager", "sdpa", "flash_attention_2"], default=None)
    parser.add_argument("--reasoning-mode", choices=["full", "prefill_future_start"], default="full")
    args = parser.parse_args()

    print("torch", torch.__version__, flush=True)
    print("cuda_available", torch.cuda.is_available(), flush=True)
    print("cuda_device_count", torch.cuda.device_count(), flush=True)
    print("gpu_initial", gpu_stats(), flush=True)
    print("camera_mode", args.camera_mode, flush=True)
    print("num_frames", args.num_frames, flush=True)
    print("gpu_mem_gib", args.gpu_mem_gib, flush=True)
    print("cpu_mem_gib", args.cpu_mem_gib, flush=True)
    print("min_pixels", args.min_pixels, flush=True)
    print("max_pixels", args.max_pixels, flush=True)
    print("device_map_mode", args.device_map_mode, flush=True)
    print("split_index", args.split_index, flush=True)
    print("repeat_infer", args.repeat_infer, flush=True)
    print("diffusion_steps", args.diffusion_steps, flush=True)
    print("attn_implementation", args.attn_implementation, flush=True)
    print("expert_attn_implementation", args.expert_attn_implementation, flush=True)
    print("reasoning_mode", args.reasoning_mode, flush=True)
    timed_run(
        clip_id=args.clip_id,
        t0_us=args.t0_us,
        num_traj_samples=args.num_traj_samples,
        max_generation_length=args.max_generation_length,
        seed=args.seed,
        camera_mode=args.camera_mode,
        num_frames=args.num_frames,
        gpu_mem_gib=args.gpu_mem_gib,
        cpu_mem_gib=args.cpu_mem_gib,
        min_pixels=args.min_pixels,
        max_pixels=args.max_pixels,
        device_map_mode=args.device_map_mode,
        split_index=args.split_index,
        repeat_infer=args.repeat_infer,
        diffusion_steps=args.diffusion_steps,
        attn_implementation=args.attn_implementation,
        expert_attn_implementation=args.expert_attn_implementation,
        reasoning_mode=args.reasoning_mode,
    )


if __name__ == "__main__":
    main()
