import { NavLink } from 'react-router-dom'
import { useMascot } from '../../store/mascotContext'
import { useAuth } from '../../store/authContext'
import { STAGE_COLORS, STAGE_LABELS } from '../../store/mascotContext'

const NAV_ITEMS = [
  { path: '/dashboard',     label: 'Dashboard',     icon: '◈', capability: null },
  { path: '/transactions',  label: 'Transactions',  icon: '≡',  capability: 'transaction_view' },
  { path: '/forecast',      label: 'Forecast',      icon: '◎', capability: 'forecast_7day' },
  { path: '/documents',     label: 'Documents',     icon: '⊡', capability: null },
  { path: '/customers',     label: 'Customers',     icon: '◉', capability: null },
  { path: '/fx',            label: 'FX Exposure',   icon: '◐', capability: 'fx_exposure' },
  { path: '/insights',      label: 'AI Insights',   icon: '✦', capability: 'ai_daily_briefing' },
  { path: '/alerts',        label: 'Alerts',        icon: '◬', capability: null },
  { path: '/settings',      label: 'Settings',      icon: '⊕', capability: null },
]

export default function Sidebar() {
  const { maturity } = useMascot()
  const { org } = useAuth()
  const capabilities = maturity?.capabilities ?? []

  return (
    <nav style={{
      width: 'var(--sidebar-width)',
      minWidth: 'var(--sidebar-width)',
      background: 'var(--color-surface)',
      borderRight: '1px solid var(--color-border)',
      display: 'flex',
      flexDirection: 'column',
      padding: 'var(--space-4) 0',
      height: '100vh',
      position: 'sticky',
      top: 0,
      overflowY: 'auto',
    }}>
      {/* Logo / Brand placeholder */}
      <div style={{ padding: 'var(--space-4) var(--space-5)', marginBottom: 'var(--space-4)' }}>
        <div style={{
          fontSize: 'var(--text-lg)',
          fontWeight: 'var(--font-bold)',
          color: 'var(--color-text-primary)',
          letterSpacing: '-0.02em',
        }}>
          {/* Brand name TBD */}
          <span style={{ color: 'var(--color-accent)' }}>Fin</span>Sight
        </div>
        {org && (
          <div style={{
            fontSize: 'var(--text-xs)',
            color: 'var(--color-text-muted)',
            marginTop: 'var(--space-1)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
            {org.name}
          </div>
        )}
      </div>

      {/* Maturity indicator */}
      {maturity?.stage && (
        <div style={{
          margin: '0 var(--space-4) var(--space-4)',
          padding: 'var(--space-3)',
          background: 'var(--color-surface-2)',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--color-border)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Intelligence</span>
            <span style={{ fontSize: '11px', color: STAGE_COLORS[maturity.stage], fontWeight: 600 }}>
              {STAGE_LABELS[maturity.stage]}
            </span>
          </div>
          <div style={{ background: 'var(--color-border)', borderRadius: '9999px', height: 4 }}>
            <div style={{
              background: STAGE_COLORS[maturity.stage],
              width: `${(maturity.progress_to_next ?? 0) * 100}%`,
              height: '100%',
              borderRadius: '9999px',
              transition: 'width 0.4s ease',
            }} />
          </div>
        </div>
      )}

      {/* Nav items */}
      <div style={{ flex: 1 }}>
        {NAV_ITEMS.map(({ path, label, icon, capability }) => {
          const locked = capability && !capabilities.includes(capability)
          return (
            <NavLink
              key={path}
              to={path}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                padding: 'var(--space-3) var(--space-5)',
                fontSize: 'var(--text-sm)',
                fontWeight: isActive ? 600 : 400,
                color: locked
                  ? 'var(--color-text-muted)'
                  : isActive
                  ? 'var(--color-text-primary)'
                  : 'var(--color-text-secondary)',
                background: isActive ? 'var(--color-accent-dim)' : 'transparent',
                borderLeft: isActive ? '2px solid var(--color-accent)' : '2px solid transparent',
                textDecoration: 'none',
                transition: 'all var(--transition-fast)',
                opacity: locked ? 0.45 : 1,
                cursor: locked ? 'default' : 'pointer',
                pointerEvents: locked ? 'none' : 'auto',
              })}
            >
              <span style={{ fontSize: 16, width: 20, textAlign: 'center' }}>{icon}</span>
              <span>{label}</span>
              {locked && (
                <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--color-text-muted)' }}>🔒</span>
              )}
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
