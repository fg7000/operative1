from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os

router = APIRouter()

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    system: str
    messages: list[Message]

@router.post("/chat")
async def onboarding_chat(request: ChatRequest):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    # Convert messages to OpenRouter format (OpenAI-compatible)
    messages = [{"role": "system", "content": request.system}]
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://operative1.vercel.app",
                "X-Title": "Operative1"
            },
            json={
                "model": "anthropic/claude-haiku-4-5",
                "messages": messages,
                "max_tokens": 1000
            },
            timeout=60.0
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"OpenRouter error: {response.text}")

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        return {"content": [{"text": content}]}
