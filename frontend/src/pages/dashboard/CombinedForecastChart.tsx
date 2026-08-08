import { useEffect, useState } from 'react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { getCombinedForecast } from '../../api/forecasting'
import type { CombinedForecast } from '../../types'

interface ChartRow {
  date: string
  bandBase: number
  bandHeight: number
  p50: number
}

function toChartRows(forecast: CombinedForecast): ChartRow[] {
  return forecast.points.map((p) => {
    const p10 = Number(p.balance_p10)
    const p90 = Number(p.balance_p90)
    return {
      date: p.date,
      bandBase: p10,             // invisible stacked base — pushes the visible band up to start at p10
      bandHeight: p90 - p10,     // visible band height — renders the P10-P90 spread
      p50: Number(p.balance_p50),
    }
  })
}

function formatMoney(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

export default function CombinedForecastChart({ orgId }: { orgId: string }) {
  const [forecast, setForecast] = useState<CombinedForecast | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getCombinedForecast(orgId)
      .then((res) => {
        if (cancelled) return
        setForecast(res.data.data)
      })
      .catch(() => {
        if (cancelled) return
        setError('Could not load the cash flow forecast.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [orgId])

  if (loading) {
    return (
      <div className="card" style={{ padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
        <div style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>Loading forecast…</div>
      </div>
    )
  }

  if (error || !forecast) {
    return (
      <div className="card" style={{ padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
        <div style={{ color: 'var(--color-danger)', fontSize: 'var(--text-sm)' }}>
          {error ?? 'No forecast available yet.'}
        </div>
      </div>
    )
  }

  if (forecast.points.length === 0) {
    return (
      <div className="card" style={{ padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
        <div style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>
          Not enough data yet to project a cash flow forecast.
        </div>
      </div>
    )
  }

  const rows = toChartRows(forecast)
  const { runway, driver_totals: driverTotals, statistical_method: statisticalMethod } = forecast

  return (
    <div className="card" style={{ padding: 'var(--space-5)', marginBottom: 'var(--space-6)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-4)' }}>
        <div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginBottom: 'var(--space-1)' }}>
            PROJECTED BALANCE — NEXT {forecast.horizon_days} DAYS
          </div>
          <div style={{ fontSize: 'var(--text-lg)', fontWeight: 700 }}>
            {formatMoney(Number(forecast.starting_balance))} today
          </div>
        </div>
        {statisticalMethod && (
          <span className="badge" style={{ fontSize: '11px', color: 'var(--color-text-secondary)' }}>
            {statisticalMethod === 'ets_seasonal' ? 'Seasonal model' : 'Trailing average'}
          </span>
        )}
      </div>

      <div style={{ width: '100%', height: 280 }}>
        <ResponsiveContainer>
          <ComposedChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              stroke="var(--color-text-muted)"
              tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-border)' }}
            />
            <YAxis
              stroke="var(--color-text-muted)"
              tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              tickLine={false}
              axisLine={false}
              tickFormatter={formatMoney}
              width={64}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--color-surface-2)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                fontSize: 'var(--text-xs)',
              }}
              labelStyle={{ color: 'var(--color-text-secondary)' }}
              formatter={(value: number, name: string) => {
                if (name === 'bandBase' || name === 'bandHeight') return [null, null]
                return [formatMoney(value), 'Most likely']
              }}
            />
            <ReferenceLine y={0} stroke="var(--color-danger)" strokeDasharray="4 4" />
            {runway.worst_case_cashout_date && (
              <ReferenceLine
                x={runway.worst_case_cashout_date}
                stroke="var(--color-danger)"
                strokeDasharray="4 4"
                label={{ value: 'Worst case', position: 'top', fill: 'var(--color-danger)', fontSize: 10 }}
              />
            )}
            <Area
              type="monotone"
              dataKey="bandBase"
              stackId="band"
              stroke="none"
              fill="transparent"
              isAnimationActive={false}
            />
            <Area
              type="monotone"
              dataKey="bandHeight"
              stackId="band"
              stroke="none"
              fill="var(--color-accent)"
              fillOpacity={0.15}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="p50"
              stroke="var(--color-accent)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {(runway.most_likely_cashout_date || runway.worst_case_cashout_date) && (
        <div style={{
          marginTop: 'var(--space-4)', padding: 'var(--space-3)',
          background: 'rgba(248, 113, 113, 0.1)', borderRadius: 'var(--radius-md)',
          fontSize: 'var(--text-xs)', color: 'var(--color-danger)',
        }}>
          {runway.worst_case_cashout_date && (
            <div>Worst case: balance could go negative by {runway.worst_case_cashout_date}</div>
          )}
          {runway.most_likely_cashout_date && (
            <div>Most likely: balance could go negative by {runway.most_likely_cashout_date}</div>
          )}
        </div>
      )}

      <div style={{ marginTop: 'var(--space-4)', display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)' }}>
        {Object.entries(driverTotals).map(([source, amount]) => (
          <span
            key={source}
            className="badge"
            style={{
              fontSize: '11px',
              color: Number(amount) >= 0 ? 'var(--color-success)' : 'var(--color-danger)',
            }}
          >
            {source.replace(/_/g, ' ')}: {formatMoney(Number(amount))}
          </span>
        ))}
      </div>
    </div>
  )
}
