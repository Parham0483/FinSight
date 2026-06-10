import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import type { User, Organisation } from '../types'
import { getMe } from '../api/auth'
import client from '../api/client'

interface AuthContextValue {
  user: User | null
  org: Organisation | null
  orgs: Organisation[]
  loading: boolean
  setOrg: (org: Organisation) => void
  refreshUser: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [org, setOrg] = useState<Organisation | null>(null)
  const [orgs, setOrgs] = useState<Organisation[]>([])
  const [loading, setLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    try {
      const res = await getMe()
      setUser(res.data)
      // Load orgs
      const orgsRes = await client.get('/orgs/')
      const orgList: Organisation[] = orgsRes.data?.data ?? orgsRes.data?.results ?? orgsRes.data ?? []
      setOrgs(orgList)
      if (!org && orgList.length > 0) setOrg(orgList[0])
    } catch {
      setUser(null)
      setOrgs([])
    }
  }, [org])

  useEffect(() => {
    refreshUser().finally(() => setLoading(false))
  }, [])

  const logout = useCallback(async () => {
    await client.post('/auth/logout/')
    setUser(null)
    setOrg(null)
    setOrgs([])
  }, [])

  return (
    <AuthContext.Provider value={{ user, org, orgs, loading, setOrg, refreshUser, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
