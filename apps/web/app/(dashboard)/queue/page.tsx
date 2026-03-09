'use client'
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'

type QueueItem = {
  id: string; platform: string; original_content: string; original_url: string
  original_author: string; draft_reply: string; edited_reply: string | null
  confidence_score: number; mentions_product: boolean; status: string
}

const platformColors: Record<string, string> = {
  twitter: '#000000', reddit: '#ff4500', linkedin: '#0077b5', hn: '#ff6600'
}

export default function QueuePage() {
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    fetchQueue()
    const channel = supabase.channel('queue_changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'reply_queue' }, fetchQueue)
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [])

  async function fetchQueue() {
    const { data } = await supabase.from('reply_queue').select('*').eq('status', 'pending').order('created_at', { ascending: false })
    setItems(data || []); setLoading(false)
  }

  async function approve(item: QueueItem) {
    setActionLoading(item.id)
    await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/queue/${item.id}/approve`, { method: 'POST' })
    await fetchQueue(); setActionLoading(null)
  }

  async function reject(id: string) {
    setActionLoading(id)
    await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/queue/${id}/reject`, { method: 'POST' })
    await fetchQueue(); setActionLoading(null)
  }

  async function saveEdit(id: string) {
    setActionLoading(id)
    await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/queue/${id}/edit?edited_reply=${encodeURIComponent(editText)}`, { method: 'PATCH' })
    setEditingId(null); await fetchQueue(); setActionLoading(null)
  }

  if (loading) return <div className="flex items-center justify-center h-64 text-[14px] text-[#6e6e73]">Loading…</div>

  return (
    <div className="max-w-[720px]">
      <div className="flex items-end justify-between mb-10">
        <div>
          <h1 className="text-[32px] font-semibold text-[#1d1d1f] leading-none">Reply Queue</h1>
          <p className="text-[15px] text-[#6e6e73] mt-2">{items.length} pending {items.length === 1 ? 'reply' : 'replies'}</p>
        </div>
        <button onClick={fetchQueue} className="text-[13px] font-medium text-[#6e6e73] hover:text-[#1d1d1f] px-4 py-2 rounded-lg hover:bg-[#f5f5f7] transition-colors">
          Refresh
        </button>
      </div>

      {items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-32 rounded-2xl" style={{background:'#f5f5f7'}}>
          <div className="text-4xl mb-4">✓</div>
          <p className="text-[15px] font-medium text-[#1d1d1f]">Queue is empty</p>
          <p className="text-[13px] text-[#6e6e73] mt-1">New replies will appear here automatically</p>
        </div>
      )}

      <div className="space-y-5">
        {items.map(item => (
          <div key={item.id} className="rounded-2xl border border-[#d1d1d6] overflow-hidden bg-white" style={{boxShadow:'0 1px 8px rgba(0,0,0,0.06)'}}>
            <div className="flex items-center justify-between px-6 py-3.5 border-b border-[#f5f5f7]" style={{background:'#fafafa'}}>
              <div className="flex items-center gap-3">
                <span className="text-[12px] font-semibold px-2.5 py-1 rounded-full text-white" style={{background: platformColors[item.platform] || '#1d1d1f'}}>
                  {item.platform}
                </span>
                <span className="text-[13px] text-[#6e6e73]">@{item.original_author}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[13px] text-[#6e6e73]">
                  Confidence <span className="font-semibold text-[#1d1d1f]">{Math.round((item.confidence_score || 0) * 100)}%</span>
                </span>
                {item.mentions_product && (
                  <span className="text-[11px] font-medium px-2.5 py-1 rounded-full text-[#1d1d1f]" style={{background:'#f5f5f7'}}>
                    mentions product
                  </span>
                )}
              </div>
            </div>

            <div className="px-6 py-5 border-b border-[#f5f5f7]">
              <div className="text-[11px] font-semibold tracking-widest uppercase text-[#aeaeb2] mb-2.5">Original Post</div>
              <p className="text-[14px] text-[#1d1d1f] leading-relaxed">{item.original_content}</p>
              {item.original_url && (
                <a href={item.original_url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-[#6e6e73] hover:text-[#1d1d1f] mt-2 inline-block hover:underline">
                  View original →
                </a>
              )}
            </div>

            <div className="px-6 py-5">
              <div className="text-[11px] font-semibold tracking-widest uppercase text-[#aeaeb2] mb-2.5">Draft Reply</div>
              {editingId === item.id ? (
                <div>
                  <textarea value={editText} onChange={e => setEditText(e.target.value)}
                    className="w-full text-[14px] border border-[#d1d1d6] rounded-xl px-4 py-3.5 focus:outline-none focus:border-[#1d1d1f] resize-none transition-colors"
                    rows={4} />
                  <div className="flex gap-2.5 mt-3">
                    <button onClick={() => saveEdit(item.id)} disabled={actionLoading === item.id}
                      className="text-[13px] font-semibold bg-[#1d1d1f] text-white px-5 py-2 rounded-lg hover:bg-black disabled:opacity-40 transition-colors">Save</button>
                    <button onClick={() => setEditingId(null)}
                      className="text-[13px] font-medium text-[#6e6e73] px-5 py-2 rounded-lg border border-[#d1d1d6] hover:bg-[#f5f5f7] transition-colors">Cancel</button>
                  </div>
                </div>
              ) : (
                <p className="text-[14px] text-[#1d1d1f] leading-relaxed">
                  {item.edited_reply || item.draft_reply}
                  {item.edited_reply && <span className="ml-2 text-[12px] text-[#6e6e73]">(edited)</span>}
                </p>
              )}
            </div>

            {editingId !== item.id && (
              <div className="flex gap-2.5 px-6 py-4 border-t border-[#f5f5f7]" style={{background:'#fafafa'}}>
                <button onClick={() => approve(item)} disabled={actionLoading === item.id}
                  className="flex-1 py-2.5 rounded-xl text-[14px] font-semibold text-white transition-opacity disabled:opacity-40"
                  style={{background:'#1d1d1f'}}>
                  Approve & Post
                </button>
                <button onClick={() => { setEditingId(item.id); setEditText(item.edited_reply || item.draft_reply) }}
                  className="px-6 py-2.5 rounded-xl text-[14px] font-medium text-[#1d1d1f] border border-[#d1d1d6] hover:bg-white transition-colors">
                  Edit
                </button>
                <button onClick={() => reject(item.id)} disabled={actionLoading === item.id}
                  className="px-6 py-2.5 rounded-xl text-[14px] font-medium text-[#ff3b30] border border-[#ffd7d5] hover:bg-[#fff5f5] disabled:opacity-40 transition-colors">
                  Reject
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
