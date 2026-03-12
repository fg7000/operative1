"""Keyword quality filter and AI keyword generator. Used by apify, product creation, and daily optimizer."""

import os
import httpx
import json
import logging
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
logger = logging.getLogger(__name__)

# Single-word terms that are too broad to produce targeted search results
BLOCKLIST = {
    'ai', 'data', 'privacy', 'tech', 'app', 'chat', 'tool', 'bot',
    'code', 'api', 'llm', 'ml', 'gpt', 'saas', 'web', 'dev',
    'hack', 'info', 'news', 'help', 'free', 'new', 'best',
    'model', 'agent', 'cloud', 'safe', 'secure', 'fast',
}


def filter_keywords(keywords: list[str]) -> tuple[list[str], list[str]]:
    """Filter out overly generic keywords.
    Returns (good_keywords, filtered_out_keywords)."""
    good = []
    filtered = []
    for kw in keywords:
        kw_stripped = kw.strip()
        if not kw_stripped:
            continue
        # Multi-word phrases are always kept
        if ' ' in kw_stripped:
            good.append(kw_stripped)
            continue
        # Single words: block if under 4 chars or in blocklist
        if len(kw_stripped) < 4 or kw_stripped.lower() in BLOCKLIST:
            filtered.append(kw_stripped)
            continue
        good.append(kw_stripped)
    return good, filtered


async def generate_keywords_for_product(product: dict, platform: str = 'twitter') -> list[str]:
    """Use AI to generate intent-based search keywords for a product."""
    name = product.get('name', '')
    description = product.get('description', '')
    value_prop = product.get('value_prop', '')

    prompt = f"""Given this product, generate 15 specific, intent-based {platform.capitalize()} search phrases that would find people who need this product. Focus on:
- Frustration signals ("I hate when ChatGPT...", "tired of...")
- Questions people ask ("is there a way to...", "how do I...")
- Competitor complaints ("ChatGPT privacy", "OpenAI data policy")
- Problem descriptions ("my AI conversations being tracked", "need private AI")
- Specific multi-word phrases, NOT single generic words

Product: {name}
Description: {description}
Value proposition: {value_prop}

Return a JSON array of strings only. Each string should be 2-6 words, specific enough to find real intent signals. Example format:
["ChatGPT privacy concerns", "AI tracking my data", "anonymous AI chat", "tired of ChatGPT logging"]"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                json={
                    'model': 'anthropic/claude-haiku-4-5',
                    'messages': [{'role': 'user', 'content': prompt}],
                    'max_tokens': 500
                }
            )
            content = res.json()['choices'][0]['message']['content']
            clean = content
            if '```' in clean:
                clean = '\n'.join(line for line in clean.split('\n') if '```' not in line)
            first = clean.find('[')
            last = clean.rfind(']')
            if first != -1 and last > first:
                keywords = json.loads(clean[first:last + 1])
                if isinstance(keywords, list) and all(isinstance(k, str) for k in keywords):
                    logger.info(f"AI generated {len(keywords)} keywords for {name}/{platform}")
                    return keywords
            logger.error(f"AI keyword generation: couldn't parse response for {name}")
    except Exception as e:
        logger.error(f"AI keyword generation error: {e}", exc_info=True)
    return []
