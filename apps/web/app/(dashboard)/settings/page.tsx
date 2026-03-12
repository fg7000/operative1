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
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

  useEffect(() => {
    async function init() {
      const { data: { user } } = await supabase.auth.getUser()
      if (user?.email) {
        setEmail(user.email)
        await checkTwitterStatus(user.email)
      }
      setLoading(false)
    }
    init()
  }, [])

  async function checkTwitterStatus(userEmail: string) {
    try {
      const res = await fetch(`${API}/settings/twitter-status?email=${encodeURIComponent(userEmail)}`)
      const data = await res.json()
      setTwitterConnected(data.connected)
      setLastUpdated(data.last_updated || null)
    } catch (e) {
      console.error('Failed to check Twitter status:', e)
    }
  }

  async function disconnectTwitter() {
    if (!email) return
    if (!confirm('Are you sure you want to disconnect Twitter?')) return

    try {
      await fetch(`${API}/settings/twitter-disconnect?email=${encodeURIComponent(email)}`, {
        method: 'DELETE'
      })
      setTwitterConnected(false)
      setLastUpdated(null)
    } catch (e) {
      console.error('Failed to disconnect:', e)
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
          {twitterConnected ? (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#22c55e' }} />
                <span style={{ fontSize: '14px', fontWeight: 500, color: '#111' }}>Connected</span>
              </div>
              {lastUpdated && (
                <p style={{ fontSize: '13px', color: '#666', marginBottom: '16px' }}>
                  Last updated: {new Date(lastUpdated).toLocaleDateString()}
                </p>
              )}
              <button
                onClick={disconnectTwitter}
                style={{
                  padding: '10px 18px',
                  borderRadius: '8px',
                  background: '#fff',
                  color: '#e53e3e',
                  fontSize: '13px',
                  fontWeight: 500,
                  border: '1px solid #ffd7d7',
                  cursor: 'pointer'
                }}
              >
                Disconnect Twitter
              </button>
            </div>
          ) : (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#999' }} />
                <span style={{ fontSize: '14px', fontWeight: 500, color: '#111' }}>Not connected</span>
              </div>
              <p style={{ fontSize: '13px', color: '#666', marginBottom: '16px', lineHeight: 1.5 }}>
                Connect your Twitter account to enable reply posting. Use the Operative1 Chrome extension to securely link your account.
              </p>
              <div style={{ padding: '16px', background: '#f5f5f5', borderRadius: '8px' }}>
                <p style={{ fontSize: '13px', color: '#555', marginBottom: '12px' }}>
                  <strong>How to connect:</strong>
                </p>
                <ol style={{ fontSize: '13px', color: '#555', lineHeight: 1.6, paddingLeft: '20px', margin: 0 }}>
                  <li>Install the Operative1 Chrome extension</li>
                  <li>Log into x.com in your browser</li>
                  <li>Click the extension and enter your email: <strong>{email}</strong></li>
                  <li>Click "Connect Twitter"</li>
                </ol>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Extension Download */}
      <div>
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: '#111', marginBottom: '16px' }}>Chrome Extension</h2>
        <div style={{ padding: '20px', background: '#fff', borderRadius: '12px', border: '1px solid #e8e8e8' }}>
          <p style={{ fontSize: '13px', color: '#666', marginBottom: '16px', lineHeight: 1.5 }}>
            The Operative1 Chrome extension enables secure Twitter connection without sharing your password.
          </p>
          <a
            href="/extension.zip"
            download
            style={{
              display: 'inline-block',
              padding: '10px 18px',
              borderRadius: '8px',
              background: '#111',
              color: '#fff',
              fontSize: '13px',
              fontWeight: 600,
              textDecoration: 'none'
            }}
          >
            Download Extension
          </a>
          <p style={{ fontSize: '12px', color: '#999', marginTop: '12px' }}>
            After downloading, unzip and load via chrome://extensions (Developer mode)
          </p>
        </div>
      </div>
    </div>
  )
}
