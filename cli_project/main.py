import argparse
import asyncio
import os
import re
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from dotenv import load_dotenv

from mcp_client import MCPClient
from core.claude import Claude

from core.cli_chat import CliChat
from core.cli import CliApp

_HERE = Path(__file__).resolve().parent
# Load env from cli_project/.env even when launched from repo root.
load_dotenv(dotenv_path=_HERE / ".env")

# Anthropic Config
claude_model = os.getenv("CLAUDE_MODEL", "")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")


if not claude_model:
    raise RuntimeError(
        "Error: CLAUDE_MODEL cannot be empty. Update cli_project/.env"
    )

if not anthropic_api_key:
    raise RuntimeError(
        "Error: ANTHROPIC_API_KEY cannot be empty. Update cli_project/.env"
    )


_ARITHMETIC_RE = re.compile(r"^\s*\d+(?:\s*[+\-*/]\s*\d+)+\s*$")


def _maybe_eval_arithmetic(query: str) -> str | None:
    """Simple local shortcut so users can sanity-check the CLI quickly.

    Only allows digits and + - * / operators (no names, no parentheses).
    """

    if not _ARITHMETIC_RE.match(query):
        return None
    # Safe because regex restricts the input to digits/operators/whitespace.
    return str(eval(query, {"__builtins__": {}}, {}))


def _offline_fallback_response(query: str) -> str:
    q = query.strip().lower()
    if q in {"hi", "hello", "hey"}:
        return "Hello! (offline mode)"
    if "what day" in q and "today" in q:
        return (
            "I can't check the real date in offline mode, but today is today. "
            "(If you add Anthropic credits, I can answer normally.)"
        )
    return (
        "Offline mode: I couldn't reach Anthropic (or credits are exhausted). "
        "Try a simple arithmetic query like `2+3`, or run with a funded API key."
    )


async def main():
    parser = argparse.ArgumentParser(description="MCP Chat CLI")
    parser.add_argument(
        "--once",
        type=str,
        default=None,
        help="Run a single query and exit (useful for quick tests / CI).",
    )
    # Use parse_known_args so additional positional args (like extra MCP server
    # scripts) don't break the CLI.
    args_ns, unknown = parser.parse_known_args()

    claude_service = Claude(model=claude_model)

    server_scripts = unknown
    clients = {}

    command, args = (
        ("uv", ["run", "mcp_server.py"])
        if os.getenv("USE_UV", "0") == "1"
        # Use the current interpreter instead of assuming `python` exists.
        else (sys.executable, ["mcp_server.py"])
    )

    async with AsyncExitStack() as stack:
        doc_client = await stack.enter_async_context(
            MCPClient(command=command, args=args)
        )
        clients["doc_client"] = doc_client

        for i, server_script in enumerate(server_scripts):
            client_id = f"client_{i}_{server_script}"
            client = await stack.enter_async_context(
                MCPClient(command="uv", args=["run", server_script])
            )
            clients[client_id] = client

        chat = CliChat(
            doc_client=doc_client,
            clients=clients,
            claude_service=claude_service,
        )

        # Wrap the agent so we can answer simple arithmetic locally.
        original_run = chat.run

        async def patched_run(query: str) -> str:
            arithmetic = _maybe_eval_arithmetic(query)
            if arithmetic is not None:
                return arithmetic
            try:
                return await original_run(query)
            except Exception as e:
                # Keep the CLI usable even when the external API is unavailable.
                print(f"\n[warning] Model call failed: {e}\n")
                return _offline_fallback_response(query)

        chat.run = patched_run  # type: ignore[method-assign]

        # Non-interactive mode: run a single query and exit.
        if args_ns.once is not None:
            response = await chat.run(args_ns.once)
            print(response)
            return

        cli = CliApp(chat)
        await cli.initialize()
        await cli.run()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
