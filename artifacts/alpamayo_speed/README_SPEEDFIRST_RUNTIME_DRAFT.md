# DRAFT: speed-first Alpamayo warm-frame runtime

This is a draft operator note for the speed-first Alpamayo/FlashDriveVLA runtime that produced steady-state shifted warm rows under 300 ms.

Status: draft, speed-first, not production-safe.

Safety/correctness caveat: the passing shifted rows use `streamingReuseMode=source_cache_draft_verify_unverified` and report `streamingReuseUnverified=true`. This is the intended speed-first path for sim timing, not a production-safe current-prompt cache proof.

## Workspace paths

Windows workspace:

```powershell
E:\ture_opamayo
```

WSL workspace:

```bash
/mnt/e/ture_opamayo/openpilot_alpamayo
```

Target model:

```bash
/mnt/e/ture_opamayo/openpilot_alpamayo/Alpamayo-1.5-10B-finetuned
```

DFlash draft model:

```bash
/mnt/e/ture_opamayo/openpilot_alpamayo/Alpamayo-1.5-DFlash
```

Alpamayo package/root:

```bash
/mnt/g/alpamayo1.5
```

DFlash package root:

```bash
/mnt/e/ture_opamayo/openpilot_alpamayo/dflash
```

Python venv:

```bash
/mnt/g/alpamayo1.5/a1_5_venv
```

## Endpoint runtime command

Run from `E:\ture_opamayo` in PowerShell:

```powershell
wsl.exe -e bash -lc 'source /mnt/g/alpamayo1.5/a1_5_venv/bin/activate && cd /mnt/e/ture_opamayo/openpilot_alpamayo && export PYTHONPATH=/mnt/e/ture_opamayo/openpilot_alpamayo:/mnt/g/alpamayo1.5:/mnt/g/alpamayo1.5/src && export ALPAMAYO_ROOT=/mnt/g/alpamayo1.5 && export ALPAMAYO_TARGET_MODEL=/mnt/e/ture_opamayo/openpilot_alpamayo/Alpamayo-1.5-10B-finetuned && export FLASHVLA_TARGET_MODEL=/mnt/e/ture_opamayo/openpilot_alpamayo/Alpamayo-1.5-10B-finetuned && export ALPAMAYO_DFLASH_ENABLED=1 && export ALPAMAYO_DFLASH_DRAFT_MODEL=/mnt/e/ture_opamayo/openpilot_alpamayo/Alpamayo-1.5-DFlash && export ALPAMAYO_DFLASH_PACKAGE_ROOT=/mnt/e/ture_opamayo/openpilot_alpamayo/dflash && export ALPAMAYO_STREAMING_VISION_ATTENTION_MASK=1 && export ALPAMAYO_STREAMING_VLM_TRUST_SHIFTED_DRAFT=0 && export ALPAMAYO_STREAMING_VLM_SOURCE_CACHE_DRAFT_VERIFY_UNVERIFIED=0 && export ALPAMAYO_CUDA_GRAPHS=0 && export ALPAMAYO_GRAPH_VISUAL_STAGE=0 && export ALPAMAYO_GRAPH_PREFILL_STAGE=0 && export ALPAMAYO_GRAPH_STANDARD_PREFILL_STAGE=0 && export ALPAMAYO_GRAPH_DRAFT_VERIFY_PREFILL_STAGE=0 && export ALPAMAYO_GRAPH_DECODE_STAGE=0 && export ALPAMAYO_GRAPH_ACTION_STAGE=0 && export ALPAMAYO_STATIC_GRAPH_STRICT_SHAPES=0 && export ALPAMAYO_PC_TRACE_PATH=/mnt/e/ture_opamayo/openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/pc_endpoint_speedfirst_validplan_65kpix.trace.jsonl && python -m openpilot.selfdrive.alpamayo.pc_endpoint'
```

Important: `ALPAMAYO_STREAMING_VLM_SOURCE_CACHE_DRAFT_VERIFY_UNVERIFIED=0` was intentionally used in the validated run. Current code still takes the speed-first shifted source-cache suffix verifier when the shifted KV plan validates, and keeps the row marked unverified in debug telemetry.

Endpoint URL:

```text
http://127.0.0.1:8765/alpamayo
```

Stop endpoint:

```powershell
wsl.exe -e bash -lc "pkill -f 'openpilot.selfdrive.alpamayo.pc_endpoin[t]' || true"
```

## Probe request artifact

Input request bundle:

```text
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/metadrive_shifted_4seq_request_triple.json
```

Validated probe outputs:

```text
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/speedfirst_validplan_65kpix_probe_frame32.json
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/speedfirst_validplan_65kpix_probe_frame36.json
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/speedfirst_validplan_65kpix_probe_frame40.json
```

Probe result highlights:

```text
frame32: wall 234.228 ms, adapter 224.040 ms, vlm 3.350 ms, diffusion 192.670 ms, action 19.344 ms
frame36: wall 222.241 ms, adapter 197.064 ms, mode shifted_source_dflash_cache_suffix_unverified, accepted 10/10
frame40: wall 204.859 ms, adapter 200.378 ms, mode shifted_source_dflash_cache_suffix_unverified, accepted 10/10
```

## Realtime async sim benchmark command

Run from `E:\ture_opamayo` in PowerShell after endpoint is resident:

```powershell
py -3.11 openpilot_alpamayo/openpilot/tools/alpamayo_speed/bench_alpamayo_metadrive_contract.py --mode alpamayo --endpoint-url http://127.0.0.1:8765/alpamayo --endpoint-timeout-s 300 --output openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/metadrive_realtime_async_speedfirst_validplan_300f_65kpix_benchmark.json --frames 300 --num-frames 4 --query-every 2 --catchup-stride-steps 1 --async-endpoint --camera-width 256 --camera-height 256 --no-video --realtime --realtime-speed 1.0
```

## Stock versus speed-first Alpamayo side-by-side video command

Run from `E:\ture_opamayo` in PowerShell after endpoint is resident:

```powershell
py -3.11 openpilot_alpamayo/openpilot/tools/alpamayo_speed/bench_alpamayo_metadrive_contract.py --mode both --endpoint-url http://127.0.0.1:8765/alpamayo --endpoint-timeout-s 300 --output openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/metadrive_side_by_side_speedfirst_validplan_300f_65kpix_benchmark.json --frames 300 --num-frames 4 --query-every 2 --catchup-stride-steps 1 --async-endpoint --camera-width 256 --camera-height 256 --realtime --realtime-speed 1.0 --video-output openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/metadrive_side_by_side_speedfirst_validplan_300f_65kpix.mp4 --video-fps 10
```

This uses `MetaDriveRouteFollower` as the stock controller and `AlpamayoTrajectoryController` as the Alpamayo trajectory tracker inside:

```text
openpilot_alpamayo/openpilot/tools/alpamayo_speed/bench_alpamayo_metadrive_contract.py
```

Benchmark output:

```text
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/metadrive_realtime_async_speedfirst_validplan_300f_65kpix_benchmark.json
```

Trace output:

```text
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/pc_endpoint_speedfirst_validplan_65kpix.trace.jsonl
```

Trace summary:

```text
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/speedfirst_validplan_65kpix_trace_summary.json
```

## Validated timing result

Realtime async MetaDrive run:

```text
frames: 218
endpoint_calls: 27
valid_endpoint_responses: 122
termination: out_of_road
```

All shifted rows including probe shifted rows:

```text
count: 29
min: 137.331 ms
mean: 169.899 ms
p50: 161.197 ms
p90: 203.033 ms
p95: 205.804 ms
max: 221.633 ms
over300: 0
```

Steady-state resident shifted rows, dropping the first two shifted cache-hit rows:

```text
count: 27
min: 137.331 ms
mean: 167.717 ms
p50: 160.738 ms
p90: 203.033 ms
p95: 205.804 ms
max: 221.633 ms
over300: 0
```

Steady-state stage timing:

```text
vlm_generate: mean 81.164 ms, max 99.339 ms
diffusion: mean 55.631 ms, max 89.757 ms
action_to_traj: mean 2.688 ms, max 5.500 ms
```

## Compile check used before runtime

```powershell
py -3.11 -m py_compile openpilot_alpamayo/openpilot/selfdrive/alpamayo/local_adapter.py
```

## Draft erratum: invalid benchmark side-by-side artifact

The earlier `bench_alpamayo_metadrive_contract.py --mode both` side-by-side command is not a valid visual stock-versus-fast-path controller comparison. It is an endpoint contract/timing harness. The produced artifact showed `stock.endpoint_calls=0`, `alpamayo.endpoint_calls=0`, and Alpamayo stayed on `stock_route_follower`, so that MP4 must be treated as invalid.

Invalid artifact:

```text
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/metadrive_side_by_side_speedfirst_validplan_300f_65kpix.mp4
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/metadrive_side_by_side_speedfirst_validplan_300f_65kpix_benchmark.json
```

Use the older working MetaDrive overlay controller for visual side-by-side comparison:

```powershell
cd E:\ture_opamayo\openpilot
$env:CUDA_PATH='C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.2'
$env:CUDA_HOME=$env:CUDA_PATH
$env:PATH="$env:CUDA_PATH\bin;$env:CUDA_PATH\libnvvp;$env:CUDA_PATH\extras\CUPTI\lib64;$env:PATH"
$env:RTP_VLM_WAIT_READY='1'
$env:RTP_VLM_IMAGE_FORMAT='jpeg'
$env:RTP_VLM_JPEG_QUALITY='85'
$env:RTP_VLM_SERVER_COMMAND='py -3.11 tools\reasoned_trajectory_poc\qwen_trt_label_engine.py --artifact-dir F:\qwen_trt_export --text-engine F:\qwen_trt_export\nvfp4_trt\qwen_text_36layer_nvfp4_trt.engine --text-seq-len 220 --score-rotate-groups --score-rotate-shared-engine --score-thresholds "pedestrian_in_path:0.5,pedestrian_entering_path:0.5,vehicle_in_path:0.5,vehicle_entering_path:0.5" --score-label-groups "construction_left,construction_right;pedestrian_in_path,pedestrian_entering_path;vehicle_in_path,vehicle_entering_path" --require-manifest --ready-jsonl serve'
py -3.11 tools\reasoned_trajectory_poc\run_metadrive_overlay_demo.py --engine vlm --novel-scene random_mixed --frames 300 --speed-mps 2.5 --disable-vlm-speed-control --tick-sec 0.05 --deadline-ms 50 --save-every 1 --map 3 --seed 7 --random-scene-seed 42 --out artifacts\reasoned_trajectory_poc\metadrive_old_controller_fastpath_300_20260531
py -3.11 tools\reasoned_trajectory_poc\render_demo_videos.py --run-dir artifacts\reasoned_trajectory_poc\metadrive_old_controller_fastpath_300_20260531 --prefix old_controller_fastpath_300 --fps 20
```

## Draft side-by-side using old controller interface plus Alpamayo fast endpoint

This supersedes the Qwen VLM command for the Alpamayo fast-path comparison. The old MetaDrive overlay controller now accepts `--engine alpamayofast`; stock still runs through the original stock episode, and the reasoned half uses the old `env.step([steer, gas])` loop with Alpamayo endpoint semantic trajectories converted into commanded controls.

Endpoint must be running with the speed-first Alpamayo runtime from above. Then run:

```powershell
cd E:\ture_opamayo\openpilot
py -3.11 tools\reasoned_trajectory_poc\run_metadrive_overlay_demo.py --engine alpamayofast --novel-scene random_mixed --frames 300 --speed-mps 2.5 --disable-vlm-speed-control --tick-sec 0.05 --deadline-ms 300 --save-every 1 --map 3 --seed 7 --random-scene-seed 42 --camera-width 256 --camera-height 256 --alpamayo-endpoint-url http://127.0.0.1:8765/alpamayo --alpamayo-endpoint-timeout-s 300 --alpamayo-num-frames 4 --alpamayo-query-every 2 --alpamayo-catchup-stride-steps 1 --out artifacts\reasoned_trajectory_poc\metadrive_old_controller_alpamayofast_300_20260531_093508
py -3.11 tools\reasoned_trajectory_poc\render_demo_videos.py --run-dir artifacts\reasoned_trajectory_poc\metadrive_old_controller_alpamayofast_300_20260531_093508 --prefix old_controller_alpamayofast_300 --fps 20
```

Latest artifact:

```text
openpilot/artifacts/reasoned_trajectory_poc/metadrive_old_controller_alpamayofast_300_20260531_093508/videos/side_by_side_old_controller_alpamayofast_300.mp4
```

Latest result status:

```text
stock_frames=300
reasoned_frames=103
alpamayo_control_frames=71
stock_fallback_frames=32
endpoint_attempts=18
endpoint_calls=17
valid_endpoint_responses=17
reasoned_terminated=true
reasoned_outcome=out_of_road
max_abs_route_lateral_m=2.290495081571109
```

Timing from `pc_endpoint_old_controller_alpamayofast_65kpix.trace.jsonl`:

```text
shifted_rows=17
steady_shifted_drop_first_two_count=15
steady_shifted_mean_latency_ms=179.0072573333333
steady_shifted_max_latency_ms=307.589839
steady_shifted_over_300=1
steady_shifted_mode=source_cache_draft_verify_unverified
```

Interpretation:

```text
The controller interface is fixed enough to prove Alpamayo fast path can command actual sim controls. It is not yet a viable driving demo because the endpoint trajectory-to-MetaDrive controller drove off-route after 103 frames. The next code issue is control-frame compatibility/trajectory interpretation, not stock-vs-reasoned plumbing.
```

