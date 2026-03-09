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
    setLoading(true); setError('')
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
    <div className="min-h-screen flex items-center justify-center p-6" style={{background:'#f5f5f7'}}>
      <div className="w-full max-w-[400px]">
        <div className="text-center mb-10">
          <div className="text-[13px] font-semibold tracking-[0.15em] uppercase text-[#6e6e73] mb-3">Operative1</div>
          <h1 className="text-[28px] font-semibold text-[#1d1d1f] leading-tight">
            {mode === 'login' ? 'Welcome back' : 'Get started'}
          </h1>
          <p className="text-[15px] text-[#6e6e73] mt-2">
            {mode === 'login' ? 'Sign in to your account' : 'Create your account'}
          </p>
        </div>

        <div className="bg-white rounded-2xl p-8" style={{boxShadow:'0 2px 20px rgba(0,0,0,0.08)'}}>
          <div className="space-y-4">
            <div>
              <label className="block text-[13px] font-medium text-[#1d1d1f] mb-1.5">Email</label>
              <input
                type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="w-full px-4 py-3 rounded-xl text-[15px] text-[#1d1d1f] outline-none transition-all"
                style={{background:'#f5f5f7', border:'1.5px solid transparent'}}
                onFocus={e => e.target.style.borderColor='#1d1d1f'}
                onBlur={e => e.target.style.borderColor='transparent'}
              />
            </div>
            <div>
              <label className="block text-[13px] font-medium text-[#1d1d1f] mb-1.5">Password</label>
              <input
                type="password" value={password} onChange={e => setPassword(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSubmit()}
                placeholder="••••••••"
                className="w-full px-4 py-3 rounded-xl text-[15px] text-[#1d1d1f] outline-none transition-all"
                style={{background:'#f5f5f7', border:'1.5px solid transparent'}}
                onFocus={e => e.target.style.borderColor='#1d1d1f'}
                onBlur={e => e.target.style.borderColor='transparent'}
              />
            </div>
          </div>

          {error && (
            <div className="mt-4 px-4 py-3 rounded-xl bg-[#fff2f2] text-[13px] text-[#ff3b30]">{error}</div>
          )}

          <button
            onClick={handleSubmit} disabled={loading}
            className="w-full mt-6 py-3.5 rounded-xl text-[15px] font-semibold text-white transition-opacity disabled:opacity-50"
            style={{background:'#1d1d1f'}}
          >
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>

          <p className="text-center text-[13px] text-[#6e6e73] mt-5">
            {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            <button onClick={() => setMode(mode === 'login' ? 'signup' : 'login')} className="text-[#1d1d1f] font-medium hover:underline">
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
