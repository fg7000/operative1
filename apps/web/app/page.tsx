'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase-client'
import { apiFetch } from '@/lib/api'

export default function Home() {
  const router = useRouter()
  const supabase = createClient()

  useEffect(() => {
    async function route() {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) { router.push('/login'); return }

      try {
        const { has_products } = await apiFetch<{has_products: boolean}>(`/products/check?user_id=${session.user.id}`)
        router.push(has_products ? '/queue' : '/onboarding')
      } catch {
        // If check fails, assume no products and go to onboarding
        router.push('/onboarding')
      }
    }
    route()
  }, [])

  return null
}
