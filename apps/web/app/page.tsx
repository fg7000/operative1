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

      const { count } = await supabase
        .from('products')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', session.user.id)

      router.push(count && count > 0 ? '/queue' : '/onboarding')
    }
    route()
  }, [])

  return null
}
