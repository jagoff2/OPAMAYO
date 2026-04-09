# Alpamayo-Enhanced openpilot: Context and Plan

Date: 2026-04-07

## Goal

Integrate Alpamayo as a low-rate semantic planning sidecar that improves openpilot in long-tail decision scenes without replacing stock openpilot's fast 20 Hz control loop.

The target is not "Alpamayo actuates the car."

The target is:

- stock openpilot remains the fast stabilizer and immediate controller
- Alpamayo runs more slowly and proposes a medium/far-horizon trajectory prior
- a fusion layer biases stock planning only where slow semantics are useful
- stale or inconsistent sidecar output is ignored immediately

## Current Repo State

This repo was force-synced to `origin/master` at:

- `c7382f8258a95161e4be999e3c8632d4760e72c9`

Important local checkout note:

- on this Windows machine, `core.symlinks` had to be set to `false` to complete the hard reset because git was denied symlink creation
- this is acceptable for preserving source context and planning notes, but if Linux runtime validation is needed later, use a Linux checkout

Concrete in-tree scaffolding now exists for this plan:

- `SemanticPlan` capnp/service definitions were added
- `alpamayod` was added as a managed process scaffold
- `modeld` now has a gated semantic fusion path
- `alpamayod` now has two in-tree providers:
  - a stock-mirror smoke-test provider
  - a compressed HTTP remote-provider path with real `VisionIPC` road and wide frame capture plus state/calibration packaging
- a transport/protocol module now exists at `selfdrive/alpamayo/protocol.py`
- an executable stub server now exists at `selfdrive/alpamayo/server_stub.py` so the remote contract can be exercised before real Alpamayo inference is plugged in

This means the sidecar interface, fusion seam, and offboard transport contract now exist in code, even though the real Alpamayo inference backend is still to be swapped in.

## Verified openpilot Architecture on Current Master

Relevant facts from the current codebase:

- `modeld` publishes `modelV2` at 20 Hz and computes the control-facing `action` from the stock model plan
- `plannerd` consumes `modelV2` and only handles longitudinal planning on top of it
- `controlsd` uses `modelV2.action.desiredCurvature` for lateral unless a test-only `lateralManeuverPlan` override is present
- `modelV2` already carries the full future position, velocity, acceleration, orientation, and orientation rate trajectory

Implication:

- the clean fusion point is upstream of `modelV2` publication inside or adjacent to `modeld`
- the first version should not patch `controlsd` directly
- the existing `lateralManeuverPlan` message is not sufficient because it only carries a scalar curvature target

Concrete code anchors:

- `selfdrive/modeld/modeld.py`
- `selfdrive/modeld/fill_model_msg.py`
- `selfdrive/controls/plannerd.py`
- `selfdrive/controls/lib/longitudinal_planner.py`
- `selfdrive/controls/controlsd.py`
- `cereal/log.capnp`
- `cereal/services.py`

## Verified openpilot Model Characteristics

Current stock openpilot model assumptions:

- narrow + wide road camera inputs
- 20 Hz runtime
- 5 second temporal context through desire history, curvature history, and feature buffer

This supports the design premise that stock openpilot should remain the fast local controller.

## Verified Alpamayo Characteristics

From the current public Alpamayo 1.5 model card and repo:

- Alpamayo 1.5 is a 10B VLA reasoning and trajectory model
- default input setting is 4 cameras with 0.4 s history at 10 Hz
- it outputs a 6.4 second future trajectory with 64 waypoints at 10 Hz
- the trajectory is internally parameterized as acceleration and curvature under a unicycle model
- navigation guidance is supported
- flexible multi-camera input is supported
- the official single-sample inference guidance is about 24 GB VRAM on one NVIDIA GPU
- inference code depends on PyTorch, Transformers, and DeepSpeed

Implication:

- Alpamayo is appropriate as a slow semantic planner / policy prior
- it is not appropriate as the direct 20 Hz actuator-rate controller
- it can be adapted to the reduced openpilot camera set, but side visibility and cross-traffic semantics will degrade relative to its default 4-camera regime

## Hardware Assumptions

Updated user-provided hardware:

- desktop host has `2 x RTX 5060 Ti 16 GB`
- combined available VRAM is therefore 32 GB, but split across two GPUs
- user wants planning around a `comma 3X -> eGPU / external GPU pathway`
- user preference is to avoid any always-on desktop PC in the loop if possible
- preferred hardware path is `comma 3X + 1 x RTX 5060 Ti 16 GB + eGPU adapter dock`, with no PC involved

Judgment:

- the `2 x 16 GB` desktop setup makes full Alpamayo inference plausible on the desktop host via multi-GPU sharding / partitioning
- this is materially better than the earlier assumption of a single 16 GB card
- the single `5060 Ti 16 GB` direct eGPU path is the user-preferred target, but it is not the lowest-risk path with the current software stack

Important constraint:

- current openpilot `USBGPU` mode hard-switches `modeld` to tinygrad `AMD` over `USB`
- current tinygrad docs list `USB` only under AMD interfaces, while NVIDIA uses `NVK` or `PCI`
- therefore, current `c3x -> tinygrad USBGPU -> NVIDIA` is not the right first implementation path

Conclusion:

- direct c3x-attached NVIDIA acceleration is the desired end state, but it currently requires new runtime work
- the lowest-risk first architecture remains a desktop GPU server sidecar reached over a wired RPC or streaming link

## Preferred vs Recommended Path

### Preferred End State

What the user prefers:

- `comma 3X + single RTX 5060 Ti 16 GB + eGPU dock`
- no external desktop server in the critical path

Why this is attractive:

- simpler deployment
- no network transport dependency
- no split system to manage in the car

What blocks it today:

- current openpilot `USBGPU` path is AMD-over-USB, not NVIDIA-over-USB
- current tinygrad docs expose `USB` for AMD and `NVK|PCI` for NVIDIA, not `USB` for NVIDIA
- c3x integration for a directly attached NVIDIA eGPU would therefore need new low-level runtime and transport support rather than just application glue

### Recommended v1

What is recommended for the first successful implementation:

- offboard Alpamayo inference on the desktop NVIDIA host
- c3x runs openpilot plus a lightweight Alpamayo client
- structured trajectory prior comes back to openpilot for fusion

Reason:

- it solves the planning problem first
- it avoids blocking on custom NVIDIA-over-USB runtime work
- it gives a working baseline against which a later direct-eGPU port can be judged

### Recommended v2

If v1 proves useful, the next step is:

- replace the desktop Alpamayo server with a direct c3x-attached NVIDIA eGPU path
- keep the exact same `SemanticPlan` interface and fusion policy
- only swap the inference backend and transport implementation

This keeps the architecture stable while changing only the execution substrate.

## Recommended Architecture

### Separation of Responsibility

- stock openpilot at 20 Hz owns immediate stabilization, short-horizon trajectory, and all safety-critical fast reactions
- Alpamayo at low rate owns semantic interpretation, long-tail scene adjudication, and medium/far-horizon trajectory prior generation
- fusion combines both only where latency is acceptable

### Time-Scale Split

- `0.0 to 0.7 s`: stock only
- `0.7 to 2.5 s`: light Alpamayo influence if fresh and consistent
- `2.5 to 6.4 s`: stronger Alpamayo influence
- beyond `6.4 s`: stock only in v1

### Fusion Rule

Use trajectory-prior fusion, not mode switching:

`traj_fused = traj_stock + alpha(freshness, consistency, confidence, risk) * W(horizon) * (traj_alpamayo - traj_stock)`

Properties:

- `W(horizon)` is near zero close in and increases with horizon
- `alpha` is forced to zero when stale, inconsistent, or low-confidence
- stock always wins near-field conflicts

### Hard Safety Rules

- Alpamayo never sends direct steering, throttle, or brake commands
- Alpamayo output must be fresh
- Alpamayo output must be self-consistent across consecutive runs before high weight is allowed
- near-range hazard handling remains stock-only
- large disagreement plus low confidence falls back to stock immediately

## Recommended System Topology

### v1 Topology

- `comma 3X` runs normal openpilot stack
- `alpamayod` on the c3x captures road and wide `VisionIPC` frames plus vehicle, calibration, and navigation context and sends it offboard
- desktop `alpamayo_server` runs Alpamayo on the `2 x 5060 Ti 16 GB` host
- server returns a compact structured trajectory prior
- `modeld` or a tightly adjacent fusion process receives the prior and fuses it before publishing `modelV2`

### Why This Topology

- it keeps all existing fast-control code paths intact
- it avoids trying to make the c3x directly host a desktop NVIDIA stack
- it decouples transport engineering from multi-GPU inference engineering
- it makes replay-first validation practical

## Messaging and Process Plan

### New Message

Add a new capnp message instead of overloading `lateralManeuverPlan`.

Suggested message name:

- `SemanticPlan`

Suggested contents:

- source timestamp
- sequence id
- processing latency
- freshness age
- confidence
- consistency score
- optional semantic risk bits
- future position trajectory
- future velocity trajectory
- future acceleration trajectory
- optional orientation / orientation rate

This should be added to:

- `cereal/log.capnp`
- `cereal/services.py`

### New Processes

Add:

- optionally `selfdrive/alpamayo/fusiond.py`

and register in:

- `system/manager/process_config.py`

Initial recommendation:

- keep fusion inside `modeld` for v1 to avoid duplicating `modelV2` publication semantics
- keep the desktop inference server outside the openpilot process manager for the first version

## Current In-Tree Implementation Status

What is implemented now:

- `alpamayod` publishes `semanticPlan` at low rate
- when `AlpamayoServerEndpoint` is unset, it uses a stock-mirror provider to keep the pipe alive
- when `AlpamayoServerEndpoint` is set, it:
  - connects to road and wide `VisionIPC`
  - copies the latest NV12 camera buffers on each semantic tick
  - packages them with calibration, egomotion, selfdrive state, navigation, and stock plan context
  - compresses the request with zstd and posts it over HTTP
  - parses a structured trajectory response back into `SemanticPlan`
  - falls back to the last valid semantic plan for up to 1.0 s on request failure
- `selfdrive/alpamayo/server_stub.py` can already answer that request in `echo` or `caution` mode

What is not implemented yet:

- real Alpamayo model inference
- multi-GPU sharding/runtime on the desktop host
- direct `c3x + NVIDIA eGPU` runtime without a desktop intermediary
- replay evaluation tooling for this new path

## Integration Point Recommendation

### Best v1 Fusion Location

Inside `selfdrive/modeld/modeld.py`, after stock `model_output` is produced but before:

- `get_action_from_model(...)`
- `fill_model_msg(...)`

Reason:

- one fusion changes both the published future trajectory and the derived `action`
- downstream consumers remain unchanged
- `plannerd`, `controlsd`, `radard`, and `selfdrived` continue to operate on normal `modelV2`

### Do Not Start Here

Do not start by:

- patching `controlsd` to blend actuator commands
- using Alpamayo as a direct steering/brake controller
- trying to reuse the single-scalar `lateralManeuverPlan`
- attempting direct `USBGPU` NVIDIA integration on the c3x

## Input Mapping Plan

### openpilot Inputs Available

From current stock openpilot:

- front narrow camera stream
- front wide camera stream
- calibration
- egomotion history
- optional nav-related messages in the stack

### Alpamayo Default Inputs

Default Alpamayo expects 4 cameras:

- front-wide
- front-tele
- cross-left
- cross-right

### v1 Mapping

Use Alpamayo flexible-camera mode with reduced input set:

- map openpilot wide road camera to Alpamayo front-wide
- map openpilot narrow road camera to Alpamayo front-tele
- provide no cross-left / cross-right in v1
- provide egomotion and timestamps
- optionally provide navigation context when available

Expected limitation:

- weaker cross-traffic, merge-side, and intersection-side semantics than full 4-camera Alpamayo

## GPU Backend Plan

### Recommended Inference Backend

For the desktop host:

- use the official PyTorch / Transformers / DeepSpeed inference stack first
- use model sharding across the `2 x 5060 Ti 16 GB`
- minimize trajectory samples in v1
- do not add quantization as a prerequisite unless memory or latency forces it

Reason:

- it is the lowest-risk path to a working semantic sidecar
- it avoids simultaneously solving integration, quantization, and custom runtime portability

### Multi-GPU Strategy

Use:

- Hugging Face `device_map` or equivalent model partitioning first
- DeepSpeed inference only if needed after baseline setup

### Direct eGPU Research Track

The preferred no-PC path should be treated as a separate backend track:

- keep the planning API identical to v1
- investigate whether Alpamayo can be executed on a single `5060 Ti 16 GB` with acceptable memory and latency under reduced sampling and aggressive inference optimization
- if memory or throughput is insufficient, test whether a partial offload or a smaller teacher-distilled model is required instead of forcing full Alpamayo
- only pursue direct c3x eGPU once the software path for NVIDIA-over-attached-link is concrete

This avoids coupling semantic planning validation to an unproven transport/runtime substrate.

Practical v1 target:

- single trajectory sample
- no expensive CFG-style multi-sample rollout in the critical path
- optimize for determinism and acceptable latency, not best benchmark quality

## Freshness and Acceptance Policy

Suggested v1 thresholds:

- reject if prior age > `1.0 s`
- reduce weight aggressively once prior age exceeds `0.5 s`
- require two consecutive sidecar outputs with low trajectory disagreement before allowing strong far-horizon bias
- reject immediately on malformed output, missing timestamps, or transport timeout

Suggested consistency checks:

- compare consecutive Alpamayo priors in the overlap horizon
- compare Alpamayo against stock in curvature and longitudinal acceleration envelopes
- cap curvature and acceleration deltas before fusion

## Evaluation Plan

### Phase 0: Replay-Only

Before any on-road use:

- collect and replay logs through stock openpilot
- run Alpamayo server offline on the same segments
- compute fused trajectory and compare against stock-only decisions

Prioritize scenes involving:

- blocked intersections
- weird yields
- ambiguous merges
- occluded actors
- construction or cone lane ambiguity
- lead-car latent hazard behavior

### Phase 1: Shadow Mode

- run client + server on-road
- do not fuse into `modeld`
- log priors, latency, freshness, and disagreement only

### Phase 2: Far-Horizon-Only Fusion

- enable fusion only beyond `2.5 s`
- zero near-field influence
- keep strict freshness gates

### Phase 3: Medium-Horizon Blend

- allow controlled influence from `0.7 s` onward
- still keep near-field at effectively zero weight

## Failure Modes

Primary risks:

- stale sidecar outputs fighting stock control
- transport jitter causing inconsistent priors
- camera schema mismatch reducing semantic quality
- desktop server dropouts or reconnect churn
- excessive coupling to openpilot's real-time loop

Mitigations:

- cached last-good prior with hard expiry
- alpha forced to zero on missing or stale data
- confidence and consistency gates
- replay regression tests before any active fusion
- keep all direct actuation authority in stock openpilot

## Immediate Build Order

Recommended implementation sequence:

1. Add a note-only design doc and freeze the architecture.
2. Add `SemanticPlan` capnp/service definitions.
3. Build `alpamayo_clientd` on the c3x to serialize camera + ego context.
4. Build a desktop `alpamayo_server` that returns a compact structured prior.
5. Add a no-op receiver path in openpilot and log freshness/latency only.
6. Add offline fusion code in `modeld` gated behind an env var or param.
7. Validate on replay.
8. Run shadow mode on-road.
9. Enable far-horizon-only fusion.
10. Expand only after latency and disagreement distributions are well understood.

Separate backend track after step 10:

1. Prototype direct NVIDIA eGPU discovery and runtime support from the c3x side.
2. Swap the desktop server with a local backend while preserving `SemanticPlan` semantics.
3. Compare latency, stability, thermal behavior, and recovery behavior against the desktop-server baseline.

## Recommended v1 Success Criteria

The first version is successful if it achieves all of the following:

- no direct actuation ownership by Alpamayo
- no regressions in close-range stabilization behavior
- reliable client/server transport with bounded latency
- sane priors in replay for ambiguous long-tail scenes
- easy full fallback to stock by zeroing fusion weight

It is not necessary for v1 to:

- beat stock lane-keeping
- run directly on the c3x GPU
- use custom tinygrad NVIDIA transport
- solve every camera mismatch issue

## Sources Consulted

Primary external references used for this plan:

- openpilot `selfdrive/modeld/models/README.md`
- openpilot 0.11 release blog
- Alpamayo 1.5 Hugging Face model card
- Alpamayo 1.5 official GitHub README
- tinygrad runtime docs

## Final Decision for Now

Best path to the stated goal:

- keep stock openpilot as the fast controller
- use the desktop `2 x 5060 Ti 16 GB` host as the first working Alpamayo backend
- integrate through a structured low-rate semantic trajectory prior
- fuse into stock planning upstream of `modelV2`
- validate in replay and shadow mode before any active on-road fusion

User-preferred long-term target:

- migrate that same architecture onto a direct `comma 3X + 1 x 5060 Ti 16 GB eGPU` setup once NVIDIA-attached execution is technically real on this stack

This is the most technically sane route with the current codebase and the current hardware.

## 2026-04-07 Backend Bring-Up Results

Concrete local bring-up status on this machine:

- official `NVlabs/alpamayo1.5` repo cloned to `G:\alpamayo1.5`
- official WSL env created and synced successfully with `torch 2.8.0+cu128` and `transformers 4.57.1`
- Hugging Face access verified for both `nvidia/Alpamayo-1.5-10B` and `nvidia/Cosmos-Reason2-8B`
- both local GPUs are `RTX 5060 Ti 16 GB` and report compute capability `(12, 0)`

Files added for concrete measurement:

- `G:\alpamayo1.5\try_load_model.py`
- `G:\alpamayo1.5\timed_inference.py`

Local Alpamayo repo patch required for 2-GPU execution:

- patched `src/alpamayo1_5/models/alpamayo1_5.py` so the diffusion step returns `pred.to(x.device)`
- reason: with model-parallel execution, the diffusion denoiser output otherwise stays on the last expert GPU and breaks the Euler update path

Measured results:

### 1. Official-style full model load works across both 5060 Ti cards

- load path: `dtype=torch.bfloat16`, `attn_implementation="eager"`, `device_map="auto"` or manual split
- measured cold model load wall time: about `60-64 s`
- weights are physically runnable on `2 x 16 GB`, but not on a single stock unquantized 16 GB card

### 2. Stock official 4-camera inference does not fit

- config: `4 cameras x 4 frames`, stock pixel budget, `device_map="auto"`
- failure: CUDA OOM during VLM generation on GPU 1
- concrete error observed: allocation short by about `1.14 GiB`

### 3. `front2` auto-sharded inference exposes a model-parallel bug

- config: `front_wide + front_tele`, `4 frames`, stock pixel budget, `device_map="auto"`
- VLM generation completes
- diffusion expert then fails with cross-device KV-cache mismatch
- root cause: prompt cache from VLM is split across GPUs, but the expert block is not split the same way by auto placement

### 4. Manual split device map fixes the expert/cache mismatch

Working configuration:

- VLM language layers `0-19` on GPU 0
- VLM language layers `20-35` on GPU 1
- expert layers `0-19` on GPU 0
- expert layers `20-35` on GPU 1
- `action_in_proj`, `diffusion`, `action_space` on GPU 0
- `action_out_proj`, VLM/Expert norms and final heads on GPU 1

### 5. First successful end-to-end inference on this PC

Config:

- `front2`
- `4 frames`
- stock pixel budget `163840-196608`
- manual split device map
- single trajectory sample

Measured:

- dataset load: `63.1 s` in the repeated run
- model load: `64.35 s`
- input token length: `1590`
- warm inference loop times: `3.30 s`, `2.71 s`, `2.64 s`
- mean warm inference wall time: `2.88 s`
- example minADE on sampled clip: `0.5435 m`

Log artifact:

- `G:\alpamayo1.5\timed_inference_front2_manual_split_repeat3.log`

### 6. Reduced-input sweep

Config:

- `front2`
- `2 frames`
- reduced pixel budget `65536`
- manual split device map

Measured:

- dataset load: `6.12 s`
- model load: `59.77 s`
- input token length: `841`
- warm inference loop times: `2.85 s`, `1.82 s`, `1.94 s`
- mean warm inference wall time: `2.20 s`
- example minADE on sampled clip: `1.4752 m`

Log artifact:

- `G:\alpamayo1.5\timed_inference_front2_2f_64k_manual_split_repeat3.log`

## Practical Conclusion From Measurements

What is now proven:

- Alpamayo 1.5 genuinely runs on this PC
- it can execute end-to-end inference across `2 x RTX 5060 Ti 16 GB`
- the openpilot-relevant `front2` camera subset is runnable

What is not yet true:

- it is not currently fast enough for a `250-1000 ms` semantic planner cadence
- it is not currently viable on `1 x 16 GB` unquantized with the stock runtime path
- it is not currently viable as a direct near-real-time c3x eGPU planner without more compression and runtime work

Implication:

- quantization is not required to prove basic functionality anymore
- quantization or a different runtime is likely required to make the `1 x 5060 Ti eGPU` target competitive

## 2026-04-08 Latency Reduction Results

Objective used for this pass:

- fit a practical semantic-planner loop on the current `2 x 5060 Ti 16 GB` proof machine
- remove as little information as possible
- optimize runtime before removing sensors or model capacity

### Profiling result

The dominant bottleneck was not diffusion. It was the VLM reasoning rollout.

Measured on `front2`, `2 frames`, `64k pixels`, manual split, eager attention:

- warm `vlm_generate_seconds`: about `1.62-2.46 s`
- warm `diffusion_seconds`: about `0.41-0.46 s`
- expert step calls: `10`

Implication:

- reducing diffusion steps alone cannot solve the budget
- the expensive piece is token-by-token natural-language CoT generation

### Runtime optimizations that were proven

1. Installed `flash-attn==2.8.3` into the WSL env.
2. Patched the Alpamayo wrapper classes so Transformers allows Flash Attention / SDPA capability inheritance from the underlying Qwen3-VL model.
3. Kept a hybrid backend:
   - VLM: `flash_attention_2`
   - expert diffusion: `eager`
4. Rebalanced the manual split from `20/16` style VLM burden to `split_index=16` so both GPUs are used more evenly.

Why hybrid attention is needed:

- full Flash Attention on both VLM and expert fails in the expert diffusion path due the expert's cached-attention pattern
- VLM Flash + expert eager works

### Critical design change that actually moved latency

To fit the budget, the required cut was:

- skip runtime autoregressive CoT decoding
- prefill `<|traj_future_start|>` directly into the prompt
- keep the image encoder and diffusion expert

This means:

- the model still conditions on the visual context and trajectory history
- the diffusion expert still predicts the 6.4 s trajectory
- but runtime natural-language CoT text is not generated on the critical path

This was the first change that materially collapsed wall time.

### Measured configurations

#### A. Full runtime reasoning, hybrid flash/eager, `front2`, `2 frames`, `64k`

- config: `flash_attention_2` for VLM, eager for expert, `split_index=16`
- warm loop times: `2.69 s`, `1.88 s`
- mean: `2.29 s`
- result: still too slow

Log:

- `G:\alpamayo1.5\timed_inference_flash_vlm_eager_expert_front2_2f_64k_split16_repeat2.log`

#### B. Fast path with prefilled `<|traj_future_start|>`, 10 diffusion steps

- config: `front2`, `2 frames`, `64k`, `split_index=16`, VLM flash, expert eager
- warm loop times: `1.75 s`, `0.79 s`
- mean: `1.27 s`
- result: close, but not enough margin for a strict `<=1.0 s` target

Log:

- `G:\alpamayo1.5\timed_inference_prefill_future_start_flash_vlm_eager_expert_front2_2f_64k_split16_repeat2.log`

#### C. Fast path with prefilled `<|traj_future_start|>`, 6 diffusion steps

- config: `front2`, `2 frames`, `64k`, `split_index=16`, VLM flash, expert eager, `diffusion_steps=6`
- loop times: `1.52 s`, `0.65 s`, `0.66 s`
- mean over 3 runs: `0.94 s`
- measured VLM prefill after warmup: about `0.38 s`
- measured diffusion after warmup: about `0.25-0.27 s`
- result: fits a `<=1.0 s` warm semantic-loop budget on this machine

Log:

- `G:\alpamayo1.5\timed_inference_prefill_future_start_flash_vlm_eager_expert_front2_2f_64k_split16_diff6_repeat3.log`

#### D. Fast path with prefilled `<|traj_future_start|>`, 4 diffusion steps

- config: same as above, but `diffusion_steps=4`
- loop times: `1.52 s`, `0.62 s`, `0.62 s`
- mean over 3 runs: `0.92 s`
- result: also fits, with slightly more margin but more algorithmic reduction

Log:

- `G:\alpamayo1.5\timed_inference_prefill_future_start_flash_vlm_eager_expert_front2_2f_64k_split16_diff4_repeat3.log`

#### E. Restoring 4 frames while keeping the fast path

- config: `front2`, `4 frames`, `64k`, fast path, `10` diffusion steps
- loop times: `2.43 s`, `1.41 s`
- mean: `1.92 s`
- result: too slow

Log:

- `G:\alpamayo1.5\timed_inference_prefill_future_start_flash_vlm_eager_expert_front2_4f_64k_split16_repeat2.log`

### Practical conclusion

Current proof configuration that meets budget on this PC:

- `2 x RTX 5060 Ti 16 GB`
- manual split with `split_index=16`
- VLM on `flash_attention_2`
- expert diffusion on `eager`
- `front_wide + front_tele`
- `2 frames`
- `64k` pixel budget
- no runtime natural-language CoT decoding
- `6` diffusion steps preferred, `4` diffusion steps available for extra margin

Recommended default proof config:

- use the `prefill_future_start` fast path
- use `6` diffusion steps as the first deployable setting
- treat `4` diffusion steps as the fallback latency margin setting

Hard conclusion:

- keeping runtime textual CoT generation on the critical path does not meet budget here
- skipping runtime CoT generation is the minimum decisive cut that gets the loop into the target regime

## 2026-04-08 Fast Path Quality Check

Question tested:

- does the budget-fitting fast path stay physically sane?
- does it stay close to the full Alpamayo path on the same scenes?

Method:

- loaded one model once
- compared `full` vs `prefill_future_start` on 5 held-out clip/timestamp pairs from `notebooks/nav_demo_samples.json`
- same runtime substrate for both:
  - `front2`
  - `2 frames`
  - `64k` pixels
  - `split_index=16`
  - VLM `flash_attention_2`
  - expert `eager`
  - `diffusion_steps=6`
  - `num_traj_samples=1`
- measured:
  - wall time
  - ADE to ground truth
  - fast-vs-full trajectory distance
  - finite / bound checks via the action space

Artifacts:

- `G:\alpamayo1.5\compare_fast_vs_full.py`
- `G:\alpamayo1.5\compare_fast_vs_full.log`
- `G:\alpamayo1.5\compare_fast_vs_full_results.json`

Summary over 5 samples:

- mean full runtime: `1.8043 s`
- mean fast runtime: `0.7254 s`
- mean speedup: `2.4986 x`
- mean full ADE to GT: `2.8287 m`
- mean fast ADE to GT: `4.2029 m`
- mean ADE delta: `+1.3743 m` for fast path
- mean fast-vs-full ADE: `3.0555 m`
- mean fast-vs-full FDE: `9.5236 m`
- all fast trajectories finite: `true`
- all fast trajectories within action-space bounds: `true`

Interpretation:

- the fast path is physically sane in this test batch
- but it is not yet close enough to the full path to claim quality equivalence
- on this first 5-sample batch, the fast path is generally worse than the full path

So the honest state is:

- budget fit: achieved
- physical sanity: achieved
- accuracy similarity to full Alpamayo: not yet achieved
- similarity to stock openpilot: not tested yet

## 2026-04-08 Wide-vs-Tele Pixel Reallocation Retest

Question tested:

- if total image budget stays roughly fixed, does shifting more pixels to `front_wide` and fewer to `front_tele` improve the fast path?

Important caveat:

- this test still uses the first 5 rows of `notebooks/nav_demo_samples.json`
- that local file is a turn/intersection-heavy navigation demo slice, not a balanced driving benchmark
- so these results are best read as stress-test results on reasoning-heavy turn scenes

Method:

- same fast path as the current proof config:
  - `prefill_future_start`
  - `2 x RTX 5060 Ti 16 GB`
  - `split_index=16`
  - VLM `flash_attention_2`
  - expert `eager`
  - `num_traj_samples=1`
  - `diffusion_steps=6`
  - `front_wide + front_tele`
  - `2 frames`
- compared 4 per-camera pixel allocations:
  - `equal_64k`: wide `65536`, tele `65536`
  - `wide_80k_tele_48k`: wide `81920`, tele `49152`
  - `wide_96k_tele_32k`: wide `98304`, tele `32768`
  - `wide_112k_tele_16k`: wide `114688`, tele `16384`
- images were resized per camera before tokenization, then run through the same fast Alpamayo path
- measured wall time, image-token count, ADE to dataset egomotion GT, and per-axis error

Artifacts:

- `G:\alpamayo1.5\compare_camera_budget_profiles.py`
- `G:\alpamayo1.5\compare_camera_budget_profiles_results.json`

Summary over 5 samples:

- `equal_64k`
  - mean runtime: `0.6701 s`
  - mean image tokens: `648`
  - mean ADE: `3.6870 m`
  - mean longitudinal MAE: `1.6726 m`
  - mean lateral MAE: `3.0766 m`
- `wide_80k_tele_48k`
  - mean runtime: `0.7211 s`
  - mean image tokens: `684`
  - mean ADE: `4.1742 m`
  - mean longitudinal MAE: `1.9353 m`
  - mean lateral MAE: `3.3395 m`
- `wide_96k_tele_32k`
  - mean runtime: `0.7007 s`
  - mean image tokens: `664`
  - mean ADE: `4.6466 m`
  - mean longitudinal MAE: `1.4852 m`
  - mean lateral MAE: `4.2043 m`
- `wide_112k_tele_16k`
  - mean runtime: `0.7129 s`
  - mean image tokens: `664`
  - mean ADE: `4.9421 m`
  - mean longitudinal MAE: `2.2844 m`
  - mean lateral MAE: `4.1516 m`

Interpretation:

- on this turn-heavy 5-sample slice, wide-biased pixel reallocation did not help overall
- the stock equal split remained the best mean ADE and best mean lateral error
- a mild reallocation (`80k/48k`) helped one sample materially, but it lost on average
- aggressive wide bias hurt lateral accuracy most, even when runtime stayed in roughly the same regime

Operational implication:

- the current fast path at about `0.67 s` wall time is a low-rate semantic-planner loop, not a direct controller
- it covers one semantic update over a bundle of `2 cameras x 2 time frames`, not one 20 Hz control tick
- at `0.67 s` per update, Alpamayo contributes at about `1.5 Hz`
- that is only physically plausible as a cached medium/far-horizon prior blended into stock openpilot, never as near-field steering or braking authority

## 2026-04-08 Normal-Driving Retest

Question tested:

- does the fast path stay much closer to full Alpamayo on normal straight/mild-driving scenes than it did on the turn-heavy nav demo slice?

How the sample set was chosen:

- started from `notebooks/clip_ids.parquet`
- used `t0_relative = 5.1 s` for every candidate
- scored clips using only egomotion, not vision or model output
- kept clips with:
  - strong forward progress
  - low lateral drift
  - low yaw change over the next `6.4 s`
  - moderate speed and modest acceleration
- this was meant to approximate plain lane-following / normal driving rather than intersections or turning maneuvers

Chosen sample manifest:

- `G:\alpamayo1.5\normal_driving_samples.json`

Chosen sample videos:

- `G:\alpamayo1.5\normal_sample_videos\sample_00_9902d97b_frontwide_tele.mp4`
- `G:\alpamayo1.5\normal_sample_videos\sample_01_85d4315a_frontwide_tele.mp4`
- `G:\alpamayo1.5\normal_sample_videos\sample_02_0145f6e0_frontwide_tele.mp4`
- `G:\alpamayo1.5\normal_sample_videos\sample_03_16907266_frontwide_tele.mp4`
- `G:\alpamayo1.5\normal_sample_videos\sample_04_3acb96b8_frontwide_tele.mp4`

Comparison setup:

- same `full vs prefill_future_start` comparison as before
- same reduced runtime substrate for both:
  - `front_wide + front_tele`
  - `2 frames`
  - `64k` pixels per image
  - `split_index=16`
  - VLM `flash_attention_2`
  - expert `eager`
  - `diffusion_steps=6`
  - `num_traj_samples=1`
- only major difference between the two modes remained:
  - full path decodes runtime reasoning text
  - fast path skips that and prefills `<|traj_future_start|>`

Artifacts:

- `G:\alpamayo1.5\compare_fast_vs_full_manifest.py`
- `G:\alpamayo1.5\compare_fast_vs_full_normal_driving_results.json`

Summary over 5 normal-driving samples:

- mean full runtime: `1.8345 s`
- mean fast runtime: `0.7343 s`
- mean speedup: `2.4954 x`
- mean full ADE to GT: `1.9913 m`
- mean fast ADE to GT: `2.0521 m`
- mean ADE delta: `+0.0608 m` for fast path
- mean full longitudinal MAE: `1.8719 m`
- mean fast longitudinal MAE: `1.7947 m`
- mean full lateral MAE: `0.5291 m`
- mean fast lateral MAE: `0.8930 m`
- mean fast-vs-full ADE: `1.5295 m`
- mean fast-vs-full FDE: `4.4876 m`
- all fast trajectories finite: `true`
- all fast trajectories within action-space bounds: `true`

Interpretation:

- on this normal-driving slice, the fast path is much closer to full Alpamayo than it was on the turn-heavy nav demo slice
- mean ADE gap to GT shrank from about `+1.37 m` on the turn-heavy slice to about `+0.06 m` here
- the remaining degradation is still mostly lateral, but much smaller in absolute terms than on the turn-heavy slice
- that supports the original hypothesis:
  - runtime reasoning matters most in hard commitment scenes
  - removing it hurts those scenes a lot more than ordinary lane-following scenes

## 2026-04-08 Openpilot Implementation State

The repo now contains a concrete end-to-end sidecar implementation, not just scaffolding.

### What is now implemented in-tree

- `selfdrive/modeld/semantic_fusion.py`
  - fusion is now horizon-only, per the latest user instruction
  - no freshness gating
  - no confidence gating
  - no consistency gating
  - no scene gating
  - no curvature/turn/intersection gating
  - near horizon stays zero-weight before `0.7 s`
  - mid horizon ramps from `0.15` to `0.6` between `0.7 s` and `2.5 s`
  - far horizon uses full semantic weight after `2.5 s`
- `selfdrive/alpamayo/alpamayod.py`
  - now reconstructs a real `1.6 s` ego-history tensor from `livePose` plus `liveCalibration`
  - history is expressed in the current local frame, matching the Alpamayo-style dataset convention
  - now captures a real `2 frame x 2 camera` bundle from `VisionIPC`
  - uses `wideRoad -> front_wide` and `road -> front_tele`
  - sends the real history tensor, real frame bundle, stock plan, calibration, vehicle state, and nav context to the remote server
  - still keeps the short last-good cache on transport failure
- `selfdrive/alpamayo/server.py`
  - new real Alpamayo server
  - loads Alpamayo from the local `alpamayo1.5` repo or `ALPAMAYO_REPO`
  - uses the proven fast runtime path:
    - manual split, `split_index=16`
    - VLM `flash_attention_2`
    - expert `eager`
    - `2` cameras
    - `2` frames
    - `64k` pixels
    - `prefill_future_start`
    - `6` diffusion steps by default
    - `num_traj_samples=1`
  - decodes NV12 camera payloads
  - builds the Alpamayo prompt
  - runs real inference
  - converts Alpamayo's predicted trajectory into an openpilot-style `semanticPlan` trajectory
  - interpolates Alpamayo onto the stock plan timebase and uses stock tail behavior beyond the Alpamayo `6.4 s` horizon

### Current policy actually implemented

This now matches the latest user directive, not the earlier conservative recommendation.

Implemented blend policy:

- `0.0-0.7 s`: no semantic influence
- `0.7-2.5 s`: low-to-moderate blend weight ramp
- `2.5 s+`: full semantic influence

Not implemented anymore:

- stale-plan rejection inside fusion
- confidence-based alpha reduction inside fusion
- consistency-based alpha reduction inside fusion
- consecutive-valid gating inside fusion
- disagreement clipping inside fusion
- scene filtering for turns / merges / intersections

Important clarification:

- the server still returns `confidence`, `consistency`, `age`, and `blendHint` fields for observability
- `modeld` no longer uses them to scale the blend
- the only remaining blend limiter is horizon weighting plus `semanticPlan.status == valid`

### Real server launch path

Current expected proof path on this machine:

1. Run the real Alpamayo server in the Alpamayo-capable environment.
2. Point openpilot `AlpamayoServerEndpoint` at that server.
3. Enable `AlpamayoEnabled`.

Reference launch shape:

```bash
python -m selfdrive.alpamayo.server --alpamayo-repo /path/to/alpamayo1.5 --host 0.0.0.0 --port 8081
```

or with environment:

```bash
ALPAMAYO_REPO=/path/to/alpamayo1.5 python -m selfdrive.alpamayo.server
```

### Validation completed for this code pass

- syntax compilation passed for:
  - `selfdrive/alpamayo/alpamayod.py`
  - `selfdrive/alpamayo/server.py`
  - `selfdrive/modeld/semantic_fusion.py`
  - `selfdrive/controls/tests/test_semantic_fusion.py`
- lightweight unit tests passed for:
  - transport protocol
  - stub server
  - semantic trajectory conversion helpers in the real server
- direct execution of the semantic fusion tests passed outside repo `pytest`
- live smoke test passed for the real server:
  - launched `python -m selfdrive.alpamayo.server` from the existing WSL Alpamayo env
  - full Alpamayo model loaded through the new in-tree server entrypoint
  - compressed `/_health` probe returned `{"ready": true}`

Environment fix required for that live smoke:

- installed `zstandard` into `G:\alpamayo1.5\a1_5_venv`
- reason: the openpilot-side transport uses zstd-compressed request/response bodies

Why direct `pytest` was not used:

- this Windows checkout still has the openpilot symlink limitation
- repo-level `pytest` brings in the top-level `conftest.py` import path issue
- the modified modules were therefore validated with direct Python execution and focused unit tests instead
