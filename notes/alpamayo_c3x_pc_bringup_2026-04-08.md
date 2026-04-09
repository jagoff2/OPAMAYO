# Alpamayo C3X/PC Bring-Up Status 2026-04-08

## Purpose

This note captures the exact state of the Alpamayo sidecar bring-up before shutting down the PC and moving the c3x into the car.

## Physical wiring

- PC comms port on the c3x: the horizontal rear USB-C port
- Harness / vehicle path: the vertical rear USB-C port
- Do not use the vertical port for PC comms in this setup

## Current PC server state

The real Alpamayo server was started successfully on the PC in WSL and reached healthy state.

Server command:

```bash
cd /mnt/g/openpilot
. /mnt/g/alpamayo1.5/a1_5_venv/bin/activate
PYTHONPATH=. python -u selfdrive/alpamayo/server.py \
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

Observed server status:

- health check returned `{"ready":true}`
- server binds `:8081` only after model load completes
- model loaded across both 5060 Ti 16 GB GPUs

Current proven runtime config:

- camera mode: `front2`
- 2 cameras
- 2 frames
- 64k pixel budget
- reasoning mode: `prefill_future_start`
- diffusion steps: `6`
- trajectory samples: `1`
- VLM attention: `flash_attention_2`
- expert attention: `eager`
- split index: `16`

## USB/ADB tunnel state

ADB saw the c3x and reverse tunneling was installed:

```bash
adb reverse tcp:8081 tcp:8081
adb reverse --list
```

Expected c3x endpoint:

```text
http://127.0.0.1:8081
```

This is the endpoint the c3x should use when connected to this PC over USB-C with ADB reverse active.

## c3x params already set

These were written directly on the c3x and are persistent across reboot and power loss:

- `AlpamayoEnabled=1`
- `AlpamayoServerEndpoint=http://127.0.0.1:8081`

Equivalent commands:

```bash
adb shell "printf 1 > /data/params/d/AlpamayoEnabled; printf 'http://127.0.0.1:8081' > /data/params/d/AlpamayoServerEndpoint; sync"
adb shell cat /data/params/d/AlpamayoEnabled
adb shell cat /data/params/d/AlpamayoServerEndpoint
```

Persistence basis:

- both keys are declared `PERSISTENT` in `common/params_keys.h`

## Build / schema issue that was fixed

The first c3x build failure was caused by a bad Cap'n Proto ordinal for `semanticPlan`.

Wrong:

```capnp
semanticPlan @151 :SemanticPlan;
```

Correct for this sunnypilot tree:

```capnp
semanticPlan @150 :SemanticPlan;
```

Reason:

- this tree already had no field at `@150`
- using `@151` created a hole
- Cap'n Proto requires sequential ordinals with no holes

Fixed overlay archive:

- `G:\alpamayo1.5\openpilot-c3x-alpamayo-port-fixed.tar.gz`

The earlier archive `openpilot-c3x-alpamayo-port.tar.gz` had the bad ordinal.

## Important non-Alpamayo crash cause

The later `MultiplePublishersError` crash was not caused by Alpamayo.

Cause:

- `selfdrive/debug/uiview.py` was running
- `uiview.py` starts and publishes services already owned by normal manager startup
- this duplicates publishers for services such as:
  - `carParams`
  - `liveCalibration`
  - `driverMonitoringState`
  - `driverStateV2`

Conclusion:

- do not run `selfdrive/debug/uiview.py` at the same time as normal openpilot manager
- the clean fix is a reboot, then launch only normal openpilot

## Build-time vs runtime dependency

The Alpamayo PC server is not needed for openpilot to build.

It is only needed at runtime when:

- `AlpamayoEnabled=1`
- `alpamayod` starts
- the c3x begins publishing real camera/model data

Normal build output that is not an Alpamayo problem:

- `clang++ ...`
- `/usr/bin/moc ...`
- `python3 ./spinner.py lagging by ... ms`
- Qt `wl-shell` deprecation warnings

## What is actually required to prove the full path works

You cannot prove the full end-to-end path with certainty while the device is only offroad.

Offroad can prove:

- params are set
- server is healthy
- ADB reverse is installed
- `alpamayod` can be started by manager

But full proof requires the c3x in normal onroad state because:

- `alpamayod` needs real `modelV2`
- `alpamayod` needs the narrow and wide camera streams
- modeld must actually consume and fuse `semanticPlan`

A stationary onroad state is sufficient. The car does not need to be moving for initial proof.

## How to verify onroad, step by step

### 1. Verify c3x sidecar process attached to the camera streams

Use:

```bash
adb shell "grep -Rin 'alpamayod connected\|alpamayod using' /data/log 2>/dev/null | tail -20"
```

Wanted log lines:

- `alpamayod connected road stream: ...`
- `alpamayod connected wideRoad stream: ...`
- `alpamayod using remote-server provider`

Interpretation:

- `road` + `wideRoad` connected means the c3x is seeing the two required camera feeds
- `remote-server provider` means it is attempting real PC inference, not stock mirroring

### 2. Verify `semanticPlan` is publishing live from the c3x

Use the c3x's venv-backed interpreter:

```bash
adb shell "cd /data/openpilot && PYTHONPATH=/data/openpilot /usr/local/venv/bin/python selfdrive/debug/dump.py semanticPlan --values semanticPlan.source,semanticPlan.status,semanticPlan.consecutiveValid,semanticPlan.generationExecutionTime,semanticPlan.age,semanticPlan.desiredCurvature,semanticPlan.desiredAcceleration"
```

Wanted fields:

- `semanticPlan.source = remoteServer`
- `semanticPlan.status = valid`
- `semanticPlan.consecutiveValid` increases above `0`
- `semanticPlan.generationExecutionTime` is nonzero
- `semanticPlan.age` stays low

Interpretation:

- this is the best live proof that frames were captured, sent to the PC, Alpamayo ran, and the response came back successfully

Bad meanings:

- `source = stockMirror`: not using remote inference
- `status = unavailable`: no usable semantic plan returned
- `status = stale`: using cached prior, not fresh inference

### 3. Verify fusion is being accepted by the active model daemon

Use:

```bash
adb shell "tail -F /data/log/swaglog.* | grep -E 'semantic plan fused|alpamayod'"
```

Wanted line:

```text
semantic plan fused source=2 alpha=1.00 age=... confidence=... consistency=...
```

Interpretation:

- this proves the active model daemon accepted `semanticPlan` and fused it into the plan output

This log line is emitted by the patched model daemons when fusion is actually applied.

### 4. Optional: watch final `modelV2.action`

Use:

```bash
adb shell "cd /data/openpilot && PYTHONPATH=/data/openpilot /usr/local/venv/bin/python selfdrive/debug/dump.py modelV2 --values modelV2.action.desiredCurvature,modelV2.action.desiredAcceleration,modelV2.action.shouldStop"
```

Interpretation:

- compare behavior with Alpamayo on vs off
- if `semanticPlan` is valid and fusion logs appear, changes here indicate the fused plan is affecting openpilot output

## Meaning of `semanticPlan` fields

Relevant schema fields:

- `source`
  - `none = 0`
  - `stockMirror = 1`
  - `remoteServer = 2`
  - `localEgpu = 3`
- `status`
  - `unavailable = 0`
  - `valid = 1`
  - `stale = 2`
  - `error = 3`

Interpretation target for this PC-sidecar setup:

- `source = remoteServer`
- `status = valid`

## Important current blind spots

The current code does not log every request on the PC server, so the cleanest proof is from the c3x-side `semanticPlan` stream and the fusion logs, not from HTTP request prints on the PC.

The server intentionally suppresses normal HTTP request logging.

## Minimal restart sequence before in-car test

1. Boot PC
2. Start the Alpamayo server with the command above
3. Connect the c3x horizontal USB-C port to the PC
4. Run:

```bash
adb reverse tcp:8081 tcp:8081
```

5. Reboot the c3x or launch openpilot normally
6. Do not run `uiview.py`
7. Put the device into onroad state
8. Run the verification commands above

## Current working assumption

The remaining uncertainty is not the PC model load or the param plumbing. The remaining uncertainty is the first clean onroad proof that:

- camera frames reach `alpamayod`
- real Alpamayo inference returns `semanticPlan`
- the active sunnypilot model runner fuses it on the c3x
