from anthropic import Anthropic
from anthropic.types import Message
from wardrobe_ai import config

def call_llm(client:Anthropic) -> Message:
    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        
        messages=[
            {
                "role": "user",
                "content": "Hello, Claude",
            }
        ],
    )
    
    return message