import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './store/authContext'
import AppShell from './components/layout/AppShell'
import Login from './pages/auth/Login'
import Register from './pages/auth/Register'
import OnboardingWizard from './pages/onboarding/OnboardingWizard'
import Dashboard from './pages/dashboard/Dashboard'

function FullPageSpinner() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: 'var(--color-bg)',
    }}>
      <div style={{
        width: 40,
        height: 40,
        borderRadius: '50%',
        border: '3px solid var(--color-border)',
        borderTopColor: 'var(--color-accent)',
        animation: 'spin 0.8s linear infinite',
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

function RequireAuth() {
  const { user, loading } = useAuth()
  if (loading) return <FullPageSpinner />
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}

function RequireOrg() {
  const { user, orgs, loading } = useAuth()
  if (loading) return <FullPageSpinner />
  if (!user) return <Navigate to="/login" replace />
  if (orgs.length === 0) return <Navigate to="/onboarding" replace />
  return <Outlet />
}

function GuestOnly() {
  const { user, loading } = useAuth()
  if (loading) return <FullPageSpinner />
  if (user) return <Navigate to="/dashboard" replace />
  return <Outlet />
}

function Placeholder({ title }: { title: string }) {
  return (
    <div style={{ padding: 'var(--space-8)' }}>
      <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, marginBottom: 'var(--space-2)' }}>{title}</h1>
      <p style={{ color: 'var(--color-text-secondary)' }}>Coming soon.</p>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      {/* Public routes — redirect to /dashboard if already signed in */}
      <Route element={<GuestOnly />}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Route>

      {/* Onboarding — requires auth, but no org yet */}
      <Route element={<RequireAuth />}>
        <Route path="/onboarding" element={<OnboardingWizard />} />
      </Route>

      {/* App routes — require auth + at least one org */}
      <Route element={<RequireOrg />}>
        <Route element={<AppShell><Outlet /></AppShell>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/transactions" element={<Placeholder title="Transactions" />} />
          <Route path="/forecast" element={<Placeholder title="Forecast" />} />
          <Route path="/documents" element={<Placeholder title="Documents" />} />
          <Route path="/customers" element={<Placeholder title="Customers" />} />
          <Route path="/fx" element={<Placeholder title="FX Exposure" />} />
          <Route path="/insights" element={<Placeholder title="AI Insights" />} />
          <Route path="/alerts" element={<Placeholder title="Alerts" />} />
          <Route path="/settings" element={<Placeholder title="Settings" />} />
        </Route>
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}
