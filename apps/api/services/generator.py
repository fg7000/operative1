import os
import httpx
import json
import logging
import random
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
logger = logging.getLogger(__name__)

MODE_INSTRUCTIONS = {
    'helpful_expert': "Be a genuinely helpful expert. Answer the question or add real value to the conversation. Only mention our product if it's directly relevant — and even then, keep it brief and natural. The goal is to build credibility, not sell.",
    'soft_mention': "Be helpful and conversational. Weave in a brief, natural mention of our product as one option among others. Don't make it the focus — just a friendly suggestion. Think 'oh btw, X does this too' energy.",
    'direct_pitch': "Be helpful but clearly recommend our product as a solution. Explain why it fits the user's need. Keep it genuine and not salesy — more like a friend recommending something they actually use."
}

PLATFORM_LENGTH = {
    'twitter': "Your reply MUST be 1-3 sentences maximum. Be punchy, direct, and conversational. No walls of text. Under 250 characters is ideal.",
    'reddit': "Be detailed and technical, 2-4 paragraphs is fine.",
    'linkedin': "Professional but concise, 2-3 sentences.",
    'hn': "Technical and specific, 1-3 sentences.",
}

def select_reply_mode(product: dict) -> str:
    dist = product.get('auto_post', {}).get('reply_mode_distribution', {
        'helpful_expert': 50, 'soft_mention': 30, 'direct_pitch': 20
    })
    modes = list(dist.keys())
    weights = [dist[m] for m in modes]
    return random.choices(modes, weights=weights, k=1)[0]

async def generate_reply(post: dict, product: dict, platform: str) -> dict:
    reply_mode = select_reply_mode(product)
    logger.info(f"Selected reply mode: {reply_mode}")

    system_prompt = product.get('system_prompt', '')
    system_prompt = system_prompt.replace('{{product_name}}', product['name'])
    system_prompt = system_prompt.replace('{{platform}}', platform)
    system_prompt = system_prompt.replace('{{value_prop}}', product.get('value_prop', ''))
    system_prompt = system_prompt.replace('{{tone}}', product.get('tone', 'helpful'))
    forbidden = ', '.join(product.get('forbidden_phrases') or [])
    system_prompt = system_prompt.replace('{{forbidden_phrases}}', forbidden)

    mode_instruction = MODE_INSTRUCTIONS[reply_mode]
    length_instruction = PLATFORM_LENGTH.get(platform, "Be concise and natural.")

    # If the post has been translated, reply in the original language
    original_language = post.get('original_language')
    language_instruction = ""
    if original_language and original_language != 'en':
        language_instruction = f"\n\nIMPORTANT: The original post is in {original_language}. Write your reply in {original_language}, NOT in English."

    user_message = f"""Reply to this {platform} post. {mode_instruction}

{length_instruction}

Keep it natural and conversational — no hashtags, no hard sell, no generic filler.{language_instruction}

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
            parsed['reply_mode'] = reply_mode
            logger.info(f"Generator parsed reply: {parsed}")
            return parsed
        except Exception as e:
            logger.error(f"Generator parse error: {e}")
            logger.error(f"Generator raw content: {res.text[:500]}")
            return None
