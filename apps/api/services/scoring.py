import os
import httpx
import json
import logging
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
logger = logging.getLogger(__name__)


async def ai_context_score(post: dict, product: dict) -> dict:
    """Single AI pass that replaces both tier1 and tier2 scoring.
    Returns {'score': 0-10, 'reason': 'one sentence explanation'} or None on failure."""

    prompt = f"""You are a marketing relevance analyst. Given this product and this tweet, rate how strategically valuable it would be for this product's brand account to reply. Consider: Is the person expressing a problem this product solves? Are they asking a question this product answers? Are they frustrated with a competitor? Are they in the target audience? Is there genuine engagement opportunity or is this spam/noise? Rate 0-10 and explain in one sentence. Return JSON only: {{"score": 7, "reason": "User is frustrated with ChatGPT privacy, directly in target audience"}}

Product: {product.get('name', '')}
Description: {product.get('description', '')}
Value prop: {product.get('value_prop', '')}
Target audience context: {product.get('system_prompt', '')[:300]}

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
