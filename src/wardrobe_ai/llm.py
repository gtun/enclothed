import anthropic
from wardrobe_ai import config

def call_llm(client:anthropic.Anthropic) -> str:
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
    
    return message.content