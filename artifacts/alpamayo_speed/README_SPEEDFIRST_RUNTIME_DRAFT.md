# DRAFT: speed-first Alpamayo warm-frame runtime

Last updated: 2026-05-31 10:35 ET.

This is a draft operator note for the speed-first Alpamayo/FlashDriveVLA runtime and MetaDrive side-by-side path. It records exactly what is currently runnable, what timing was observed, and which older artifacts are invalid.

Status: draft, speed-first, sim-only. The relevant metric is steady-state warm shifted rows after the cache path is resident. Cold first-frame latency is intentionally not part of the target.

## Current state

Current viable visual demo path:

```text
Alpamayo PC endpoint + openpilot/tools/reasoned_trajectory_poc/run_metadrive_overlay_demo.py --engine alpamayofast --alpamayo-control-mode planner_bridge
```

Current speed result:

```text
latest 300-frame planner_bridge full-reasoning run:
  reasoned_frames=300
  alpamayo_control_frames=268
  endpoint_attempts/calls/valid=64/63/63
  terminated=false
  truncated=false
  max_abs_route_lateral_m=0.8491436227834122
  cold_first_endpoint_latency_ms=94399.71699996386
  warm_endpoint_p95_ms=226.87209997093305
  warm_endpoint_p99_ms=295.05580000113696
```

Interpretation:

```text
The current sim demo is fast enough by the stated steady-state warm shifted resident-frame criterion: warm p99 stayed below 300 ms in the latest 300-frame planner_bridge run.
The first endpoint response is still very slow because model/load/cache residency is cold. That is accepted for this effort.
The controller path that should be used for visual side-by-side is planner_bridge, not direct trajectory.
```

Current control diagnosis:

```text
Direct trajectory mode is not a valid driving interface for MetaDrive.
It feeds Alpamayo trajectory velocity/acceleration into low-level MetaDrive gas, which caused speed runaway and out-of-road termination.
planner_bridge treats Alpamayo semanticPlan.trajectory as planner/path intent only, extracts bounded lateral intent at preview distance, and lets the old MetaDrive route follower own actuator stabilization and speed discipline.
```

Current reasoning status:

```text
semanticPlan.reasoningText and semanticPlan.debug.cotText are now exposed by LocalAlpamayoAdapter.
The MetaDrive harness writes one full reasoning row per endpoint response to vlm/alpamayo_response_reasoning.jsonl.
In the latest full-reasoning run, all 63 responses generated the same 13-token reasoning text:
  Yield due to a pedestrian walking across the lane ahead
That repetition is model/runtime output, not an overlay truncation bug.
```

## Workspace paths

Windows workspace:

```powershell
E:\ture_opamayo
```

openpilot git checkout used for the pushed branch:

```powershell
E:\ture_opamayo\openpilot
```

Alpamayo endpoint workspace used for local runtime:

```powershell
E:\ture_opamayo\openpilot_alpamayo
```

WSL endpoint workspace:

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
wsl.exe -e bash -lc 'source /mnt/g/alpamayo1.5/a1_5_venv/bin/activate && cd /mnt/e/ture_opamayo/openpilot_alpamayo && export PYTHONPATH=/mnt/e/ture_opamayo/openpilot_alpamayo:/mnt/g/alpamayo1.5:/mnt/g/alpamayo1.5/src && export ALPAMAYO_ROOT=/mnt/g/alpamayo1.5 && export ALPAMAYO_TARGET_MODEL=/mnt/e/ture_opamayo/openpilot_alpamayo/Alpamayo-1.5-10B-finetuned && export FLASHVLA_TARGET_MODEL=/mnt/e/ture_opamayo/openpilot_alpamayo/Alpamayo-1.5-10B-finetuned && export ALPAMAYO_DFLASH_ENABLED=1 && export ALPAMAYO_DFLASH_DRAFT_MODEL=/mnt/e/ture_opamayo/openpilot_alpamayo/Alpamayo-1.5-DFlash && export ALPAMAYO_DFLASH_PACKAGE_ROOT=/mnt/e/ture_opamayo/openpilot_alpamayo/dflash && export ALPAMAYO_STREAMING_VISION_ATTENTION_MASK=1 && export ALPAMAYO_STREAMING_VLM_TRUST_SHIFTED_DRAFT=0 && export ALPAMAYO_STREAMING_VLM_SOURCE_CACHE_DRAFT_VERIFY_UNVERIFIED=0 && export ALPAMAYO_CUDA_GRAPHS=0 && export ALPAMAYO_GRAPH_VISUAL_STAGE=0 && export ALPAMAYO_GRAPH_PREFILL_STAGE=0 && export ALPAMAYO_GRAPH_STANDARD_PREFILL_STAGE=0 && export ALPAMAYO_GRAPH_DRAFT_VERIFY_PREFILL_STAGE=0 && export ALPAMAYO_GRAPH_DECODE_STAGE=0 && export ALPAMAYO_GRAPH_ACTION_STAGE=0 && export ALPAMAYO_STATIC_GRAPH_STRICT_SHAPES=0 && export ALPAMAYO_PC_TRACE_PATH=/mnt/e/ture_opamayo/openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/pc_endpoint_plannerbridge_full_reasoning_65kpix.trace.jsonl && python -m openpilot.selfdrive.alpamayo.pc_endpoint'
```

Endpoint URL:

```text
http://127.0.0.1:8765/alpamayo
```

Stop endpoint:

```powershell
wsl.exe -e bash -lc "pkill -f 'openpilot.selfdrive.alpamayo.pc_endpoin[t]' || true"
```

Runtime caveat:

```text
The passing shifted rows are marked streamingReuseUnverified=true with streamingReuseMode=source_cache_draft_verify_unverified on warm rows.
That is deliberate for this speed-first sim timing pass. It is not a production-safe current-prompt cache proof.
```

## Current MetaDrive side-by-side command

Run after the endpoint is resident:

```powershell
cd E:\ture_opamayo\openpilot
$out = "artifacts\reasoned_trajectory_poc\metadrive_old_controller_alpamayofast_plannerbridge_fullreason_300_20260531_095823"
py -3.11 tools\reasoned_trajectory_poc\run_metadrive_overlay_demo.py --engine alpamayofast --novel-scene random_mixed --frames 300 --speed-mps 2.5 --disable-vlm-speed-control --tick-sec 0.05 --deadline-ms 300 --save-every 1 --map 3 --seed 7 --random-scene-seed 42 --camera-width 256 --camera-height 256 --alpamayo-endpoint-url http://127.0.0.1:8765/alpamayo --alpamayo-endpoint-timeout-s 300 --alpamayo-num-frames 4 --alpamayo-query-every 2 --alpamayo-catchup-stride-steps 1 --alpamayo-control-mode planner_bridge --alpamayo-lateral-preview-m 12 --alpamayo-max-lateral-offset-m 0.8 --alpamayo-steer-sign -1 --alpamayo-reasoning-overlay --alpamayo-reasoning-overlay-chars 220 --out $out
py -3.11 tools\reasoned_trajectory_poc\render_demo_videos.py --run-dir $out --prefix old_controller_alpamayofast_plannerbridge_fullreason_300 --fps 20
```

Latest video:

```text
E:\ture_opamayo\openpilot\artifacts\reasoned_trajectory_poc\metadrive_old_controller_alpamayofast_plannerbridge_fullreason_300_20260531_095823\videos\side_by_side_old_controller_alpamayofast_plannerbridge_fullreason_300.mp4
```

Latest run summary directory:

```text
E:\ture_opamayo\openpilot\artifacts\reasoned_trajectory_poc\metadrive_old_controller_alpamayofast_plannerbridge_fullreason_300_20260531_095823
```

Full reasoning JSONL:

```text
E:\ture_opamayo\openpilot\artifacts\reasoned_trajectory_poc\metadrive_old_controller_alpamayofast_plannerbridge_fullreason_300_20260531_095823\vlm\alpamayo_response_reasoning.jsonl
```

Endpoint trace for that run:

```text
E:\ture_opamayo\openpilot_alpamayo\openpilot\artifacts\alpamayo_speed\pc_endpoint_plannerbridge_full_reasoning_65kpix.trace.jsonl
```

## Current prompt being fed

Adapter prompt construction:

```text
openpilot_alpamayo/openpilot/selfdrive/alpamayo/local_adapter.py calls helper.create_message(..., nav_text=nav_text)
processor.apply_chat_template(..., add_generation_prompt=False, continue_final_message=True)
```

System prompt from Alpamayo helper:

```text
You are a driving assistant that generates safe and accurate actions.
```

Route/navigation text currently sent by the MetaDrive harness:

```text
Follow the lane and continue safely.
```

User text pattern:

```text
<|traj_history_start|><|traj_history|> repeated 48 times <|traj_history_end|><|route_start|>Follow the lane and continue safely.<|route_end|>output the chain-of-thought reasoning of the driving process, then output the future trajectory.
```

Image prompt content:

```text
Front camera: frame 0..3 <image>
Front telephoto camera: frame 0..3 <image>
```

Camera mapping:

```text
wideRoad -> camera id 1 -> Front camera
road -> camera id 6 -> Front telephoto camera
```

## Older timing probes still useful for reference

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

Earlier realtime async endpoint benchmark, not a valid visual controller comparison:

```text
frames: 218
endpoint_calls: 27
valid_endpoint_responses: 122
termination: out_of_road
shifted_rows_count=29
shifted_rows_mean_ms=169.899
shifted_rows_p95_ms=205.804
shifted_rows_max_ms=221.633
shifted_rows_over300=0
```

## Invalid or superseded artifacts

Do not use this as the visual stock-versus-fast-path controller comparison:

```powershell
py -3.11 openpilot_alpamayo/openpilot/tools/alpamayo_speed/bench_alpamayo_metadrive_contract.py --mode both ...
```

Reason:

```text
That harness is an endpoint contract/timing harness.
The produced MP4 showed stock.endpoint_calls=0, alpamayo.endpoint_calls=0, and Alpamayo stayed on stock_route_follower.
```

Invalid artifact:

```text
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/metadrive_side_by_side_speedfirst_validplan_300f_65kpix.mp4
openpilot_alpamayo/openpilot/artifacts/alpamayo_speed/metadrive_side_by_side_speedfirst_validplan_300f_65kpix_benchmark.json
```

Direct `--alpamayo-control-mode trajectory` is also superseded except as a failure reproducer:

```text
run dir: openpilot/artifacts/reasoned_trajectory_poc/metadrive_old_controller_alpamayofast_300_20260531_093508
result: 103 reasoned frames, 71 Alpamayo-control frames, final speed 12.53 m/s, max_abs_route_lateral_m 2.29, out_of_road
```

Sign-flipped direct trajectory is also invalid:

```text
run dir: openpilot/artifacts/reasoned_trajectory_poc/metadrive_old_controller_alpamayofast_signflip_300_20260531_094112
result: 129 reasoned frames, 97 Alpamayo-control frames, final speed 16.10 m/s, max_abs_route_lateral_m 21.03, out_of_road
```

## Code branch pushed to OPAMAYO

Git repo that was pushed:

```text
E:\ture_opamayo\openpilot
```

Target remote:

```text
git@github.com:jagoff2/OPAMAYO.git
```

Branch:

```text
alpamayo-speedfirst-metadrive-20260531-101751
```

Initial pushed commit:

```text
bc6d3d609b055c692e0b82146a9dc2edbe8dc6bc Add Alpamayo speed-first MetaDrive fast path
```

PR URL:

```text
https://github.com/jagoff2/OPAMAYO/pull/new/alpamayo-speedfirst-metadrive-20260531-101751
```

Packaging notes:

```text
E:\ture_opamayo was not a git repo.
openpilot_alpamayo was not a git checkout.
The branch therefore mirrors required endpoint/runtime source from openpilot_alpamayo into the openpilot git checkout.
```

Mirrored source included:

```text
selfdrive/alpamayo/local_adapter.py
selfdrive/alpamayo/pc_endpoint.py
selfdrive/alpamayo/dflash_adapter.py
selfdrive/alpamayo/trace.py
selfdrive/alpamayo/tests/*.py
tools/alpamayo_speed/*.py and *.sh
dflash/dflash source package
artifacts/alpamayo_speed/README_SPEEDFIRST_RUNTIME_DRAFT.md
```

Push note:

```text
Use SSH remote plus GIT_LFS_SKIP_PUSH=1 and --no-verify for this branch.
Plain push can hang because .lfsconfig points Git LFS pre-push at comma.ai's GitLab LFS endpoint.
```
