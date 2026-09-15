import json
from typing import Optional

from mcp.types import CallToolResult, TextContent
from mcp_client import MCPClient


class ToolManager:

    @classmethod
    async def get_all_tools(
        cls,
        clients: dict[str, MCPClient],
    ) -> list[dict]:

        tools = []

        for client in clients.values():
            tool_models = await client.list_tools()

            tools += [
                {
                    "name": t.name,
                    "description": t.description or "",
                    "input_schema": t.inputSchema,
                }
                for t in tool_models
            ]

        return tools

    @classmethod
    async def _find_client_with_tool(
        cls,
        clients: list[MCPClient],
        tool_name: str,
    ) -> Optional[MCPClient]:

        for client in clients:
            tools = await client.list_tools()

            tool = next(
                (t for t in tools if t.name == tool_name),
                None,
            )

            if tool:
                return client

        return None

    @classmethod
    async def execute_tool_requests(
        cls,
        clients: dict[str, MCPClient],
        message,
    ) -> list[dict]:

        tool_result_parts = []

        if not message.tool_calls:
            return tool_result_parts

        for tool_call in message.tool_calls:

            tool_use_id = tool_call.id

            tool_name = tool_call.function.name

            try:
                tool_input = json.loads(
                    tool_call.function.arguments
                )
            except json.JSONDecodeError:
                tool_result_parts.append({
                    "tool_use_id": tool_use_id,
                    "name": tool_name,
                    "content": json.dumps({
                        "error": "Invalid JSON arguments"
                    }),
                })
                continue

            client = await cls._find_client_with_tool(
                list(clients.values()),
                tool_name,
            )

            if not client:
                tool_result_parts.append({
                    "tool_use_id": tool_use_id,
                    "name": tool_name,
                    "content": json.dumps({
                        "error": "Could not find that tool"
                    }),
                })
                continue

            try:
                tool_output: CallToolResult | None = (
                    await client.call_tool(
                        tool_name,
                        tool_input,
                    )
                )

                items = []

                if tool_output:
                    items = tool_output.content

                content_list = [
                    item.text
                    for item in items
                    if isinstance(item, TextContent)
                ]

                content_json = json.dumps(content_list)

                if tool_output and tool_output.isError:
                    content_json = json.dumps({
                        "error": content_list
                    })

                tool_result_parts.append({
                    "tool_use_id": tool_use_id,
                    "name": tool_name,
                    "content": content_json,
                })

            except Exception as e:

                error_message = (
                    f"Error executing tool '{tool_name}': {e}"
                )

                print(error_message)

                tool_result_parts.append({
                    "tool_use_id": tool_use_id,
                    "name": tool_name,
                    "content": json.dumps({
                        "error": error_message
                    }),
                })

        return tool_result_parts
