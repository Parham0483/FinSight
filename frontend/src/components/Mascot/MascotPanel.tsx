import { useMascot, STAGE_COLORS, STAGE_LABELS } from '../../store/mascotContext'
import CheetahSvg from './CheetahSvg'

/** Expanded assistant panel — maturity stage, capabilities, and guidance. */
export default function MascotPanel({ onClose }: { onClose: () => void }) {
  const { maturity, mood } = useMascot()

  return (
    <div className="mascot-panel" role="dialog" aria-label="AI assistant panel">
      <div className="mascot-panel-header">
        <div className="mascot-panel-avatar">
          <CheetahSvg mood={mood} asleep={false} />
        </div>
        <div className="mascot-panel-title">Your AI Assistant</div>
        <button className="mascot-panel-close" onClick={onClose} aria-label="Close">✕</button>
      </div>

      <div className="mascot-panel-body">
        {maturity ? (
          <>
            <div style={{ marginBottom: 'var(--space-4)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
                <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>Intelligence Level</span>
                <span
                  className="badge"
                  style={{
                    background: `${STAGE_COLORS[maturity.stage]}22`,
                    color: STAGE_COLORS[maturity.stage],
                  }}
                >
                  {STAGE_LABELS[maturity.stage]}
                </span>
              </div>

              <div className="maturity-bar">
                <div
                  className="maturity-bar-fill"
                  style={{
                    width: `${maturity.progress_to_next * 100}%`,
                    background: STAGE_COLORS[maturity.stage],
                  }}
                />
              </div>

              {maturity.stage !== 'expert' && (
                <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginTop: 'var(--space-2)' }}>
                  Next: {maturity.next_milestone_label}
                </div>
              )}
            </div>

            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', lineHeight: 1.6, marginBottom: 'var(--space-4)' }}>
              {maturity.mascot_message}
            </p>

            <div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginBottom: 'var(--space-2)' }}>
                AVAILABLE NOW
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                {maturity.capabilities.map((cap) => (
                  <span key={cap} className="badge badge-info" style={{ fontSize: '11px' }}>
                    {cap.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>

            {maturity.days_of_data > 0 && (
              <div style={{ marginTop: 'var(--space-4)', fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
                {maturity.days_of_data} days of data · {maturity.forecast_horizon_days > 0 ? `${maturity.forecast_horizon_days}-day forecast` : 'no forecast yet'}
              </div>
            )}
          </>
        ) : (
          <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
            Connect your first data source to get started.
          </p>
        )}
      </div>
    </div>
  )
}
