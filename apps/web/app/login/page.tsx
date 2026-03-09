'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase-client'
import { useRouter } from 'next/navigation'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()
  const supabase = createClient()

  async function handleSubmit() {
    setLoading(true)
    setError('')
    if (mode === 'signup') {
      const { error } = await supabase.auth.signUp({ email, password })
      if (error) { setError(error.message); setLoading(false); return }
      router.push('/onboarding')
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password })
      if (error) { setError(error.message); setLoading(false); return }
      router.push('/queue')
    }
    setLoading(false)
  }

  return (
    <div style={{fontFamily:'Georgia, serif'}} className="min-h-screen bg-white flex items-center justify-center p-8">
      <div className="w-full max-w-sm">
        <div className="border-b-2 border-black pb-6 mb-8">
          <div className="text-xs font-bold tracking-[0.3em] text-black uppercase mb-2">Operative1</div>
          <div className="text-xs tracking-widest text-gray-500 uppercase">Autonomous Reply Engine</div>
        </div>

        <h2 style={{fontFamily:'Georgia, serif'}} className="text-2xl font-normal text-black mb-8">
          {mode === 'login' ? 'Sign in to continue' : 'Create your account'}
        </h2>

        <div className="space-y-5">
          <div>
            <label className="block text-xs tracking-widest uppercase text-gray-500 mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full border border-black px-4 py-3 text-sm text-black bg-white focus:outline-none focus:ring-1 focus:ring-black"
              placeholder="you@company.com"
            />
          </div>
          <div>
            <label className="block text-xs tracking-widest uppercase text-gray-500 mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSubmit()}
              className="w-full border border-black px-4 py-3 text-sm text-black bg-white focus:outline-none focus:ring-1 focus:ring-black"
              placeholder="••••••••"
            />
          </div>
        </div>

        {error && <p className="text-xs text-black border-l-2 border-black pl-3 mt-4">{error}</p>}

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full mt-8 bg-black text-white text-xs tracking-widest uppercase py-4 hover:bg-gray-900 transition-colors disabled:opacity-40"
        >
          {loading ? 'Please wait...' : mode === 'login' ? 'Sign In' : 'Create Account'}
        </button>

        <p className="text-center text-xs text-gray-400 mt-6">
          {mode === 'login' ? "No account? " : 'Have an account? '}
          <button onClick={() => setMode(mode === 'login' ? 'signup' : 'login')} className="text-black underline">
            {mode === 'login' ? 'Sign up' : 'Sign in'}
          </button>
        </p>
      </div>
    </div>
  )
}
