# Rename project from robobase to robochan
**Status:** open | **Created:** 2026-05-10 | **Priority:** 2

## Problem
The project is being renamed from `robobase` to `robochan`. The repo directory is already renamed; the package name, module directory, env vars, and docs need to follow.

## Scope
- **Python module**: rename `robobase/` directory to `robochan/`; update all `import robobase` / `from robobase` across `robobase/`, `roboimpl/`, `test/`, `examples/`, `tools/`.
- **Env vars**: `ROBOBASE_LOGLEVEL`, `ROBOBASE_LOGS_DIR`, `ROBOBASE_STORE_LOGS` → `ROBOCHAN_*`. Update reads in code and any docs/scripts referencing them.
- **Logger names**: `ROBOBASE` logger (loggez) → `ROBOCHAN`. Check `roboimpl` sub-loggers (`ROBOIMPL_YOLO`, etc.) — `roboimpl` is *not* being renamed.
- **Packaging**: `setup.py` name/description/URL, `robobase.egg-info/` (regenerate after rename).
- **Docs**: README.md, CLAUDE.md (project-name references, env var names, file paths in "Key Files" sections).
- **Tests**: `test/robobase/` directory rename to `test/robochan/`; update pytest invocations in README.

## Out of scope
- `roboimpl` stays as is.
- Git remote / repo URL change (handled separately).

## Done when
- `grep -ri "robobase" .` returns only intentional references (e.g., changelog/history notes, if any).
- `pytest test/robochan` and `pytest test/roboimpl` pass.
- `pip install -e .` installs as `robochan`.
- README, CLAUDE.md, setup.py reflect the new name.
