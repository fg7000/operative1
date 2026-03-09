'use client'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { createClient } from '@/lib/supabase-client'

const nav = [
  { href: '/products', label: 'Products' },
  { href: '/queue', label: 'Queue' },
  { href: '/history', label: 'History' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/settings', label: 'Settings' },
]

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!session) router.push('/login')
    })
  }, [])

  async function signOut() {
    await supabase.auth.signOut()
    router.push('/login')
  }

  return (
    <div className="flex h-screen bg-white">
      <aside className="w-56 flex flex-col border-r border-[#d1d1d6]" style={{background:'#f5f5f7'}}>
        <div className="px-6 py-6">
          <div className="text-[13px] font-semibold tracking-[0.15em] uppercase text-[#1d1d1f]">Operative1</div>
        </div>
        <nav className="flex-1 px-3 space-y-0.5">
          {nav.map(n => (
            <Link key={n.href} href={n.href} className={`flex items-center px-3 py-2.5 rounded-lg text-[14px] font-medium transition-colors ${
              pathname === n.href
                ? 'bg-white text-[#1d1d1f]'
                : 'text-[#6e6e73] hover:text-[#1d1d1f] hover:bg-white/60'
            }`} style={pathname === n.href ? {boxShadow:'0 1px 4px rgba(0,0,0,0.08)'} : {}}>
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="px-3 py-5">
          <button onClick={signOut} className="w-full text-left px-3 py-2.5 rounded-lg text-[14px] text-[#6e6e73] hover:text-[#1d1d1f] hover:bg-white/60 transition-colors">
            Sign Out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto bg-white p-10">{children}</main>
    </div>
  )
}
