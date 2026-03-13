from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pipelines.scheduler import start_scheduler
from routers import products, queue, posting, metrics, onboarding, settings, analytics, broadcast
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migrations():
    """Run ALTER TABLE migrations using direct Postgres connection via Supavisor."""
    try:
        import psycopg2
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            logger.info("No DATABASE_URL set, skipping migrations")
            return False

        conn = psycopg2.connect(db_url, connect_timeout=10)
        cur = conn.cursor()

        migrations = [
            'ALTER TABLE reply_queue ADD COLUMN IF NOT EXISTS relevance_reason TEXT;',
            'ALTER TABLE reply_queue ADD COLUMN IF NOT EXISTS original_language TEXT;',
            'ALTER TABLE reply_queue ADD COLUMN IF NOT EXISTS translated_content TEXT;',
            # Performance indexes for multi-product filtering
            'CREATE INDEX IF NOT EXISTS idx_reply_queue_product_status ON reply_queue(product_id, status);',
            'CREATE INDEX IF NOT EXISTS idx_reply_queue_product_created ON reply_queue(product_id, created_at DESC);',
            'CREATE INDEX IF NOT EXISTS idx_products_user ON products(user_id);',
            # Broadcast posts table for scheduling and posting original content
            '''CREATE TABLE IF NOT EXISTS broadcast_posts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                product_id UUID NOT NULL REFERENCES products(id),
                user_id UUID NOT NULL,
                campaign_id UUID,
                platform TEXT NOT NULL,
                content TEXT NOT NULL,
                media_url TEXT,
                media_type TEXT,
                media_id TEXT,
                scheduled_at TIMESTAMPTZ,
                posted_at TIMESTAMPTZ,
                status TEXT NOT NULL DEFAULT 'draft',
                external_id TEXT,
                external_url TEXT,
                engagement_metrics JSONB,
                amplification_status TEXT DEFAULT 'none',
                amplification_replies_count INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );''',
            'CREATE INDEX IF NOT EXISTS idx_broadcast_product_status ON broadcast_posts(product_id, status);',
            'CREATE INDEX IF NOT EXISTS idx_broadcast_product_scheduled ON broadcast_posts(product_id, scheduled_at);',
            'CREATE INDEX IF NOT EXISTS idx_broadcast_campaign ON broadcast_posts(campaign_id);',
            # Link replies to broadcasts for amplification tracking
            'ALTER TABLE reply_queue ADD COLUMN IF NOT EXISTS amplifies_broadcast_id UUID;',
            # Reply templates for content recycling (stored on products)
            'ALTER TABLE products ADD COLUMN IF NOT EXISTS reply_templates JSONB DEFAULT \'[]\'::jsonb;',
        ]

        for sql in migrations:
            logger.info(f"Migration: {sql}")
            cur.execute(sql)

        conn.commit()
        cur.close()
        conn.close()
        logger.info("All migrations completed successfully")
        return True
    except Exception as e:
        logger.error(f"Migration error: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrated = run_migrations()
    if migrated:
        from services.database import set_extra_columns_exist
        set_extra_columns_exist(True)
    start_scheduler()
    yield

app = FastAPI(title="Operative1 API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(queue.router, prefix="/queue", tags=["queue"])
app.include_router(posting.router, prefix="/posting", tags=["posting"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(onboarding.router, prefix="/onboarding", tags=["onboarding"])
app.include_router(settings.router, prefix="/settings", tags=["settings"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(broadcast.router, prefix="/broadcast", tags=["broadcast"])

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/migrate")
def migrate():
    """Manually trigger migrations."""
    success = run_migrations()
    if success:
        from services.database import set_extra_columns_exist
        set_extra_columns_exist(True)
        return {"status": "migrations completed"}
    return {"status": "migrations failed or no DATABASE_URL"}

@app.post("/keyword-cleanup")
async def keyword_cleanup():
    """One-time cleanup: replace generic keywords with AI-generated ones for all products."""
    from services.optimizer import run_keyword_cleanup
    result = await run_keyword_cleanup()
    return result
