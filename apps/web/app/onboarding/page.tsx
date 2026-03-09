'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase-client'
import { useRouter } from 'next/navigation'

type Message = { role: 'assistant' | 'user', content: string }

const INITIAL_MESSAGE = `Welcome to Operative1.\n\nLet's configure your first product. Tell me what it is and what it does — describe it naturally, as you would to a colleague.`

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
        setMessages(prev => [...prev, { role: 'assistant', content: `Configuration ready for ${parsed.config.name}.\n\nKeywords: ${parsed.config.keywords.twitter.slice(0,3).join(', ')} and more\nTone: ${parsed.config.tone}\nPlatforms: Twitter, Reddit, HN, LinkedIn\n\nReview above and hit Launch, or tell me what to adjust.` }])
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
    <div style={{fontFamily:'Georgia, serif'}} className="min-h-screen bg-white flex flex-col">
      <div className="border-b-2 border-black px-8 py-5 flex items-center justify-between">
        <div className="text-xs font-bold tracking-[0.3em] uppercase">Operative1</div>
        <div className="text-xs tracking-widest uppercase text-gray-400">Product Setup</div>
      </div>

      <div className="flex-1 overflow-auto px-8 py-8 max-w-2xl mx-auto w-full">
        <div className="space-y-6">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-lg text-sm leading-relaxed whitespace-pre-wrap px-5 py-4 ${
                m.role === 'user'
                  ? 'bg-black text-white'
                  : 'bg-white text-black border border-black'
              }`}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="border border-black px-5 py-4 text-xs tracking-widest text-gray-400 uppercase">
                Thinking...
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="border-t-2 border-black px-8 py-6 max-w-2xl mx-auto w-full">
        {done && productConfig ? (
          <div className="flex gap-3">
            <button onClick={launchProduct} disabled={loading} className="flex-1 bg-black text-white text-xs tracking-widest uppercase py-4 hover:bg-gray-900 transition-colors disabled:opacity-40">
              Launch {productConfig.name}
            </button>
            <button onClick={() => setDone(false)} className="px-6 border border-black text-black text-xs tracking-widest uppercase hover:bg-gray-50">
              Edit
            </button>
          </div>
        ) : (
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && sendMessage()}
              placeholder="Describe your product..."
              className="flex-1 border border-black px-4 py-3 text-sm text-black bg-white focus:outline-none focus:ring-1 focus:ring-black"
            />
            <button onClick={sendMessage} disabled={loading || !input.trim()} className="px-8 bg-black text-white text-xs tracking-widest uppercase hover:bg-gray-900 transition-colors disabled:opacity-40">
              Send
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
