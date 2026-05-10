# logsviz

<font color="red"> NOTE: VIBE CODED </font>

Interactive timeline visualization for robochan `DataChannel` and `ActionsQueue` logs.

## Usage

```bash
python viz.py -d /path/to/logs/2026-02-14T12:43:05
# logsviz running at http://localhost:5555
```

The `-d` directory should be a session folder containing `DataChannel/` and/or `ActionsQueue/` subdirectories with `.npy` files (produced by `DataStorer` when `ROBOCHAN_STORE_LOGS=2`).

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `-d`, `--dir` | *(required)* | Path to the logs session directory |
| `-p`, `--port` | `5555` | HTTP server port |

## What it shows

Two horizontal timeline bands:

- **DataChannel** (blue dots) — each dot is one perception data snapshot
- **ActionsQueue** (orange dots) — each dot is one action that was enqueued

Dashed lines connect actions to the perception data that triggered them (via `data_ts`). Hovering a dot highlights its connections and shows a tooltip with timestamp, keys, action name/params, etc.

## Interaction

- **Scroll** to zoom in/out (centered on cursor)
- **Drag** to pan the timeline
- **Double-click** to reset the view to fit all data

## Live updates

The UI polls the server every 2 seconds. Only new entries (since the last fetch) are transferred — the client merges them incrementally. If the server's log directory changes (e.g. restarted with a different `-d`), the client detects the session change and resets automatically.

## File structure

```
tools/logsviz/
  viz.py       — Python HTTP server (reads .npy files, serves JSON API)
  index.html   — Single-page frontend (canvas rendering, no dependencies)
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /` | Serves `index.html` |
| `GET /api/data` | Returns all log entries as JSON |
| `GET /api/data?after=<timestamp>` | Returns only entries with `timestamp > after` (incremental) |

Response shape:
```json
{
  "session": "/absolute/path/to/logs/dir",
  "DataChannel": [
    {"timestamp": "2026-02-14T12:43:05.123456", "keys": ["rgb", "depth"]}
  ],
  "ActionsQueue": [
    {
      "timestamp": "2026-02-14T12:43:05.234567",
      "keys": ["action", "data_ts"],
      "action_name": "step",
      "action_params": {"velocity": "0.5"},
      "data_ts": "2026-02-14T12:43:05.123456"
    }
  ]
}
```
