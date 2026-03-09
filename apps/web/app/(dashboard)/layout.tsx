import Link from 'next/link'

const nav = [
  { href: '/products', label: 'Products' },
  { href: '/queue', label: 'Queue' },
  { href: '/history', label: 'History' },
  { href: '/analytics', label: 'Analytics' },
  { href: '/settings', label: 'Settings' },
]

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen">
      <aside className="w-56 bg-gray-900 text-white flex flex-col p-6 gap-4">
        <div className="text-xl font-bold mb-6">Operative1</div>
        {nav.map(n => (
          <Link key={n.href} href={n.href} className="hover:text-gray-300 transition-colors">
            {n.label}
          </Link>
        ))}
      </aside>
      <main className="flex-1 overflow-auto bg-gray-50 p-8">{children}</main>
    </div>
  )
}
