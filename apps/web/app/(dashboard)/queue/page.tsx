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
    // realtime subscription
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

  function startEdit(item: QueueItem) {
    setEditingId(item.id)
    setEditText(item.edited_reply || item.draft_reply)
  }

  const platformColor: Record<string, string> = {
    twitter: 'bg-sky-100 text-sky-700',
    reddit: 'bg-orange-100 text-orange-700',
    linkedin: 'bg-blue-100 text-blue-700',
    hn: 'bg-amber-100 text-amber-700',
  }

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400">Loading queue...</div>

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reply Queue</h1>
          <p className="text-gray-500 mt-1">{items.length} pending {items.length === 1 ? 'reply' : 'replies'}</p>
        </div>
        <button onClick={fetchQueue} className="text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg px-3 py-1.5">
          Refresh
        </button>
      </div>

      {items.length === 0 && (
        <div className="text-center py-24 text-gray-400">
          <div className="text-4xl mb-4">✓</div>
          <p className="text-lg">Queue is empty</p>
          <p className="text-sm mt-1">New replies will appear here automatically</p>
        </div>
      )}

      <div className="space-y-6">
        {items.map(item => (
          <div key={item.id} className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-gray-50">
              <div className="flex items-center gap-3">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${platformColor[item.platform] || 'bg-gray-100 text-gray-600'}`}>
                  {item.platform}
                </span>
                <span className="text-xs text-gray-500">@{item.original_author}</span>
              </div>
              <div className="flex items-center gap-3 text-xs text-gray-400">
                <span>Confidence: <span className={`font-medium ${item.confidence_score > 0.7 ? 'text-green-600' : 'text-yellow-600'}`}>{Math.round((item.confidence_score || 0) * 100)}%</span></span>
                {item.mentions_product && <span className="bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full">mentions product</span>}
              </div>
            </div>

            {/* Original post */}
            <div className="px-5 py-4 border-b border-gray-100">
              <div className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Original Post</div>
              <p className="text-sm text-gray-700 leading-relaxed">{item.original_content}</p>
              {item.original_url && (
                <a href={item.original_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline mt-2 block">
                  View original →
                </a>
              )}
            </div>

            {/* Draft reply */}
            <div className="px-5 py-4">
              <div className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">Draft Reply</div>
              {editingId === item.id ? (
                <div>
                  <textarea
                    value={editText}
                    onChange={e => setEditText(e.target.value)}
                    className="w-full text-sm border border-gray-200 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                    rows={4}
                  />
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={() => saveEdit(item.id)}
                      disabled={actionLoading === item.id}
                      className="text-sm bg-blue-600 text-white px-4 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => setEditingId(null)}
                      className="text-sm text-gray-500 hover:text-gray-700 px-4 py-1.5 rounded-lg border border-gray-200"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-800 leading-relaxed">
                  {item.edited_reply || item.draft_reply}
                  {item.edited_reply && <span className="ml-2 text-xs text-blue-500">(edited)</span>}
                </p>
              )}
            </div>

            {/* Actions */}
            {editingId !== item.id && (
              <div className="flex items-center gap-3 px-5 py-3 border-t border-gray-100 bg-gray-50">
                <button
                  onClick={() => approve(item)}
                  disabled={actionLoading === item.id}
                  className="flex items-center gap-1.5 bg-green-600 text-white text-sm font-medium px-5 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
                >
                  ✓ Approve & Post
                </button>
                <button
                  onClick={() => startEdit(item)}
                  className="flex items-center gap-1.5 border border-gray-200 text-gray-700 text-sm font-medium px-5 py-2 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  ✏️ Edit
                </button>
                <button
                  onClick={() => reject(item.id)}
                  disabled={actionLoading === item.id}
                  className="flex items-center gap-1.5 border border-red-200 text-red-600 text-sm font-medium px-5 py-2 rounded-lg hover:bg-red-50 disabled:opacity-50 transition-colors"
                >
                  ✕ Reject
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
