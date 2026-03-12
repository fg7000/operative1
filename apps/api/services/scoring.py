import os
import httpx
import json
import logging
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
logger = logging.getLogger(__name__)

def tier1_score(post: dict, keywords: list) -> int:
    score = 30
    text = post.get('text', '').lower()
    for kw in keywords:
        if kw.lower() in text:
            score += 15
    likes = post.get('likes', 0)
    if likes > 5: score += 10
    if likes > 20: score += 10
    if likes > 100: score += 10
    replies = post.get('replies', 0)
    if replies > 1: score += 10
    if replies > 5: score += 10
    if len(text) > 100: score += 10
    if len(text) > 200: score += 5
    if text.startswith('rt '): score -= 20
    if text.startswith('@'): score -= 10
    final = min(score, 100)
    logger.info(f"Tier1 score: {final} for: {post.get('text', '')[:80]}")
    return final

async def tier2_score(post: dict, product: dict) -> float:
    prompt = f"""Rate the relevance of this tweet to the product on a scale of 0.0 to 1.0.

Product: {product['name']}
Value proposition: {product['value_prop']}

Tweet: {post.get('text', '')}

Respond with ONLY a JSON object, no other text, no markdown, no explanation:
{{"relevance": 0.7}}"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'anthropic/claude-haiku-4-5',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 50
                }
            )
            raw = res.json()
            logger.info(f"Tier2 raw response: {raw}")
            content = raw['choices'][0]['message']['content'].strip()
            logger.info(f"Tier2 content: {content}")
            clean = content
            if '```' in clean:
                clean = '\n'.join(line for line in clean.split('\n') if '```' not in line)
            first = clean.find('{')
            last = clean.rfind('}')
            if first != -1 and last > first:
                clean = clean[first:last + 1]
            score = json.loads(clean).get('relevance', 0.0)
            logger.info(f"Tier2 score: {score} for: {post.get('text', '')[:60]}")
            return score
    except Exception as e:
        logger.error(f"Tier2 error: {e}")
        return 0.0
