import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../store/authContext'
import { useMascot, STAGE_COLORS, STAGE_LABELS } from '../../store/mascotContext'

export default function Dashboard() {
  const { org } = useAuth()
  const { maturity, speak } = useMascot()

  useEffect(() => {
    if (!maturity) return
    if (maturity.stage === 'new') {
      speak({
        text: "Upload your first invoice or bank statement to activate forecasting.",
        mood: 'idle',
        duration: 7000,
      })
    } else if (maturity.stage === 'learning') {
      speak({
        text: `I have ${maturity.days_of_data} days of data. ${maturity.next_milestone_label}`,
        mood: 'thinking',
        duration: 5000,
      })
    }
  }, [maturity?.stage])

  return (
    <div>
      {/* Page header */}
      <div style={{ marginBottom: 'var(--space-8)' }}>
        <h1 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, letterSpacing: '-0.02em' }}>
          Dashboard
        </h1>
        {org && (
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)', marginTop: 'var(--space-1)' }}>
            {org.name} · {org.base_currency} · {org.country_code}
          </p>
        )}
      </div>

      {/* Maturity card */}
      {maturity && (
        <MaturityCard maturity={maturity} />
      )}

      {/* Stage-aware content */}
      {maturity?.stage === 'new' ? (
        <GettingStartedPanel />
      ) : (
        <StatsGrid maturity={maturity} />
      )}
    </div>
  )
}

// ── Maturity status card ──────────────────────────────────────────────────
function MaturityCard({ maturity }: { maturity: NonNullable<ReturnType<typeof useMascot>['maturity']> }) {
  const color = STAGE_COLORS[maturity.stage]
  const label = STAGE_LABELS[maturity.stage]

  return (
    <div className="card" style={{ marginBottom: 'var(--space-6)', padding: 'var(--space-5)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
        <div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
            INTELLIGENCE LEVEL
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
            <span style={{
              fontSize: 'var(--text-lg)',
              fontWeight: 700,
              color,
            }}>
              {label}
            </span>
            <span className="badge" style={{ background: `${color}22`, color, fontSize: '11px' }}>
              {maturity.days_of_data} {maturity.days_of_data === 1 ? 'day' : 'days'} of data
            </span>
          </div>
        </div>
        {maturity.forecast_horizon_days > 0 && (
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
              FORECAST HORIZON
            </div>
            <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700 }}>
              {maturity.forecast_horizon_days} days
            </div>
          </div>
        )}
      </div>

      <div style={{ background: 'var(--color-surface-2)', borderRadius: 'var(--radius-full)', height: 8, overflow: 'hidden' }}>
        <div style={{
          background: color,
          width: `${maturity.progress_to_next * 100}%`,
          height: '100%',
          borderRadius: 'var(--radius-full)',
          transition: 'width 0.6s ease',
        }} />
      </div>

      {maturity.stage !== 'expert' && (
        <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
          {maturity.next_milestone_label}
        </div>
      )}

      <p style={{ marginTop: 'var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
        {maturity.mascot_message}
      </p>
    </div>
  )
}

// ── Getting started (new org) ─────────────────────────────────────────────
function GettingStartedPanel() {
  const actions = [
    {
      icon: '⊡',
      title: 'Upload your first document',
      desc: 'Invoices, receipts, bank statements — any format, any quality.',
      to: '/documents',
      cta: 'Go to Documents',
    },
    {
      icon: '≡',
      title: 'Add transactions manually',
      desc: 'Enter transactions directly if you prefer to start without uploading files.',
      to: '/transactions',
      cta: 'Go to Transactions',
    },
  ]

  return (
    <div>
      <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 600, marginBottom: 'var(--space-4)' }}>
        Get started
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--space-4)' }}>
        {actions.map(({ icon, title, desc, to, cta }) => (
          <div key={title} className="card" style={{ padding: 'var(--space-5)' }}>
            <div style={{
              width: 44,
              height: 44,
              borderRadius: 'var(--radius-md)',
              background: 'var(--color-accent-dim)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 22,
              marginBottom: 'var(--space-3)',
            }}>
              {icon}
            </div>
            <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--space-2)' }}>{title}</div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', lineHeight: 1.5, marginBottom: 'var(--space-4)' }}>
              {desc}
            </div>
            <Link to={to} className="btn btn-primary" style={{ fontSize: 'var(--text-xs)', display: 'inline-block' }}>
              {cta}
            </Link>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Stats grid (once org has data) ───────────────────────────────────────
function StatsGrid({ maturity }: { maturity: NonNullable<ReturnType<typeof useMascot>['maturity']> | null }) {
  const stats = [
    { label: 'Days of data', value: maturity?.days_of_data ?? 0, unit: 'days' },
    { label: 'Forecast horizon', value: maturity?.forecast_horizon_days ?? 0, unit: 'days' },
    { label: 'Capabilities', value: maturity?.capabilities.length ?? 0, unit: 'active' },
  ]

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 'var(--space-4)', marginBottom: 'var(--space-6)' }}>
        {stats.map(({ label, value, unit }) => (
          <div key={label} className="card" style={{ padding: 'var(--space-5)' }}>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginBottom: 'var(--space-2)' }}>
              {label.toUpperCase()}
            </div>
            <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: '-0.02em' }}>
              {value}
            </div>
            <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', marginTop: 'var(--space-1)' }}>
              {unit}
            </div>
          </div>
        ))}
      </div>

      {/* Active capabilities */}
      {maturity && maturity.capabilities.length > 0 && (
        <div className="card" style={{ padding: 'var(--space-5)' }}>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginBottom: 'var(--space-3)' }}>
            ACTIVE CAPABILITIES
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
            {maturity.capabilities.map((cap) => (
              <span key={cap} className="badge badge-info" style={{ fontSize: '12px' }}>
                {cap.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
