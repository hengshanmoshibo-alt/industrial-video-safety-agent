# Developer Commands

`scripts/dev.py` is the cross-platform command runner for local development and
demo verification. It uses only the Python standard library.

Python commands prefer `.venv`, then `.venv-test`, then the current interpreter.
Set `SAFETY_AGENT_PYTHON=/path/to/python` to override this behavior.

## First Run

```bash
python scripts/dev.py doctor
python scripts/dev.py init-env
python scripts/dev.py up
python scripts/dev.py seed
```

Open `http://localhost:5173` and log in with `admin / Admin123!`.

## Commands

| Command | Purpose |
| --- | --- |
| `doctor` | Check Git, Docker, Node, npm, `.env`, and compose files. |
| `init-env` | Create `.env` from `.env.example` if missing. |
| `up` | Build and start the safety-only Docker Compose stack. |
| `down` | Stop the safety-only stack. |
| `ps` | Show container status. |
| `logs [service]` | Follow all logs or one service log. |
| `seed [--with-ticket]` | Create the deterministic safety Agent demo. |
| `test` | Run Python tests. |
| `frontend-build` | Build the React frontend. |
| `compose-check` | Validate `docker-compose.safety.yml`. |
| `docs-check` | Validate local Markdown links. |
| `workflow-check` | Validate the safety Agent workflow spec against code and docs. |
| `prompt-check` | Validate the VLM prompt and output schema contract. |
| `benchmark-report` | Generate the smoke benchmark Markdown report and SVG chart. |
| `verify` | Run tests, frontend build, and compose validation. |
| `mcp-tools` | List MCP tools through the stdio client. |
| `api-demo` | Run the API client example against localhost. |

## CI Equivalent

The same gates used by CI can be run locally:

```bash
python scripts/dev.py verify
```
