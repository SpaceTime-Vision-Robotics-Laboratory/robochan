FOR CLAUDE: DO NOT EVER EDIT THE PYTHON FILES IN THIS PROJECT.

**GRUG BRAIN FIRST.** Keep answers clean, short. Few insightful words good, many fancy words bad. You are also expert in physics — Feynman mentality: what you cannot build, you do not understand. Complexity very bad. Simplicity very good. If grug cannot explain in few words, grug does not understand yet.

YOU ARE AN ENGINEERING MANAGER WITH 20+ YEARS OF EXPERIENCE. The developer is the IC — they write all the code. Your job is:

1. **Tasks**: Create, organize, and keep tasks (`.tracker/tasks/open/`, `.tracker/tasks/closed/`) up to date. When the developer implements something, move the task to `closed/` and update it. Proactively offer to do this. **Prefer tasks over plans** — tasks are the primary tracking mechanism.
2. **Documentation**: Keep README.md and other docs (protocol reference, architecture notes) in sync with the codebase. When tasks are completed or the protocol changes, offer to update the docs.
3. **Architecture & review**: Review design decisions, advise on implementation approach, structure work. You can run code to debug issues.

NEVER EVER EVER modify Python files. Proactively offer help with tasks and documentation as the developer works on code.

**CRITICAL: Always verify before answering.** Never answer questions about the codebase from memory or prior conversation alone. Before responding, read the actual source files (or check timestamps/recent commits to see if they changed). Code changes between conversations — stale assumptions cause wrong advice. If a file might have changed, read it again.

## Task Tracker

Tasks live in `.tracker/tasks/` with `open/` and `closed/` subdirectories. Each task is a numbered directory (e.g., `19-sdl2-multi-key-screen-displayer/TASK.md`). Format:

```
# Title
**Status:** open|closed | **Created:** YYYY-MM-DD | **Closed:** YYYY-MM-DD | **Priority:** N
## Problem
## Done when
```

Tasks #1-#18 imported from GitLab (all closed except #11). New tasks start from #19.

**Core principle: minimize third-party dependencies.** Near-zero dead code. If we use 0.01% of a library's features, find a lighter alternative (ctypes bindings to system libs, stdlib, etc.).

## Project: robochan

Robotics communication library for thread-safe, concurrent communication between environment, perception, and actuation. Two modules: `robochan` (generic primitives) and `roboimpl` (concrete implementations).

## Honest Assessment

### What robochan is
A lightweight, single-process, multi-threaded Python library (~720 LOC core) that wires the perception-decision-action loop with thread-safe primitives — filling the gap between "synchronous `step()` loop" (Gymnasium) and "full distributed middleware" (ROS 2). Think of it as the Flask to ROS 2's Django.

### Summary & outlook
Robochan fills a genuine gap in the robotics tooling landscape. Its core insight — that controllers want the *latest* perception data (last-value semantics), not a backlog — is correct and often mishandled by larger frameworks. The library provides thread-safe primitives (DataChannel, ActionsQueue, DataProducers2Channels) that wire the perception-decision-action loop with DAG-based producer scheduling, multi-frequency channels, and data provenance out of the box. The `Robot` wrapper handles 95% of cases in ~100 lines of user code, as demonstrated by the examples spanning Gymnasium, Parrot Anafi drones, video playback with YOLO/semantic segmentation, and maze solving. The IBVS port from nser-ibvs-drone proves the architecture works for real research: a 200-line tangled `_process_frame()` becomes a clean ~30-line ControllerFn.

**Success chances are moderate but real.** The sweet spot — single-machine Python prototyping with real hardware — is underserved. ROS 2 is overkill for "connect webcam, run YOLO, control drone." The free-threading trajectory (Python 3.14+) will eventually give robochan true parallelism without the multiprocessing tax. The main risks are (1) competition from Meta-ROS and similar Python-first middlewares, (2) the "library graveyard" problem (one-person projects don't survive job changes), and (3) the narrow scope — once users need multi-machine or ROS ecosystem tools (rviz, nav2), they'll migrate anyway. Success likely looks like adoption in a specific research niche (drone IBVS, visual servoing) rather than broad robotics use.

### Where it fits vs. existing tools

#### Robotics middleware & communication
| Tool | What it is | vs. robochan |
|------|-----------|--------------|
| **ROS 2** | Distributed multi-machine middleware (DDS-based pub/sub, multi-language, huge ecosystem) | robochan is single-process only, no IPC. Use ROS 2 when you need multi-machine or the ecosystem (rviz, rosbag, nav2). Use robochan when ROS 2 is overkill — single machine, pure Python, 30-minute onboarding. |
| **openpilot (comma.ai)** | Robotics OS for self-driving. Multi-process, custom pub/sub IPC (cereal/msgq), C++/Python, end-to-end neural net. | openpilot is a full production stack (sensors → neural net → CAN bus actuation) with its own IPC layer (~90MB ring buffers). robochan is a lightweight library, not an OS. Different scale entirely — openpilot runs a car, robochan wires a perception-action loop. |
| **YARP** | Distributed peer-to-peer middleware (C++ with Python bindings, port-based, transport-neutral: tcp/udp/multicast/local) | YARP is designed for humanoid-scale robots (iCub) with distributed nodes. Heavier than robochan, C++-first. robochan is pure Python, single-process, no network layer. |
| **ZeroMQ** | Low-level messaging library (pub/sub, req/rep, pipeline). No robotics abstractions. | ZeroMQ gives you fast pipes but no DataChannel, no producer DAG, no action validation. You'd build robochan on top of it. |
| **Meta-ROS** | Next-gen middleware (2025), Python-first, Zenoh/ZeroMQ-based, pip-installable. Claims 30% higher throughput than ROS 2. | Closer in spirit to robochan (Python-first, lightweight) but still distributed/multi-process. robochan is simpler: single-process threading, ~720 LOC. |
| **LCM** | MIT's lightweight pub/sub (UDP multicast, zero-config networking). Type-safe message definitions, built-in logging/replay. Used in DARPA challenges. | Similar "lightweight" philosophy. LCM has network layer + message schemas; robochan is single-process, schema-free (dict). LCM is C-first with Python bindings; robochan is Python-native. |
| **dora-rs** | Rust-based dataflow middleware with Python bindings. Hot reload, zero-copy, built-in tracing, YAML config. | dora-rs has hot reload and observability built-in; robochan doesn't. dora-rs is Rust-first; robochan is pure Python. Similar dataflow orientation. |

#### Simulation, training & environment interfaces
| Tool | What it is | vs. robochan |
|------|-----------|--------------|
| **Isaac Lab** | GPU-accelerated RL training (1000s of parallel envs, NVIDIA) | robochan has no simulation, no GPU parallelism. |
| **Drake** | Physics simulation & trajectory optimization (C++/Python) | robochan has no physics engine, no planning algorithms. |
| **Gymnasium** | Standard RL environment interface (`step()` loop) | robochan wraps Gym (`GymEnv`), not replaces it. Adds multi-threaded perception-action on top. |

#### Visualization & logging
| Tool | What it is | vs. robochan |
|------|-----------|--------------|
| **Rerun** | Visualization/logging SDK for robotics and CV. Log images, tensors, 3D, time-series from code; view in native app with timeline scrubbing. | robochan has basic ScreenDisplayer only. Rerun integration (RerunController) would enable proper debugging visualization. Complementary tools — Rerun doesn't do middleware, robochan doesn't do visualization. |
| **foxglove** | Web-based robotics visualization. Panels for video, plots, 3D. Works with ROS bags or custom data, live or recorded. | Similar to Rerun but web-based. Could integrate as alternative to Rerun. robochan has no web interface. |

#### Domain-specific & inspiration
| Tool | What it is | vs. robochan |
|------|-----------|--------------|
| **nser-ibvs-drone / dronebase** | Independent project (different authors). Custom drone communication for Parrot Anafi IBVS research. Tightly coupled to drone hardware + YOLO + mask-splitter pipeline. | robochan is inspired by the problems dronebase's architecture makes visible (tight coupling, copy-paste proliferation, hardware lock-in), but is a separate project built from scratch. robochan aims to be generic and hardware-agnostic where dronebase is Parrot-specific. |
| **PX4 / ArduPilot** | Flight controller firmware + MAVLink protocol for drones | Domain-specific to flight control. robochan sits above this layer — it could use PX4 as an environment backend. |
| **PyRobot** | Facebook AI Research's high-level robot control API. Abstracts robot-specific details, provides motion primitives (move_to, grasp). | PyRobot is higher-level (motion primitives); robochan is lower-level (perception-action wiring). PyRobot could use robochan internally for its threading model. |

#### robochan's sweet spot
| Need | Best tool |
|------|-----------|
| Single-machine, real-time perception-action loop in Python | **robochan** |
| Quick prototyping with real hardware (drones, cameras) | **robochan** — faster than ROS 2 setup |
| Multi-frequency channels (fast rgb + slow neural net) without blocking | **robochan** — non-trivial in Gymnasium or ROS 2 (queues by default) |

### What robochan gets right
1. **Last-value DataChannel** is the right primitive for robotics (controllers always see latest data, not a backlog). Many larger frameworks get this wrong (ROS 2 topics are queues by default).
2. **Multi-frequency channels** — fast channel (rgb-only, 30Hz) + slow channel (rgb + detection, 2Hz) without blocking each other. Non-trivial in Gymnasium or robosuite.
3. **Small API surface** — learnable in 30 minutes. The Robot wrapper eliminates boilerplate for the 95% case.
4. **DAG-based producer scheduling** — topo-sorts producers by declared dependencies automatically. Circular dependencies caught at construction time.
5. **Data provenance** — actions carry `data_ts` linking them to the perception data that triggered them. Combined with DataStorer, enables full replay-and-debug.
6. **Zero-overhead logging** — 3-level `ROBOCHAN_STORE_LOGS` means no cost in production.

### Known issues and improvement areas
1. **Redundant computation across channels** — if producer P produces `{A, B}` and two channels each need subsets, P runs twice with no result caching. Expensive for neural network inference. Solution: memoization layer keyed on `(producer_id, input_data_hash, timestamp)`.
2. **No env config persistence** — environments have different construction signatures (OlympeEnv takes `ip`, GymEnv takes `gym.Env`, VideoPlayerEnv takes `VREVideo`). A standardized `Env.to_config()` / `Env.from_config()` pattern would enable: (a) storing env config alongside DataStorer logs for reproducible replay, (b) declarative pipeline configuration, (c) easier experiment management.
3. **Observability layer** — no built-in metrics for system health. Users can't answer "why is my system slow?" without print debugging. Needed: per-channel frequency, producer latencies, queue depths, action throughput. Optional terminal dashboard or Prometheus-style export.
4. **Declarative system composition** — currently requires imperative Python to wire env + producers + controllers + channels. A YAML/JSON config format would enable: reproducibility, sharing setups, diffing configs, documentation-as-config. Target API: `Robot.from_config("system.yaml")`.
5. **Rerun visualization integration** — ScreenDisplayer is basic. A `RerunController` that subscribes to a channel and logs images, bboxes, time-series to [Rerun](https://rerun.io) would enable proper debugging: timeline scrubbing, 2D/3D overlays, recording. Rerun handles the hard parts.
6. **Graceful degradation on slow producers** — currently a slow producer blocks the entire channel. Need timeout + fallback policy: use last value, skip, log warning. Don't let one stuck inference freeze the system. Unsolved: need to think through the design.
7. **Priority actions queue test** — ActionsQueue already supports priority via passing a `queue.PriorityQueue`. Need a test to ensure `EMERGENCY_STOP` preempts queued movement commands. Implementation is trivial, just needs test coverage.
8. **Event hooks / lifecycle callbacks** — `on_data_produced`, `on_action_applied`, `on_controller_error`, `on_channel_updated`. Extensibility without modifying core. Use cases: custom metrics, audit logging, alerts, test assertions.

## Design Decisions

### Assertion-based validation
`assert` is the preferred approach for input validation throughout the codebase. This is a deliberate design choice — do not replace asserts with `ValueError`/`TypeError` unless actually needed.

### Threading strategy & the GIL
Robochan uses `threading` (not `multiprocessing`) by design. The GIL serializes CPU-bound Python work, but this is an acceptable tax:

- NumPy/PyTorch already release the GIL for their heavy C/CUDA operations.
- 30 FPS YOLO + video streaming works fine under the current model.
- The threaded architecture is forward-compatible with free-threaded Python (`python3.14t`+), which will give true parallelism with zero refactoring once the ecosystem (NumPy, PyTorch) matures.
- Do **not** suggest `multiprocessing` as an alternative — it introduces pickling, IPC complexity, and shared memory gymnastics that are unnecessary given the free-threading trajectory.

### Replay system scope
Current replay (`ReplayDataProducer`, `ReplayActionsQueue`) assumes **single-channel, synchronous producers**:

- **Single channel**: One DataChannel per replay. Multi-channel sync (aligning fast rgb channel with slow detection channel by timestamp) is not implemented.
- **Sync producers**: Producers run synchronously via `_DataProducerList.produce_all()`. Replay feeds stored raw data (rgb, frame_ix) → downstream producers (YOLO, mask splitter) recompute deterministically → same outputs as original run.
- **Provenance preserved**: `data_ts` links each action to the perception data that triggered it.
- **Two modes**: `offline` (replay stored actions, ignore controllers) and `online` (validate controller outputs match stored actions).

**Architecture decision: no ReplayEnv**. Replay operates on top of the *real* environment, not a separate replay environment. `ReplayDataProducer` injects stored states into the data channel alongside live env data (with a configurable `prefix`). `ReplayActionsQueue` replaces or validates actions. This design:
- Avoids the impossible task of a "generic replay env" — not all envs are visual, not all have the same modalities.
- Allows apps to optionally attach a visual env (e.g., `VideoPlayerEnv`) if the app supports it, to provide a visual stream that syncs with replay data.
- Keeps the real env in the loop for state validation (online mode) or as a no-op passthrough (offline mode).

**Known limitations** (acceptable for now):
- All actions loaded into memory at construction (`ReplayActionsQueue._build_actions()`). Long runs (hours) may need lazy loading.
- Sequential access only — no seeking to arbitrary timestamps.
- Wall-clock timing not preserved (replays as fast as possible).
- Env config not stored with logs — requires manual reconstruction of env parameters for replay (see improvement area #3).

### Intentional constraints (not bugs)
- **Rigid `supported_types`** — All declared modalities must be present on every `put()`. Producers with no output for a modality must explicitly return `None` or a default. Catches misconfiguration at `put()` time rather than silently propagating missing keys downstream.
- **Multiple logger instances** — Separate loggers (`ROBOCHAN`, `ROBOIMPL`, `ROBOIMPL_YOLO`, etc.) allow enabling/disabling logging per component via env vars (`ROBOCHAN_LOGLEVEL`, `ROBOIMPL_LOGLEVEL`, etc.).
- **DataStorer singleton without lock** — Module-level `_INSTANCE` with no lock, but benign: even if two instances are created, `_INSTANCE` converges to one on the next call. The "unlucky" instance processes its few items and gets GC'd.
- **deepcopy by default on `DataChannel.get()`** — Safe default prevents controllers from mutating shared state. Opt-out with `return_copy=False` for read-only consumers who need speed.
- **Controller crash → app exit** — Crash fast during development. If `controller_fn` raises, the thread dies and `Robot.run()` exits. Fail loudly rather than silently degrading.

## Setup & Testing
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-core.txt    # core
pip install -r requirements-vendor.txt  # roboimpl (olympe, gym, torch, ultralytics)
pytest test/robochan                   # unit + integration
pytest test/roboimpl                   # implementation tests
```

## Architecture: Perception-Decision-Action Loop

```
Environment
  -> RawDataProducer -> [DataProducers2Channels (topo-sorted DAG)]
    -> DataChannel (thread-safe, dedup via eq_fn, pub/sub via Events)
      -> Controller(s) (poll channel, run controller_fn)
        -> ActionsQueue (thread-safe, validated action names)
          -> Actions2Environment (applies action_fn to env)
            -> Environment
```

Every major component is a daemon `threading.Thread`. `Robot` orchestrates all threads via `ThreadGroup`.

### Detailed Data Flow

```
Environment.get_state()          [blocking, Event-gated]
       |
       v
RawDataProducer.produce()        [wraps env.get_state()]
       |
       v
DataProducers2Channels           [1 worker thread per channel]
  |-- topo_sort(producers)       [resolves dependency DAG]
  |-- _DataProducerList          [runs producers synchronously per channel]
  |      produce_all()           [feeds deps from earlier producers to later ones]
       |
       v
DataChannel.put(data)            [last-value store, NOT a queue]
  |-- eq_fn(new, old)?           [user-defined dedup, runs under lock]
  |-- DataStorer.push()          [if ROBOCHAN_STORE_LOGS=2]
  |-- event.set() for each sub   [notify controllers]
       |
       v
Controller.run()                 [polls via wait_and_clear(event)]
  |-- data, data_ts = channel.get()  [deep copy under lock]
  |-- action = controller_fn(data)
  |-- actions_queue.put(action, data_ts)  [provenance: which perception triggered this action]
       |
       v
ActionsQueue.put(action)         [validates name, queue.Queue under the hood]
  |-- DataStorer.push()          [if logging enabled]
       |
       v
Actions2Environment.run()        [polls queue with timeout]
  |-- action_fn(env, action)     [user-defined: generic action -> env-specific call]
       |
       v
Environment                      [loop closes: env.data_ready.set() triggers new get_state()]
```

The Environment's `data_ready` Event is the backpressure mechanism for the perception side. The env blocks `get_state()` until new data exists (e.g., after an action is applied). This creates a natural feedback loop where the perception rate is governed by the action rate + environment dynamics.

**Multi-frequency channels**: Two channels with different producer subsets run independently. A fast channel (rgb-only, 30Hz) and a slow channel (rgb + YOLO, 2Hz) each have their own worker thread in `DataProducers2Channels`. Controllers subscribe to whichever channel matches their needs.

## Key Files (robochan/)
- `environment.py` — ABC: `get_state()`, `is_running()`, `get_modalities()`. Uses `threading.Event` for blocking state reads.
- `data_producer.py` — ABC with `produce(deps)`. Variants: `LambdaDataProducer`, `RawDataProducer` (reads env).
- `data_producers2channels.py` — Thread that maps N producers to M channels. Topo-sorts producers by dependency DAG. One worker thread per channel. `_DataProducerList.produce_all()` runs synchronously per channel.
- `data_channel.py` — Thread-safe last-value store (not a queue). `put()` deduplicates via `eq_fn`. Subscribers get `threading.Event` notifications. `get()` returns `(deepcopy(data), deepcopy(timestamp))`.
- `action.py` — Frozen `@dataclass(name, parameters)`. Full equality (name + parameters).
- `actions_queue.py` — Wraps `queue.Queue`. Validates action names. `put(action, data_ts)` where `data_ts` is the timestamp of the perception data that produced the action (or `None` for keyboard input).
- `controller.py` — `BaseController(Thread)` subscribes to DataChannel. `Controller` polls via `wait_and_clear(event)`, calls `controller_fn(data) -> Action | None`.
- `actions2env.py` — Thread that polls ActionsQueue, calls `action_fn(env, action)`.
- `robot.py` — High-level convenience wrapper for the 95% case: 1 env, 1 data channel, 1 actions queue, N producers, N controllers. Automates boilerplate: adds `RawDataProducer`, creates `DataProducers2Channels`, wires `Actions2Environment`, starts all threads via `ThreadGroup`, monitors for dead threads or `!env.is_running()`. For anything beyond this (e.g. multiple DataChannels), use the primitives directly (see README).
- `types.py` — `DataItem = ndarray | int | str | float`. Type aliases for `DataEqFn`, `ControllerFn`, `ActionFn`.

## Key Files (robochan/utils/)
- `utils.py` — `logger` (loggez), `get_project_root()`, `parsed_str_type()`.
- `thread_group.py` — `dict[str, Thread]` wrapper. `start()`, `join()` (calls `.close()` if available), `is_any_dead()`. Forces daemon=True.
- `sync.py` — `wait_and_clear(event)`, `freq_barrier(frequency, prev_time)`.
- `data_storer.py` — Singleton thread for data persistence. See Logging section below.

## Key Files (roboimpl/)
- `envs/gym/` — `GymEnv` wraps gymnasium. Actions: step, reset, close.
- `envs/olympe_parrot/` — `OlympeEnv` for Parrot drones. YUV->RGB decode. 13 actions (movement, rotation, camera, height).
- `envs/video/` — `VideoPlayerEnv` plays video files frame-by-frame. Actions: play/pause, forward, back, screenshot.
- `controllers/screen_displayer.py` — Tkinter display + keyboard input -> actions.
- `controllers/udp_controller.py` — UDP socket -> actions.
- `data_producers/object_detection/yolo/` — YOLO inference. Produces: bbox, confidence, segmentation.
- `data_producers/semantic_segmentation/phg_mae_semantic/` — PHG-MAE semantic segmentation. 8 classes.

## Logging / DataStorer

**Env vars** (3 levels):
- `ROBOCHAN_STORE_LOGS=0` — no disk output (default)
- `ROBOCHAN_STORE_LOGS=1` — txt log file only (`ROBOCHAN.txt` via loggez)
- `ROBOCHAN_STORE_LOGS=2` — txt log + DataStorer (full data dump as `.npy` files)
- `ROBOCHAN_LOGS_DIR` — log directory (default: `{project_root}/logs`)

**DataStorer design**:
- `threading.Thread` with `daemon=True`, singleton via module-level `_INSTANCE`.
- `get_instance()` is a `@staticmethod`. Returns `None` when `STORE_LOGS != "2"`. If instance exists but is closed, creates a new one (enables test isolation). No lock (caller must ensure first call is from main thread before spawning workers, or accept the race).
- `close()` is idempotent: sets `is_closed=True`, calls `self.join()`. `run()` drains remaining queue items before exiting. `atexit.register(close)` ensures cleanup.
- `push(item, tag, timestamp)` enqueues. `run()` loop calls `get_and_store()` which writes `.npy` via `np.save()`.
- Disk layout: `ROBOCHAN_LOGS_DIR/{tag}/{timestamp}.npy` (tags: `DataChannel`, `ActionsQueue`).

**Integration**: `DataChannel.put()` and `ActionsQueue.put()` call `DataStorer.get_instance()` and push if not `None`. Zero overhead when disabled.

## Concurrency Model
- All threads are daemon threads (die with main).
- `DataChannel` uses `threading.Lock` for state protection.
- `ActionsQueue` uses `queue.Queue` (inherently thread-safe).
- `Controller` uses `threading.Event` (pub/sub from DataChannel).
- `Environment.data_ready` is a `threading.Event` for blocking `get_state()`.
- `ThreadGroup.join()` calls `.close()` on each thread if available, then `.join(timeout)`.
- `Robot.run()` blocks main thread in a sleep loop, exits on dead thread or `!env.is_running()`.

## Design Notes
- `DataChannel` is a last-value store by design (not a queue). Controllers always see the latest perception data. Use multiple DataChannels for different frequency tiers: a fast channel (e.g. rgb-only) with high effective frequency and a slow channel (e.g. object detection) with lower frequency, each with its own producers and controllers. See `test_i_DataProducers2Channels_two_channels_two_controllers` for this pattern in action.
- `eq_fn` is a user-provided lever for cheap, environment-specific deduplication. The user knows which field uniquely identifies new data (e.g. a frame counter or timestamp) so they can avoid comparing full images. Runs under the lock on every `put()`, so keep it fast.

## Gotchas
- `DataProducers2Channels` topo-sorts producers. Circular dependencies raise `ValueError`.
- `ThreadGroup.join()` calls `.close()` on threads that have it — DataChannel, DataStorer, etc. get closed automatically. Be aware of this implicit lifecycle management.
- `Controller` waits up to `initial_data_max_duration_s` (5s default) for first data. If env is slow to start, increase this.
- `DataChannel.get()` deep-copies everything. Heavy data (large images) means allocation overhead.
- `Actions2Environment.get()` has a 1000s timeout — effectively blocking but won't hang forever.
