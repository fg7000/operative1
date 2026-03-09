'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase-client'
import { useRouter } from 'next/navigation'

type Message = { role: 'assistant' | 'user', content: string }

const INITIAL_MESSAGE = `Welcome to Operative1! I'll help you set up your first product in about 2 minutes.\n\nLet's start: What's your product called, and what does it do? Just describe it naturally.`

export default function OnboardingPage() {
  const [messages, setMessages] = useState<Message[]>([{ role: 'assistant', content: INITIAL_MESSAGE }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [productConfig, setProductConfig] = useState<any>(null)
  const router = useRouter()
  const supabase = createClient()

  async function sendMessage() {
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    const history = [...messages, { role: 'user' as const, content: userMsg }]
    setMessages(history)
    setLoading(true)

    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1000,
        system: `You are an onboarding assistant for Operative1, an autonomous reply marketing engine. Gather info about the user's product through natural conversation then generate config.

Gather through conversation (one question at a time):
1. Product name and description
2. Value proposition
3. Target audience
4. Platforms to monitor (Twitter, Reddit, LinkedIn, HN)
5. Tone preference

After 3-4 exchanges when you have enough info, respond with ONLY this JSON and nothing else:
{"ready":true,"config":{"name":"Product Name","slug":"product-slug","description":"short description","value_prop":"detailed value prop","system_prompt":"full system prompt telling AI how to respond as this brand","keywords":{"twitter":["kw1","kw2","kw3"],"reddit":["kw1","kw2"],"hn":["kw1"],"linkedin":["kw1","kw2"]},"tone":"helpful-technical","target_subreddits":["sub1","sub2"]}}

Until then respond conversationally. Be friendly and brief.`,
        messages: history.map(m => ({ role: m.role, content: m.content }))
      })
    })

    const data = await res.json()
    const content = data.content[0].text

    try {
      const parsed = JSON.parse(content)
      if (parsed.ready && parsed.config) {
        setProductConfig(parsed.config)
        setMessages(prev => [...prev, { role: 'assistant', content: `Perfect! I have everything I need for **${parsed.config.name}**.\n\nHere's what I configured:\n- Keywords: ${parsed.config.keywords.twitter.slice(0,3).join(', ')} and more\n- Tone: ${parsed.config.tone}\n- Platforms: Twitter, Reddit, HN, LinkedIn\n\nHit Launch to start monitoring, or tell me what to change.` }])
        setDone(true)
        setLoading(false)
        return
      }
    } catch {}

    setMessages(prev => [...prev, { role: 'assistant', content: content }])
    setLoading(false)
  }

  async function launchProduct() {
    if (!productConfig) return
    setLoading(true)
    const { data: { user } } = await supabase.auth.getUser()
    const { error } = await supabase.from('products').insert({
      ...productConfig,
      user_id: user?.id,
      auto_post: { twitter: false, reddit: false, linkedin: false, hn: false },
      max_daily_replies: { twitter: 5, reddit: 3, linkedin: 3, hn: 1 },
      active: true
    })
    if (error) { setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${error.message}` }]); setLoading(false); return }
    router.push('/queue')
  }

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <div className="border-b border-gray-800 px-6 py-4">
        <h1 className="text-white font-semibold">Operative1 — Product Setup</h1>
      </div>
      <div className="flex-1 overflow-auto px-4 py-6 max-w-2xl mx-auto w-full">
        <div className="space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-lg rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${m.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-100'}`}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl px-4 py-3">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{animationDelay:'0ms'}}/>
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{animationDelay:'150ms'}}/>
                  <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{animationDelay:'300ms'}}/>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
      <div className="border-t border-gray-800 px-4 py-4 max-w-2xl mx-auto w-full">
        {done && productConfig ? (
          <div className="flex gap-3">
            <button onClick={launchProduct} disabled={loading} className="flex-1 bg-green-600 hover:bg-green-700 text-white font-medium py-3 rounded-xl transition-colors disabled:opacity-50">
              Launch {productConfig.name}
            </button>
            <button onClick={() => setDone(false)} className="px-6 border border-gray-700 text-gray-400 rounded-xl hover:border-gray-600">
              Edit
            </button>
          </div>
        ) : (
          <div className="flex gap-3">
            <input type="text" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && sendMessage()} placeholder="Describe your product..." className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-blue-500" />
            <button onClick={sendMessage} disabled={loading || !input.trim()} className="px-6 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-colors disabled:opacity-50">Send</button>
          </div>
        )}
      </div>
    </div>
  )
}
