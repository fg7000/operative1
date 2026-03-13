import os
import httpx
import json
import logging
import random
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
logger = logging.getLogger(__name__)


def sanitize_dashes(text: str) -> str:
    """Replace em dashes and en dashes with hyphens or commas."""
    # Replace em dash (—) and en dash (–) with comma-space for natural flow
    text = text.replace('—', ', ')
    text = text.replace('–', '-')
    # Clean up any double spaces or comma-comma
    text = text.replace('  ', ' ')
    text = text.replace(', ,', ',')
    return text.strip()


def get_mode_instructions(reply_mode: str, product_mention: str) -> str:
    """Get mode-specific instructions with product mention injected."""
    if reply_mode == 'helpful_expert':
        return "Be a genuinely helpful expert. Answer the question or add real value to the conversation. Do NOT mention the product at all. No name, no link, no handle. Be purely helpful. The goal is to build credibility, not sell. NEVER use em dashes or en dashes in your reply. Use commas, periods, or hyphens instead."
    elif reply_mode == 'soft_mention':
        return f"Be helpful and conversational. Weave in a brief, natural mention of our product as one option among others. When mentioning the product, write exactly: {product_mention}. Include this mention about 70% of the time. Don't make it the focus, just a friendly suggestion. Think 'oh btw, {product_mention} does this too' energy. NEVER use em dashes or en dashes in your reply. Use commas, periods, or hyphens instead."
    elif reply_mode == 'direct_pitch':
        return f"Be helpful but clearly recommend our product as a solution. When mentioning the product, write exactly: {product_mention}. ALWAYS include this mention. Explain why it fits the user's need. Keep it genuine and not salesy, more like a friend recommending something they actually use. NEVER use em dashes or en dashes in your reply. Use commas, periods, or hyphens instead."
    return ""

PLATFORM_LENGTH = {
    'twitter': "Your reply MUST be under 200 characters to leave room for the @mention and tweet link. Be punchy, direct, and conversational. 1-2 sentences max.",
    'reddit': "Be detailed and technical, 2-4 paragraphs is fine.",
    'linkedin': "Professional but concise, 2-3 sentences.",
    'hn': "Technical and specific, 1-3 sentences.",
}

def select_reply_mode(product: dict) -> str:
    dist = product.get('auto_post', {}).get('reply_mode_distribution', {
        'direct_pitch': 50, 'soft_mention': 35, 'helpful_expert': 15
    })
    modes = list(dist.keys())
    weights = [dist[m] for m in modes]
    return random.choices(modes, weights=weights, k=1)[0]


def get_product_mention(product: dict) -> str:
    """
    Get the product mention string based on the configured strategy.

    Strategies:
    - website: Use the website domain (e.g., burnchat.ai)
    - handle: Use the Twitter handle (e.g., @BurnChatAI)
    - mix: Randomly alternate (70% website, 30% handle)
    """
    strategy = product.get('mention_strategy', 'website')
    website_url = product.get('website_url', '')
    twitter_handle = product.get('twitter_handle', '')

    # Extract domain from URL (e.g., https://burnchat.ai -> burnchat.ai)
    domain = website_url
    if domain:
        domain = domain.replace('https://', '').replace('http://', '').rstrip('/')

    # Fallback to product name if neither is set
    if not domain and not twitter_handle:
        return product.get('name', 'our product')

    if strategy == 'website':
        return domain if domain else twitter_handle
    elif strategy == 'handle':
        return twitter_handle if twitter_handle else domain
    elif strategy == 'mix':
        # 70% website, 30% handle
        if random.random() < 0.7:
            return domain if domain else twitter_handle
        else:
            return twitter_handle if twitter_handle else domain

    return domain or twitter_handle or product.get('name', 'our product')


def post_process_mention(reply: str, product: dict, reply_mode: str, product_mention: str) -> str:
    """
    Post-process reply to ensure product mentions use the correct format.

    If the AI wrote the product name (e.g., "BurnChat") instead of the proper
    mention format (e.g., "burnchat.ai"), replace it.

    Skip this for helpful_expert mode since it shouldn't mention the product.
    """
    if reply_mode == 'helpful_expert':
        return reply

    product_name = product.get('name', '')
    if not product_name:
        return reply

    # Check if the product name appears but not the correct mention
    # Case-insensitive check
    if product_name.lower() in reply.lower() and product_mention.lower() not in reply.lower():
        # Replace product name with proper mention (case-insensitive)
        import re
        pattern = re.compile(re.escape(product_name), re.IGNORECASE)
        reply = pattern.sub(product_mention, reply)
        logger.info(f"Post-processed mention: replaced '{product_name}' with '{product_mention}'")

    return reply

def get_relevant_templates(product: dict, platform: str, max_templates: int = 3) -> list:
    """Get relevant reply templates to inform the generator's tone and style."""
    templates = product.get('reply_templates') or []
    if not templates:
        return []

    # Filter by platform and take most recent
    platform_templates = [t for t in templates if t.get('platform') == platform]
    if not platform_templates:
        platform_templates = templates  # Fall back to all templates

    # Return up to max_templates
    return platform_templates[:max_templates]


async def generate_reply(post: dict, product: dict, platform: str, custom_prompt: str = None) -> dict:
    reply_mode = select_reply_mode(product)
    product_mention = get_product_mention(product)
    logger.info(f"Selected reply mode: {reply_mode}, product mention: {product_mention}")

    system_prompt = product.get('system_prompt', '')
    system_prompt = system_prompt.replace('{{product_name}}', product['name'])
    system_prompt = system_prompt.replace('{{platform}}', platform)
    system_prompt = system_prompt.replace('{{value_prop}}', product.get('value_prop', ''))
    system_prompt = system_prompt.replace('{{tone}}', product.get('tone', 'helpful'))
    forbidden = ', '.join(product.get('forbidden_phrases') or [])
    system_prompt = system_prompt.replace('{{forbidden_phrases}}', forbidden)

    # Add template examples to help inform tone and style
    templates = get_relevant_templates(product, platform)
    template_section = ""
    if templates:
        examples = "\n".join([f"- {t['text']}" for t in templates])
        template_section = f"\n\nHere are examples of our brand voice and style:\n{examples}\n\nMatch this tone and style, but create original content for this specific reply."

    mode_instruction = get_mode_instructions(reply_mode, product_mention)
    length_instruction = PLATFORM_LENGTH.get(platform, "Be concise and natural.")

    # If the post has been translated, reply in the original language
    original_language = post.get('original_language')
    language_instruction = ""
    if original_language and original_language != 'en':
        language_instruction = f"\n\nIMPORTANT: The original post is in {original_language}. Write your reply in {original_language}, NOT in English."

    # Use custom prompt if provided (for amplification replies)
    if custom_prompt:
        user_message = custom_prompt
    else:
        user_message = f"""Reply to this {platform} post. {mode_instruction}

{length_instruction}

Keep it natural and conversational — no hashtags, no hard sell, no generic filler.{language_instruction}{template_section}

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
            parsed['product_mention'] = product_mention
            # Sanitize dashes from the reply
            if 'reply' in parsed:
                parsed['reply'] = sanitize_dashes(parsed['reply'])
                # Post-process to ensure correct mention format
                parsed['reply'] = post_process_mention(parsed['reply'], product, reply_mode, product_mention)
            logger.info(f"Generator parsed reply: {parsed}")
            return parsed
        except Exception as e:
            logger.error(f"Generator parse error: {e}")
            logger.error(f"Generator raw content: {res.text[:500]}")
            return None
