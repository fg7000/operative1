'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase-client'

export default function Home() {
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    async function route() {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) { router.push('/login'); return }

      const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const res = await fetch(`${API}/products/check?user_id=${session.user.id}`)
      const { has_products } = await res.json()

      router.push(has_products ? '/queue' : '/onboarding')
    }
    route()
  }, [])

  return null
}
