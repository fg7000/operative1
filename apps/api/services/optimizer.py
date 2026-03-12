import os
import httpx
import json
import logging
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
logger = logging.getLogger(__name__)

async def run_optimizer():
    """Weekly optimization: analyze engagement data per product and suggest distribution changes."""
    logger.info("Optimizer running")
    try:
        from services.database import supabase

        products = supabase.table('products').select('*').eq('active', True).execute()

        for product in products.data:
            pid = product['id']
            # Gather posted replies with engagement data
            res = supabase.table('reply_queue').select('*').eq('product_id', pid).eq('status', 'posted').execute()

            if len(res.data) < 5:
                logger.info(f"Product {product['name']}: only {len(res.data)} posted replies, skipping optimization (need 5+)")
                continue

            # Build performance summary per mode
            mode_stats = {}
            for row in res.data:
                metrics = row.get('engagement_metrics') or {}
                mode = metrics.get('reply_mode', 'unknown')
                if mode == 'unknown':
                    continue
                if mode not in mode_stats:
                    mode_stats[mode] = {'count': 0, 'total_engagement': 0}
                s = mode_stats[mode]
                s['count'] += 1
                s['total_engagement'] += (
                    metrics.get('likes', 0) +
                    metrics.get('retweets', 0) * 2 +
                    metrics.get('replies', 0) * 3
                )

            if not mode_stats:
                logger.info(f"Product {product['name']}: no mode data available yet")
                continue

            summary = {}
            for mode, s in mode_stats.items():
                summary[mode] = {
                    'count': s['count'],
                    'avg_engagement': round(s['total_engagement'] / s['count'], 2)
                }

            current_dist = product.get('auto_post', {}).get('reply_mode_distribution', {
                'helpful_expert': 50, 'soft_mention': 30, 'direct_pitch': 20
            })

            # Ask LLM for optimization recommendations
            prompt = f"""You are an engagement optimizer for a social media reply bot.

Product: {product['name']}
Value prop: {product.get('value_prop', '')}

Current reply mode distribution: {json.dumps(current_dist)}

Performance data per reply mode:
{json.dumps(summary, indent=2)}

Based on this engagement data, suggest an optimized distribution.
Rules:
- Values must sum to 100
- Don't set any mode below 10 (we need ongoing data from all modes)
- If a mode has very few samples, don't overreact to its metrics

Respond with ONLY a JSON object:
{{"helpful_expert": 50, "soft_mention": 30, "direct_pitch": 20, "reasoning": "brief explanation"}}"""

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                    json={
                        'model': 'anthropic/claude-haiku-4-5',
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': 300
                    }
                )
                content = resp.json()['choices'][0]['message']['content']

                # Robust JSON extraction
                clean = content
                if '```' in clean:
                    clean = '\n'.join(line for line in clean.split('\n') if '```' not in line)
                first = clean.find('{')
                last = clean.rfind('}')
                if first == -1 or last == -1 or last <= first:
                    logger.error(f"Optimizer: no JSON found in response for {product['name']}")
                    continue
                suggestion = json.loads(clean[first:last + 1])

            reasoning = suggestion.pop('reasoning', '')
            logger.info(f"Optimizer suggestion for {product['name']}: {suggestion} — {reasoning}")
            logger.info(f"Current distribution: {current_dist}")
            logger.info(f"Optimizer does NOT auto-apply. Review and update manually if desired.")

    except Exception as e:
        logger.error(f"Optimizer error: {e}", exc_info=True)
