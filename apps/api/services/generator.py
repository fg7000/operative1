import os
import httpx
import json
import logging
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
logger = logging.getLogger(__name__)

async def generate_reply(post: dict, product: dict, platform: str) -> dict:
    system_prompt = product.get('system_prompt', '')
    system_prompt = system_prompt.replace('{{product_name}}', product['name'])
    system_prompt = system_prompt.replace('{{platform}}', platform)
    system_prompt = system_prompt.replace('{{value_prop}}', product.get('value_prop', ''))
    system_prompt = system_prompt.replace('{{tone}}', product.get('tone', 'helpful'))
    forbidden = ', '.join(product.get('forbidden_phrases') or [])
    system_prompt = system_prompt.replace('{{forbidden_phrases}}', forbidden)

    user_message = f"""Reply to this {platform} post in a way that's genuinely helpful and subtly highlights our product where relevant. Keep it natural and conversational — no hashtags, no hard sell.

Post to reply to:
{post.get('text', '')}

Respond with ONLY a JSON object, no other text, no markdown:
{{"reply": "your reply text here", "confidence": 0.8, "mentions_product": false}}"""

    model = product.get('model', 'anthropic/claude-haiku-4-5')
    logger.info(f"Generator request — model: {model}, platform: {platform}")
    logger.info(f"Generator system prompt: {system_prompt[:200]}...")
    logger.info(f"Generator user message: {user_message[:200]}...")

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message}
                ],
                'max_tokens': 500
            }
        )
        try:
            raw = res.json()
            logger.info(f"Generator raw response status: {res.status_code}")
            content = raw['choices'][0]['message']['content']
            logger.info(f"Generator content: {content}")

            # Strip code fences, then extract JSON between first { and last }
            clean = content
            if '```' in clean:
                clean = '\n'.join(line for line in clean.split('\n') if '```' not in line)
            first = clean.find('{')
            last = clean.rfind('}')
            if first == -1 or last == -1 or last <= first:
                logger.error(f"Generator: no JSON object found in response")
                return None
            clean = clean[first:last + 1]
            parsed = json.loads(clean)
            logger.info(f"Generator parsed reply: {parsed}")
            return parsed
        except Exception as e:
            logger.error(f"Generator parse error: {e}")
            logger.error(f"Generator raw content: {res.text[:500]}")
            return None
