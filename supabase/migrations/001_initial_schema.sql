CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  description TEXT,
  value_prop TEXT NOT NULL,
  system_prompt TEXT NOT NULL,
  model TEXT DEFAULT 'anthropic/claude-opus-4-5',
  keywords JSONB NOT NULL,
  target_subreddits TEXT[],
  tone TEXT DEFAULT 'helpful-technical',
  auto_post JSONB DEFAULT '{"twitter":false,"reddit":false,"linkedin":false,"hn":false}',
  max_daily_replies JSONB DEFAULT '{"twitter":5,"reddit":3,"linkedin":3,"hn":1}',
  forbidden_phrases TEXT[],
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE social_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES products(id) ON DELETE CASCADE,
  platform TEXT NOT NULL,
  handle TEXT NOT NULL,
  credentials_encrypted JSONB,
  status TEXT DEFAULT 'active',
  account_age_days INTEGER,
  karma_score INTEGER,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(product_id, platform)
);

CREATE TABLE media_assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES products(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  storage_url TEXT NOT NULL,
  media_type TEXT NOT NULL,
  tags TEXT[],
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE seen_posts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  platform TEXT NOT NULL,
  external_id TEXT NOT NULL,
  external_url TEXT,
  author TEXT,
  content TEXT,
  engagement_score INTEGER,
  discovered_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(platform, external_id)
);

CREATE TABLE reply_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES products(id),
  seen_post_id UUID REFERENCES seen_posts(id),
  platform TEXT NOT NULL,
  original_content TEXT NOT NULL,
  original_url TEXT,
  original_author TEXT,
  relevance_score FLOAT,
  draft_reply TEXT,
  confidence_score FLOAT,
  mentions_product BOOLEAN,
  media_asset_id UUID REFERENCES media_assets(id),
  status TEXT DEFAULT 'pending',
  edited_reply TEXT,
  rejection_reason TEXT,
  posted_at TIMESTAMPTZ,
  engagement_metrics JSONB,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE daily_stats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id UUID REFERENCES products(id),
  platform TEXT NOT NULL,
  date DATE NOT NULL,
  posts_discovered INTEGER DEFAULT 0,
  posts_relevant INTEGER DEFAULT 0,
  replies_drafted INTEGER DEFAULT 0,
  replies_approved INTEGER DEFAULT 0,
  replies_posted INTEGER DEFAULT 0,
  replies_rejected INTEGER DEFAULT 0,
  total_likes INTEGER DEFAULT 0,
  total_replies INTEGER DEFAULT 0,
  total_impressions INTEGER DEFAULT 0,
  UNIQUE(product_id, platform, date)
);
