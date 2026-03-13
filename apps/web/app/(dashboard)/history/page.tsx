'use client'
import { useEffect, useState } from 'react'
import { useProducts } from '@/lib/product-context'
import { PLATFORM_COLORS, API_URL } from '@/lib/constants'

type HistoryItem = {
  id: string; platform: string; original_content: string; original_url: string
  original_author: string; draft_reply: string; edited_reply: string | null
  status: string; posted_at: string | null; created_at: string
  rejection_reason: string | null
  engagement_metrics: Record<string, any> | null
}

const statusStyle: Record<string,{bg:string,color:string}> = {
  posted: { bg: '#e8f5e9', color: '#2e7d32' },
  failed: { bg: '#ffebee', color: '#c62828' },
  rejected: { bg: '#fff3e0', color: '#e65100' },
}

export default function HistoryPage() {
  const { selectedProduct, selectedProductId, loading: productsLoading } = useProducts()
  const [items, setItems] = useState<HistoryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all'|'posted'|'failed'|'rejected'>('all')

  useEffect(() => {
    if (selectedProductId) {
      fetchHistory()
    }
  }, [selectedProductId])

  async function fetchHistory() {
    if (!selectedProductId) return
    setLoading(true)
    try {
      const res = await fetch(`${API_URL}/queue/history?product_id=${selectedProductId}`)
      const data = await res.json()
      setItems(data || [])
    } catch (e) {
      console.error('Failed to fetch history:', e)
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  const filtered = filter === 'all' ? items : items.filter(i => i.status === filter)

  if (productsLoading) {
    return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'200px',color:'#999',fontSize:'14px'}}>Loading...</div>
  }

  if (!selectedProduct) {
    return (
      <div style={{textAlign:'center',padding:'80px 40px',background:'#fafafa',borderRadius:'16px',border:'1px solid #e8e8e8'}}>
        <div style={{fontSize:'32px',marginBottom:'12px'}}>📦</div>
        <p style={{fontSize:'15px',fontWeight:500,color:'#111'}}>Select a product</p>
        <p style={{fontSize:'13px',color:'#999',marginTop:'4px'}}>Choose a product from the sidebar to view its history</p>
      </div>
    )
  }

  if (loading) return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'200px',color:'#999',fontSize:'14px'}}>Loading history...</div>

  return (
    <div style={{maxWidth:'680px'}}>
      <div style={{display:'flex',alignItems:'flex-end',justifyContent:'space-between',marginBottom:'32px'}}>
        <div>
          <h1 style={{fontSize:'28px',fontWeight:600,color:'#111',lineHeight:1}}>History</h1>
          <p style={{fontSize:'14px',color:'#999',marginTop:'6px'}}>
            {selectedProduct.name} — {filtered.length} {filter === 'all' ? 'total' : filter} items
          </p>
        </div>
        <div style={{display:'flex',gap:'8px'}}>
          {(['all','posted','failed','rejected'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              style={{fontSize:'13px',color:filter===f?'#fff':'#666',background:filter===f?'#111':'#f5f5f5',border:'none',borderRadius:'8px',padding:'8px 14px',cursor:'pointer',fontWeight:500,textTransform:'capitalize'}}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 && (
        <div style={{textAlign:'center',padding:'80px 40px',background:'#fafafa',borderRadius:'16px',border:'1px solid #e8e8e8'}}>
          <p style={{fontSize:'15px',fontWeight:500,color:'#111'}}>No {filter === 'all' ? '' : filter + ' '}items yet</p>
        </div>
      )}

      <div style={{display:'flex',flexDirection:'column',gap:'16px'}}>
        {filtered.map(item => {
          const style = statusStyle[item.status] || { bg: '#f0f0f0', color: '#555' }
          const postedTweetId = item.engagement_metrics?.posted_tweet_id

          return (
            <div key={item.id} style={{borderRadius:'16px',border:'1px solid #e8e8e8',overflow:'hidden',background:'#fff',boxShadow:'0 2px 12px rgba(0,0,0,0.05)'}}>
              {/* Header */}
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',padding:'12px 20px',background:'#fafafa',borderBottom:'1px solid #f0f0f0',flexWrap:'wrap',gap:'8px'}}>
                <div style={{display:'flex',alignItems:'center',gap:'8px'}}>
                  <span style={{fontSize:'11px',fontWeight:700,padding:'3px 10px',borderRadius:'20px',color:'#fff',background:PLATFORM_COLORS[item.platform]||'#111',textTransform:'uppercase',letterSpacing:'0.05em'}}>{item.platform}</span>
                  <span style={{fontSize:'11px',fontWeight:600,padding:'3px 10px',borderRadius:'20px',background:style.bg,color:style.color,textTransform:'uppercase'}}>{item.status}</span>
                  <span style={{fontSize:'13px',color:'#999'}}>@{item.original_author}</span>
                </div>
                <span style={{fontSize:'12px',color:'#999'}}>
                  {item.posted_at ? new Date(item.posted_at).toLocaleString() : new Date(item.created_at).toLocaleString()}
                </span>
              </div>

              {/* Error message for failed items */}
              {item.status === 'failed' && item.rejection_reason && (
                <div style={{padding:'10px 20px',background:'#ffebee',borderBottom:'1px solid #ffcdd2',fontSize:'13px',color:'#c62828'}}>
                  <strong>Error:</strong> {item.rejection_reason}
                </div>
              )}

              {/* Rejection reason */}
              {item.status === 'rejected' && item.rejection_reason && (
                <div style={{padding:'10px 20px',background:'#fff3e0',borderBottom:'1px solid #ffe0b2',fontSize:'13px',color:'#e65100'}}>
                  <strong>Reason:</strong> {item.rejection_reason}
                </div>
              )}

              {/* Original Post */}
              <div style={{padding:'16px 20px',borderBottom:'1px solid #f5f5f5'}}>
                <div style={{fontSize:'11px',fontWeight:600,letterSpacing:'0.12em',textTransform:'uppercase',color:'#bbb',marginBottom:'8px'}}>Original Post</div>
                <p style={{fontSize:'14px',color:'#111',lineHeight:1.6}}>{item.original_content}</p>
                {item.original_url && <a href={item.original_url} target="_blank" rel="noopener noreferrer" style={{fontSize:'13px',color:'#999',marginTop:'6px',display:'inline-block'}}>View original &rarr;</a>}
              </div>

              {/* Reply */}
              <div style={{padding:'16px 20px'}}>
                <div style={{fontSize:'11px',fontWeight:600,letterSpacing:'0.12em',textTransform:'uppercase',color:'#bbb',marginBottom:'8px'}}>
                  {item.status === 'posted' ? 'Posted Reply' : 'Draft Reply'}
                </div>
                <p style={{fontSize:'14px',color:'#111',lineHeight:1.6}}>{item.edited_reply || item.draft_reply}</p>
                {postedTweetId && (
                  <a href={`https://twitter.com/i/web/status/${postedTweetId}`} target="_blank" rel="noopener noreferrer"
                    style={{fontSize:'13px',color:'#1da1f2',marginTop:'8px',display:'inline-block'}}>
                    View on Twitter &rarr;
                  </a>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
