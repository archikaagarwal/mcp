import sys
import json
import asyncio
from typing import Optional, Any
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from pydantic import AnyUrl


class MCPClient:
    def __init__(
        self,
        command: str,
        args: list[str],
        env: Optional[dict] = None,
    ):
        self._command = command
        self._args = args
        self._env = env
        self._session: Optional[ClientSession] = None
        self._exit_stack: AsyncExitStack = AsyncExitStack()

    async def connect(self):
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )
        stdio_transport = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        _stdio, _write = stdio_transport
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(_stdio, _write)
        )
        await self._session.initialize()

    def session(self) -> ClientSession:
        if self._session is None:
            raise ConnectionError(
                "Client session not initialized or cache not populated. Call connect_to_server first."
            )
        return self._session

    async def list_tools(self) -> list[types.Tool]:
        session = self.session()
        return (await session.list_tools()).tools

    async def call_tool(
        self, tool_name: str, tool_input: dict
    ) -> types.CallToolResult | None:
        session = self.session()
        return await session.call_tool(tool_name, tool_input)

    async def list_prompts(self) -> list[types.Prompt]:
        session = self.session()
        return (await session.list_prompts()).prompts

    async def get_prompt(
        self, prompt_name: str, args: dict[str, str]
    ) -> list[types.PromptMessage]:
        session = self.session()
        prompt = await session.get_prompt(prompt_name, args)
        return prompt.messages

    async def read_resource(self, uri: str) -> Any:
        session = self.session()
        result = await session.read_resource(AnyUrl(uri))
        contents = getattr(result, "contents", None) or []

        if not contents:
            return None

        resource = contents[0]
        mime_type = getattr(resource, "mimeType", None)

        if hasattr(resource, "text"):
            text = resource.text
            if mime_type == "application/json":
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
            return text

        if hasattr(resource, "json"):
            return resource.json

        if hasattr(resource, "blob"):
            blob = resource.blob
            if isinstance(blob, (bytes, bytearray)):
                return bytes(blob)
            return blob

        return resource

    async def cleanup(self):
        await self._exit_stack.aclose()
        self._session = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()


# For testing
async def main():
    async with MCPClient(
        # If using Python without UV, update command to 'python' and remove "run" from args.
        command="uv",
        args=["run", "mcp_server.py"],
    ) as _client:
        results = await _client.list_tools()
        print("Tools:", results)
        results = await _client.list_prompts()
        print("Prompts:", results)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
