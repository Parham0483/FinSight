import { useAuth } from '../../store/authContext'

export default function TopBar() {
  const { user, org, orgs, setOrg, logout } = useAuth()

  return (
    <header style={{
      height: 'var(--topbar-height)',
      background: 'var(--color-surface)',
      borderBottom: '1px solid var(--color-border)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 var(--space-8)',
      gap: 'var(--space-4)',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Org switcher */}
      {orgs.length > 1 && (
        <select
          value={org?.id ?? ''}
          onChange={(e) => {
            const selected = orgs.find((o) => o.id === e.target.value)
            if (selected) setOrg(selected)
          }}
          style={{
            background: 'var(--color-surface-2)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            color: 'var(--color-text-primary)',
            fontSize: 'var(--text-sm)',
            padding: 'var(--space-2) var(--space-3)',
            cursor: 'pointer',
          }}
        >
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>{o.name}</option>
          ))}
        </select>
      )}

      <div style={{ flex: 1 }} />

      {/* User display */}
      {user && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
            {user.full_name || user.email}
          </span>
          <button className="btn btn-ghost" style={{ padding: 'var(--space-1) var(--space-3)', fontSize: 'var(--text-xs)' }} onClick={logout}>
            Sign out
          </button>
        </div>
      )}
    </header>
  )
}
