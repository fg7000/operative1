import os
import httpx
import json
import logging
from dotenv import load_dotenv
from services.agent_prompts import CONTEXT_SCORER_PROMPT

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
logger = logging.getLogger(__name__)


async def ai_context_score(post: dict, product: dict) -> dict:
    """Single AI pass that replaces both tier1 and tier2 scoring.
    Returns {'score': 0-10, 'reason': 'one sentence explanation'} or None on failure."""

    prompt = CONTEXT_SCORER_PROMPT.format(
        product_name=product.get('name', ''),
        description=product.get('description', ''),
        value_prop=product.get('value_prop', ''),
    ) + f"""

Tweet: {post.get('text', '')}
Author: @{post.get('author', 'unknown')}
Likes: {post.get('likes', 0)} | Replies: {post.get('replies', 0)}"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                json={
                    'model': 'anthropic/claude-haiku-4-5',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 150
                }
            )
            raw = res.json()
            content = raw['choices'][0]['message']['content'].strip()
            logger.info(f"AI context score raw: {content}")

            clean = content
            if '```' in clean:
                clean = '\n'.join(line for line in clean.split('\n') if '```' not in line)
            first = clean.find('{')
            last = clean.rfind('}')
            if first == -1 or last == -1 or last <= first:
                logger.error("AI context score: no JSON found")
                return None
            parsed = json.loads(clean[first:last + 1])
            score = parsed.get('score', 0)
            reason = parsed.get('reason', '')
            logger.info(f"AI context score: {score}/10 — {reason} — for: {post.get('text', '')[:60]}")
            return {'score': score, 'reason': reason}
    except Exception as e:
        logger.error(f"AI context score error: {e}", exc_info=True)
        return None
