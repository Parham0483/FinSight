import client from './client'
import type { ApiResponse, CombinedForecast, MaturityProfile } from '../types'

// Note: every DRF response is wrapped in {success, data} by EnvelopeRenderer
// (see backend/core/renderers.py) — callers must read `res.data.data`, not
// `res.data`, to get the actual payload. Typed as ApiResponse<T> so
// TypeScript catches the unwrap at the call site (this used to be typed as
// bare MaturityProfile, which let mascotContext.tsx silently read `res.data`
// as if it were the profile itself — the wrapper wasn't reflected in the
// type, so nothing caught it).
export const getMaturity = (orgId: string) =>
  client.get<ApiResponse<MaturityProfile>>(`/forecast/orgs/${orgId}/maturity/`)

export const getCombinedForecast = (orgId: string, options?: { horizonDays?: number; safetyBuffer?: string }) => {
  const params = new URLSearchParams()
  if (options?.horizonDays !== undefined) params.set('horizon_days', String(options.horizonDays))
  if (options?.safetyBuffer !== undefined) params.set('safety_buffer', options.safetyBuffer)
  const query = params.toString() ? `?${params.toString()}` : ''
  return client.get<ApiResponse<CombinedForecast>>(`/forecast/orgs/${orgId}/combined/${query}`)
}
