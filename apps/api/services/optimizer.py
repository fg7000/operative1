import os
import httpx
import json
import logging
from dotenv import load_dotenv
from services.agent_prompts import OPTIMIZER_PROMPT
from services.keyword_quality import filter_keywords, generate_keywords_for_product

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
                'direct_pitch': 50, 'soft_mention': 35, 'helpful_expert': 15
            })

            prompt = OPTIMIZER_PROMPT.format(
                current_distribution=json.dumps(current_dist),
                performance_data=json.dumps(summary, indent=2),
            )

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                    json={
                        'model': 'anthropic/claude-haiku-4-5',
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': 500
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

            new_dist = suggestion.get('new_distribution', {})
            recommendations = suggestion.get('recommendations', [])
            logger.info(f"Optimizer suggestion for {product['name']}: {new_dist}")
            logger.info(f"Recommendations: {recommendations}")
            logger.info(f"Current distribution: {current_dist}")
            logger.info(f"Optimizer does NOT auto-apply. Review and update manually if desired.")

    except Exception as e:
        logger.error(f"Optimizer error: {e}", exc_info=True)


async def run_keyword_optimizer():
    """Daily keyword quality check: replace generic keywords with AI-generated intent-based ones."""
    logger.info("Keyword optimizer running")
    try:
        from services.database import supabase

        products = supabase.table('products').select('*').eq('active', True).execute()

        for product in products.data:
            keywords = product.get('keywords', {})
            if not keywords:
                continue

            updated = False
            for platform, kw_list in keywords.items():
                if not isinstance(kw_list, list) or not kw_list:
                    continue

                good, filtered_out = filter_keywords(kw_list)

                if not filtered_out:
                    logger.info(f"Keyword optimizer: {product['name']}/{platform} — all {len(kw_list)} keywords are quality, no changes")
                    continue

                logger.warning(f"Keyword optimizer: {product['name']}/{platform} — filtering out generic: {filtered_out}")

                if good:
                    # Some good keywords remain, generate replacements for filtered ones
                    replacement_count = len(filtered_out)
                    ai_keywords = await generate_keywords_for_product(product, platform)
                    if ai_keywords:
                        # Add AI keywords to fill the gap, dedup against existing
                        existing_lower = {k.lower() for k in good}
                        new_ones = [k for k in ai_keywords if k.lower() not in existing_lower][:replacement_count + 5]
                        keywords[platform] = good + new_ones
                        logger.info(f"Keyword optimizer: {product['name']}/{platform} — kept {len(good)}, added {len(new_ones)} AI-generated")
                        updated = True
                    else:
                        keywords[platform] = good
                        updated = True
                else:
                    # All keywords were generic — full replacement
                    logger.warning(f"Keyword optimizer: {product['name']}/{platform} — ALL keywords generic, full AI replacement")
                    ai_keywords = await generate_keywords_for_product(product, platform)
                    if ai_keywords:
                        keywords[platform] = ai_keywords
                        logger.info(f"Keyword optimizer: {product['name']}/{platform} — replaced with {len(ai_keywords)} AI keywords: {ai_keywords[:5]}...")
                        updated = True

            if updated:
                supabase.table('products').update({'keywords': keywords}).eq('id', product['id']).execute()
                logger.info(f"Keyword optimizer: saved updated keywords for {product['name']}")

    except Exception as e:
        logger.error(f"Keyword optimizer error: {e}", exc_info=True)


async def run_keyword_cleanup():
    """One-time cleanup: check ALL products and replace generic keywords with AI-generated ones.
    Also clears seen_posts for a fresh start."""
    logger.info("=== ONE-TIME KEYWORD CLEANUP STARTING ===")
    try:
        from services.database import supabase

        products = supabase.table('products').select('*').execute()
        results = []

        for product in products.data:
            keywords = product.get('keywords', {})
            if not keywords:
                continue

            product_result = {'name': product.get('name'), 'changes': {}}
            updated = False

            for platform, kw_list in keywords.items():
                if not isinstance(kw_list, list) or not kw_list:
                    continue

                good, filtered_out = filter_keywords(kw_list)
                if not filtered_out:
                    product_result['changes'][platform] = 'all keywords quality, no changes'
                    continue

                old_keywords = kw_list[:]
                ai_keywords = await generate_keywords_for_product(product, platform)

                if ai_keywords:
                    # Merge good existing + AI-generated, dedup
                    existing_lower = {k.lower() for k in good}
                    new_ones = [k for k in ai_keywords if k.lower() not in existing_lower]
                    keywords[platform] = (good + new_ones)[:20]  # cap at 20
                    updated = True
                    product_result['changes'][platform] = {
                        'removed_generic': filtered_out,
                        'kept': good,
                        'ai_generated': new_ones[:10],
                        'total': len(keywords[platform])
                    }
                elif good:
                    keywords[platform] = good
                    updated = True
                    product_result['changes'][platform] = {
                        'removed_generic': filtered_out,
                        'kept': good,
                    }

            if updated:
                supabase.table('products').update({'keywords': keywords}).eq('id', product['id']).execute()
                logger.info(f"Cleanup: saved updated keywords for {product.get('name')}")

            results.append(product_result)

        # Clear seen_posts for fresh start
        seen_res = supabase.table('seen_posts').delete().neq('platform', '__never__').execute()
        cleared = len(seen_res.data) if seen_res.data else 0
        logger.info(f"Cleanup: cleared {cleared} seen_posts")

        logger.info("=== ONE-TIME KEYWORD CLEANUP COMPLETE ===")
        return {'products': results, 'seen_posts_cleared': cleared}

    except Exception as e:
        logger.error(f"Keyword cleanup error: {e}", exc_info=True)
        return {'error': str(e)}
