"""Minimal MCP client for the Industrial Video Safety Agent tools."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "services" / "safety-mcp-server" / "server.py"


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    return value


async def run(args: argparse.Namespace) -> int:
    env = os.environ.copy()
    env["SAFETY_AGENT_API_BASE"] = args.api_base
    if args.token:
        env["SAFETY_AGENT_TOKEN"] = args.token

    server = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        cwd=str(ROOT),
        env=env,
    )
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Available MCP tools")
            print(json.dumps(to_jsonable(tools), ensure_ascii=False, indent=2))

            if args.audit_id:
                result = await session.call_tool(
                    "query_video_memory",
                    {"audit_id": args.audit_id, "has_bbox": True},
                )
                print("\nquery_video_memory result")
                print(json.dumps(to_jsonable(result), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="List and call Industrial Safety Agent MCP tools.")
    parser.add_argument("--api-base", default="http://localhost:8000/api")
    parser.add_argument("--token", default=os.getenv("SAFETY_AGENT_TOKEN", ""))
    parser.add_argument("--audit-id", type=int, default=0, help="Optional audit id for query_video_memory.")
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
