'use client'
import { useEffect, useState, useRef } from 'react'
import { useProducts } from '@/lib/product-context'
import { PLATFORM_COLORS, API_URL } from '@/lib/constants'
import { apiFetch } from '@/lib/api'

const EXTENSION_ID = process.env.NEXT_PUBLIC_EXTENSION_ID || ''

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  draft: { bg: '#f5f5f5', color: '#666' },
  scheduled: { bg: '#e3f2fd', color: '#1565c0' },
  ready_to_post: { bg: '#fff3e0', color: '#e65100' },
  posting: { bg: '#fff8e1', color: '#f57c00' },
  posted: { bg: '#e8f5e9', color: '#2e7d32' },
  failed: { bg: '#ffebee', color: '#c62828' },
}

const CONTENT_LIMITS: Record<string, number> = {
  twitter: 280,
  reddit: 300,
  linkedin: 3000,
  hn: 2000,
}

type Broadcast = {
  id: string
  product_id: string
  platform: string
  content: string
  media_url: string | null
  media_type: string | null
  scheduled_at: string | null
  posted_at: string | null
  status: string
  external_id: string | null
  external_url: string | null
  engagement_metrics: Record<string, any> | null
  amplification_status: string
  amplification_replies_count: number
  error_message: string | null
  created_at: string
}

type MediaSuggestion = {
  recommended_media_type: string
  description: string
  dimensions: string
  style_notes: string
  platform_tip: string
  alt_text_suggestion: string
}

export default function BroadcastPage() {
  const { selectedProduct, selectedProductId, loading: productsLoading } = useProducts()
  const [broadcasts, setBroadcasts] = useState<Broadcast[]>([])
  const [loading, setLoading] = useState(true)
  const [extensionConnected, setExtensionConnected] = useState<boolean | null>(null)

  // Create modal state
  const [showCreate, setShowCreate] = useState(false)
  const [createPlatform, setCreatePlatform] = useState('twitter')
  const [createContent, setCreateContent] = useState('')
  const [createMediaUrl, setCreateMediaUrl] = useState<string | null>(null)
  const [createMediaType, setCreateMediaType] = useState<string | null>(null)
  const [createScheduled, setCreateScheduled] = useState(false)
  const [createScheduleTime, setCreateScheduleTime] = useState('')
  const [creating, setCreating] = useState(false)

  // Media upload state
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Media suggestion state
  const [suggesting, setSuggesting] = useState(false)
  const [mediaSuggestion, setMediaSuggestion] = useState<MediaSuggestion | null>(null)

  // Action state
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionSuccess, setActionSuccess] = useState<string | null>(null)

  // Recycle modal state
  const [showRecycle, setShowRecycle] = useState<string | null>(null)
  const [recycleText, setRecycleText] = useState('')
  const [recycleTags, setRecycleTags] = useState('')
  const [recycling, setRecycling] = useState(false)

  // Polling for ready_to_post
  const pollRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (selectedProductId) {
      fetchBroadcasts()
    }
    checkExtension()

    // Poll for ready_to_post items every 5 seconds
    pollRef.current = setInterval(() => {
      if (selectedProductId && extensionConnected) {
        checkReadyToPost()
      }
    }, 5000)

    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [selectedProductId, extensionConnected])

  async function checkExtension(): Promise<boolean> {
    if (!EXTENSION_ID || typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {
      setExtensionConnected(false)
      return false
    }
    try {
      const response = await new Promise<{ success: boolean }>((resolve) => {
        chrome.runtime.sendMessage(EXTENSION_ID, { action: 'ping' }, (resp) => {
          if (chrome.runtime.lastError || !resp) resolve({ success: false })
          else resolve(resp)
        })
      })
      setExtensionConnected(response.success)
      return response.success
    } catch {
      setExtensionConnected(false)
      return false
    }
  }

  async function fetchBroadcasts() {
    if (!selectedProductId) return
    setLoading(true)
    try {
      const data = await apiFetch<{items?: Broadcast[]}>(`/broadcast/list?product_id=${selectedProductId}&limit=100`)
      setBroadcasts(Array.isArray(data?.items) ? data.items : [])
    } catch (e) {
      console.error('Failed to fetch broadcasts:', e)
      setBroadcasts([])
    } finally {
      setLoading(false)
    }
  }

  async function checkReadyToPost() {
    // Find any ready_to_post broadcasts and post them via extension
    const readyItems = broadcasts.filter(b => b.status === 'ready_to_post')
    for (const item of readyItems) {
      await postViaExtension(item)
    }
  }

  async function postViaExtension(broadcast: Broadcast) {
    if (!extensionConnected) return

    setActionLoading(broadcast.id)
    setActionError(null)

    try {
      const result = await new Promise<{ success: boolean; tweet_id?: string; error?: string }>((resolve) => {
        chrome.runtime.sendMessage(EXTENSION_ID, {
          action: 'post_broadcast',
          content: broadcast.content,
          media_url: broadcast.media_url,
        }, (resp) => {
          if (chrome.runtime.lastError || !resp) {
            resolve({ success: false, error: 'Extension communication failed' })
          } else {
            resolve(resp)
          }
        })
      })

      if (result.success && result.tweet_id) {
        // Mark as posted
        await apiFetch(`/broadcast/${broadcast.id}/mark-posted`, {
          method: 'POST',
          body: JSON.stringify({
            external_id: result.tweet_id,
            external_url: `https://x.com/i/status/${result.tweet_id}`,
          }),
        })
        setActionSuccess(`Posted! View at x.com/i/status/${result.tweet_id}`)
        fetchBroadcasts()
      } else {
        // Mark as failed
        await apiFetch(`/broadcast/${broadcast.id}/mark-failed?error_message=${encodeURIComponent(result.error || 'Unknown error')}`, {
          method: 'POST',
        })
        setActionError(result.error || 'Failed to post')
        fetchBroadcasts()
      }
    } catch (e) {
      setActionError('Failed to communicate with extension')
    } finally {
      setActionLoading(null)
    }
  }

  async function handleCreate() {
    if (!selectedProductId || !createContent.trim()) return
    setCreating(true)
    setActionError(null)

    try {
      const body: any = {
        product_id: selectedProductId,
        platform: createPlatform,
        content: createContent,
        media_url: createMediaUrl,
        media_type: createMediaType,
      }

      if (createScheduled && createScheduleTime) {
        body.scheduled_at = new Date(createScheduleTime).toISOString()
      }

      await apiFetch(`/broadcast/create`, {
        method: 'POST',
        body: JSON.stringify(body),
      })

      setShowCreate(false)
      resetCreateForm()
      fetchBroadcasts()
      setActionSuccess('Broadcast created!')
    } catch (e: any) {
      setActionError(e.message)
    } finally {
      setCreating(false)
    }
  }

  function resetCreateForm() {
    setCreatePlatform('twitter')
    setCreateContent('')
    setCreateMediaUrl(null)
    setCreateMediaType(null)
    setCreateScheduled(false)
    setCreateScheduleTime('')
    setMediaSuggestion(null)
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !selectedProductId) return

    setUploading(true)
    setActionError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      // Get auth token for file upload (can't use apiFetch with FormData)
      const { createClient } = await import('@/lib/supabase-client')
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()

      const headers: HeadersInit = {}
      if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`
      }

      const res = await fetch(`${API_URL}/broadcast/upload-media?platform=${createPlatform}&product_id=${selectedProductId}`, {
        method: 'POST',
        headers,
        body: formData,
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Upload failed')
      }

      const data = await res.json()
      setCreateMediaUrl(data.url)
      setCreateMediaType(data.media_type)
    } catch (e: any) {
      setActionError(e.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleSuggestMedia() {
    if (!createContent.trim()) return
    setSuggesting(true)

    try {
      const data = await apiFetch<MediaSuggestion>(`/broadcast/suggest-media`, {
        method: 'POST',
        body: JSON.stringify({ content: createContent, platform: createPlatform }),
      })
      setMediaSuggestion(data)
    } catch (e: any) {
      setActionError(e.message)
    } finally {
      setSuggesting(false)
    }
  }

  async function handlePostNow(id: string) {
    setActionLoading(id)
    setActionError(null)

    try {
      const broadcast = await apiFetch<Broadcast>(`/broadcast/${id}/post-now`, { method: 'POST' })
      // Update local state
      setBroadcasts(prev => prev.map(b => b.id === id ? broadcast : b))

      // Post via extension immediately
      await postViaExtension(broadcast)
    } catch (e: any) {
      setActionError(e.message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleAmplify(id: string) {
    setActionLoading(id)
    setActionError(null)

    try {
      const data = await apiFetch<{conversations_found: number, replies_queued: number}>(`/broadcast/${id}/amplify`, { method: 'POST' })
      setActionSuccess(`Amplification started: ${data.conversations_found} conversations found, ${data.replies_queued} replies queued`)
      fetchBroadcasts()
    } catch (e: any) {
      setActionError(e.message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleDelete(id: string) {
    if (!confirm('Delete this broadcast?')) return
    setActionLoading(id)

    try {
      await apiFetch(`/broadcast/${id}`, { method: 'DELETE' })
      fetchBroadcasts()
    } catch (e: any) {
      setActionError(e.message)
    } finally {
      setActionLoading(null)
    }
  }

  function openRecycleModal(broadcast: Broadcast) {
    setShowRecycle(broadcast.id)
    setRecycleText(broadcast.content)
    setRecycleTags('')
  }

  async function handleRecycle() {
    if (!showRecycle || !recycleText.trim()) return
    setRecycling(true)
    setActionError(null)

    try {
      const tags = recycleTags.split(',').map(t => t.trim()).filter(t => t)
      const data = await apiFetch<{total_templates: number}>(`/broadcast/${showRecycle}/recycle`, {
        method: 'POST',
        body: JSON.stringify({ template_text: recycleText, tags }),
      })

      setActionSuccess(`Saved as template! Total templates: ${data.total_templates}`)
      setShowRecycle(null)
      setRecycleText('')
      setRecycleTags('')
    } catch (e: any) {
      setActionError(e.message)
    } finally {
      setRecycling(false)
    }
  }

  const charLimit = CONTENT_LIMITS[createPlatform] || 280
  const charCount = createContent.length
  const charColor = charCount > charLimit ? '#c62828' : charCount > charLimit * 0.9 ? '#e65100' : '#666'

  if (productsLoading) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>Loading...</div>
  }

  if (!selectedProduct) {
    return <div style={{ padding: 40, textAlign: 'center', color: '#999' }}>Select a product to view broadcasts</div>
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>Broadcast</h1>
        <button
          onClick={() => setShowCreate(true)}
          style={{
            padding: '10px 20px',
            background: '#000',
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            cursor: 'pointer',
            fontWeight: 500,
          }}
        >
          + Create Post
        </button>
      </div>

      {/* Extension Warning */}
      {extensionConnected === false && (
        <div style={{ padding: 16, background: '#fff3e0', borderRadius: 8, marginBottom: 16, fontSize: 14 }}>
          <strong>Extension not connected.</strong> Install the Operative1 extension to post broadcasts.
        </div>
      )}

      {/* Scheduling Warning */}
      {extensionConnected && (
        <div style={{ padding: 12, background: '#e3f2fd', borderRadius: 8, marginBottom: 16, fontSize: 13, color: '#1565c0' }}>
          Scheduled posts require this dashboard to be open. Keep the tab open or your posts will wait until you return.
        </div>
      )}

      {/* Status Messages */}
      {actionError && (
        <div style={{ padding: 12, background: '#ffebee', borderRadius: 8, marginBottom: 16, fontSize: 14, color: '#c62828' }}>
          {actionError}
          <button onClick={() => setActionError(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>x</button>
        </div>
      )}
      {actionSuccess && (
        <div style={{ padding: 12, background: '#e8f5e9', borderRadius: 8, marginBottom: 16, fontSize: 14, color: '#2e7d32' }}>
          {actionSuccess}
          <button onClick={() => setActionSuccess(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>x</button>
        </div>
      )}

      {/* Broadcasts List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>Loading broadcasts...</div>
      ) : broadcasts.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, background: '#fafafa', borderRadius: 12 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📢</div>
          <div style={{ fontSize: 16, color: '#666', marginBottom: 8 }}>No broadcasts yet</div>
          <div style={{ fontSize: 14, color: '#999' }}>Create your first broadcast to start reaching your audience</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {broadcasts.map(b => (
            <div key={b.id} style={{ background: '#fff', border: '1px solid #e8e8e8', borderRadius: 12, padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: PLATFORM_COLORS[b.platform] || '#666' }} />
                  <span style={{ fontSize: 12, fontWeight: 500, textTransform: 'capitalize' }}>{b.platform}</span>
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: 12,
                    fontSize: 11,
                    fontWeight: 500,
                    background: STATUS_COLORS[b.status]?.bg || '#f5f5f5',
                    color: STATUS_COLORS[b.status]?.color || '#666',
                  }}>
                    {b.status.replace('_', ' ')}
                  </span>
                  {b.amplification_status !== 'none' && (
                    <span style={{ padding: '2px 8px', borderRadius: 12, fontSize: 11, background: '#e8f5e9', color: '#2e7d32' }}>
                      {b.amplification_replies_count} amplified
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 12, color: '#999' }}>
                  {b.posted_at ? `Posted ${new Date(b.posted_at).toLocaleDateString()}` :
                    b.scheduled_at ? `Scheduled ${new Date(b.scheduled_at).toLocaleString()}` :
                      `Created ${new Date(b.created_at).toLocaleDateString()}`}
                </div>
              </div>

              <div style={{ fontSize: 14, lineHeight: 1.5, marginBottom: 12, whiteSpace: 'pre-wrap' }}>
                {b.content}
              </div>

              {b.media_url && (
                <div style={{ marginBottom: 12 }}>
                  <img src={b.media_url} alt="Media" style={{ maxWidth: 200, maxHeight: 150, borderRadius: 8, objectFit: 'cover' }} />
                </div>
              )}

              {b.error_message && (
                <div style={{ fontSize: 12, color: '#c62828', marginBottom: 12 }}>
                  Error: {b.error_message}
                </div>
              )}

              {b.external_url && (
                <a href={b.external_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: '#1565c0', textDecoration: 'none' }}>
                  View on {b.platform} →
                </a>
              )}

              {/* Actions */}
              <div style={{ display: 'flex', gap: 8, marginTop: 12, borderTop: '1px solid #f0f0f0', paddingTop: 12 }}>
                {(b.status === 'draft' || b.status === 'scheduled') && (
                  <>
                    <button
                      onClick={() => handlePostNow(b.id)}
                      disabled={actionLoading === b.id || !extensionConnected}
                      style={{
                        padding: '6px 12px',
                        background: extensionConnected ? '#000' : '#ccc',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 6,
                        fontSize: 12,
                        cursor: extensionConnected ? 'pointer' : 'not-allowed',
                      }}
                    >
                      {actionLoading === b.id ? 'Posting...' : 'Post Now'}
                    </button>
                    <button
                      onClick={() => handleDelete(b.id)}
                      disabled={actionLoading === b.id}
                      style={{ padding: '6px 12px', background: '#fff', color: '#c62828', border: '1px solid #c62828', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
                    >
                      Delete
                    </button>
                  </>
                )}
                {b.status === 'posted' && (
                  <>
                    {b.amplification_status === 'none' && (
                      <button
                        onClick={() => handleAmplify(b.id)}
                        disabled={actionLoading === b.id}
                        style={{ padding: '6px 12px', background: '#e8f5e9', color: '#2e7d32', border: 'none', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
                      >
                        {actionLoading === b.id ? 'Starting...' : 'Amplify'}
                      </button>
                    )}
                    <button
                      onClick={() => openRecycleModal(b)}
                      style={{ padding: '6px 12px', background: '#f3e5f5', color: '#7b1fa2', border: 'none', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
                    >
                      Recycle
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, width: 500, maxHeight: '90vh', overflow: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Create Broadcast</h2>
              <button onClick={() => { setShowCreate(false); resetCreateForm() }} style={{ background: 'none', border: 'none', fontSize: 24, cursor: 'pointer', color: '#999' }}>×</button>
            </div>

            {/* Platform */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 6, color: '#666' }}>Platform</label>
              <select
                value={createPlatform}
                onChange={(e) => setCreatePlatform(e.target.value)}
                style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 14 }}
              >
                <option value="twitter">Twitter</option>
                <option value="reddit" disabled>Reddit (Coming Soon)</option>
                <option value="linkedin" disabled>LinkedIn (Coming Soon)</option>
              </select>
            </div>

            {/* Content */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                <label style={{ fontSize: 12, fontWeight: 500, color: '#666' }}>Content</label>
                <span style={{ fontSize: 12, color: charColor }}>{charCount}/{charLimit}</span>
              </div>
              <textarea
                value={createContent}
                onChange={(e) => setCreateContent(e.target.value)}
                placeholder="What do you want to share?"
                rows={4}
                style={{
                  width: '100%',
                  padding: 12,
                  borderRadius: 8,
                  border: `1px solid ${charCount > charLimit ? '#c62828' : '#e0e0e0'}`,
                  fontSize: 14,
                  resize: 'vertical',
                  fontFamily: 'inherit',
                }}
              />
            </div>

            {/* Media */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 6, color: '#666' }}>Media (optional)</label>
              {createMediaUrl ? (
                <div style={{ position: 'relative', display: 'inline-block' }}>
                  <img src={createMediaUrl} alt="Preview" style={{ maxWidth: 200, maxHeight: 150, borderRadius: 8 }} />
                  <button
                    onClick={() => { setCreateMediaUrl(null); setCreateMediaType(null) }}
                    style={{ position: 'absolute', top: -8, right: -8, width: 24, height: 24, borderRadius: '50%', background: '#c62828', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 14 }}
                  >
                    ×
                  </button>
                </div>
              ) : (
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/gif,image/webp"
                    onChange={handleFileUpload}
                    style={{ display: 'none' }}
                  />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    style={{ padding: '8px 16px', background: '#f5f5f5', border: '1px solid #e0e0e0', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}
                  >
                    {uploading ? 'Uploading...' : 'Upload Image'}
                  </button>
                  <button
                    onClick={handleSuggestMedia}
                    disabled={suggesting || !createContent.trim()}
                    style={{ padding: '8px 16px', background: '#e3f2fd', color: '#1565c0', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}
                  >
                    {suggesting ? 'Thinking...' : 'Suggest Media'}
                  </button>
                </div>
              )}
            </div>

            {/* Media Suggestion */}
            {mediaSuggestion && (
              <div style={{ marginBottom: 16, padding: 12, background: '#f8f9fa', borderRadius: 8, fontSize: 13 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>AI Recommendation: {mediaSuggestion.recommended_media_type}</div>
                <div style={{ marginBottom: 4 }}><strong>Description:</strong> {mediaSuggestion.description}</div>
                <div style={{ marginBottom: 4 }}><strong>Dimensions:</strong> {mediaSuggestion.dimensions}</div>
                <div style={{ marginBottom: 4 }}><strong>Style:</strong> {mediaSuggestion.style_notes}</div>
                <div style={{ color: '#666', fontStyle: 'italic' }}>{mediaSuggestion.platform_tip}</div>
              </div>
            )}

            {/* Schedule */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ display: 'flex', gap: 16, marginBottom: 8 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input
                    type="radio"
                    checked={!createScheduled}
                    onChange={() => setCreateScheduled(false)}
                  />
                  <span style={{ fontSize: 14 }}>Post immediately</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
                  <input
                    type="radio"
                    checked={createScheduled}
                    onChange={() => setCreateScheduled(true)}
                  />
                  <span style={{ fontSize: 14 }}>Schedule for later</span>
                </label>
              </div>
              {createScheduled && (
                <input
                  type="datetime-local"
                  value={createScheduleTime}
                  onChange={(e) => setCreateScheduleTime(e.target.value)}
                  min={new Date().toISOString().slice(0, 16)}
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #e0e0e0', fontSize: 14 }}
                />
              )}
            </div>

            {/* Submit */}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => { setShowCreate(false); resetCreateForm() }}
                style={{ padding: '10px 20px', background: '#f5f5f5', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 14 }}
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating || !createContent.trim() || charCount > charLimit || (createScheduled && !createScheduleTime)}
                style={{
                  padding: '10px 20px',
                  background: creating || !createContent.trim() || charCount > charLimit ? '#ccc' : '#000',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  cursor: creating ? 'wait' : 'pointer',
                  fontSize: 14,
                  fontWeight: 500,
                }}
              >
                {creating ? 'Creating...' : createScheduled ? 'Schedule' : 'Post Now'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Recycle Modal */}
      {showRecycle && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, width: 450, maxHeight: '90vh', overflow: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Save as Reply Template</h2>
              <button onClick={() => setShowRecycle(null)} style={{ background: 'none', border: 'none', fontSize: 24, cursor: 'pointer', color: '#999' }}>×</button>
            </div>

            <p style={{ fontSize: 13, color: '#666', marginBottom: 16 }}>
              This content will be used to inform the tone and style of future AI-generated replies.
            </p>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 6, color: '#666' }}>Template Text</label>
              <textarea
                value={recycleText}
                onChange={(e) => setRecycleText(e.target.value)}
                rows={4}
                style={{
                  width: '100%',
                  padding: 12,
                  borderRadius: 8,
                  border: '1px solid #e0e0e0',
                  fontSize: 14,
                  resize: 'vertical',
                  fontFamily: 'inherit',
                }}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 500, marginBottom: 6, color: '#666' }}>Tags (comma-separated, optional)</label>
              <input
                type="text"
                value={recycleTags}
                onChange={(e) => setRecycleTags(e.target.value)}
                placeholder="e.g., product-launch, helpful, technical"
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: 8,
                  border: '1px solid #e0e0e0',
                  fontSize: 14,
                }}
              />
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowRecycle(null)}
                style={{ padding: '10px 20px', background: '#f5f5f5', border: 'none', borderRadius: 8, cursor: 'pointer', fontSize: 14 }}
              >
                Cancel
              </button>
              <button
                onClick={handleRecycle}
                disabled={recycling || !recycleText.trim()}
                style={{
                  padding: '10px 20px',
                  background: recycling || !recycleText.trim() ? '#ccc' : '#7b1fa2',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 8,
                  cursor: recycling ? 'wait' : 'pointer',
                  fontSize: 14,
                  fontWeight: 500,
                }}
              >
                {recycling ? 'Saving...' : 'Save Template'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
