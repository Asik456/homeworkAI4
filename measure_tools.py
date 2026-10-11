import json

import tiktoken

from strategies import ask
from tools import make_tools

tools = make_tools()
encoding = tiktoken.get_encoding("o200k_base")
print("tiktoken o200k_base, tool JSON:", len(encoding.encode(json.dumps(tools))))

messages = [{"role": "user", "content": "Say hi."}]
_, without_tools, _ = ask(messages)
_, with_tools, _ = ask(messages, tools=tools)
print("usage.prompt_tokens without tools:", without_tools)
print("usage.prompt_tokens with tools:", with_tools)
print("tools add:", with_tools - without_tools)
