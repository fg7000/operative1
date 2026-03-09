import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

def tier1_score(post: dict, keywords: list) -> int:
    score = 0
    text = post.get('text', '').lower()
    for kw in keywords:
        if kw.lower() in text:
            score += 20
    likes = post.get('likes', 0)
    if likes > 10: score += 10
    if likes > 50: score += 10
    if likes > 100: score += 10
    replies = post.get('replies', 0)
    if replies > 2: score += 10
    if len(text) > 100: score += 10
    return min(score, 100)

async def tier2_score(post: dict, product: dict) -> float:
    prompt = f"""Rate the relevance of this post to the product on a scale of 0.0 to 1.0.

Product: {product['name']}
Value proposition: {product['value_prop']}

Post: {post.get('text', '')}

Return only a JSON object: {{"relevance": 0.0}}"""

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
            json={
                'model': product.get('model', 'anthropic/claude-haiku-4-5'),
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 50
            }
        )
        try:
            content = res.json()['choices'][0]['message']['content']
            return json.loads(content).get('relevance', 0.0)
        except:
            return 0.0
