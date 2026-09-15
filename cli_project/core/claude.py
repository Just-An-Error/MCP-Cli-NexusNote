import os
from groq import Groq


class Claude:
    def __init__(self, model: str):
        self.client = Groq(
            api_key=os.getenv("GROQ_API_KEY")
        )
        self.model = model

    def add_user_message(self, messages: list, message):
        if isinstance(message, list):
            for item in message:
                messages.append({
                    "role": "tool",
                    "tool_call_id": item["tool_use_id"],
                    "name": item.get("name", ""),
                    "content": item["content"],
                })
        else:
            messages.append({
                "role": "user",
                "content": message,
            })

    def add_assistant_message(self, messages: list, message):
        messages.append(message)

    def text_from_message(self, message):
        return message.content or ""

    def chat(
        self,
        messages,
        system=None,
        temperature=1.0,
        stop_sequences=None,
        tools=None,
        thinking=False,
        thinking_budget=1024,
    ):
        if stop_sequences is None:
            stop_sequences = []

        api_messages = list(messages)

        if system:
            api_messages.insert(
                0,
                {
                    "role": "system",
                    "content": system,
                },
            )

        groq_tools = None

        if tools:
            groq_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool["input_schema"],
                    },
                }
                for tool in tools
            ]

        params = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
        }

        if stop_sequences:
            params["stop"] = stop_sequences

        if groq_tools:
            params["tools"] = groq_tools
            params["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**params)

        return response.choices[0].message
