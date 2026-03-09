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
    <div style={{fontFamily:'Georgia, serif'}} className="flex h-screen bg-white">
      <aside className="w-52 bg-white border-r-2 border-black flex flex-col">
        <div className="px-6 py-6 border-b border-black">
          <div className="text-xs font-bold tracking-[0.3em] uppercase text-black">Operative1</div>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-1">
          {nav.map(n => (
            <Link
              key={n.href}
              href={n.href}
              className={`flex items-center px-3 py-2.5 text-xs tracking-widest uppercase transition-colors ${
                pathname === n.href
                  ? 'bg-black text-white'
                  : 'text-gray-500 hover:text-black hover:bg-gray-50'
              }`}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-black">
          <button
            onClick={signOut}
            className="w-full text-left px-3 py-2 text-xs tracking-widest uppercase text-gray-400 hover:text-black transition-colors"
          >
            Sign Out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto p-10 bg-white">{children}</main>
    </div>
  )
}
