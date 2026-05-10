# Robochan - Robotics communication library

Robotics communication library between common robotics parts: environment (real or simulated), robot perception modules and robot actuators. The library is built in a generic way, and it can be used for pure Reinforcement Learning applications as well (i.e. we wrap `GymEnv` natively), as well as interacting with real world SDKs (i.e. parrot) or simulated environments (i.e. olympe/unreal).

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────┐     ┌───────────────┐     ┌──────────────┐
│ Environment │────▶│ DataProducer(s) │────▶│ DataChannel │────▶│ Controller(s) │────▶│ ActionsQueue │
│  (sensors)  │     │  (algos, nns)   │     │ (last-value)│     │   (decide)    │     │   (buffer)   │
└─────────────┘     └─────────────────┘     └─────────────┘     └───────────────┘     └──────────────┘
       ▲                                                                                       │
       │                                Actions2Environment                                    │
       └───────────────────────────────────(execute)───────────────────────────────────────────┘
```

The library is built around 2 modules:
- `robochan` Generic primitives for thread-safe, concurrent and hopefully performant communication
- `roboimpl` Environment and robots specific implementations (e.g. `olympe-parrot`, `gym`, `ffmpeg`, `robosim` etc.)

## Installation and testing

```
python -m venv .venv # python 3.11 or above
source .venv/bin/activate
pip install -r requirements-core.txt # only the `robochan` stuff
pytest test/robochan
pip install -r requirements-vendor.txt # all the environments supported in `robobimpl` like olympe from parrot or gym
pytest test/roboimpl
bash test/e2e/run_all.sh
```

## Running or making your own robot controllers

### First steps: Running the provided examples

The 'hello world' runnable examples are:
- [hello-world-controller](./examples/basic/hello-world-controller/main.py)
- [hello-world-webcam](./examples/basic/hello-world-webcam/main.py).
- [video-player + neural-network](./examples/video/2-video-player-with-neural-network-data-producers/README.md)
  - In the readme you can see a nice yolo + public webcam example, as well as how to download some standard nn checkpoints easily.

### Creating your controllers: Using the `Robot` high-level wrapper

Every `main` script will contain the following logic:

```python
def main():
    """main fn"""
    drone_env = XXXDrone(ip="192.168.0.101") # XXX = specific real or simulated drone like Olympe
    drone_env.connect() # establish connection to the drone before any callbacks
    actions_queue = ActionsQueue(action_names=["a1", "a2", ...]) # defines the generic actions. Actions can have parameters via Action("a1", (param, ...))
    data_channel = DataChannel(supported_types=["rgb", "pose", ...], eq_fn=lambda a, b: a["rgb"] == b["rgb"]) # defines the data types and how to compare equality (i.e. drone produced same frame twice)

    # actions_fn converts generic "a1", "a2" actions to raw drone-specific action e.g. parrot.piloting(...)
    robot = Robot(env=drone_env, data_channel=data_channel, actions_queue=actions_queue,
                  actions_fn=lambda env, actions: [env.generic_to_raw(action) for action in actions])
    # Define the data producers. The 'raw' one is added by default (env to raw data). Controllers receive the latest available data.
    robot.add_data_producer(SemanticDataProducer(ckpt_path=path_to_model, ...))
    # Define the controllers: the logic of the robot to act in the environment
    robot.add_controller(KeyboardController(key_to_action={"space": Act("a1"), "w": Act("a2")})) # maunal control from keyboard
    robot.add_controller(ScreenDisplayer(data_channel, actions_queue, name="Screen displayer")) # UI display
    robot.add_controller(lambda data, actions_queue: actions_queue.put(Act(random.choice(["a1", "a2"]))), name="Trajectory planner") # controller algorithmic logic
    # Run the main loop which starts and monitors the threads behind the scenes (data producers, controllers, env communication etc.)
    robot.run()

    drone_env.disconnect() # disconnect from the drone.
    data_channel.close() # close the data channel as well which also waits for logs (if enabled) to be written to disk.

if __name__ == "__main__":
    main()
```

### Relevant environment variables

We have a few environment variables, moslty that control logging:
```bash
ROBOCHAN_LOGLEVEL=0/1/2/3 # 0 = disabled, 1 = info, 2 = debug, 3 = trace
ROBOIMPL_LOGLEVEL=0/1/2/3 # 0 = disabled, 1 = info, 2 = debug, 3 = trace
ROBOCHAN_LOGS_DIR=/path/to/logsdir # if not set, will use the 'robochan_repo_root/logs'
ROBOCHAN_STORE_LOGS=0/1/2 # 0 nothing, 1 txt only, 2 DataStorer (defaults to 1)
ROBOCHAN_DATA_STORER_QUEUE_SIZE=100 # max items buffered in DataStorer queue before backpressure
ROBOIMPL_SCREEN_DISPLAYER_BACKEND=tkinter/sdl2 # For ScreenDisplayer controller. Defaults to 'sdl2'
ROBOIMPL_KEYBOARD_CONTROLLER_FREQ=30 # keyboard poll frequency (Hz) for KeyboardController
```
Notes on `ROBOCHAN_STORE_LOGS`: if set to 0, will not store anything on disk, if set to 1, will store only logger (.txt), if set to 2, will also store all the data that passes through the system (i.e. DataChannel and ActionsQueue). This may consume GBs of disk! Use with caution.

Additionally, you can use the [vizualization tool](tools/logsviz/) to see (in real time or after the fact) the interaction between the data and controller's action of your robot. For now, it only supports tracking data to action.


The two 'core' components of any robotics application are: the *data channel* and the *actions queue*. The data consumers interact with the drone (or any robot) to get raw data and write them to the data channel, while the data consumers interact with the channel and always have access to the latest data. Some data consumers are also action products and write to the actions queue. Then, the actions consumer reads one action at a time from the actions queue and sends raw actions to the drone.

The usual flow is like this:
```
┌─────────────┐     ┌──────────────────────────────────────────────────────────────────────┐
│ Environment │────▶│                   DataProducers2Channels (topo-DAG)                  ├────────┐
│   (robot)   │     │                                                                      │        │
└─────────────┘     │   ┌───────┐    ┌──────────┐    ┌───────┐    ┌─────────┐              │        │
       ▲            │   │  raw  │───▶│ semantic │───▶│ depth │───▶│ normals │              │        │
       │            │   └───┬───┘    └──────────┘    └───────┘    └─────────┘              │        │
       │            │       │                                                              │        │
       │            │       │        ┌──────┐                                              │        ▼
       │            │       └───────▶│ pose │                                              │  ┌──────────────┐
       │            │                └──────┘                                              │  │ DataChannel  │
       │            └──────────────────────────────────────────────────────────────────────┘  │ (last-value) │
       │                                                                                      └──────────────┘
       │                                 ┌────────────────────────────────────────────┐         │
       │                                 │              Controllers                   │         |
       │         ┌──────────────┐        │ ┌─────────┐ ┌─────────┐ ┌────────────┐     │         |
       └─────────┤ ActionsQueue │◀───────┤ │ Ctrl 1  │ │ Ctrl 2  │ │  Ctrl N    │     │◀────────┘
                 │ LIFT,MOVE... │        │ │(display)│ │(planner)│ │  (safety)  │     │
                 └──────────────┘        │ └─────────┘ └─────────┘ └────────────┘     │
          Actions2Environment (action_fn)└────────────────────────────────────────────┘
```


### Creating your controllers: Using the low-level primitives defined by the library

The `Robot` class above is just a nice wrapper on top of the low-level machinery. We could replace it completely for more control (i.e. >1 data channels if we want) like this:

```python
def main():
    """main fn"""
    drone_env = XXXDrone(ip="192.168.0.101") # XXX = specific real or simulated drone like Olympe
    drone_env.connect() # establish connection to the drone before any callbacks
    actions_queue = ActionsQueue(action_names=["a1", "a2", ...], queue=Queue()) # defines the generic actions and the queue type.
    data_channel = DataChannel(supported_types=["rgb", "pose", ...], eq_fn=lambda a, b: a["rgb"] == b["rgb"]) # defines the data types and how to compare equality (i.e. drone produced same frame twice)

    # define the data producers.
    raw_data = RawDataProducer(drone_env) # populates the data channel with RGB & pose from drone (raw data)
    semantic_data_producer = SemanticdataProducer(ckpt_path=path_to_model, ...)
    data_producers = DataProducers2Channels([drone2data, semantic_data_producer, ...], [channel, ...]) # data structure for all data
    # define the controllers (only screen displayer + keyboard controls here). Actions can have parameters via Action("a1", (param1, ...)).
    keyboard_controller = KeyboardController(key_to_action={"space": Action("a1", parameters=()), "w": Action("a2")})
    screen_displayer = ScreenDisplayer(data_channel, actions_queue) # data consumer + actions producer (keyboard)
    # action->drone converts a generic action to an actual drone action
    def XXXactions_fn(env: XXXDrone, actions: list[Action]) -> bool:
        for action in actions:
            env.generic_to_raw(action) # convert generic "a1", "a2" to raw drone-specific action
        return True # false if any of it failed for logging
    actions2nev = Actions2Environment(drone_env, actions_queue, action_fn=XXXactions_fn)

    threads = ThreadGroup({ # simple dict[str, Thread] wrapper to manage all of them at once.
        "Drone -> Data": data_producers,
        "Screen displayer": screen_displayer,
        "Keyboard controller": keyboard_controller,
        "Actions -> Drone": actions2nev,
    }).start()

    while not threads.is_any_dead(): # wait for any of them to die or drone to disconnect
        time.sleep(1) # important to not throttle everything with this main thread

    drone_env.disconnect() # disconnect from the drone.
    status = threads.join(timeout=1) # stop all the threads.
    data_channel.close() # close the data channel as well which also waits for logs (if enabled) to be written to disk.
    for k, v in status.items(): # join() returns a dict[str, ThreadStatus] allowing us to see exceptions and tracebacks
        if v.exception is not None:
            print(v.exception)

if __name__ == "__main__":
    main()
```
