// Shared constants for Operative1 dashboard

export const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const PLATFORM_COLORS: Record<string, string> = {
  twitter: '#000',
  reddit: '#ff4500',
  linkedin: '#0077b5',
  hn: '#ff6600',
}

export const MODE_COLORS: Record<string, { bg: string; color: string }> = {
  helpful_expert: { bg: '#e8f5e9', color: '#2e7d32' },
  soft_mention: { bg: '#e3f2fd', color: '#1565c0' },
  direct_pitch: { bg: '#fff3e0', color: '#e65100' },
}

export const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  posted: { bg: '#e8f5e9', color: '#2e7d32' },
  failed: { bg: '#ffebee', color: '#c62828' },
  rejected: { bg: '#fff3e0', color: '#e65100' },
  pending: { bg: '#e3f2fd', color: '#1565c0' },
}
