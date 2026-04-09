import json
import shutil
import subprocess
import argparse
from pathlib import Path

import numpy as np
import physical_ai_av
from PIL import Image, ImageDraw, ImageFont


DEFAULT_SAMPLES_PATH = Path("/mnt/g/alpamayo1.5/notebooks/nav_demo_samples.json")
DEFAULT_OUT_DIR = Path("/mnt/g/alpamayo1.5/sample_videos")

FPS = 10
PRE_SECONDS = 2.0
POST_SECONDS = 6.5


def load_samples(samples_path: Path, limit: int = 5) -> list[dict]:
    with samples_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, dict):
        if "chosen_samples" in payload:
            samples = payload["chosen_samples"]
        elif "samples" in payload:
            samples = payload["samples"]
        else:
            raise ValueError(f"Unsupported manifest format in {samples_path}")
    else:
        samples = payload
    return samples[:limit]


def make_timestamps(t0_us: int, fps: int, pre_seconds: float, post_seconds: float) -> np.ndarray:
    step_us = int(round(1_000_000 / fps))
    start_us = max(0, t0_us - int(round(pre_seconds * 1_000_000)))
    end_us = t0_us + int(round(post_seconds * 1_000_000))
    return np.arange(start_us, end_us + step_us, step_us, dtype=np.int64)


def compose_frame(
    wide_frame: np.ndarray,
    tele_frame: np.ndarray,
    sample: dict,
    rel_seconds: float,
    frame_idx: int,
) -> Image.Image:
    wide = Image.fromarray(wide_frame)
    tele = Image.fromarray(tele_frame)
    tele = tele.resize(wide.size, resample=Image.Resampling.BILINEAR)

    banner_h = 92
    canvas = Image.new("RGB", (wide.width * 2, wide.height + banner_h), color=(18, 18, 18))
    canvas.paste(wide, (0, banner_h))
    canvas.paste(tele, (wide.width, banner_h))

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    draw.rectangle((0, 0, canvas.width, banner_h), fill=(18, 18, 18))
    draw.text((12, 10), f"frame {frame_idx:03d}", fill=(255, 255, 255), font=font)
    draw.text((12, 32), f"clip {sample['clip_id']}", fill=(230, 230, 230), font=font)
    summary_text = sample.get("label")
    if summary_text is None:
        if "nav_maneuver" in sample:
            summary_text = f"nav {sample.get('nav_maneuver')} | {sample.get('nav_text')} | distance {sample.get('distance_m')}m"
        else:
            summary_text = (
                f"normal score {sample.get('score', 'n/a')} | end_x {sample.get('end_x_m', 'n/a')}m"
                f" | max|y| {sample.get('max_abs_y_m', 'n/a')}m | max|yaw| {sample.get('max_abs_yaw_deg', 'n/a')}deg"
            )
    draw.text((12, 52), summary_text, fill=(180, 220, 255), font=font)
    draw.text(
        (canvas.width - 180, 10),
        f"t rel {rel_seconds:+.1f}s",
        fill=(255, 220, 120),
        font=font,
    )
    if abs(rel_seconds) < 0.051:
        draw.rectangle((canvas.width - 180, 34, canvas.width - 20, 74), outline=(255, 80, 80), width=3)
        draw.text((canvas.width - 168, 44), "T0 EVAL FRAME", fill=(255, 80, 80), font=font)

    draw.text((12, banner_h + 8), "front_wide", fill=(255, 255, 255), font=font)
    draw.text((wide.width + 12, banner_h + 8), "front_tele", fill=(255, 255, 255), font=font)
    return canvas


def export_sample_video(
    sample: dict,
    avdi: physical_ai_av.PhysicalAIAVDatasetInterface,
    sample_idx: int,
    out_dir: Path,
) -> Path:
    tmp_dir = out_dir / "_frames"
    timestamps = make_timestamps(
        int(sample["t0_relative"]),
        fps=FPS,
        pre_seconds=PRE_SECONDS,
        post_seconds=POST_SECONDS,
    )
    frame_dir = tmp_dir / f"sample_{sample_idx:02d}"
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True, exist_ok=True)

    wide_feature = avdi.get_clip_feature(
        sample["clip_id"],
        avdi.features.CAMERA.CAMERA_FRONT_WIDE_120FOV,
        maybe_stream=True,
    )
    tele_feature = avdi.get_clip_feature(
        sample["clip_id"],
        avdi.features.CAMERA.CAMERA_FRONT_TELE_30FOV,
        maybe_stream=True,
    )
    wide_frames, _ = wide_feature.decode_images_from_timestamps(timestamps)
    tele_frames, _ = tele_feature.decode_images_from_timestamps(timestamps)

    for frame_idx, (ts_us, wide_frame, tele_frame) in enumerate(zip(timestamps, wide_frames, tele_frames)):
        rel_seconds = (int(ts_us) - int(sample["t0_relative"])) / 1_000_000.0
        image = compose_frame(wide_frame, tele_frame, sample, rel_seconds, frame_idx)
        image.save(frame_dir / f"frame_{frame_idx:04d}.png")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"sample_{sample_idx:02d}_{sample['clip_id'][:8]}_frontwide_tele.mp4"
    if out_path.exists():
        out_path.unlink()
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            str(frame_dir / "frame_%04d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(out_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples-path", type=Path, default=DEFAULT_SAMPLES_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    out_dir = args.out_dir
    tmp_dir = out_dir / "_frames"
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    avdi = physical_ai_av.PhysicalAIAVDatasetInterface()
    samples = load_samples(args.samples_path, limit=args.limit)
    outputs = []
    for idx, sample in enumerate(samples):
        out_path = export_sample_video(sample, avdi, idx, out_dir=out_dir)
        outputs.append(
            {
                "sample_index": idx,
                "clip_id": sample["clip_id"],
                "t0_relative": int(sample["t0_relative"]),
                "video_path": str(out_path),
            }
        )
        print(json.dumps(outputs[-1]), flush=True)

    manifest_path = out_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(outputs, f, indent=2)
    print("manifest", str(manifest_path), flush=True)


if __name__ == "__main__":
    main()
