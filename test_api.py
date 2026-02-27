import os
from anthropic import Anthropic

key = "api03-OaYutxgBcvqyVqt_l_hp_NBR9GHcZSVFtka574Q55Q5G9q7p06lUXAtx3c7fTw3puTGrzne7d7eZ1m7OeRC3gQ-q4CVfwAA"
if not key.startswith("sk-ant-"):
    key = "sk-ant-" + key

print(f"Testing key: {key[:15]}...")
try:
    client = Anthropic(api_key=key)
    response = client.messages.create(
        max_tokens=10,
        messages=[
            {
                "role": "user",
                "content": "Hello",
            }
        ],
        model="claude-3-haiku-20240307",
    )
    print("Success:", response.content[0].text)
except Exception as e:
    print("Error:", e)
