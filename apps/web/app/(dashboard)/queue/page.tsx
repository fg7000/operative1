'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'

type QueueItem = {
  id: string
  platform: string
  original_content: string
  original_url: string
  original_author: string
  draft_reply: string
  edited_reply: string | null
  confidence_score: number
  relevance_score: number
  mentions_product: boolean
  status: string
  created_at: string
}

export default function QueuePage() {
  const [items, setItems] = useState<QueueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useEffect(() => {
    fetchQueue()
    const channel = supabase
      .channel('queue_changes')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'reply_queue' }, fetchQueue)
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [])

  async function fetchQueue() {
    const { data } = await supabase
      .from('reply_queue')
      .select('*')
      .eq('status', 'pending')
      .order('created_at', { ascending: false })
    setItems(data || [])
    setLoading(false)
  }

  async function approve(item: QueueItem) {
    setActionLoading(item.id)
    const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    await fetch(`${API}/queue/${item.id}/approve`, { method: 'POST' })
    await fetchQueue()
    setActionLoading(null)
  }

  async function reject(id: string) {
    setActionLoading(id)
    const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    await fetch(`${API}/queue/${id}/reject`, { method: 'POST' })
    await fetchQueue()
    setActionLoading(null)
  }

  async function saveEdit(id: string) {
    setActionLoading(id)
    const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    await fetch(`${API}/queue/${id}/edit?edited_reply=${encodeURIComponent(editText)}`, { method: 'PATCH' })
    setEditingId(null)
    await fetchQueue()
    setActionLoading(null)
  }

  if (loading) return (
    <div style={{fontFamily:'Georgia, serif'}} className="flex items-center justify-center h-64 text-xs tracking-widest uppercase text-gray-400">
      Loading...
    </div>
  )

  return (
    <div style={{fontFamily:'Georgia, serif'}} className="max-w-3xl">
      <div className="border-b-2 border-black pb-6 mb-10 flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-normal text-black">Reply Queue</h1>
          <p className="text-xs tracking-widest uppercase text-gray-400 mt-2">{items.length} pending {items.length === 1 ? 'reply' : 'replies'}</p>
        </div>
        <button onClick={fetchQueue} className="text-xs tracking-widest uppercase text-gray-400 hover:text-black border border-gray-300 hover:border-black px-4 py-2 transition-colors">
          Refresh
        </button>
      </div>

      {items.length === 0 && (
        <div className="text-center py-32 border border-dashed border-gray-300">
          <p className="text-xs tracking-widest uppercase text-gray-400">Queue is empty</p>
          <p className="text-xs text-gray-300 mt-2">New replies appear automatically</p>
        </div>
      )}

      <div className="space-y-8">
        {items.map(item => (
          <div key={item.id} className="border border-black">
            <div className="flex items-center justify-between px-6 py-3 border-b border-black bg-gray-50">
              <div className="flex items-center gap-4">
                <span className="text-xs font-bold tracking-widest uppercase">{item.platform}</span>
                <span className="text-xs text-gray-400">@{item.original_author}</span>
              </div>
              <div className="flex items-center gap-4 text-xs text-gray-400">
                <span>Confidence: <span className="text-black font-bold">{Math.round((item.confidence_score || 0) * 100)}%</span></span>
                {item.mentions_product && <span className="border border-black px-2 py-0.5 text-black text-xs tracking-wider uppercase">Mentions product</span>}
              </div>
            </div>

            <div className="px-6 py-5 border-b border-gray-200">
              <div className="text-xs tracking-widest uppercase text-gray-400 mb-3">Original Post</div>
              <p className="text-sm text-black leading-relaxed">{item.original_content}</p>
              {item.original_url && (
                <a href={item.original_url} target="_blank" rel="noopener noreferrer" className="text-xs text-gray-400 hover:text-black underline mt-2 block">
                  View original →
                </a>
              )}
            </div>

            <div className="px-6 py-5">
              <div className="text-xs tracking-widest uppercase text-gray-400 mb-3">Draft Reply</div>
              {editingId === item.id ? (
                <div>
                  <textarea
                    value={editText}
                    onChange={e => setEditText(e.target.value)}
                    className="w-full text-sm border border-black p-4 focus:outline-none resize-none bg-white"
                    rows={4}
                  />
                  <div className="flex gap-3 mt-3">
                    <button onClick={() => saveEdit(item.id)} disabled={actionLoading === item.id} className="text-xs tracking-widest uppercase bg-black text-white px-6 py-2 hover:bg-gray-900 disabled:opacity-40">Save</button>
                    <button onClick={() => setEditingId(null)} className="text-xs tracking-widest uppercase border border-black px-6 py-2 hover:bg-gray-50">Cancel</button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-black leading-relaxed">
                  {item.edited_reply || item.draft_reply}
                  {item.edited_reply && <span className="ml-2 text-xs text-gray-400 uppercase tracking-wider">(edited)</span>}
                </p>
              )}
            </div>

            {editingId !== item.id && (
              <div className="flex items-center gap-px border-t border-black">
                <button onClick={() => approve(item)} disabled={actionLoading === item.id} className="flex-1 bg-black text-white text-xs tracking-widest uppercase py-3 hover:bg-gray-900 disabled:opacity-40 transition-colors">
                  Approve & Post
                </button>
                <button onClick={() => { setEditingId(item.id); setEditText(item.edited_reply || item.draft_reply) }} className="flex-1 border-l border-black bg-white text-black text-xs tracking-widest uppercase py-3 hover:bg-gray-50 transition-colors">
                  Edit
                </button>
                <button onClick={() => reject(item.id)} disabled={actionLoading === item.id} className="flex-1 border-l border-black bg-white text-black text-xs tracking-widest uppercase py-3 hover:bg-gray-50 disabled:opacity-40 transition-colors">
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
