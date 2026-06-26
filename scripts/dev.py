"""Developer command runner for the Industrial Video Safety Agent.

The script is intentionally stdlib-only so a fresh clone can run environment
checks before project dependencies are installed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
COMPOSE = ["docker", "compose", "-p", "aicoding", "-f", "docker-compose.safety.yml"]


def project_python() -> str:
    configured = os.getenv("SAFETY_AGENT_PYTHON")
    if configured:
        return configured
    candidates = [
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv-test" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
        ROOT / ".venv-test" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def python_with_module(module: str) -> str:
    seen: set[str] = set()
    for executable in (project_python(), sys.executable):
        if executable in seen:
            continue
        seen.add(executable)
        result = subprocess.run(
            [executable, "-c", f"import {module}"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode == 0:
            return executable
    raise SystemExit(
        f"Python module '{module}' is not installed. "
        f"Run: {project_python()} -m pip install -r services/safety-mcp-server/requirements.txt"
    )


def run(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> int:
    executable = cmd[0]
    if "\\" not in executable and "/" not in executable:
        resolved = shutil.which(executable)
        if resolved:
            cmd = [resolved, *cmd[1:]]
    print(f"$ {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.returncode


def ensure_env() -> None:
    if ENV_FILE.exists():
        return
    if not ENV_EXAMPLE.exists():
        raise SystemExit(".env.example is missing")
    ENV_FILE.write_text(ENV_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    print("Created .env from .env.example", flush=True)


def check_tool(name: str, args: list[str], required: bool = True) -> bool:
    path = shutil.which(name)
    if not path:
        status = "missing" if required else "optional missing"
        print(f"[{status}] {name}", flush=True)
        return False
    print(f"[ok] {name}: {path}", flush=True)
    if args:
        run([path, *args], check=False)
    return True


def doctor(_: argparse.Namespace) -> None:
    print("Industrial Video Safety Agent doctor\n", flush=True)
    print(f"repo: {ROOT}", flush=True)
    print(f"python: {sys.version.split()[0]}", flush=True)
    check_tool("git", ["--version"])
    check_tool("docker", ["--version"])
    check_tool("node", ["--version"])
    check_tool("npm", ["--version"])
    if ENV_FILE.exists():
        print("[ok] .env exists", flush=True)
    else:
        print("[warn] .env missing. Run: python scripts/dev.py init-env", flush=True)
    if ENV_EXAMPLE.exists():
        print("[ok] .env.example exists", flush=True)
    else:
        print("[missing] .env.example", flush=True)
    if (ROOT / "docker-compose.safety.yml").exists():
        print("[ok] docker-compose.safety.yml exists", flush=True)
    else:
        print("[missing] docker-compose.safety.yml", flush=True)


def init_env(_: argparse.Namespace) -> None:
    ensure_env()


def up(_: argparse.Namespace) -> None:
    ensure_env()
    run([*COMPOSE, "up", "-d", "--build"])


def down(_: argparse.Namespace) -> None:
    run([*COMPOSE, "down"])


def ps(_: argparse.Namespace) -> None:
    run([*COMPOSE, "ps"])


def logs(args: argparse.Namespace) -> None:
    cmd = [*COMPOSE, "logs", "-f"]
    if args.service:
        cmd.append(args.service)
    run(cmd)


def seed(args: argparse.Namespace) -> None:
    ensure_env()
    cmd = [*COMPOSE, "exec", "video-audit-service", "python", "/app/scripts/seed_demo_safety_agent.py"]
    if args.with_ticket:
        cmd.append("--with-ticket")
    run(cmd)


def test(_: argparse.Namespace) -> None:
    run([project_python(), "-m", "pytest", "-q"])


def frontend_build(_: argparse.Namespace) -> None:
    run(["npm", "run", "build"], cwd=FRONTEND)


def compose_check(_: argparse.Namespace) -> None:
    ensure_env()
    run([*COMPOSE, "config", "--quiet"])


def docs_check(_: argparse.Namespace) -> None:
    run([project_python(), "scripts/check_docs.py"])


def workflow_check(_: argparse.Namespace) -> None:
    run([project_python(), "scripts/check_workflow_spec.py"])


def prompt_check(_: argparse.Namespace) -> None:
    run([project_python(), "scripts/check_prompt_contract.py"])


def benchmark_report(_: argparse.Namespace) -> None:
    run([project_python(), "scripts/generate_benchmark_report.py"])


def verify(_: argparse.Namespace) -> None:
    ensure_env()
    run([project_python(), "scripts/check_docs.py"])
    run([project_python(), "scripts/check_workflow_spec.py"])
    run([project_python(), "scripts/check_prompt_contract.py"])
    run([project_python(), "-m", "pytest", "-q"])
    run(["npm", "run", "build"], cwd=FRONTEND)
    run([*COMPOSE, "config", "--quiet"])


def mcp_tools(_: argparse.Namespace) -> None:
    run([python_with_module("mcp"), "examples/mcp_stdio_client_demo.py"])


def api_demo(_: argparse.Namespace) -> None:
    run([project_python(), "examples/api_client_demo.py"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Developer commands for the Industrial Video Safety Agent.")
    sub = parser.add_subparsers(dest="command", required=True)

    commands = {
        "doctor": (doctor, "Check required local tools and repo files."),
        "init-env": (init_env, "Create .env from .env.example if it does not exist."),
        "up": (up, "Build and start the safety-only Docker Compose stack."),
        "down": (down, "Stop the safety-only Docker Compose stack."),
        "ps": (ps, "Show safety stack container status."),
        "test": (test, "Run Python tests."),
        "frontend-build": (frontend_build, "Build the React frontend."),
        "compose-check": (compose_check, "Validate docker-compose.safety.yml."),
        "docs-check": (docs_check, "Validate local Markdown links."),
        "workflow-check": (workflow_check, "Validate the safety Agent workflow spec."),
        "prompt-check": (prompt_check, "Validate the VLM prompt and output schema contract."),
        "benchmark-report": (benchmark_report, "Generate benchmark report and SVG chart artifacts."),
        "verify": (verify, "Run tests, frontend build, and compose validation."),
        "mcp-tools": (mcp_tools, "List MCP tools through the stdio client."),
        "api-demo": (api_demo, "Run the API client demo against localhost."),
    }
    for name, (handler, help_text) in commands.items():
        item = sub.add_parser(name, help=help_text)
        item.set_defaults(func=handler)

    seed_parser = sub.add_parser("seed", help="Seed a deterministic safety Agent demo.")
    seed_parser.add_argument("--with-ticket", action="store_true", help="Create the remediation ticket during seeding.")
    seed_parser.set_defaults(func=seed)

    logs_parser = sub.add_parser("logs", help="Follow Docker Compose logs.")
    logs_parser.add_argument("service", nargs="?", help="Optional service name, for example video-worker.")
    logs_parser.set_defaults(func=logs)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
