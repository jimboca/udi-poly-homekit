# Development

Clone path: `plugins/udi-poly-homekit-hub` (repo `https://github.com/jimboca/udi-poly-homekit-hub`).

Setup and tests:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```

Lint is checked in **GitHub Actions** with [Ruff](https://docs.astral.sh/ruff/) (pinned in the workflow). Locally: `make lint` or `pip install -r requirements-dev.txt && ruff check .`.

## Releases

Polyglot installs use a **git URL + branch**. This repo uses two remote branches: **`beta`** (pre-release) and **`production`** (stable). On a **branch** (not detached `HEAD`) with a **clean** git tree:

- **`make beta`** — runs **`make lint`** (Ruff, same as CI), then pushes **current `HEAD`** to **`origin/beta`** (override remote: **`GIT_REMOTE=myfork`**; override branch name: **`BRANCH_BETA=...`**).
- **`make production`** — runs **`make lint`**, then pushes to **`origin/production`** (**`BRANCH_PRODUCTION=...`**). Builds **`HomeKitHub-Production-Professional-<VERSION>.zip`** (full plugin) and **`HomeKitHub-Production-Standard-<VERSION>.zip`** (Standard strip).
- **`make release`** — runs **`make lint`**, parses **`VERSION`** from **`nodes/__init__.py`**, creates annotated **`v`<version>**, **`git push`**es the current branch and **`v`<version>**. Does **not** build a zip.

**`make zip`** remains for an optional **local `HomeKitHub.zip`** (legacy / manual upload); primary delivery is the branches above.

## Layout

- `homekit-poly.py` — entry point
- `homekit_hub/bridge.py` — aiohomekit + WebSocket (default port **8163**), multi-slot pairing
- `nodes/Controller.py` — PG3 lifecycle and custom params/data
- `CONFIG.md` — primary setup guide embedded in the PG3 Configuration UI via `setCustomParamsDoc()`
- `CONFIG_EXTRA.md` — advanced flat custom params (MQTT, WebSocket, zeroconf); not embedded in PG3 UI
- **PG3 doc links:** sibling docs linked from `CONFIG.md` must use GitHub `master` blob URLs with HTML `target="_blank"` — relative `.md` links do not work in the Polyglot help panel
- `PROTOCOL.md` — JSON message contract (`version` **1**)
