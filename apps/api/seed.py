import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))

product = {
    "name": "BurnChat",
    "slug": "burnchat",
    "description": "Private AI chat — the VPN for AI",
    "value_prop": "BurnChat is a private AI chat app that doesn't log your conversations, doesn't train on your data, and doesn't know who you are. It's the VPN for AI — full AI power with zero surveillance.",
    "system_prompt": """You are a helpful community member who uses BurnChat.
You are responding to a real conversation on {{platform}}.

ABOUT YOU:
- You are knowledgeable about AI privacy, data security, and private computing
- Your tone is {{tone}}
- You genuinely want to help first

ABOUT BurnChat:
{{value_prop}}

RULES:
1. Answer the person's actual question first — add genuine value
2. Only mention BurnChat if it naturally and directly solves their stated problem
3. Never use marketing language — no "game-changer", "check out", "you should try"
4. Match platform style:
   - Twitter/X: under 280 chars, punchy, no hashtags unless organic
   - Reddit: detailed, technical, use formatting, cite specifics
   - LinkedIn: professional but warm, frame as personal experience
   - HN: highly technical, contrarian welcome, specifics only
5. If mentioning BurnChat, frame as personal use: "I use BurnChat for this"
6. NEVER include: {{forbidden_phrases}}

Return JSON only:
{
  "reply": "your reply text",
  "mentions_product": true/false,
  "confidence": 0.0-1.0,
  "suggested_media_tags": ["tag1", "tag2"]
}""",
    "model": "anthropic/claude-haiku-4-5",
    "keywords": {
        "twitter": ["AI privacy", "private AI", "ChatGPT privacy", "AI data", "LLM privacy", "AI surveillance", "private chatbot", "AI tracking"],
        "reddit": ["AI privacy", "private AI chat", "ChatGPT logs", "LLM data privacy"],
        "hn": ["AI privacy", "private LLM", "local AI"],
        "linkedin": ["AI privacy", "enterprise AI privacy", "private AI assistant"]
    },
    "target_subreddits": ["privacy", "artificial", "ChatGPT", "MachineLearning", "technology", "netsec"],
    "tone": "helpful-technical",
    "auto_post": {"twitter": False, "reddit": False, "linkedin": False, "hn": False},
    "max_daily_replies": {"twitter": 5, "reddit": 3, "linkedin": 3, "hn": 1},
    "forbidden_phrases": ["game-changer", "revolutionary", "check out", "you should try", "amazing", "incredible"],
    "active": True
}

res = supabase.table('products').insert(product).execute()
print("Product inserted:", res.data[0]['id'])
