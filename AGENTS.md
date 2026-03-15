# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

AIQUIZ-v1 is a Japanese educational quiz game ("AI脱出クイズ"). The runnable components in this repo are:

| Service | Entry point | Port | Notes |
|---|---|---|---|
| Quiz API Server (FastAPI) | `cd server && python main.py` | 8000 | Primary service; serves quiz questions from `offline_bank.json` |
| 2D Pygame Client | `python 2D_pygame.py` | N/A | Desktop GUI app; requires display. Not runnable in headless Cloud VMs |

### Running the server

```bash
cd server
cp .env.example .env   # only needed once
python main.py          # starts on http://0.0.0.0:8000
```

Swagger docs at `http://127.0.0.1:8000/docs`. See `server/README.md` for full endpoint reference.

### Linting

```bash
ruff check server/        # server code — should pass clean
ruff check 2D_pygame.py   # pygame client — has pre-existing style warnings (E702 etc.), do not fix
```

### Testing

No automated test suite exists. Validate the API using `fastapi.testclient.TestClient`:

```python
from fastapi.testclient import TestClient
import sys; sys.path.insert(0, 'server')
from main import app
client = TestClient(app)
r = client.get('/quiz/offline', params={'subject': '算数', 'grade': 3, 'count': 2})
assert r.status_code == 200
```

### Key caveats

- The server must be started from the `server/` directory (or the working directory must allow `quiz_engine.py` to resolve `../offline_bank.json`).
- `~/.local/bin` must be on `PATH` for `ruff`, `uvicorn`, `pytest`, etc. The update script handles this.
- The 2D Pygame client (`2D_pygame.py`) requires a display and cannot be tested in headless environments. It works in offline mode without API keys.
- External API keys (`OPENAI_API_KEY`, `GOOGLE_API_KEY`) are optional — the server and client both work fully offline.
