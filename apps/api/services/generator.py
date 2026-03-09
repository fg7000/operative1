import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

async def generate_reply(post: dict, product: dict, platform: str) -> dict:
    system_prompt = product.get('system_prompt', '')
    system_prompt = system_prompt.replace('{{product_name}}', product['name'])
    system_prompt = system_prompt.replace('{{platform}}', platform)
    system_prompt = system_prompt.replace('{{value_prop}}', product.get('value_prop', ''))
    system_prompt = system_prompt.replace('{{tone}}', product.get('tone', 'helpful'))
    forbidden = ', '.join(product.get('forbidden_phrases') or [])
    system_prompt = system_prompt.replace('{{forbidden_phrases}}', forbidden)

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
            json={
                'model': product.get('model', 'anthropic/claude-haiku-4-5'),
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f"Post to reply to:\n\n{post.get('text', '')}"}
                ],
                'max_tokens': 500
            }
        )
        try:
            content = res.json()['choices'][0]['message']['content']
            clean = content.strip().replace('```json', '').replace('```', '')
            return json.loads(clean)
        except:
            return None
