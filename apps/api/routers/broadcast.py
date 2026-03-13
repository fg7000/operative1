"""
Broadcast router for Operative1 API.

Handles scheduling and posting original content (text + images) from brand accounts.

Endpoints:
- POST /broadcast/create — Create new broadcast post (draft or scheduled)
- GET /broadcast/list — List broadcasts for a product (paginated)
- PATCH /broadcast/{id} — Update draft/scheduled post
- DELETE /broadcast/{id} — Delete draft/scheduled post
- POST /broadcast/{id}/post-now — Mark as ready_to_post for extension
- POST /broadcast/{id}/mark-posted — Called by frontend after extension posts
- POST /broadcast/{id}/amplify — Trigger amplification campaign
- POST /broadcast/upload-media — Upload media to Supabase Storage
- POST /broadcast/suggest-media — AI recommends ideal media type
- POST /broadcast/{id}/cross-post — Create adapted versions for other platforms
"""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, timezone
import logging
import uuid
import os
import httpx

from services.auth import get_current_user, verify_product_ownership
from services.database import supabase
from services.media_validator import validate_media, get_magic_bytes_type, PLATFORM_LIMITS

router = APIRouter()
logger = logging.getLogger(__name__)

# Content length limits per platform
CONTENT_LIMITS = {
    'twitter': 280,
    'reddit': 300,  # Title limit
    'linkedin': 3000,
    'hn': 2000,
}


class CreateBroadcastRequest(BaseModel):
    product_id: str
    platform: str
    content: str
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    scheduled_at: Optional[datetime] = None

    @validator('platform')
    def validate_platform(cls, v):
        allowed = ['twitter', 'reddit', 'linkedin', 'hn']
        if v not in allowed:
            raise ValueError(f'Platform must be one of: {allowed}')
        return v

    @validator('content')
    def validate_content(cls, v, values):
        if not v or not v.strip():
            raise ValueError('Content cannot be empty')
        platform = values.get('platform', 'twitter')
        limit = CONTENT_LIMITS.get(platform, 280)
        if len(v) > limit:
            raise ValueError(f'Content exceeds {platform} limit of {limit} characters')
        return v


class UpdateBroadcastRequest(BaseModel):
    content: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    scheduled_at: Optional[datetime] = None

    @validator('content')
    def validate_content(cls, v):
        if v is not None and not v.strip():
            raise ValueError('Content cannot be empty')
        return v


class MarkPostedRequest(BaseModel):
    external_id: str
    external_url: str


class CrossPostRequest(BaseModel):
    target_platforms: List[str]

    @validator('target_platforms')
    def validate_platforms(cls, v):
        allowed = ['twitter', 'reddit', 'linkedin', 'hn']
        for p in v:
            if p not in allowed:
                raise ValueError(f'Invalid platform: {p}')
        return v


class SuggestMediaRequest(BaseModel):
    content: str
    platform: str


class RecycleContentRequest(BaseModel):
    template_text: str
    tags: Optional[List[str]] = []


@router.post("/create")
async def create_broadcast(
    body: CreateBroadcastRequest,
    user_id: str = Depends(get_current_user)
):
    """Create a new broadcast post (draft or scheduled)."""
    await verify_product_ownership(user_id, body.product_id)

    # Determine initial status
    status = 'scheduled' if body.scheduled_at else 'draft'

    row = {
        'id': str(uuid.uuid4()),
        'product_id': body.product_id,
        'user_id': user_id,
        'platform': body.platform,
        'content': body.content,
        'media_url': body.media_url,
        'media_type': body.media_type,
        'scheduled_at': body.scheduled_at.isoformat() if body.scheduled_at else None,
        'status': status,
    }

    try:
        res = supabase.table('broadcast_posts').insert(row).execute()
        logger.info(f"Created broadcast {row['id']} for product {body.product_id}")
        return res.data[0] if res.data else {'error': 'Insert failed'}
    except Exception as e:
        logger.error(f"Failed to create broadcast: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create broadcast: {e}")


@router.get("/list")
async def list_broadcasts(
    product_id: str,
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: str = Depends(get_current_user)
):
    """List broadcasts for a product (paginated)."""
    await verify_product_ownership(user_id, product_id)

    query = supabase.table('broadcast_posts').select('*', count='exact') \
        .eq('product_id', product_id) \
        .order('created_at', desc=True) \
        .range(offset, offset + limit - 1)

    if status:
        query = query.eq('status', status)

    try:
        res = query.execute()
        return {
            'items': res.data or [],
            'total': res.count or 0,
            'limit': limit,
            'offset': offset,
        }
    except Exception as e:
        logger.error(f"Failed to list broadcasts: {e}")
        raise HTTPException(status_code=500, detail="Failed to list broadcasts")


@router.get("/{broadcast_id}")
async def get_broadcast(
    broadcast_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get a single broadcast by ID."""
    res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    await verify_product_ownership(user_id, res.data['product_id'])
    return res.data


@router.patch("/{broadcast_id}")
async def update_broadcast(
    broadcast_id: str,
    body: UpdateBroadcastRequest,
    user_id: str = Depends(get_current_user)
):
    """Update a draft or scheduled broadcast."""
    # Get existing broadcast
    res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    broadcast = res.data
    await verify_product_ownership(user_id, broadcast['product_id'])

    # Only allow updates to draft/scheduled
    if broadcast['status'] not in ('draft', 'scheduled'):
        raise HTTPException(status_code=400, detail="Cannot edit a posted broadcast")

    # Validate content length if updating content
    if body.content:
        platform = broadcast['platform']
        limit = CONTENT_LIMITS.get(platform, 280)
        if len(body.content) > limit:
            raise HTTPException(status_code=400, detail=f"Content exceeds {platform} limit of {limit} characters")

    update_data = {}
    if body.content is not None:
        update_data['content'] = body.content
    if body.media_url is not None:
        update_data['media_url'] = body.media_url
    if body.media_type is not None:
        update_data['media_type'] = body.media_type
    if body.scheduled_at is not None:
        update_data['scheduled_at'] = body.scheduled_at.isoformat()
        update_data['status'] = 'scheduled'

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        updated = supabase.table('broadcast_posts').update(update_data).eq('id', broadcast_id).execute()
        return updated.data[0] if updated.data else {'error': 'Update failed'}
    except Exception as e:
        logger.error(f"Failed to update broadcast: {e}")
        raise HTTPException(status_code=500, detail="Failed to update broadcast")


@router.delete("/{broadcast_id}")
async def delete_broadcast(
    broadcast_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete a draft or scheduled broadcast."""
    res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    broadcast = res.data
    await verify_product_ownership(user_id, broadcast['product_id'])

    # Only allow deletion of draft/scheduled
    if broadcast['status'] not in ('draft', 'scheduled'):
        raise HTTPException(status_code=400, detail="Cannot delete a posted broadcast")

    try:
        supabase.table('broadcast_posts').delete().eq('id', broadcast_id).execute()
        logger.info(f"Deleted broadcast {broadcast_id}")
        return {'status': 'deleted'}
    except Exception as e:
        logger.error(f"Failed to delete broadcast: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete broadcast")


@router.post("/{broadcast_id}/post-now")
async def post_now(
    broadcast_id: str,
    user_id: str = Depends(get_current_user)
):
    """Mark a broadcast as ready_to_post for the extension to handle."""
    res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    broadcast = res.data
    await verify_product_ownership(user_id, broadcast['product_id'])

    if broadcast['status'] not in ('draft', 'scheduled'):
        raise HTTPException(status_code=400, detail=f"Cannot post broadcast with status: {broadcast['status']}")

    try:
        supabase.table('broadcast_posts').update({
            'status': 'ready_to_post'
        }).eq('id', broadcast_id).execute()

        # Return full broadcast data for the extension
        updated = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
        return updated.data
    except Exception as e:
        logger.error(f"Failed to mark broadcast ready: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark broadcast ready")


@router.post("/{broadcast_id}/mark-posted")
async def mark_posted(
    broadcast_id: str,
    body: MarkPostedRequest,
    user_id: str = Depends(get_current_user)
):
    """Called by frontend after extension successfully posts."""
    res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    broadcast = res.data
    await verify_product_ownership(user_id, broadcast['product_id'])

    try:
        supabase.table('broadcast_posts').update({
            'status': 'posted',
            'posted_at': datetime.now(timezone.utc).isoformat(),
            'external_id': body.external_id,
            'external_url': body.external_url,
        }).eq('id', broadcast_id).execute()

        logger.info(f"Marked broadcast {broadcast_id} as posted: {body.external_url}")
        return {'status': 'posted', 'external_url': body.external_url}
    except Exception as e:
        logger.error(f"Failed to mark broadcast posted: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark broadcast posted")


@router.post("/{broadcast_id}/mark-failed")
async def mark_failed(
    broadcast_id: str,
    error_message: str = Query(...),
    user_id: str = Depends(get_current_user)
):
    """Called by frontend if extension fails to post."""
    res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    broadcast = res.data
    await verify_product_ownership(user_id, broadcast['product_id'])

    try:
        supabase.table('broadcast_posts').update({
            'status': 'failed',
            'error_message': error_message,
        }).eq('id', broadcast_id).execute()

        logger.info(f"Marked broadcast {broadcast_id} as failed: {error_message}")
        return {'status': 'failed', 'error_message': error_message}
    except Exception as e:
        logger.error(f"Failed to mark broadcast failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark broadcast failed")


@router.post("/{broadcast_id}/amplify")
async def amplify_broadcast(
    broadcast_id: str,
    user_id: str = Depends(get_current_user)
):
    """Trigger amplification campaign for a posted broadcast."""
    res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    broadcast = res.data
    await verify_product_ownership(user_id, broadcast['product_id'])

    if broadcast['status'] != 'posted':
        raise HTTPException(status_code=400, detail="Can only amplify posted broadcasts")

    if broadcast['amplification_status'] == 'active':
        raise HTTPException(status_code=400, detail="Amplification already in progress")

    # Mark as active and trigger amplification
    try:
        supabase.table('broadcast_posts').update({
            'amplification_status': 'active'
        }).eq('id', broadcast_id).execute()

        # Run amplification asynchronously
        from services.amplifier import run_amplification
        result = await run_amplification(broadcast_id)

        return {
            'status': 'amplification_started',
            'conversations_found': result.get('conversations_found', 0),
            'replies_queued': result.get('replies_queued', 0),
        }
    except Exception as e:
        logger.error(f"Failed to start amplification: {e}")
        # Reset status on failure
        supabase.table('broadcast_posts').update({
            'amplification_status': 'none'
        }).eq('id', broadcast_id).execute()
        raise HTTPException(status_code=500, detail=f"Failed to start amplification: {e}")


@router.post("/upload-media")
async def upload_media(
    file: UploadFile = File(...),
    platform: str = Query("twitter"),
    product_id: str = Query(...),
    user_id: str = Depends(get_current_user)
):
    """Upload media to Supabase Storage for use in broadcasts."""
    await verify_product_ownership(user_id, product_id)

    # Read file content
    content = await file.read()

    # Validate using magic bytes
    detected_type = get_magic_bytes_type(content)
    if not detected_type:
        raise HTTPException(status_code=400, detail="Could not detect file type from content")

    # Get file extension
    extension = file.filename.split('.')[-1].lower() if file.filename else ''

    # Validate media for platform
    validation = validate_media(content, detected_type, extension, platform)
    if not validation['valid']:
        raise HTTPException(status_code=400, detail=validation['error'])

    # Generate unique path
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"{product_id}/{timestamp}_{uuid.uuid4().hex[:8]}.{extension}"

    try:
        # Upload to Supabase Storage
        storage = supabase.storage.from_('broadcast-media')
        storage.upload(filename, content, {'content-type': detected_type})

        # Get public URL
        public_url = storage.get_public_url(filename)

        logger.info(f"Uploaded media: {filename}")
        return {
            'url': public_url,
            'media_type': detected_type,
            'filename': filename,
            'size_bytes': len(content),
        }
    except Exception as e:
        logger.error(f"Failed to upload media: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload media: {e}")


@router.post("/suggest-media")
async def suggest_media(
    body: SuggestMediaRequest,
    user_id: str = Depends(get_current_user)
):
    """AI recommends ideal media type for the content."""
    from services.agent_prompts import MEDIA_ADVISOR_PROMPT

    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")

    prompt = MEDIA_ADVISOR_PROMPT.format(
        content=body.content,
        platform=body.platform
    )

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
            response_content = res.json()['choices'][0]['message']['content']

            # Parse JSON from response
            import json
            clean = response_content
            if '```' in clean:
                clean = '\n'.join(line for line in clean.split('\n') if '```' not in line)
            first = clean.find('{')
            last = clean.rfind('}')
            if first != -1 and last > first:
                suggestion = json.loads(clean[first:last + 1])
                return suggestion

            raise HTTPException(status_code=500, detail="Could not parse AI response")

    except Exception as e:
        logger.error(f"Failed to get media suggestion: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get media suggestion: {e}")


@router.post("/{broadcast_id}/cross-post")
async def cross_post(
    broadcast_id: str,
    body: CrossPostRequest,
    user_id: str = Depends(get_current_user)
):
    """Create adapted versions for other platforms."""
    res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    broadcast = res.data
    await verify_product_ownership(user_id, broadcast['product_id'])

    from services.agent_prompts import CROSS_POST_ADAPTER_PROMPT

    OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured")

    # Create or reuse campaign_id
    campaign_id = broadcast.get('campaign_id') or str(uuid.uuid4())

    # Update original with campaign_id if not set
    if not broadcast.get('campaign_id'):
        supabase.table('broadcast_posts').update({
            'campaign_id': campaign_id
        }).eq('id', broadcast_id).execute()

    created_posts = []
    media_warnings = []

    for target_platform in body.target_platforms:
        if target_platform == broadcast['platform']:
            continue  # Skip same platform

        # Adapt content via AI
        prompt = CROSS_POST_ADAPTER_PROMPT.format(
            source_platform=broadcast['platform'],
            target_platform=target_platform,
            content=broadcast['content']
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.post(
                    'https://openrouter.ai/api/v1/chat/completions',
                    headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                    json={
                        'model': 'anthropic/claude-haiku-4-5',
                        'messages': [{'role': 'user', 'content': prompt}],
                        'max_tokens': 1000
                    }
                )
                adapted_content = res.json()['choices'][0]['message']['content'].strip()

                # Validate length for target platform
                limit = CONTENT_LIMITS.get(target_platform, 280)
                if len(adapted_content) > limit:
                    adapted_content = adapted_content[:limit - 3] + '...'

                # Check media compatibility
                media_warning = None
                if broadcast.get('media_url') and broadcast.get('media_type'):
                    # Add media warning if aspect ratio might not be optimal
                    if target_platform == 'linkedin' and broadcast['platform'] == 'twitter':
                        media_warning = "LinkedIn posts perform 2x better with 1:1 images. Consider cropping to square."
                    if media_warning:
                        media_warnings.append({'platform': target_platform, 'warning': media_warning})

                # Create new broadcast post
                new_post = {
                    'id': str(uuid.uuid4()),
                    'product_id': broadcast['product_id'],
                    'user_id': user_id,
                    'campaign_id': campaign_id,
                    'platform': target_platform,
                    'content': adapted_content,
                    'media_url': broadcast.get('media_url'),
                    'media_type': broadcast.get('media_type'),
                    'status': 'draft',
                }

                insert_res = supabase.table('broadcast_posts').insert(new_post).execute()
                if insert_res.data:
                    created_posts.append(insert_res.data[0])

        except Exception as e:
            logger.error(f"Failed to adapt content for {target_platform}: {e}")

    return {
        'campaign_id': campaign_id,
        'created_posts': created_posts,
        'media_warnings': media_warnings,
    }


@router.post("/{broadcast_id}/recycle")
async def recycle_as_template(
    broadcast_id: str,
    body: RecycleContentRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Recycle high-performing broadcast content as a reply template.

    Templates are stored on the product and can be used by the generator
    to inform tone and style of future replies.
    """
    res = supabase.table('broadcast_posts').select('*').eq('id', broadcast_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Broadcast not found")

    broadcast = res.data
    await verify_product_ownership(user_id, broadcast['product_id'])

    if broadcast['status'] != 'posted':
        raise HTTPException(status_code=400, detail="Can only recycle posted broadcasts")

    # Get current product templates
    product_res = supabase.table('products').select('reply_templates').eq('id', broadcast['product_id']).single().execute()
    if not product_res.data:
        raise HTTPException(status_code=404, detail="Product not found")

    existing_templates = product_res.data.get('reply_templates') or []

    # Create new template
    new_template = {
        'id': str(uuid.uuid4()),
        'text': body.template_text,
        'tags': body.tags,
        'source_broadcast_id': broadcast_id,
        'platform': broadcast['platform'],
        'created_at': datetime.now(timezone.utc).isoformat(),
    }

    # Add to templates (limit to 50 templates per product)
    updated_templates = [new_template] + existing_templates[:49]

    try:
        supabase.table('products').update({
            'reply_templates': updated_templates
        }).eq('id', broadcast['product_id']).execute()

        logger.info(f"Recycled broadcast {broadcast_id} as template for product {broadcast['product_id']}")
        return {
            'template_id': new_template['id'],
            'total_templates': len(updated_templates),
        }
    except Exception as e:
        logger.error(f"Failed to recycle broadcast: {e}")
        raise HTTPException(status_code=500, detail="Failed to save template")


@router.get("/templates/{product_id}")
async def list_templates(
    product_id: str,
    user_id: str = Depends(get_current_user)
):
    """List all reply templates for a product."""
    await verify_product_ownership(user_id, product_id)

    product_res = supabase.table('products').select('reply_templates').eq('id', product_id).single().execute()
    if not product_res.data:
        raise HTTPException(status_code=404, detail="Product not found")

    templates = product_res.data.get('reply_templates') or []
    return {'templates': templates, 'count': len(templates)}


@router.delete("/templates/{product_id}/{template_id}")
async def delete_template(
    product_id: str,
    template_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete a reply template."""
    await verify_product_ownership(user_id, product_id)

    product_res = supabase.table('products').select('reply_templates').eq('id', product_id).single().execute()
    if not product_res.data:
        raise HTTPException(status_code=404, detail="Product not found")

    existing_templates = product_res.data.get('reply_templates') or []
    updated_templates = [t for t in existing_templates if t.get('id') != template_id]

    if len(updated_templates) == len(existing_templates):
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        supabase.table('products').update({
            'reply_templates': updated_templates
        }).eq('id', product_id).execute()

        return {'status': 'deleted', 'remaining': len(updated_templates)}
    except Exception as e:
        logger.error(f"Failed to delete template: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete template")
