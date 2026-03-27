# ContribAI Gamification / Tamagotchi Layer: Implementation Plan (GameFly)

This document outlines the detailed, step-by-step strategy for building the Gamification/Tamagotchi visual layer onto the existing ContribAI dashboard. The goal is to provide a live, 2D isometric/pixel-art representation of the bot's real-time state, running efficiently on edge devices (like Orange Pi) without hindering the core LLM/GitHub async loop.

---

## Pillar 1: State Management & Emission (Backend)

We need to introduce a lightweight, non-blocking mechanism to track and emit the `current_state` within the `SuperHumanLoop` (`contribai/orchestrator/human.py`), and a bridge to pass this state to the web layer.

### 1. State Dictionary & Transitions
Add a `current_state` property to the `SuperHumanLoop` class. This dictionary will hold the bot's current status and metadata:
```python
{
    "status": "working",      # The visual state identifier
    "task": "Scanning repos", # Human-readable sub-task
    "prs_today": 2,           # Progress metric
    "target_prs": 5           # Target metric
}
```

### 2. Mapping Actions to Visual States
We will insert state update calls inside `SuperHumanLoop` methods (`run_daily_routine`, `_do_hunt`, `_do_patrol`) using a non-blocking helper (e.g., `self._emit_state(status, task)`). The mapping will be:
- **`HUNTING` / `PATROLLING` -> "working"**: Triggered during `_do_hunt()` and `_do_patrol()`. Avatar types at the PC.
- **`REST_SHORT` / `WPM_DELAY` -> "thinking" or "stretching"**: Triggered during short `asyncio.sleep()` intervals between dry hunts or standard delays.
- **`REST_LONG` (Lunch/Timeout) -> "coffee_break"**: Triggered during the 1-hour lunch break or Quota Exhaustion (LLM Rate Limit).
- **`SLEEPING` -> "sleeping"**: Night mode / Shutdown state. Avatar in bed, lights off.
- **`ERROR_STRESS` -> "frustrated"**: Triggered on `GitHubAPIError` or unhandled exceptions before taking a stress break.

### 3. IPC (Inter-Process Communication) Strategy
Since `SuperHumanLoop` is usually started via the CLI (`contribai superhuman`) and the FastAPI server runs in a separate process, they need a simple shared medium.
- **Approach**: An ephemeral JSON file (e.g., `.contribai_state.json` written to the cache/storage directory) or leveraging the existing SQLite `Memory` instance via a new `bot_state` table.
- **Recommendation**: Writing to a tiny `.contribai_state.json` file using an async/non-blocking file write provides the lowest overhead and zero database locking contention, keeping the `SuperHumanLoop` completely unblocked.

---

## Pillar 2: Real-time Communication (API Layer)

The web dashboard needs a way to receive these state updates in real time without refreshing. We will modify `contribai/web/server.py`.

### 1. WebSocket Endpoint
Add a WebSocket route `/ws/bot-state` to `server.py` using `fastapi.WebSocket`.
- The endpoint will accept incoming connections and add them to an active connection manager mapping.
- **Polling Loop**: A background task (using `asyncio.create_task` during the WebSocket connection) will read the shared `.contribai_state.json` file (or SQLite) once every second.
- **Diff Check**: To minimize network overhead on the edge device, the server will keep the previous state in memory and only broadcast the JSON payload to all connected clients if the state has mutated.

### 2. Static Files Mounting
Currently, `server.py` returns a raw `HTMLResponse` from `dashboard.py`. We will refactor this to serve a dedicated frontend directory.
- Mount actual static files: `app.mount("/static", StaticFiles(directory="contribai/web/static"), name="static")`.
- Update the root route (`/`) to serve `contribai/web/static/index.html`. 

---

## Pillar 3: The Pixel Office (Frontend)

We will build the Tamagotchi visualizer in a new directory: `contribai/web/static/`.

### 1. Frontend Architecture & Edge Rendering
- **Constraint**: Must be extremely lightweight for the Orange Pi edge device.
- **Recommendation**: **Vanilla HTML5 Canvas + CSS Sprites**. We will avoid heavy frameworks (No React/Vue, No heavy WebGL engines) to save CPU/RAM. We will use a single `<canvas id="office">` element and an optimized `requestAnimationFrame` loop in `game.js`.

### 2. File Structure
```text
contribai/web/static/
├── index.html       # The main dashboard combined with the canvas
├── style.css        # Layout, Retro/Pixel typography, and HUD styling
├── game.js          # WebSocket client, Canvas rendering, and Sprite animation logic
└── assets/
    └── sprites/     # Pixel-art sprite sheets (avatar, room, desk, bed)
```

### 3. WebSocket Client & Animation Logic (`game.js`)
- Establish a `WebSocket` connection to `ws://<host>:<port>/ws/bot-state`.
- **Event Listener**: On `message` event, parse the JSON state.
- **State Machine**:
  - `if (state.status === "working") { currentAnimation = workingSprite; }`
  - Update HUD DOM elements directly `document.getElementById('prs-counter').innerText = state.prs_today;`.
- **Animation Loop**: The `requestAnimationFrame` loop simply cycles through the sprite frames of the `currentAnimation` based on a fixed frame-rate (e.g., 8-12 fps for retro pixel art), drawing the background and the character onto the `ctx`.

---

## Pillar 4: Asset Strategy & Dependencies

### 1. Python Dependencies
- Ensure **`websockets`** is included in `pyproject.toml` or `requirements.txt`. FastAPI relies on the `websockets` library to run its WebSocket endpoints (`pip install websockets`).

### 2. Game Assets (Sprites)
- To maintain optimal performance, consolidate assets into **Sprite Sheets** (.png).
- **Backgrounds**: `room_day.png`, `room_night.png`.
- **Avatar States**: `avatar_spritesheet.png` (contains rows for typing, drinking coffee, sleeping, frustrated/head-scratching).

### 3. Implementation Steps Checklist
1. **[Backend]** Add `websockets` to dependencies.
2. **[Backend]** Implement the non-blocking state emitter (`.contribai_state.json`) inside `human.py`.
3. **[API]** Refactor `server.py` to mount `contribai/web/static` and serve `index.html`.
4. **[API]** Add the `/ws/bot-state` WebSocket endpoint using FastAPI.
5. **[Frontend]** Create `index.html`, `style.css`, and `game.js` in `web/static/`.
6. **[Frontend]** Implement the HTML5 Canvas loop and the WebSocket listener in `game.js`.
7. **[Assets]** Place placeholder/final pixel-art sprites into `web/static/assets/sprites/`.
8. **[Test]** Run the bot and ensure visual state matches the backend logs accurately without high CPU usage.
