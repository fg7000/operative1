// API utility for Operative1 dashboard
// All API calls should go through this module for consistent auth and error handling

import { API_URL } from './constants'
import { createClient } from './supabase-client'

/**
 * Fetch wrapper that automatically includes auth token
 *
 * Usage:
 *   const data = await apiFetch('/products')
 *   const data = await apiFetch('/products/123', { method: 'PATCH', body: JSON.stringify({...}) })
 */
export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  // Add auth header if we have a session
  if (session?.access_token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${session.access_token}`
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const error = await res.text()
    throw new Error(error || `API error: ${res.status}`)
  }

  return res.json()
}

/**
 * Fetch without auth requirement (for public endpoints)
 */
export async function publicFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  })

  if (!res.ok) {
    const error = await res.text()
    throw new Error(error || `API error: ${res.status}`)
  }

  return res.json()
}
