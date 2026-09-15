from core.claude import Claude
from mcp_client import MCPClient
from core.tools import ToolManager


class Chat:
    def __init__(
        self,
        claude_service: Claude,
        clients: dict[str, MCPClient],
    ):
        self.claude_service = claude_service
        self.clients = clients
        self.messages = []

    async def run(self, query: str) -> str:
        final_text_response = ""

        self.messages.append({
            "role": "user",
            "content": query,
        })

        while True:
            response = self.claude_service.chat(
                messages=self.messages,
                tools=await ToolManager.get_all_tools(self.clients),
            )

            # Convertiamo il messaggio Groq in dict
            assistant_message = {
                "role": "assistant",
                "content": response.content,
            }

            if response.tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in response.tool_calls
                ]

            self.messages.append(assistant_message)

            if response.tool_calls:
                print(self.claude_service.text_from_message(response))

                tool_result_parts = (
                    await ToolManager.execute_tool_requests(
                        self.clients,
                        response,
                    )
                )

                self.claude_service.add_user_message(
                    self.messages,
                    tool_result_parts,
                )

            else:
                final_text_response = (
                    self.claude_service.text_from_message(response)
                )
                break

        return final_text_response
