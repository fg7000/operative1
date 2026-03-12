'use client'
import { useEffect, useState } from 'react'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

export default function SettingsPage() {
  const [email, setEmail] = useState<string | null>(null)
  const [twitterConnected, setTwitterConnected] = useState(false)
  const [loading, setLoading] = useState(true)

  const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  useEffect(() => {
    async function init() {
      const { data: { user } } = await supabase.auth.getUser()
      if (user?.email) {
        setEmail(user.email)
      }
      await checkTwitterStatus()
      setLoading(false)
    }
    init()
  }, [])

  async function checkTwitterStatus() {
    try {
      const res = await fetch(`${API}/settings/twitter-status`)
      const data = await res.json()
      setTwitterConnected(data.connected)
    } catch (e) {
      console.error('Failed to check Twitter status:', e)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px', color: '#999', fontSize: '14px' }}>
        Loading...
      </div>
    )
  }

  return (
    <div style={{ maxWidth: '600px' }}>
      <h1 style={{ fontSize: '28px', fontWeight: 600, color: '#111', marginBottom: '8px' }}>Settings</h1>
      <p style={{ fontSize: '14px', color: '#999', marginBottom: '32px' }}>Manage your account and connections</p>

      {/* Account Section */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: '#111', marginBottom: '16px' }}>Account</h2>
        <div style={{ padding: '16px 20px', background: '#fafafa', borderRadius: '12px', border: '1px solid #e8e8e8' }}>
          <div style={{ fontSize: '12px', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#999', marginBottom: '4px' }}>Email</div>
          <div style={{ fontSize: '14px', color: '#111' }}>{email || 'Not signed in'}</div>
        </div>
      </div>

      {/* Twitter Connection Section */}
      <div style={{ marginBottom: '32px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: '#111', marginBottom: '16px' }}>Twitter Connection</h2>
        <div style={{ padding: '20px', background: '#fff', borderRadius: '12px', border: '1px solid #e8e8e8' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: twitterConnected ? '#22c55e' : '#999' }} />
            <span style={{ fontSize: '14px', fontWeight: 500, color: '#111' }}>
              {twitterConnected ? 'Connected (via environment variables)' : 'Not connected'}
            </span>
          </div>
          <p style={{ fontSize: '13px', color: '#666', lineHeight: 1.5 }}>
            Twitter connection is managed via environment variables (TWITTER_AUTH_TOKEN and TWITTER_CT0).
            Contact support to update your Twitter credentials.
          </p>
        </div>
      </div>
    </div>
  )
}
