import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import type { MascotMood, MaturityProfile, ForecastStage } from '../types'
import { getMaturity } from '../api/forecasting'
import { useAuth } from './authContext'

interface MascotMessage {
  text: string
  mood: MascotMood
  duration?: number   // ms — auto-dismiss after this. undefined = stays until next message.
}

interface MascotContextValue {
  mood: MascotMood
  message: MascotMessage | null
  isExpanded: boolean
  maturity: MaturityProfile | null
  speak: (msg: MascotMessage) => void
  setMood: (mood: MascotMood) => void
  toggleExpanded: () => void
  refreshMaturity: () => Promise<void>
}

const MascotContext = createContext<MascotContextValue | null>(null)

export function MascotProvider({ children }: { children: React.ReactNode }) {
  const { org } = useAuth()
  const [mood, setMood] = useState<MascotMood>('idle')
  const [message, setMessage] = useState<MascotMessage | null>(null)
  const [isExpanded, setIsExpanded] = useState(false)
  const [maturity, setMaturity] = useState<MaturityProfile | null>(null)

  const speak = useCallback((msg: MascotMessage) => {
    setMessage(msg)
    setMood(msg.mood)
    if (msg.duration) {
      setTimeout(() => setMessage(null), msg.duration)
    }
  }, [])

  const toggleExpanded = useCallback(() => setIsExpanded((v) => !v), [])

  const refreshMaturity = useCallback(async () => {
    if (!org) return
    try {
      const res = await getMaturity(org.id)
      const profile = res.data.data
      setMaturity(profile)
      setMood(profile.mascot_mood as MascotMood)
    } catch {
      // non-critical — mascot still works without maturity data
    }
  }, [org])

  useEffect(() => {
    refreshMaturity()
  }, [refreshMaturity])

  return (
    <MascotContext.Provider value={{ mood, message, isExpanded, maturity, speak, setMood, toggleExpanded, refreshMaturity }}>
      {children}
    </MascotContext.Provider>
  )
}

export function useMascot() {
  const ctx = useContext(MascotContext)
  if (!ctx) throw new Error('useMascot must be used within MascotProvider')
  return ctx
}

export const STAGE_COLORS: Record<ForecastStage, string> = {
  new: 'var(--color-stage-new)',
  learning: 'var(--color-stage-learning)',
  developing: 'var(--color-stage-developing)',
  established: 'var(--color-stage-established)',
  expert: 'var(--color-stage-expert)',
}

export const STAGE_LABELS: Record<ForecastStage, string> = {
  new: 'Getting Started',
  learning: 'Learning',
  developing: 'Developing',
  established: 'Established',
  expert: 'Full Intelligence',
}
