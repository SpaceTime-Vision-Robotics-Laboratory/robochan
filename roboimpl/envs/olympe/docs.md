# Olympe Parrot Environment

robochan environment for Parrot drones via the [Olympe SDK](https://developer.parrot.com/docs/olympe/).

## Overview

`OlympeEnv` connects to a Parrot drone over Wi-Fi, streams video, and exposes drone state (gimbal, flying state, frame metadata) through the robochan `Environment` interface. `olympe_actions_fn` translates robochan `Action` objects into Olympe SDK calls.

Compatible drones: ANAFI, ANAFI Thermal, ANAFI USA, ANAFI AI.

## OlympeEnv

```python
from roboimpl.envs.olympe_parrot import OlympeEnv

env = OlympeEnv(ip="192.168.42.1", image_size=(480, 640))
```

### Constructor

| Parameter | Type | Description |
|-----------|------|-------------|
| `ip` | `str` | Drone IP address. Default for Parrot drones over Wi-Fi is `192.168.42.1`. |
| `image_size` | `tuple[int, int] \| None` | Optional `(height, width)` to resize frames. `None` keeps the original resolution. |

Connects to the drone and starts the video stream on construction. Asserts on failure.

### State (get_state)

Returns a dict with four modalities:

| Key | Type | Description |
|-----|------|-------------|
| `rgb` | `np.ndarray` | Current video frame as an RGB numpy array (HxWx3, uint8). Converted from the drone's YUV stream. Resized if `image_size` was set. |
| `metadata` | `dict` | Frame metadata: `time` (ISO 8601 timestamp), `drone` (telemetry from vmeta), `camera` (camera params from vmeta). |
| `gimbal` | `dict` | Gimbal orientation: `roll_absolute`, `pitch_absolute`, `yaw_absolute` (degrees). |
| `flying_state` | `str` | Current flight state name (e.g. `"landed"`, `"hovering"`, `"flying"`). From `FlyingStateChanged`. |

`get_state()` blocks until a new frame arrives (via `data_ready` event). On the first call, it waits up to 5 seconds for the stream to start.

### Lifecycle

- `is_running()` — `True` while the drone is connected and the stream is playing (`PdrawState.Playing`).
- `close()` — Disconnects from the drone. Unblocks any pending `get_state()` call.

### Logging

Set `OLYMPE_LOG_LEVEL` env var to control Olympe SDK log verbosity (e.g. `DEBUG`, `INFO`). Defaults to `CRITICAL` (silent).

## Actions

```python
from roboimpl.envs.olympe_parrot import olympe_actions_fn, OLYMPE_SUPPORTED_ACTIONS
```

`olympe_actions_fn(env, action)` is the `action_fn` callback for use with `Actions2Environment`. It maps robochan `Action` objects to Olympe SDK calls.

### Supported actions

#### Lifecycle actions (no parameters)

| Action | Olympe call | Effect |
|--------|-------------|--------|
| `DISCONNECT` | `drone.streaming.stop()` | Stops the video stream. |
| `LIFT` | `drone(TakeOff()).wait().success()` | Takeoff. Blocks until complete. |
| `LAND` | `drone(Landing()).wait().success()` | Landing. Blocks until complete. |

#### Movement actions (parameters: `(intensity, duration)`)

These call `drone.piloting(roll, pitch, yaw, gaz, duration)`. Each axis value is a percentage (-100 to 100). The command is held for `duration` seconds, then all axes return to zero (hover).

| Action | Arg mapping | Description |
|--------|------------|-------------|
| `FORWARD` | `pitch=+intensity` | Move forward. |
| `BACKWARD` | `pitch=-intensity` | Move backward. |
| `LEFT` | `roll=-intensity` | Strafe left. |
| `RIGHT` | `roll=+intensity` | Strafe right. |
| `ROTATE_LEFT` | `yaw=-intensity` | Rotate counter-clockwise. |
| `ROTATE_RIGHT` | `yaw=+intensity` | Rotate clockwise. |
| `INCREASE_HEIGHT` | `gaz=+intensity` | Ascend. |
| `DECREASE_HEIGHT` | `gaz=-intensity` | Descend. |

#### Gimbal actions (parameters: `(delta_pitch,)`)

| Action | Effect |
|--------|--------|
| `TILT_UP` | Increase gimbal pitch by `delta_pitch` degrees (absolute frame). |
| `TILT_DOWN` | Decrease gimbal pitch by `delta_pitch` degrees (absolute frame). |

Gimbal commands read the current pitch via `gimbal.attitude`, then set the new target as `current_pitch +/- delta_pitch`. Uses absolute pitch frame of reference; roll and yaw are fixed at 0.

---

## Olympe SDK Reference

Low-level documentation for the Parrot SDK primitives used by `OlympeEnv` and `olympe_actions_fn`.

### Drone class (olympe.Drone)

The top-level controller object. Created with `olympe.Drone(ip)`.

#### Connection

| Method | Returns | Description |
|--------|---------|-------------|
| `drone.connect(timeout=..., retry=1)` | `bool` | Establishes connection. `retry` = number of attempts. |
| `drone.disconnect(timeout=5)` | `bool` | Terminates connection. Blocks until complete or timeout. |
| `drone.connection_state()` | `bool` | Current connection status. |

#### Piloting

| Method | Returns | Description |
|--------|---------|-------------|
| `drone.piloting(roll, pitch, yaw, gaz, piloting_time)` | `bool` | Sends manual PCMD for `piloting_time` seconds. Non-blocking. All values [-100, 100]. |
| `drone.start_piloting()` | `bool` | Initialize the piloting interface. |
| `drone.stop_piloting()` | `bool` | Terminate the piloting interface. |

#### State & commands

| Method | Returns | Description |
|--------|---------|-------------|
| `drone.get_state(message)` | `OrderedDict` | Last received state for a given event message type. |
| `drone.check_state(message, *args, **kwds)` | `bool` | Check if a specific state has been reached. |
| `drone(expectations)` | expectation object | Send commands and monitor events via the Olympe DSL. Call `.wait()` then `.success()` to block and check result. |

#### Streaming

| Method | Description |
|--------|-------------|
| `drone.streaming.start()` | Start the video stream. |
| `drone.streaming.stop()` | Stop the video stream. |
| `drone.streaming.set_callbacks(raw_cb, start_cb, end_cb, flush_raw_cb)` | Register callbacks for stream events. `raw_cb` receives each decoded `VideoFrame`. |
| `drone.streaming.state` | Current stream state (`PdrawState` enum: `Playing`, `Closed`, etc.). |

### ardrone3.Piloting — Flight commands

From `olympe.messages.ardrone3.Piloting`. These are the ARSDK messages that `drone.piloting()` and `drone(...)` wrap.

#### PCMD (Pilot Command)

```python
from olympe.messages.ardrone3.Piloting import PCMD
```

The low-level piloting command. Sent by the SDK every **50ms** while active.

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `flag` | `u8` | 0 or 1 | Enables roll/pitch values. 0 = roll/pitch ignored. |
| `roll` | `i8` | [-100, 100] | Lateral tilt. Percentage of max pitch/roll setting (copters) or physical max roll (fixed wings). |
| `pitch` | `i8` | [-100, 100] | Longitudinal tilt. Percentage of max pitch/roll setting (copters) or physical max pitch (fixed wings). |
| `yaw` | `i8` | [-100, 100] | Yaw rotation speed. Percentage of max yaw speed. On fixed wings, >75% triggers circling. |
| `gaz` | `i8` | [-100, 100] | Vertical throttle. Percentage of max vertical speed (copters) or physical max throttle (fixed wings). |
| `timestampAndSeqNum` | `u32` | — | Low 24 bits = timestamp, high 8 bits = sequence number. Managed by the SDK. |

Triggers events: `SpeedChanged`, `AttitudeChanged`, `GpsLocationChanged`.

**Note:** Positive gaz during landing cancels the landing. The drone waits for PCMD=0 (hover) before starting a Return Home.

```
          pitch (+) = forward
               ^
               |
roll (-) <--- drone ---> roll (+)
  = left       |          = right
               v
          pitch (-) = backward

yaw (-) = rotate left     yaw (+) = rotate right
gaz (+) = ascend           gaz (-) = descend
```

#### TakeOff / Landing

```python
from olympe.messages.ardrone3.Piloting import TakeOff, Landing
```

| Command | Expected event | Notes |
|---------|----------------|-------|
| `TakeOff()` | `FlyingStateChanged(state="takingoff")` | Typical sequence: `landed` -> `motor_ramping` -> `takingoff` -> `hovering`. |
| `Landing()` | `FlyingStateChanged(state="landing")` | Positive gaz during landing cancels it. |

Both are sent via `drone(TakeOff()).wait().success()` to block until the expected state transition.

#### moveBy (relative displacement)

```python
from olympe.messages.ardrone3.Piloting import moveBy
```

Alternative to PCMD for precise relative movement.

| Parameter | Type | Unit | Description |
|-----------|------|------|-------------|
| `dX` | `float` | meters | Forward displacement (drone body frame). |
| `dY` | `float` | meters | Right displacement (drone body frame). |
| `dZ` | `float` | meters | Down displacement (drone body frame). |
| `dPsi` | `float` | radians | Heading rotation. |

Expected event: `moveByEnd`. Moves are relative to the current drone orientation.

### ardrone3.PilotingState — Flight state

```python
from olympe.messages.ardrone3.PilotingState import FlyingStateChanged
```

`drone.get_state(FlyingStateChanged)` returns `{"state": <enum>}`. The `.name` property gives the string.

| State | Value | Description |
|-------|-------|-------------|
| `landed` | 0 | On the ground, motors off. |
| `takingoff` | 1 | Takeoff in progress. |
| `hovering` | 2 | Stable in the air (copters). Circling (fixed wings). |
| `flying` | 3 | Actively moving. |
| `landing` | 4 | Landing in progress. |
| `emergency` | 5 | Emergency — motors cut. |
| `usertakeoff` | 6 | Waiting for user confirmation to take off. |
| `motor_ramping` | 7 | Motors spinning up before takeoff. |
| `emergency_landing` | 8 | Autopilot-initiated landing due to defective sensor(s). |

Typical state transitions:

```
landed -> motor_ramping -> takingoff -> hovering
hovering -> flying -> hovering  (movement commands)
hovering -> landing -> landed
* -> emergency  (any state, on critical failure)
* -> emergency_landing  (defective sensor detected)
```

### gimbal — Camera gimbal control

```python
from olympe.messages import gimbal
```

#### gimbal.set_target

Sets the gimbal orientation.

| Parameter | Type | Description |
|-----------|------|-------------|
| `gimbal_id` | `u8` | Gimbal identifier (0 for the main camera). |
| `control_mode` | enum | `"position"` (degrees) or `"velocity"` (signed ratio -1 to 1 of `max_speed`). |
| `yaw_frame_of_reference` | enum | `"none"` (don't change), `"relative"` (drone body), `"absolute"` (magnetic north, clockwise). |
| `yaw` | `float` | Yaw target. |
| `pitch_frame_of_reference` | enum | `"none"`, `"relative"` (drone body, + = towards top), `"absolute"` (horizon, + = towards sky). |
| `pitch` | `float` | Pitch target. |
| `roll_frame_of_reference` | enum | `"none"`, `"relative"`, `"absolute"`. |
| `roll` | `float` | Roll target. |

In `olympe_actions_fn`, we use `control_mode="position"`, `pitch_frame_of_reference="absolute"`, and set yaw/roll frames to `"none"` (unchanged).

#### gimbal.attitude (event)

`drone.get_state(gimbal.attitude)` returns a list of dicts (one per gimbal). Each dict contains:

| Field | Type | Description |
|-------|------|-------------|
| `gimbal_id` | `u8` | Gimbal identifier. |
| `yaw_relative`, `pitch_relative`, `roll_relative` | `float` | Orientation relative to drone body (degrees). |
| `yaw_absolute`, `pitch_absolute`, `roll_absolute` | `float` | Orientation in absolute frame (degrees). |
| `yaw_frame_of_reference`, `pitch_frame_of_reference`, `roll_frame_of_reference` | enum | Active frame of reference per axis. |

#### Other gimbal events

| Event | Description |
|-------|-------------|
| `gimbal.calibration_state` | Calibration status: `required`, `in_progress`, `ok`. |
| `gimbal.calibration_result` | Outcome: `success`, `failure`, `canceled`. |
| `gimbal.gimbal_capabilities` | Model and controllable axes. |
| `gimbal.absolute_attitude_bounds` | Min/max angles in absolute frame. |
| `gimbal.relative_attitude_bounds` | Min/max angles in relative frame. |
| `gimbal.max_speed` | Speed bounds and current limits (degrees/second). |
| `gimbal.stabilization_state` | Per-axis stabilization: active/inactive. |
| `gimbal.axis_lock_state` | Locked axis bitfield. |
| `gimbal.alert` | Error conditions. |

### Video streaming (pdraw)

The Olympe video pipeline uses **PDrAW** (Parrot Drones Awesome Video Viewer) under the hood.

#### Frame callback

```python
drone.streaming.set_callbacks(raw_cb=my_callback)
```

`raw_cb` receives an `olympe.VideoFrame` for each decoded frame. The frame provides:

| Method | Returns | Description |
|--------|---------|-------------|
| `yuv_frame.as_ndarray()` | `np.ndarray` | Raw YUV pixel data. |
| `yuv_frame.format()` | enum | Pixel format: `VDEF_I420` or `VDEF_NV12`. |
| `yuv_frame.vmeta()` | `(dict, dict)` | `[0]` = protobuf metadata, `[1]` = dict with `"drone"` (telemetry) and `"camera"` (camera params). |
| `yuv_frame.ref()` / `yuv_frame.unref()` | — | Reference counting. Must `ref()` before use and `unref()` when done. |

`OlympeEnv` converts YUV to RGB via OpenCV:
- `VDEF_I420` -> `cv2.COLOR_YUV2RGB_I420`
- `VDEF_NV12` -> `cv2.COLOR_YUV2RGB_NV12`

#### Stream states (PdrawState)

| State | Description |
|-------|-------------|
| `Playing` | Stream is active and delivering frames. |
| `Closed` | Stream is stopped. |

`OlympeEnv.is_running()` checks `drone.streaming.state == PdrawState.Playing`.

---

## SDK Internals & Architecture

How the Olympe SDK is built, where the code lives on disk, and what happens under the hood.

### Layer cake

```
olympe_actions_fn / OlympeEnv          <- robochan (our code)
         |
    drone.piloting()                   <- Python: olympe.arsdkng.controller (convenience method)
         |
    PilotingCommand + timer            <- Python: olympe.arsdkng.controller (state + 25ms timer)
         |
    _send_command_impl(PCMD, {...})    <- Python: olympe.arsdkng.cmd_itf (serializes to ARSDK msg)
         |
    ardrone3.Piloting.PCMD             <- Python: olympe.arsdkng.messages (generated from XML)
         |
    libarsdkctrl.so / libarsdk.so      <- C: native ARSDK libraries (compiled, in olympe_deps/)
         |
    network (UDP/TCP to drone)         <- Wire protocol to the drone firmware
```

### File locations (conda env: parrot)

All paths under `/home/mihai/libs/miniconda3/envs/parrot/lib/python3.12/site-packages/`:

| Path | What it is |
|------|------------|
| `olympe/` | Python SDK — the Olympe package |
| `olympe/arsdkng/controller.py` | `ControllerBase` class: `piloting()`, `start_piloting()`, connection management, piloting timer |
| `olympe/arsdkng/messages.py` | `ArsdkMessage` — generates Python message classes from XML definitions at import time |
| `olympe/arsdkng/cmd_itf.py` | Command interface — `_send_command_impl()`, event routing, expectation handling |
| `olympe/arsdkng/xml.py` | `ArsdkXml` — parses the ARSDK XML definitions via `arsdkparser` |
| `olympe/arsdkng/enums.py` | Enum classes generated from XML (e.g. `FlyingStateChanged_State`) |
| `olympe/arsdkng/expectations.py` | Expectation DSL — how `drone(TakeOff()).wait().success()` works |
| `olympe/video/` | PDrAW video pipeline (streaming, frame decoding) |
| `arsdk/xml/` | **ARSDK XML definitions** — the source of truth for all commands, events, and enums |
| `arsdk/xml/ardrone3.xml` | Defines all `ardrone3.*` commands: `Piloting.PCMD`, `TakeOff`, `Landing`, `moveBy`, `FlyingStateChanged`, etc. |
| `arsdk/xml/gimbal.xml` | Defines all `gimbal.*` commands: `set_target`, `attitude`, calibration, etc. |
| `arsdkparser.py` | XML parser that reads `arsdk/xml/*.xml` and builds the message/enum structures |
| `olympe_deps/` | Pre-compiled C shared libraries (the native ARSDK layer) |
| `olympe_deps/__init__.py` | `ctypes` bindings — auto-generated Python wrappers for the C structs and functions |
| `olympe_deps/libarsdkctrl.so` | ARSDK controller library — manages connection, discovery, command sending |
| `olympe_deps/libarsdk.so` | Core ARSDK library — message serialization/deserialization |
| `olympe_deps/libarsdkgen.so` | Generated ARSDK code (from XML, compiled to C) |
| `olympe_deps/libpdraw.so` | PDrAW — video stream decoding (H.264/H.265) |
| `olympe_deps/libpomp.so` | Event loop library used by ARSDK internally |

### How drone.piloting() works

Source: `olympe/arsdkng/controller.py`

1. `drone.piloting(roll, pitch, yaw, gaz, piloting_time)` calls `start_piloting()` (if not already started), then stores the values in a `PilotingCommand` object along with the current timestamp.

2. `start_piloting()` sets up a **timer that fires every 25ms** (with 100ms initial delay). Each tick calls `_piloting_timer_cb` -> `_send_piloting_command()`.

3. `_send_piloting_command()` checks if `piloting_time` has elapsed. If yes, it resets all axes to 0 (hover). Then it sends `ardrone3.Piloting.PCMD` with the current values via `_send_command_impl()`. The `flag` field is auto-set to 1 if roll or pitch is nonzero.

4. The PCMD is sent as a `NON_ACK` buffer (fire-and-forget UDP, no delivery confirmation). The 25ms timer ensures continuous transmission — the drone expects periodic commands and will hover/stop if they cease.

```python
# Simplified from controller.py:
class PilotingCommand:
    def update_piloting_command(self, roll, pitch, yaw, gaz, piloting_time):
        self.roll = roll          # stored, sent every 25ms
        self.pitch = pitch
        self.yaw = yaw
        self.gaz = gaz
        self.piloting_time = piloting_time
        self.initial_time = time.time()

    def set_default_piloting_command(self):
        self.roll = self.pitch = self.yaw = self.gaz = 0  # hover
        self.piloting_time = 0
```

Key insight: `drone.piloting()` is **non-blocking**. It sets the desired values and returns immediately. The background timer keeps sending PCMD packets at 25ms intervals until `piloting_time` elapses, then auto-resets to hover. This is why the drone doesn't just jerk once — it gets a sustained stream of identical commands.

### ARSDK XML: the source of truth

All commands, events, and enums are defined in XML files at `arsdk/xml/`. At import time, `olympe.arsdkng.messages` parses these via `arsdkparser` and dynamically generates Python classes. There is no hand-written Python for individual commands like `PCMD` or `TakeOff` — they're all generated from XML.

Example from `arsdk/xml/ardrone3.xml`:
```xml
<project name="ardrone3" id="1">
  <class name="Piloting" id="0">
    <cmd name="PCMD" id="2" buffer="NON_ACK">
      <arg name="flag" type="u8">...</arg>
      <arg name="roll" type="i8">...</arg>
      <arg name="pitch" type="i8">...</arg>
      <arg name="yaw" type="i8">...</arg>
      <arg name="gaz" type="i8">...</arg>
      <arg name="timestampAndSeqNum" type="u32">...</arg>
    </cmd>
  </class>
</project>
```

The `buffer="NON_ACK"` attribute means this command uses unreliable (UDP-like) transport — appropriate for high-frequency piloting commands where losing a single packet is fine (the next one arrives in 25ms). Commands like `TakeOff` and `Landing` use the default acknowledged buffer.

### Can you talk directly to ardrone3?

**Yes.** You can bypass `drone.piloting()` and send ARSDK messages directly:

```python
import olympe
from olympe.messages.ardrone3.Piloting import PCMD, TakeOff, moveBy
from olympe.messages.ardrone3.PilotingState import FlyingStateChanged

drone = olympe.Drone("192.168.42.1")
drone.connect()

# Direct ARSDK command (same as what drone.piloting() sends internally)
drone(PCMD(flag=1, roll=0, pitch=50, yaw=0, gaz=0, timestampAndSeqNum=0))

# But you'd need to send it repeatedly (every ~25-50ms) yourself,
# because the drone expects continuous PCMD packets.
# drone.piloting() handles this for you via its timer.

# For one-shot commands, direct ARSDK is cleaner:
drone(TakeOff()).wait().success()
drone(moveBy(dX=1.0, dY=0, dZ=0, dPsi=0)).wait().success()

# State queries work the same way:
state = drone.get_state(FlyingStateChanged)["state"]
```

The practical difference:
- **`drone.piloting()`** = convenience wrapper that handles the 25ms timer loop for you. Use for continuous movement.
- **`drone(PCMD(...))`** = single ARSDK message send. You'd need your own timer loop for sustained movement.
- **`drone(TakeOff())`** = direct ARSDK command with expectation handling. Already the cleanest way to send one-shot commands.

For anything beyond Olympe, you could also talk to the drone at the wire protocol level (UDP packets with ARSDK framing), but you'd need to reimplement connection, discovery, command serialization, and the video pipeline. The C libraries in `olympe_deps/` (`libarsdkctrl.so`, `libarsdk.so`) handle all of that.

---

Sources:
- [Olympe SDK documentation](https://developer.parrot.com/docs/olympe/)
- [ardrone3.Piloting and SpeedSettings](https://developer.parrot.com/docs/olympe/arsdkng_ardrone3_piloting.html)
- [Gimbal feature](https://developer.parrot.com/docs/olympe/arsdkng_gimbal.html)
- [Olympe API Reference](https://developer.parrot.com/docs/olympe/olympeapi.html)
- [Moving around - Waiting for hovering](https://developer.parrot.com/docs/olympe/userguide/basics/moving_around.html)
