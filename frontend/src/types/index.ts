export interface User {
  id: string
  email: string
  full_name: string
  is_verified: boolean
  created_at: string
}

export interface Organisation {
  id: string
  name: string
  industry: string
  country_code: string
  base_currency: string
  timezone: string
  locale: string
  is_demo: boolean
  created_at: string
}

export type ForecastStage = 'new' | 'learning' | 'developing' | 'established' | 'expert'
export type MascotMood = 'idle' | 'thinking' | 'happy' | 'concerned' | 'celebrating'

export interface MaturityProfile {
  stage: ForecastStage
  days_of_data: number
  forecast_horizon_days: number
  progress_to_next: number
  mascot_message: string
  mascot_mood: MascotMood
  capabilities: string[]
  next_milestone_days: number
  next_milestone_label: string
}

export interface DailyBalancePoint {
  date: string
  known_net: string
  statistical_p10: string
  statistical_p50: string
  statistical_p90: string
  balance_p10: string
  balance_p50: string
  balance_p90: string
  drivers: Record<string, string>
}

export interface CombinedForecast {
  starting_balance: string
  horizon_days: number
  statistical_method: string | null
  points: DailyBalancePoint[]
  runway: {
    most_likely_cashout_date: string | null
    worst_case_cashout_date: string | null
  }
  driver_totals: Record<string, string>
}

export interface ApiResponse<T> {
  success: boolean
  data: T
  meta?: { pagination?: { total: number; next: string | null; previous: string | null } }
}

export interface ApiError {
  success: false
  error: { code: string; message: string; field_errors: Record<string, string[]> }
}
