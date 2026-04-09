#OpAmayo - an Alpamayo Openpilot Live Integration Proof And Runbook

## Scope

This document records:

- the exact PC server bring-up path
- the c3x runtime assumptions
- proof that `semanticPlan` is being produced by Alpamayo on the PC
- proof that `modeld` is consuming and fusing that plan
- proof that the fused `modelV2` path is consumed downstream by `controlsd`
- proof that this remains true when using NNLC

This is a runtime proof and operator runbook, not a design note.

## Addendum: PC Server Repo Completeness, Environment Rebuild, And Fast-Path Replication

This repo contains the **source code** needed to launch the PC Alpamayo server:

- `selfdrive/alpamayo/server.py`
- `selfdrive/alpamayo/protocol.py`
- `selfdrive/alpamayo/alpamayod.py`
- the c3x integration files under `cereal/`, `common/`, `system/`, `selfdrive/modeld/`, and `sunnypilot/modeld*`
- the vendored Alpamayo source tree under `alpamayo1.5/`
- the benchmark, comparison, and run scripts used during bring-up

This repo does **not** contain:

- the live rebuilt Linux virtualenv
- Hugging Face auth state
- the gated Alpamayo and Cosmos model weights/cache

The reason the venv is not stored in git is simple: the working Linux venv is about **8.1 GiB** and mostly consists of compiled CUDA, Torch, FlashAttention, and NVIDIA shared libraries. That is not a sane git artifact.

### Exact Working Environment That Was Used

The server and benchmarking path were validated in WSL/Linux with:

- Python `3.12.3`
- `uv 0.9.16`
- `nvcc 12.0.140`
- `torch 2.8.0`
- `flash_attn 2.8.3`
- `transformers 4.57.1`
- `accelerate 1.12.0`
- `physical_ai_av 0.2.0`
- `opencv-python-headless 4.13.0.92`
- `zstandard 0.25.0`

The exact pip environment used to run this is captured in:

- `alpamayo1.5/requirements.txt`

### Rebuild The Venv From Scratch

Assumptions:

- Linux or WSL with NVIDIA GPU access already working
- `nvcc` available on PATH
- Python 3.12 available
- enough disk for a multi-gigabyte env and model cache

Concrete procedure:

```bash
# 1. Enter the vendored Alpamayo source tree
cd /path/to/OPAMAYO/alpamayo1.5

# 2. Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 3. Create and activate the environment
uv venv a1_5_venv --python 3.12
source a1_5_venv/bin/activate

# 4. Install the exact package set used during bring-up
python -m pip install -r requirements.txt

# 5. Authenticate for the gated model + dataset
hf auth login

# 6. Optional but recommended cache location
export HF_HOME=/path/to/hf-cache

# 7. Sanity-check the critical runtime pieces
python -c 'import torch, flash_attn, cv2, zstandard; print(torch.__version__)'
python -m py_compile timed_inference.py src/alpamayo1_5/models/alpamayo1_5.py src/alpamayo1_5/models/base_model.py
```

Important notes:

- `flash-attn` is part of the proven fast path. Do not skip it if the goal is to reproduce the measured sub-1-second warm semantic loop.
- `opencv-python-headless` and `zstandard` are required for the openpilot-side server transport path.
- The model weights are **not** installed by git. They are pulled by Hugging Face on first use after auth succeeds.

### Launch The PC Server From This Repo

From the OPAMAYO repo root:

```bash
cd /path/to/OPAMAYO
source alpamayo1.5/a1_5_venv/bin/activate
export PYTHONPATH=$PWD
export HF_HOME=/path/to/hf-cache

python -m selfdrive.alpamayo.server \
  --host 0.0.0.0 \
  --port 8081 \
  --source remoteServer \
  --gpu-mem-gib 15 \
  --cpu-mem-gib 96 \
  --split-index 16 \
  --min-pixels 65536 \
  --max-pixels 65536 \
  --diffusion-steps 6 \
  --num-traj-samples 1 \
  --attn-implementation flash_attention_2 \
  --expert-attn-implementation eager \
  --reasoning-mode prefill_future_start
```

Operational detail:

- `PYTHONPATH=$PWD` matters.
- `python -m selfdrive.alpamayo.server ...` is the safe invocation.
- Invoking `python selfdrive/alpamayo/server.py ...` directly without the repo root on `PYTHONPATH` can fail on `ModuleNotFoundError: selfdrive`.

### How The Fast Alpamayo Path Was Made

The fast path was not a generic quantization trick. It was a specific runtime simplification and execution-layout change.

Mechanically, the fast path consists of:

1. **Skip runtime CoT token generation**
   - Instead of waiting for the model to autoregressively emit reasoning text and then `<|traj_future_start|>`, the prompt is rewritten so the assistant prefill starts directly at `<|traj_future_start|>`.
   - In the repo this is implemented by the `prefill_future_start` path in:
     - `alpamayo1.5/timed_inference.py`
     - `selfdrive/alpamayo/server.py`
   - And by using `skip_vlm_generation=True` when calling `sample_trajectories_from_data_with_vlm_rollout(...)` in:
     - `alpamayo1.5/src/alpamayo1_5/models/alpamayo1_5.py`

2. **Use a manual 2-GPU layer split**
   - The VLM/expert stack is split across 2 GPUs at `split_index=16`.
   - The helper for this is `build_manual_split_device_map(...)` in:
     - `alpamayo1.5/timed_inference.py`
     - `selfdrive/alpamayo/server.py`

3. **Use mixed attention backends**
   - VLM attention: `flash_attention_2`
   - expert attention: `eager`
   - The attention-plumbing modifications live in:
     - `alpamayo1.5/src/alpamayo1_5/models/base_model.py`
     - `alpamayo1.5/src/alpamayo1_5/models/alpamayo1_5.py`

4. **Reduce visual/context load without dropping the 2-camera sidecar design**
   - cameras: `front2`
   - frames: `2`
   - pixel budget: `65536` min/max
   - trajectory samples: `1`
   - diffusion steps: `6`

5. **Keep the output semantic**
   - The fast path still produces a full future trajectory prior.
   - It does not emit runtime chain-of-thought text on the critical path.

### Reproduce The Fast Benchmark

From `alpamayo1.5/`:

```bash
cd /path/to/OPAMAYO/alpamayo1.5
source a1_5_venv/bin/activate
export HF_HOME=/path/to/hf-cache

python timed_inference.py \
  --camera-mode front2 \
  --num-frames 2 \
  --gpu-mem-gib 15 \
  --cpu-mem-gib 96 \
  --min-pixels 65536 \
  --max-pixels 65536 \
  --device-map-mode manual_split \
  --split-index 16 \
  --repeat-infer 3 \
  --num-traj-samples 1 \
  --diffusion-steps 6 \
  --attn-implementation flash_attention_2 \
  --expert-attn-implementation eager \
  --reasoning-mode prefill_future_start
```

The measured successful warm-loop profile from this repo was approximately:

- first post-load iteration: `~1.52 s`
- warm iteration 1: `~0.65 s`
- warm iteration 2: `~0.66 s`

Those numbers are recorded in:

- `alpamayo1.5/timed_inference_prefill_future_start_flash_vlm_eager_expert_front2_2f_64k_split16_diff6_repeat3.log`

That is the configuration the PC server defaults were aligned with.

## System Mechanics In Plain English

The system is a two-rate planner:

- stock openpilot still runs the fast real-time driving loop
- Alpamayo runs more slowly as a semantic sidecar
- Alpamayo does not directly actuate steering, gas, or brake
- Alpamayo returns a future trajectory prior
- `modeld` blends that prior into the stock model trajectory
- downstream control consumes the fused `modelV2`, not two separate plans

So there is no direct actuator fight between two controllers. There is only one downstream trajectory after fusion.

The intended role split is:

- near horizon: stock only
- medium horizon: mixed stock plus Alpamayo
- far horizon: Alpamayo can dominate

That means Alpamayo is not a reflex controller. It is a low-rate semantic planner prior.

## End-To-End Mechanics

The live runtime path is:

1. `camerad` publishes road and wide frames.
2. `alpamayod` subscribes to those `VisionIPC` streams on the c3x.
3. `alpamayod` also reads stock context from the openpilot message bus, including `modelV2`, `livePose`, and calibration state.
4. `alpamayod` builds a request containing:
   - 2 cameras
   - 2 time frames
   - compressed image payloads
   - ego-history and calibration metadata
   - stock plan context
5. That request is sent over HTTP to `http://127.0.0.1:8081`.
6. `adb reverse` forwards that request from the c3x to the PC.
7. The Windows host forwards localhost traffic into WSL where the Alpamayo server is running.
8. The server decodes the images and metadata.
9. Alpamayo runs inference on the PC GPUs.
10. The server returns a structured semantic trajectory prior, not actuator commands.
11. `alpamayod` publishes that result as `semanticPlan` on the c3x.
12. `modeld` reads `semanticPlan`, fuses it into the stock plan, and recomputes `modelV2.action`.
13. `controlsd` consumes that fused `modelV2`.
14. NNLC also consumes the fused `modelV2` as part of its feedforward input.

The key operational fact is that the sidecar returns a trajectory, not direct steering or brake commands.

## Why This Can Affect The Car Even Though Alpamayo Is Slow

The control loop still runs at stock openpilot speed. Alpamayo is not trying to make every 50 ms decision.

What happens instead is:

- stock openpilot keeps publishing fresh `modelV2`
- Alpamayo periodically publishes a slower semantic prior
- `modeld` merges that slower prior into the medium and far horizon
- `controlsd` follows the fused result every cycle

So Alpamayo can influence:

- braking earlier
- delaying commitment
- changing future path shape
- biasing the car toward a different long-horizon trajectory

It is not trying to own:

- near-field servo corrections
- last-moment hazard reflexes
- raw 20 Hz actuation

This is exactly why freshness around `0.75s` can still matter. That latency is too slow for reflex control, but it is still usable for medium/far-horizon planning.

## Methodology

The proof was built from four independent observations, not one.

1. **Transport proof**
   - prove the c3x can reach the endpoint
   - prove the endpoint is the real WSL server

2. **Server execution proof**
   - observe real in-car requests arriving on the PC
   - observe timing and `status=valid source=remoteServer`

3. **Fusion proof**
   - observe live `semanticPlan`
   - observe live `semantic plan fused ...` log entries from `modeld`

4. **Downstream consumption proof**
   - observe live `modelV2.action.desiredCurvature`
   - observe live `controlsState.desiredCurvature`
   - confirm they match exactly on the live running system
   - inspect the deployed sunnypilot code path and verify NNLC takes `modelV2`

The conclusion depends on the combination of all four. Any one of them alone would be weaker.

## What Counts As Proof Here

This document proves runtime causality inside the software stack:

- the c3x sends camera-derived requests
- the PC runs Alpamayo
- the c3x receives a remote semantic plan
- `modeld` fuses that semantic plan
- the fused `modelV2` is what downstream control consumes

This does **not** prove, in the strict scientific A/B sense, that the physical driven path of the vehicle changed by a measured amount on the road. That would require paired experimental runs or deliberate toggling, which was not appropriate during live driving.

So the proof level here is:

- **software-path proof**: yes
- **planner influence proof**: yes
- **strict physical A/B vehicle-motion proof**: not in this runbook

## Physical Topology

- c3x horizontal rear USB port: PC comms
- c3x vertical rear USB port: vehicle / harness only
- transport: `adb reverse tcp:8081 tcp:8081`
- c3x endpoint: `http://127.0.0.1:8081`

## Runtime Configuration

### PC server

Run the Alpamayo server in WSL with the proven fast config:

```bash
source /mnt/g/alpamayo1.5/a1_5_venv/bin/activate
export PYTHONPATH=/mnt/g/openpilot
cd /mnt/g/openpilot
python -u -m selfdrive.alpamayo.server \
  --host 0.0.0.0 \
  --port 8081 \
  --alpamayo-repo /mnt/g/alpamayo1.5 \
  --gpu-mem-gib 15 \
  --cpu-mem-gib 96 \
  --split-index 16 \
  --min-pixels 65536 \
  --max-pixels 65536 \
  --diffusion-steps 6 \
  --num-traj-samples 1 \
  --attn-implementation flash_attention_2 \
  --expert-attn-implementation eager \
  --reasoning-mode prefill_future_start \
  --source remoteServer
```

### c3x params

These must be present on the device:

```bash
AlpamayoEnabled=1
AlpamayoServerEndpoint=http://127.0.0.1:8081
```

They are persistent params.

### Tunnel

Install the reverse tunnel from the PC:

```bash
adb reverse tcp:8081 tcp:8081
adb reverse --list
```

Expected:

```text
(null) tcp:8081 tcp:8081
```

## Reachability Proof

The endpoint is reachable from the c3x through the reverse tunnel. Manual probes from the c3x to `http://127.0.0.1:8081/_health` succeeded repeatedly with:

- HTTP `200`
- body length `23`
- latency about `0.008s` to `0.029s`

This proves the chain below is working:

```text
c3x -> adb reverse -> Windows localhost -> WSL localhost -> Alpamayo server
```

This rules out WSL routing as the blocker.

## Image Transport Path

The original live request path was too large. The sidecar transport was changed to JPEG-encoded resized BGR frames instead of raw NV12 frame bodies.

Relevant files:

- [protocol.py](G:\openpilot\selfdrive\alpamayo\protocol.py)
- [server.py](G:\openpilot\selfdrive\alpamayo\server.py)
- [alpamayod.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\selfdrive\alpamayo\alpamayod.py)

Results after the transport change:

- compressed request size dropped from about `9.1 MB` to about `34 KB` to `58 KB`
- live server total request time dropped to about `0.67s` to `0.78s`

## Proof That Alpamayod Receives Frames

The daemon now polls `VisionIPC` every loop instead of only on semantic publish ticks. That was the key bug fix required to make live remote inference actually run.

The c3x daemon attached to the real road and wide streams:

- `alpamayod connected road stream: 1928x1208`
- `alpamayod connected wideRoad stream: 1928x1208`
- `alpamayod remote provider initialized`

This proves the c3x sidecar is attached to live camera feeds and configured for remote Alpamayo inference.

## Proof That The PC Server Is Actually Running Alpamayo

The live WSL server emitted repeated request-completion logs during driving with values like:

```text
alpamayo request ok id=... in=36739 out=5574 read=0.010s decode=0.001s infer=0.666s encode=0.000s total=0.678s status=valid source=remoteServer ...
```

Observed server timings on real in-car requests:

- total: about `0.67s` to `0.78s`
- inference: about `0.63s` to `0.72s`
- status: `valid`
- source: `remoteServer`

This is direct proof that the car is sending requests to the PC and the PC is running Alpamayo inference, not just serving health checks.

## Proof That SemanticPlan Is Live And Remote

Live c3x observations of `semanticPlan` during driving showed:

```text
semanticPlan.status = valid
semanticPlan.source = remoteServer
semanticPlan.age = 0.7655778527259827
semanticPlan.generationExecutionTime = 1.1171375513076782
semanticPlan.desiredCurvature = -0.027970125898718834
semanticPlan.desiredAcceleration = -0.3513976037502289
```

and

```text
semanticPlan.status = valid
semanticPlan.source = remoteServer
semanticPlan.age = 0.7464171051979065
semanticPlan.generationExecutionTime = 0.9224347472190857
semanticPlan.desiredCurvature = -0.001730378600768745
semanticPlan.desiredAcceleration = -0.40232858061790466
```

This proves:

- the message is live
- it is coming from the remote server, not fallback
- it is fresh enough to be fused in the intended medium/far-horizon role

## Proof That Modeld Consumes And Fuses SemanticPlan

The deployed c3x `modeld` path is:

- fuse semantic trajectory into `model_output` in [modeld.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\selfdrive\modeld\modeld.py#L394)
- derive `action` from the fused `model_output` in [modeld.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\selfdrive\modeld\modeld.py#L404)
- publish `modelV2` from the fused plan in [modeld.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\selfdrive\modeld\modeld.py#L406)

Exact deployed code:

```python
if alpamayo_enabled and sm.seen['semanticPlan']:
  model_output, fusion_result = apply_semantic_fusion(model_output, sm['semanticPlan'])
...
action = get_action_from_model(model_output, prev_action, lat_delay + DT_MDL, long_delay + DT_MDL, v_ego)
fill_model_msg(...)
```

Live c3x `swaglog` entries during driving showed repeated successful fusion:

```text
semantic plan fused source=2 alpha=1.00 age=0.75s confidence=0.85 consistency=1.00
semantic plan fused source=2 alpha=1.00 age=0.77s confidence=0.85 consistency=1.00
semantic plan fused source=2 alpha=1.00 age=0.76s confidence=0.85 consistency=1.00
semantic plan fused source=2 alpha=1.00 age=0.78s confidence=0.85 consistency=1.00
```

This proves `modeld` is not discarding `semanticPlan`.

## Fusion Mechanics

`semanticPlan` is not copied directly into `modelV2.action`.

The mechanism is:

1. stock model inference produces `model_output`
2. `apply_semantic_fusion(...)` blends semantic trajectory arrays into the stock plan
3. `get_action_from_model(...)` derives a fresh `action` from the fused plan
4. `fill_model_msg(...)` publishes the fused trajectory and the recomputed action

So the scalar action values seen by the rest of openpilot are downstream products of the fused trajectory, not direct copies of scalar fields from `semanticPlan`.

The horizon policy in the deployed implementation is:

- `0.0s` to `0.7s`: zero semantic influence
- `0.7s` to `2.5s`: ramped blend
- `2.5s+`: full semantic weight

In practical terms:

- close-in control stays stock
- medium horizon gets mixed influence
- far horizon is where Alpamayo can dominate

That is why the correct runtime proof is:

- live remote `semanticPlan`
- live `semantic plan fused ...` logs
- live downstream `modelV2 -> controlsState` propagation

not a direct equality check between `semanticPlan.desiredCurvature` and `modelV2.action.desiredCurvature`

## Proof That The Modified ModelV2 Path Is Consumed Downstream

The active sunnypilot `controlsd` path directly consumes `modelV2.action.desiredCurvature`:

- [controlsd.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\selfdrive\controls\controlsd.py#L140)
- [controlsd.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\selfdrive\controls\controlsd.py#L143)
- [controlsd.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\selfdrive\controls\controlsd.py#L208)

Exact deployed code:

```python
new_desired_curvature = model_v2.action.desiredCurvature if CC.latActive else self.curvature
self.desired_curvature, curvature_limited = clip_curvature(...)
actuators.curvature = self.desired_curvature
...
cs.desiredCurvature = self.desired_curvature
```

Live same-window samples from the c3x matched exactly:

```text
modelV2.action.desiredCurvature @ 7652806111031 = 0.00012016872642561793
controlsState.desiredCurvature @ 7652813064399 = 0.00012016872642561793

modelV2.action.desiredCurvature @ 7652849082035 = 0.00011393759632483125
controlsState.desiredCurvature @ 7652854845648 = 0.00011393759632483125

modelV2.action.desiredCurvature @ 7652902253947 = 0.00010993104660883546
controlsState.desiredCurvature @ 7652912808349 = 0.00010993104660883546

modelV2.action.desiredCurvature @ 7652953017288 = 9.995466098189354e-05
controlsState.desiredCurvature @ 7652962391102 = 9.995466098189354e-05

modelV2.action.desiredCurvature @ 7653004448449 = 0.00010208125604549423
controlsState.desiredCurvature @ 7653012361777 = 0.00010208125604549423
```

This is the strongest direct runtime proof that the modified `modelV2` path is being consumed by the control stack and not discarded.

## NNLC-Specific Proof

NNLC is downstream of `modelV2`, not an alternate planner that bypasses it.

`controlsd` explicitly pushes `modelV2` into the lateral extension in [controlsd.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\selfdrive\controls\controlsd.py#L100):

```python
self.LaC.extension.update_model_v2(self.sm['modelV2'])
```

That stores the full message in [latcontrol_torque_ext_base.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\sunnypilot\selfdrive\controls\lib\latcontrol_torque_ext_base.py#L98):

```python
def update_model_v2(self, model_v2):
  self.model_v2 = model_v2
```

NNLC then uses the fused `modelV2` trajectory/state in [nnlc.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\sunnypilot\selfdrive\controls\lib\nnlc\nnlc.py#L123) and [nnlc.py](G:\alpamayo1.5\openpilot-c3x-full\openpilot\sunnypilot\selfdrive\controls\lib\nnlc\nnlc.py#L128):

```python
future_rolls = [np.interp(t, ModelConstants.T_IDXS, self.model_v2.orientation.x) ...]
future_planned_lateral_accels = [np.interp(t, ModelConstants.T_IDXS, self.model_v2.acceleration.y) ...]
```

Meaning:

- Alpamayo modifies the planner trajectory inside `modeld`
- `modeld` publishes the fused `modelV2`
- `controlsd` consumes `modelV2.action.desiredCurvature`
- NNLC also consumes the fused `modelV2` orientation and lateral-acceleration trajectory

So NNLC does not bypass the fused trajectory. It is downstream of it.

## Important Nuance

The thing that matters is not whether `semanticPlan.desiredCurvature` is copied verbatim into `modelV2.action.desiredCurvature`.

That is not how the integration works.

The actual sequence is:

1. Alpamayo returns a semantic trajectory prior.
2. `modeld` fuses that trajectory into the stock `model_output`.
3. `modeld` recomputes `action` from the fused `model_output`.
4. `controlsd` consumes the recomputed `modelV2.action`.
5. NNLC consumes the recomputed `modelV2` trajectory fields.

So the correct proof is:

- `semanticPlan` is valid and remote
- `modeld` logs live fusion
- `modelV2.action.desiredCurvature` is published
- `controlsState.desiredCurvature` matches that `modelV2.action.desiredCurvature`
- NNLC explicitly consumes `modelV2`

## Non-Disruptive Verification Commands

These are safe read-only checks.

### Check tunnel

```bash
adb reverse --list
```

### Check endpoint from c3x

```bash
adb shell "PYTHONPATH=/data/openpilot /usr/local/venv/bin/python - <<'PY'
import requests, time
t=time.time()
r=requests.get('http://127.0.0.1:8081/_health', timeout=2)
print(r.status_code, len(r.content), time.time()-t, r.headers.get('Content-Type'))
PY"
```

### Check live semanticPlan

```bash
adb shell "timeout 3 sh -c 'cd /data/openpilot && PYTHONPATH=/data/openpilot /usr/local/venv/bin/python selfdrive/debug/dump.py semanticPlan --values semanticPlan.status,semanticPlan.source,semanticPlan.age,semanticPlan.generationExecutionTime,semanticPlan.desiredCurvature,semanticPlan.desiredAcceleration'"
```

### Check live modelV2 action

```bash
adb shell "timeout 3 sh -c 'cd /data/openpilot && PYTHONPATH=/data/openpilot /usr/local/venv/bin/python selfdrive/debug/dump.py modelV2 --values modelV2.action.desiredCurvature,modelV2.action.desiredAcceleration'"
```

### Check live controlsState curvature

```bash
adb shell "timeout 3 sh -c 'cd /data/openpilot && PYTHONPATH=/data/openpilot /usr/local/venv/bin/python selfdrive/debug/dump.py controlsState --values controlsState.desiredCurvature'"
```

### Check latest fusion logs

```bash
adb shell "PYTHONPATH=/data/openpilot /usr/local/venv/bin/python - <<'PY'
from pathlib import Path
files = sorted(Path('/data/log').glob('swaglog.*'), key=lambda p: p.stat().st_mtime, reverse=True)
print(files[0] if files else 'NOLOG')
if files:
  lines = files[0].read_text(errors='ignore').splitlines()
  hits = [ln for ln in lines if 'semantic plan fused' in ln]
  for ln in hits[-5:]:
    print(ln)
PY"
```

## Failure Interpretation

### `semanticPlan.status = unavailable` or `source = none`

Meaning:

- sidecar is not currently returning usable remote results
- stock openpilot continues
- no live semantic influence is being applied

### No `semantic plan fused` logs

Meaning:

- `modeld` is not currently applying the remote semantic plan
- either `semanticPlan` is missing, invalid, stale, or ignored

### `modelV2.action.desiredCurvature` and `controlsState.desiredCurvature` diverge

Meaning:

- the control path is no longer directly following `modelV2.action`
- this would indicate a real downstream path mismatch and should be treated as a bug

## Bottom Line

The current live evidence proves all of the following:

- the c3x reaches the PC Alpamayo endpoint reliably
- Alpamayo is receiving real camera-derived requests from the c3x
- the PC is returning valid remote semantic plans
- `modeld` is fusing those plans into `model_output`
- the fused `modelV2.action.desiredCurvature` is being consumed by `controlsd`
- NNLC is downstream of the same fused `modelV2` and therefore does not bypass the modified trajectory path

This is sufficient runtime proof that the Alpamayo-modified `modelV2` path is real, live, and in the control stack.
