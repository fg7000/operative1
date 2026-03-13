'use client'
import { useEffect, useState, useRef } from 'react'
import { useProducts } from '@/lib/product-context'
import { PLATFORM_COLORS, MODE_COLORS, API_URL } from '@/lib/constants'

// Extension ID - set via NEXT_PUBLIC_EXTENSION_ID env var after loading extension in Chrome
const EXTENSION_ID = process.env.NEXT_PUBLIC_EXTENSION_ID || ''

type QueueItem = {
  id: string; platform: string; original_content: string; original_url: string
  original_author: string; draft_reply: string; edited_reply: string | null
  confidence_score: number; mentions_product: boolean; status: string
  engagement_metrics: Record<string, any> | null
  relevance_reason: string | null
  original_language: string | null
  translated_content: string | null
}

type ItemStatus = {
  type: 'success' | 'error'
  message: string
  tweetId?: string
}

function getMetaField(item: QueueItem, field: string): string {
  // Try dedicated column first, then engagement_metrics JSONB
  if ((item as any)[field]) return (item as any)[field]
  return item.engagement_metrics?.[field] || ''
}

export default function QueuePage() {
  const { selectedProduct, selectedProductId, loading: productsLoading } = useProducts()
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [ranking, setRanking] = useState(false)
  const [rankNotes, setRankNotes] = useState<Record<string,string>>({})
  const [extensionConnected, setExtensionConnected] = useState<boolean | null>(null)
  const [itemStatuses, setItemStatuses] = useState<Record<string, ItemStatus>>({})
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (selectedProductId) {
      fetchQueue()
    }
    // Start polling for extension every 3 seconds until connected
    checkExtensionWithPolling()
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [selectedProductId])

  async function checkExtension(): Promise<boolean> {
    if (!EXTENSION_ID || typeof chrome === 'undefined' || !chrome.runtime?.sendMessage) {
      return false
    }
    try {
      const response = await new Promise<{success: boolean; version?: string}>((resolve) => {
        chrome.runtime.sendMessage(EXTENSION_ID, { action: 'ping' }, (resp) => {
          if (chrome.runtime.lastError || !resp) {
            resolve({ success: false })
          } else {
            resolve(resp)
          }
        })
      })
      return response.success
    } catch {
      return false
    }
  }

  async function checkExtensionWithPolling() {
    const connected = await checkExtension()
    setExtensionConnected(connected)

    if (!connected) {
      // Poll every 3 seconds until connected
      pollIntervalRef.current = setInterval(async () => {
        const isConnected = await checkExtension()
        if (isConnected) {
          setExtensionConnected(true)
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
            pollIntervalRef.current = null
          }
        }
      }, 3000)
    }
  }

  async function fetchQueue() {
    if (!selectedProductId) return
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/queue/pending?product_id=${selectedProductId}`)
      const data = await res.json()
      setItems(data || [])
      setRankNotes({})
      setItemStatuses({})
    } catch (e) {
      console.error('Failed to fetch queue:', e)
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  async function smartRank() {
    if (!selectedProductId) return
    setRanking(true)
    try {
      const res = await fetch(`${API_URL}/queue/rank?product_id=${selectedProductId}`, { method: 'POST' })
      const data = await res.json()
      if (data.ranked_ids && Array.isArray(data.ranked_ids)) {
        const idOrder = new Map(data.ranked_ids.map((id: string, i: number) => [id, i]))
        setItems(prev => {
          const sorted = [...prev].sort((a, b) => {
            const aIdx = idOrder.has(a.id) ? idOrder.get(a.id)! : 999
            const bIdx = idOrder.has(b.id) ? idOrder.get(b.id)! : 999
            return (aIdx as number) - (bIdx as number)
          })
          return sorted
        })
        setRankNotes(data.notes || {})
      }
    } catch (e) { console.error('Rank error:', e) }
    setRanking(false)
  }

  function extractTweetId(url: string): string {
    if (!url) return ''
    const parts = url.split('/')
    for (let i = 0; i < parts.length; i++) {
      if (parts[i] === 'status' && i + 1 < parts.length) {
        return parts[i + 1].split('?')[0]
      }
    }
    return ''
  }

  async function postViaExtension(tweetId: string, replyText: string): Promise<{success: boolean; tweet_id?: string; error?: string}> {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(EXTENSION_ID, {
        action: 'post_reply',
        tweet_id: tweetId,
        reply_text: replyText
      }, (response) => {
        if (chrome.runtime.lastError || !response) {
          resolve({ success: false, error: 'Extension not responding. Try refreshing the page.' })
        } else {
          resolve(response)
        }
      })
    })
  }

  async function approve(item: QueueItem) {
    // Extension required - no server-side fallback
    if (!extensionConnected) {
      return
    }

    setActionLoading(item.id)
    // Clear any previous status
    setItemStatuses(prev => {
      const next = { ...prev }
      delete next[item.id]
      return next
    })

    const replyText = item.edited_reply || item.draft_reply
    const tweetId = extractTweetId(item.original_url)

    if (!tweetId) {
      setItemStatuses(prev => ({
        ...prev,
        [item.id]: { type: 'error', message: 'Could not extract tweet ID from URL' }
      }))
      setActionLoading(null)
      return
    }

    const result = await postViaExtension(tweetId, replyText)

    if (result.success) {
      // Update backend DB status
      await fetch(`${API_URL}/queue/${item.id}/mark-posted?product_id=${selectedProductId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ posted_tweet_id: result.tweet_id })
      })

      // Show success message on card
      setItemStatuses(prev => ({
        ...prev,
        [item.id]: {
          type: 'success',
          message: 'Posted successfully!',
          tweetId: result.tweet_id
        }
      }))
      setActionLoading(null)

      // Remove from queue after 3 seconds
      setTimeout(() => {
        setItems(prev => prev.filter(i => i.id !== item.id))
        setItemStatuses(prev => {
          const next = { ...prev }
          delete next[item.id]
          return next
        })
      }, 3000)
    } else {
      // Show error on card but keep item in queue
      setItemStatuses(prev => ({
        ...prev,
        [item.id]: { type: 'error', message: result.error || 'Unknown error' }
      }))
      setActionLoading(null)
      // Do NOT remove from queue - user can try again or skip
    }
  }

  async function reject(id: string) {
    if (!selectedProductId) return
    setActionLoading(id)
    await fetch(`${API_URL}/queue/${id}/reject?product_id=${selectedProductId}`, { method: 'POST' })
    setItems(prev => prev.filter(i => i.id !== id))
    setActionLoading(null)
  }

  async function skip(id: string) {
    // Clear any error status and move item to bottom
    setItemStatuses(prev => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    setItems(prev => {
      const item = prev.find(i => i.id === id)
      if (!item) return prev
      return [...prev.filter(i => i.id !== id), item]
    })
  }

  async function saveEdit(id: string) {
    if (!selectedProductId) return
    setActionLoading(id)
    await fetch(`${API_URL}/queue/${id}/edit?product_id=${selectedProductId}&edited_reply=${encodeURIComponent(editText)}`, { method: 'PATCH' })
    setEditingId(null)
    setItems(prev => prev.map(i => i.id === id ? { ...i, edited_reply: editText } : i))
    setActionLoading(null)
  }

  if (productsLoading) {
    return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'200px',color:'#999',fontSize:'14px'}}>Loading...</div>
  }

  if (!selectedProduct) {
    return (
      <div style={{textAlign:'center',padding:'80px 40px',background:'#fafafa',borderRadius:'16px',border:'1px solid #e8e8e8'}}>
        <div style={{fontSize:'32px',marginBottom:'12px'}}>📦</div>
        <p style={{fontSize:'15px',fontWeight:500,color:'#111'}}>Select a product</p>
        <p style={{fontSize:'13px',color:'#999',marginTop:'4px'}}>Choose a product from the sidebar to view its queue</p>
      </div>
    )
  }

  if (loading) return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'200px',color:'#999',fontSize:'14px'}}>Loading queue...</div>

  return (
    <div style={{maxWidth:'680px'}}>
      {/* Extension Status Banner */}
      {extensionConnected === false && (
        <div style={{padding:'12px 16px',marginBottom:'16px',background:'#ffebee',border:'1px solid #ffcdd2',borderRadius:'10px',display:'flex',alignItems:'center',gap:'10px'}}>
          <span style={{fontSize:'16px'}}>&#9888;</span>
          <div>
            <div style={{fontSize:'13px',fontWeight:600,color:'#c62828'}}>Connect Chrome Extension Required</div>
            <div style={{fontSize:'12px',color:'#e53935'}}>Install and enable the Operative1 Chrome extension to post replies. Checking for extension...</div>
          </div>
        </div>
      )}
      {extensionConnected === null && (
        <div style={{padding:'10px 16px',marginBottom:'16px',background:'#fff3e0',border:'1px solid #ffe0b2',borderRadius:'10px',display:'flex',alignItems:'center',gap:'8px'}}>
          <span style={{fontSize:'13px',color:'#f57c00'}}>Detecting extension...</span>
        </div>
      )}
      {extensionConnected === true && (
        <div style={{padding:'10px 16px',marginBottom:'16px',background:'#e8f5e9',border:'1px solid #c8e6c9',borderRadius:'10px',display:'flex',alignItems:'center',gap:'8px'}}>
          <span style={{width:'8px',height:'8px',borderRadius:'50%',background:'#4caf50'}}></span>
          <span style={{fontSize:'13px',fontWeight:500,color:'#2e7d32'}}>Extension connected - replies will post from your browser</span>
        </div>
      )}

      <div style={{display:'flex',alignItems:'flex-end',justifyContent:'space-between',marginBottom:'32px'}}>
        <div>
          <h1 style={{fontSize:'28px',fontWeight:600,color:'#111',lineHeight:1}}>Reply Queue</h1>
          <p style={{fontSize:'14px',color:'#999',marginTop:'6px'}}>
            {selectedProduct.name} — {items.length} pending {items.length===1?'reply':'replies'}
          </p>
        </div>
        <div style={{display:'flex',gap:'8px'}}>
          <button onClick={smartRank} disabled={ranking || items.length === 0}
            style={{fontSize:'13px',color:'#111',background:'#fff',border:'1px solid #e0e0e0',borderRadius:'8px',padding:'8px 14px',cursor:'pointer',fontWeight:600,opacity:ranking?0.5:1}}>
            {ranking ? 'Ranking...' : 'Smart Rank'}
          </button>
          <button onClick={fetchQueue} style={{fontSize:'13px',color:'#666',background:'#f5f5f5',border:'none',borderRadius:'8px',padding:'8px 14px',cursor:'pointer',fontWeight:500}}>Refresh</button>
        </div>
      </div>

      {items.length===0 && (
        <div style={{textAlign:'center',padding:'80px 40px',background:'#fafafa',borderRadius:'16px',border:'1px solid #e8e8e8'}}>
          <div style={{fontSize:'32px',marginBottom:'12px'}}>&#10003;</div>
          <p style={{fontSize:'15px',fontWeight:500,color:'#111'}}>Queue is empty</p>
          <p style={{fontSize:'13px',color:'#999',marginTop:'4px'}}>New replies appear automatically</p>
        </div>
      )}

      <div style={{display:'flex',flexDirection:'column',gap:'16px'}}>
        {items.map((item, idx) => {
          const replyMode = getMetaField(item, 'reply_mode')
          const relevanceReason = getMetaField(item, 'relevance_reason')
          const originalLang = getMetaField(item, 'original_language')
          const translatedContent = getMetaField(item, 'translated_content')
          const relevanceScore = item.engagement_metrics?.relevance_score
          const modeStyle = MODE_COLORS[replyMode] || { bg: '#f0f0f0', color: '#555' }
          const rankNote = rankNotes[item.id]
          const itemStatus = itemStatuses[item.id]

          return (
          <div key={item.id} style={{borderRadius:'16px',border:'1px solid #e8e8e8',overflow:'hidden',background:'#fff',boxShadow:'0 2px 12px rgba(0,0,0,0.05)'}}>
            {/* Header */}
            <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'12px 20px',background:'#fafafa',borderBottom:'1px solid #f0f0f0',flexWrap:'wrap',gap:'8px'}}>
              <div style={{display:'flex',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                <span style={{fontSize:'11px',fontWeight:700,padding:'3px 10px',borderRadius:'20px',color:'#fff',background:PLATFORM_COLORS[item.platform]||'#111',textTransform:'uppercase',letterSpacing:'0.05em'}}>{item.platform}</span>
                {replyMode && (
                  <span style={{fontSize:'10px',fontWeight:600,padding:'3px 8px',borderRadius:'20px',background:modeStyle.bg,color:modeStyle.color,textTransform:'uppercase',letterSpacing:'0.04em'}}>
                    {replyMode.replace('_', ' ')}
                  </span>
                )}
                {originalLang && originalLang !== 'en' && (
                  <span style={{fontSize:'10px',fontWeight:600,padding:'3px 8px',borderRadius:'20px',background:'#fce4ec',color:'#c62828',textTransform:'uppercase'}}>{originalLang}</span>
                )}
                <span style={{fontSize:'13px',color:'#999'}}>@{item.original_author}</span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
                {relevanceScore != null && (
                  <span style={{fontSize:'13px',color:'#999'}}>Relevance <strong style={{color:'#111'}}>{relevanceScore}/10</strong></span>
                )}
                <span style={{fontSize:'13px',color:'#999'}}>Confidence <strong style={{color:'#111'}}>{Math.round((item.confidence_score||0)*100)}%</strong></span>
                {item.mentions_product && <span style={{fontSize:'11px',fontWeight:500,padding:'3px 10px',borderRadius:'20px',background:'#f0f0f0',color:'#555'}}>mentions product</span>}
              </div>
            </div>

            {/* Success/Error Status */}
            {itemStatus?.type === 'success' && (
              <div style={{padding:'12px 20px',background:'#e8f5e9',borderBottom:'1px solid #c8e6c9',display:'flex',alignItems:'center',justifyContent:'space-between'}}>
                <span style={{fontSize:'13px',fontWeight:600,color:'#2e7d32'}}>{itemStatus.message}</span>
                {itemStatus.tweetId && (
                  <a href={`https://x.com/i/web/status/${itemStatus.tweetId}`} target="_blank" rel="noopener noreferrer"
                    style={{fontSize:'13px',fontWeight:500,color:'#1da1f2',textDecoration:'none'}}>
                    View Tweet &rarr;
                  </a>
                )}
              </div>
            )}
            {itemStatus?.type === 'error' && (
              <div style={{padding:'12px 20px',background:'#ffebee',borderBottom:'1px solid #ffcdd2'}}>
                <span style={{fontSize:'13px',fontWeight:600,color:'#c62828'}}>Error: {itemStatus.message}</span>
              </div>
            )}

            {/* AI Rank Note */}
            {rankNote && (
              <div style={{padding:'8px 20px',background:'#fffde7',borderBottom:'1px solid #fff9c4',fontSize:'13px',color:'#f57f17',fontWeight:500}}>
                #{idx+1} &mdash; {rankNote}
              </div>
            )}

            {/* Relevance Reason */}
            {relevanceReason && (
              <div style={{padding:'8px 20px',background:'#f8f9fa',borderBottom:'1px solid #f0f0f0',fontSize:'13px',color:'#666',fontStyle:'italic'}}>
                {relevanceReason}
              </div>
            )}

            {/* Original Post */}
            <div style={{padding:'16px 20px',borderBottom:'1px solid #f5f5f5'}}>
              <div style={{fontSize:'11px',fontWeight:600,letterSpacing:'0.12em',textTransform:'uppercase',color:'#bbb',marginBottom:'8px'}}>Original Post</div>
              <p style={{fontSize:'14px',color:'#111',lineHeight:1.6}}>{item.original_content}</p>
              {translatedContent && (
                <div style={{marginTop:'10px',padding:'10px 14px',background:'#f5f5f5',borderRadius:'8px',border:'1px solid #eee'}}>
                  <div style={{fontSize:'10px',fontWeight:600,letterSpacing:'0.1em',textTransform:'uppercase',color:'#999',marginBottom:'4px'}}>Translated</div>
                  <p style={{fontSize:'13px',color:'#444',lineHeight:1.5}}>{translatedContent}</p>
                </div>
              )}
              {item.original_url && <a href={item.original_url} target="_blank" rel="noopener noreferrer" style={{fontSize:'13px',color:'#999',marginTop:'6px',display:'inline-block'}}>View original &rarr;</a>}
            </div>

            {/* Draft Reply */}
            <div style={{padding:'16px 20px'}}>
              <div style={{fontSize:'11px',fontWeight:600,letterSpacing:'0.12em',textTransform:'uppercase',color:'#bbb',marginBottom:'8px'}}>Draft Reply</div>
              {editingId===item.id ? (
                <div>
                  <textarea value={editText} onChange={e=>setEditText(e.target.value)} rows={4}
                    style={{width:'100%',padding:'12px 14px',borderRadius:'10px',border:'1px solid #e0e0e0',fontSize:'14px',color:'#111',resize:'none',outline:'none',fontFamily:'inherit'}}
                    onFocus={e=>e.target.style.borderColor='#111'} onBlur={e=>e.target.style.borderColor='#e0e0e0'}
                  />
                  <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                    <button onClick={()=>saveEdit(item.id)} disabled={actionLoading===item.id} style={{padding:'8px 18px',borderRadius:'8px',background:'#111',color:'#fff',fontSize:'13px',fontWeight:600,border:'none',cursor:'pointer',opacity:actionLoading===item.id?0.5:1}}>Save</button>
                    <button onClick={()=>setEditingId(null)} style={{padding:'8px 18px',borderRadius:'8px',background:'#f5f5f5',color:'#555',fontSize:'13px',fontWeight:500,border:'none',cursor:'pointer'}}>Cancel</button>
                  </div>
                </div>
              ) : (
                <p style={{fontSize:'14px',color:'#111',lineHeight:1.6}}>
                  {item.edited_reply||item.draft_reply}
                  {item.edited_reply && <span style={{marginLeft:'8px',fontSize:'12px',color:'#999'}}>(edited)</span>}
                </p>
              )}
            </div>

            {/* Actions */}
            {editingId!==item.id && itemStatus?.type !== 'success' && (
              <div style={{display:'flex',gap:'8px',padding:'12px 20px',background:'#fafafa',borderTop:'1px solid #f0f0f0'}}>
                <button
                  onClick={()=>approve(item)}
                  disabled={actionLoading===item.id || !extensionConnected}
                  title={!extensionConnected ? 'Connect Chrome extension to post' : ''}
                  style={{
                    flex:1,
                    padding:'10px',
                    borderRadius:'10px',
                    background: extensionConnected ? '#111' : '#ccc',
                    color:'#fff',
                    fontSize:'13px',
                    fontWeight:600,
                    border:'none',
                    cursor: extensionConnected ? 'pointer' : 'not-allowed',
                    opacity:actionLoading===item.id?0.5:1
                  }}>
                  {actionLoading===item.id ? 'Posting...' : 'Approve & Post'}
                </button>
                <button onClick={()=>{setEditingId(item.id);setEditText(item.edited_reply||item.draft_reply)}}
                  style={{padding:'10px 18px',borderRadius:'10px',background:'#fff',color:'#111',fontSize:'13px',fontWeight:500,border:'1px solid #e0e0e0',cursor:'pointer'}}>
                  Edit
                </button>
                <button onClick={()=>skip(item.id)}
                  style={{padding:'10px 18px',borderRadius:'10px',background:'#fff',color:'#666',fontSize:'13px',fontWeight:500,border:'1px solid #e0e0e0',cursor:'pointer'}}>
                  Skip
                </button>
                <button onClick={()=>reject(item.id)} disabled={actionLoading===item.id}
                  style={{padding:'10px 18px',borderRadius:'10px',background:'#fff',color:'#e53e3e',fontSize:'13px',fontWeight:500,border:'1px solid #ffd7d7',cursor:'pointer',opacity:actionLoading===item.id?0.5:1}}>
                  Reject
                </button>
              </div>
            )}
          </div>
          )
        })}
      </div>
    </div>
  )
}
