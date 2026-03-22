'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase-client'
import { ProductProvider, useProducts } from '@/lib/product-context'
import { apiFetch } from '@/lib/api'
import { useIsMobile } from '@/lib/hooks'

const nav = [
  { href: '/products', label: 'Products' },
  { href: '/queue', label: 'Queue' },
  { href: '/broadcast', label: 'Broadcast' },
  { href: '/history', label: 'History' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/settings', label: 'Settings' },
]

// Bottom tab bar items (subset — Settings lives in hamburger)
const bottomTabs = [
  { href: '/queue', label: 'Queue' },
  { href: '/broadcast', label: 'Broadcast' },
  { href: '/products', label: 'Products' },
  { href: '/history', label: 'History' },
  { href: '/analytics', label: 'Analytics' },
]

function ProductSwitcher({ onSelect }: { onSelect?: () => void }) {
  const { products, selectedProduct, selectProduct, loading } = useProducts()
  const [open, setOpen] = useState(false)
  const { isMobile } = useIsMobile()

  if (loading || products.length <= 1) return null

  return (
    <div style={{ padding: '0 12px 12px', position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%',
          padding: isMobile ? '12px 14px' : '10px 12px',
          borderRadius: '8px',
          background: '#fff',
          border: '1px solid #e8e8e8',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: isMobile ? '15px' : '13px',
          fontWeight: 500,
          color: '#111',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
          minHeight: '44px',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {selectedProduct?.name || 'Select product'}
        </span>
        <span style={{ fontSize: '10px', color: '#999', marginLeft: '8px' }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: '12px',
            right: '12px',
            background: '#fff',
            border: '1px solid #e8e8e8',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
            zIndex: 100,
            marginTop: '4px',
            maxHeight: '300px',
            overflowY: 'auto',
          }}
        >
          {products.map((p) => (
            <button
              key={p.id}
              onClick={() => {
                selectProduct(p.id)
                setOpen(false)
                onSelect?.()
              }}
              style={{
                width: '100%',
                padding: isMobile ? '14px 14px' : '10px 12px',
                background: p.id === selectedProduct?.id ? '#f5f5f5' : 'transparent',
                border: 'none',
                borderBottom: '1px solid #f0f0f0',
                cursor: 'pointer',
                textAlign: 'left',
                fontSize: isMobile ? '15px' : '13px',
                color: '#111',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                minHeight: '44px',
              }}
            >
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: p.active ? '#22c55e' : '#999',
                  flexShrink: 0,
                }}
              />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                {p.name}
              </span>
              {p.pending_count ? (
                <span style={{ marginLeft: 'auto', fontSize: '12px', color: '#999', flexShrink: 0 }}>
                  {p.pending_count}
                </span>
              ) : null}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

type HealthData = {
  health: string
  tier: number
  daily_cap: number
  posts_today: number
  paused: boolean
  paused_until: string | null
  pause_reason: string | null
}

const HEALTH_COLORS: Record<string, { dot: string; bg: string; text: string; label: string }> = {
  green:  { dot: '#22c55e', bg: 'rgba(34, 197, 94, 0.08)',  text: '#166534', label: 'Autopilot active' },
  yellow: { dot: '#eab308', bg: 'rgba(234, 179, 8, 0.08)',   text: '#854d0e', label: 'Autopilot degraded' },
  red:    { dot: '#ef4444', bg: 'rgba(239, 68, 68, 0.08)',   text: '#991b1b', label: 'Autopilot unhealthy' },
}

function AutopilotIndicator() {
  const { selectedProduct, selectedProductId } = useProducts()
  const isAutopilotActive = selectedProduct?.autopilot?.enabled ?? false
  const [health, setHealth] = useState<HealthData | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  useEffect(() => {
    if (!isAutopilotActive) return

    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = 'Autopilot is running. Closing this tab will pause automatic posting.'
      return e.returnValue
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isAutopilotActive])

  useEffect(() => {
    if (!isAutopilotActive || !selectedProductId) {
      setHealth(null)
      return
    }
    let cancelled = false
    async function fetchHealth() {
      try {
        const data = await apiFetch<HealthData>(`/queue/health?product_id=${selectedProductId}`)
        if (!cancelled) setHealth(data)
      } catch {
        if (!cancelled) setHealth(null)
      }
    }
    fetchHealth()
    const interval = setInterval(fetchHealth, 30000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [isAutopilotActive, selectedProductId])

  if (!isAutopilotActive) return null

  const colors = HEALTH_COLORS[health?.health || 'green'] || HEALTH_COLORS.green
  const isPaused = health?.paused ?? false
  const pauseReason = health?.pause_reason
  const pausedUntil = health?.paused_until

  async function togglePause() {
    if (!selectedProductId || actionLoading) return
    setActionLoading(true)
    try {
      if (isPaused) {
        await apiFetch(`/queue/resume`, {
          method: 'POST',
          body: JSON.stringify({ product_id: selectedProductId })
        })
      } else {
        await apiFetch(`/queue/pause`, {
          method: 'POST',
          body: JSON.stringify({ product_id: selectedProductId })
        })
      }
      const data = await apiFetch<HealthData>(`/queue/health?product_id=${selectedProductId}`)
      setHealth(data)
    } catch (e) {
      console.error('Pause/resume failed:', e)
    }
    setActionLoading(false)
  }

  function formatPauseInfo(): string {
    if (!isPaused) return ''
    if (pauseReason === 'extension_offline') return 'Extension offline'
    if (pauseReason === 'failure_streak') {
      if (pausedUntil) {
        const until = new Date(pausedUntil)
        return `Cooling down until ${until.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
      }
      return 'Paused (too many failures)'
    }
    if (pauseReason === 'manual') return 'Manually paused'
    if (pausedUntil) {
      const until = new Date(pausedUntil)
      return `Paused until ${until.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    }
    return 'Paused'
  }

  return (
    <div style={{ margin: '0 12px 8px' }}>
      {/* Main status row */}
      <div style={{
        padding: '8px 12px',
        background: isPaused ? 'rgba(239, 68, 68, 0.08)' : colors.bg,
        borderRadius: isPaused ? '8px 8px 0 0' : '8px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
      }}>
        <div style={{
          width: '8px',
          height: '8px',
          borderRadius: '50%',
          background: isPaused ? '#ef4444' : colors.dot,
          animation: isPaused ? 'none' : 'autopilotPulse 2s ease-in-out infinite',
        }}/>
        <span style={{
          fontSize: '12px',
          fontWeight: 500,
          color: isPaused ? '#991b1b' : colors.text,
          flex: 1,
        }}>
          {isPaused ? formatPauseInfo() : colors.label}
        </span>
        {health && (
          <span style={{ fontSize: '10px', color: '#999' }}>
            T{health.tier} {health.posts_today}/{health.daily_cap}
          </span>
        )}
        <button
          onClick={togglePause}
          disabled={actionLoading}
          style={{
            background: 'none',
            border: 'none',
            cursor: actionLoading ? 'not-allowed' : 'pointer',
            fontSize: '11px',
            fontWeight: 600,
            color: isPaused ? '#166534' : '#991b1b',
            padding: '2px 8px',
            borderRadius: '4px',
            opacity: actionLoading ? 0.5 : 1,
          }}
        >
          {actionLoading ? '...' : (isPaused ? 'Resume' : 'Pause')}
        </button>
      </div>

      {/* Pause reason banner */}
      {isPaused && pauseReason === 'extension_offline' && (
        <div style={{
          padding: '6px 12px',
          background: '#fff3e0',
          borderRadius: '0 0 8px 8px',
          borderTop: '1px solid #ffe0b2',
          fontSize: '11px',
          color: '#e65100',
        }}>
          Extension not sending heartbeats. Open the dashboard tab with the extension active to resume.
        </div>
      )}
      {isPaused && pauseReason === 'failure_streak' && (
        <div style={{
          padding: '6px 12px',
          background: '#ffebee',
          borderRadius: '0 0 8px 8px',
          borderTop: '1px solid #ffcdd2',
          fontSize: '11px',
          color: '#c62828',
        }}>
          Multiple consecutive posting failures detected. Check your Twitter connection.
        </div>
      )}
    </div>
  )
}

function DashboardShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const supabase = createClient()
  const [authed, setAuthed] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { isMobile } = useIsMobile()

  useEffect(() => {
    async function check() {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) { router.push('/login'); return }

      try {
        const { has_products } = await apiFetch<{has_products: boolean}>(`/products/check?user_id=${session.user.id}`)
        if (!has_products) { router.push('/onboarding'); return }
      } catch {
        router.push('/onboarding'); return
      }
      setAuthed(true)
    }
    check()
  }, [])

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false)
  }, [pathname])

  async function signOut() {
    await supabase.auth.signOut()
    router.push('/login')
  }

  if (!authed) return null

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#fff', position: 'relative' }}>
      {/* Mobile: Hamburger header bar */}
      {isMobile && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 150,
          height: '52px', background: '#fafafa', borderBottom: '1px solid #e8e8e8',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '0 16px',
        }}>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              padding: '8px', fontSize: '20px', color: '#111',
              minWidth: '44px', minHeight: '44px',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            aria-label="Menu"
          >
            {sidebarOpen ? '\u2715' : '\u2630'}
          </button>
          <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '0.15em', textTransform: 'uppercase', color: '#111' }}>
            Operative1
          </span>
          <div style={{ width: '44px' }} />
        </div>
      )}

      {/* Mobile: Sidebar overlay backdrop */}
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed', inset: 0, zIndex: 190,
            background: 'rgba(0,0,0,0.4)',
            transition: 'opacity 0.2s',
          }}
        />
      )}

      {/* Sidebar */}
      <aside style={{
        width: isMobile ? '280px' : '220px',
        background: '#fafafa',
        borderRight: '1px solid #e8e8e8',
        display: 'flex',
        flexDirection: 'column',
        ...(isMobile ? {
          position: 'fixed',
          top: 0,
          left: sidebarOpen ? 0 : '-280px',
          bottom: 0,
          zIndex: 200,
          transition: 'left 0.25s ease',
          boxShadow: sidebarOpen ? '4px 0 20px rgba(0,0,0,0.15)' : 'none',
          overflowY: 'auto',
        } : {}),
      }}>
        <div style={{ padding: isMobile ? '20px 20px 16px' : '24px 20px 16px' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.2em', textTransform: 'uppercase', color: '#111' }}>Operative1</div>
        </div>
        <ProductSwitcher onSelect={() => setSidebarOpen(false)} />
        <AutopilotIndicator />
        <nav style={{ flex: 1, padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {nav.map(n => (
            <Link key={n.href} href={n.href} onClick={() => setSidebarOpen(false)} style={{
              display: 'flex',
              padding: isMobile ? '12px 14px' : '8px 12px',
              borderRadius: '8px',
              fontSize: isMobile ? '16px' : '14px',
              fontWeight: 500,
              textDecoration: 'none',
              transition: 'background 0.1s',
              background: pathname === n.href ? '#fff' : 'transparent',
              color: pathname === n.href ? '#111' : '#666',
              boxShadow: pathname === n.href ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
              minHeight: '44px',
              alignItems: 'center',
            }}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div style={{ padding: '12px' }}>
          <button onClick={signOut} style={{
            width: '100%', textAlign: 'left',
            padding: isMobile ? '12px 14px' : '8px 12px',
            borderRadius: '8px', fontSize: isMobile ? '16px' : '14px',
            color: '#999', background: 'none', border: 'none', cursor: 'pointer',
            minHeight: '44px',
          }}>
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main style={{
        flex: 1,
        overflowY: 'auto',
        padding: isMobile ? '68px 16px 80px' : '40px',
        background: '#fff',
        width: '100%',
      }}>
        {children}
      </main>

      {/* Mobile: Bottom Tab Bar */}
      {isMobile && (
        <nav style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 150,
          height: '64px',
          background: '#fff',
          borderTop: '1px solid #e8e8e8',
          display: 'flex',
          alignItems: 'stretch',
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        }}>
          {bottomTabs.map(tab => {
            const active = pathname === tab.href
            return (
              <Link
                key={tab.href}
                href={tab.href}
                style={{
                  flex: 1,
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  textDecoration: 'none',
                  gap: '2px',
                  minHeight: '44px',
                  color: active ? '#111' : '#999',
                  position: 'relative',
                }}
              >
                {active && (
                  <div style={{
                    position: 'absolute', top: 0, left: '50%', transform: 'translateX(-50%)',
                    width: '24px', height: '3px', borderRadius: '0 0 3px 3px', background: '#111',
                  }} />
                )}
                <span style={{
                  fontSize: '11px',
                  fontWeight: active ? 700 : 500,
                  letterSpacing: '0.02em',
                  marginTop: '4px',
                }}>
                  {tab.label}
                </span>
              </Link>
            )
          })}
        </nav>
      )}
    </div>
  )
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProductProvider>
      <DashboardShell>{children}</DashboardShell>
      <style>{`
        @keyframes autopilotPulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.2); }
        }
      `}</style>
    </ProductProvider>
  )
}
