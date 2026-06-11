import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../store/authContext'
import { useMascot } from '../../store/mascotContext'
import { createOrg, type CreateOrgPayload } from '../../api/organisations'

// ── Step definitions ──────────────────────────────────────────────────────
const STEPS = ['Welcome', 'Your Business', 'What to Expect'] as const
type Step = 0 | 1 | 2

const COUNTRIES = [
  { code: 'US', name: 'United States' },
  { code: 'GB', name: 'United Kingdom' },
  { code: 'CA', name: 'Canada' },
  { code: 'AU', name: 'Australia' },
  { code: 'DE', name: 'Germany' },
  { code: 'FR', name: 'France' },
  { code: 'NL', name: 'Netherlands' },
  { code: 'IT', name: 'Italy' },
  { code: 'ES', name: 'Spain' },
  { code: 'CH', name: 'Switzerland' },
  { code: 'SE', name: 'Sweden' },
  { code: 'NO', name: 'Norway' },
  { code: 'DK', name: 'Denmark' },
  { code: 'FI', name: 'Finland' },
  { code: 'PL', name: 'Poland' },
  { code: 'JP', name: 'Japan' },
  { code: 'CN', name: 'China' },
  { code: 'KR', name: 'South Korea' },
  { code: 'IN', name: 'India' },
  { code: 'SG', name: 'Singapore' },
  { code: 'HK', name: 'Hong Kong' },
  { code: 'TW', name: 'Taiwan' },
  { code: 'ID', name: 'Indonesia' },
  { code: 'MY', name: 'Malaysia' },
  { code: 'TH', name: 'Thailand' },
  { code: 'VN', name: 'Vietnam' },
  { code: 'PH', name: 'Philippines' },
  { code: 'AE', name: 'UAE' },
  { code: 'SA', name: 'Saudi Arabia' },
  { code: 'QA', name: 'Qatar' },
  { code: 'KW', name: 'Kuwait' },
  { code: 'BH', name: 'Bahrain' },
  { code: 'OM', name: 'Oman' },
  { code: 'IR', name: 'Iran' },
  { code: 'TR', name: 'Turkey' },
  { code: 'IL', name: 'Israel' },
  { code: 'EG', name: 'Egypt' },
  { code: 'MA', name: 'Morocco' },
  { code: 'NG', name: 'Nigeria' },
  { code: 'ZA', name: 'South Africa' },
  { code: 'KE', name: 'Kenya' },
  { code: 'GH', name: 'Ghana' },
  { code: 'ET', name: 'Ethiopia' },
  { code: 'TZ', name: 'Tanzania' },
  { code: 'BR', name: 'Brazil' },
  { code: 'MX', name: 'Mexico' },
  { code: 'AR', name: 'Argentina' },
  { code: 'CL', name: 'Chile' },
  { code: 'CO', name: 'Colombia' },
  { code: 'PE', name: 'Peru' },
  { code: 'PK', name: 'Pakistan' },
  { code: 'BD', name: 'Bangladesh' },
  { code: 'LK', name: 'Sri Lanka' },
  { code: 'NZ', name: 'New Zealand' },
  { code: 'RU', name: 'Russia' },
  { code: 'UA', name: 'Ukraine' },
  { code: '', name: 'Other' },
]

const CURRENCIES = [
  { code: 'USD', name: 'US Dollar' },
  { code: 'EUR', name: 'Euro' },
  { code: 'GBP', name: 'British Pound' },
  { code: 'CAD', name: 'Canadian Dollar' },
  { code: 'AUD', name: 'Australian Dollar' },
  { code: 'CHF', name: 'Swiss Franc' },
  { code: 'JPY', name: 'Japanese Yen' },
  { code: 'CNY', name: 'Chinese Yuan' },
  { code: 'HKD', name: 'Hong Kong Dollar' },
  { code: 'SGD', name: 'Singapore Dollar' },
  { code: 'KRW', name: 'South Korean Won' },
  { code: 'INR', name: 'Indian Rupee' },
  { code: 'IDR', name: 'Indonesian Rupiah' },
  { code: 'MYR', name: 'Malaysian Ringgit' },
  { code: 'THB', name: 'Thai Baht' },
  { code: 'PHP', name: 'Philippine Peso' },
  { code: 'VND', name: 'Vietnamese Dong' },
  { code: 'AED', name: 'UAE Dirham' },
  { code: 'SAR', name: 'Saudi Riyal' },
  { code: 'QAR', name: 'Qatari Riyal' },
  { code: 'KWD', name: 'Kuwaiti Dinar' },
  { code: 'BHD', name: 'Bahraini Dinar' },
  { code: 'OMR', name: 'Omani Rial' },
  { code: 'IRR', name: 'Iranian Rial' },
  { code: 'TRY', name: 'Turkish Lira' },
  { code: 'ILS', name: 'Israeli Shekel' },
  { code: 'EGP', name: 'Egyptian Pound' },
  { code: 'MAD', name: 'Moroccan Dirham' },
  { code: 'NGN', name: 'Nigerian Naira' },
  { code: 'ZAR', name: 'South African Rand' },
  { code: 'KES', name: 'Kenyan Shilling' },
  { code: 'GHS', name: 'Ghanaian Cedi' },
  { code: 'BRL', name: 'Brazilian Real' },
  { code: 'MXN', name: 'Mexican Peso' },
  { code: 'ARS', name: 'Argentine Peso' },
  { code: 'CLP', name: 'Chilean Peso' },
  { code: 'COP', name: 'Colombian Peso' },
  { code: 'PKR', name: 'Pakistani Rupee' },
  { code: 'BDT', name: 'Bangladeshi Taka' },
  { code: 'LKR', name: 'Sri Lankan Rupee' },
  { code: 'NZD', name: 'New Zealand Dollar' },
  { code: 'RUB', name: 'Russian Ruble' },
  { code: 'SEK', name: 'Swedish Krona' },
  { code: 'NOK', name: 'Norwegian Krone' },
  { code: 'DKK', name: 'Danish Krone' },
  { code: 'PLN', name: 'Polish Zloty' },
]

// Must match backend INDUSTRY_CHOICES exactly
const INDUSTRIES: { value: string; label: string }[] = [
  { value: 'retail',                label: 'Retail' },
  { value: 'wholesale',             label: 'Wholesale' },
  { value: 'import_export',         label: 'Import / Export' },
  { value: 'manufacturing',         label: 'Manufacturing' },
  { value: 'construction',          label: 'Construction' },
  { value: 'hospitality',           label: 'Hospitality / Food & Beverage' },
  { value: 'technology',            label: 'Technology / SaaS' },
  { value: 'professional_services', label: 'Professional Services' },
  { value: 'logistics',             label: 'Logistics / Transport' },
  { value: 'agriculture',           label: 'Agriculture' },
  { value: 'healthcare',            label: 'Healthcare' },
  { value: 'education',             label: 'Education' },
  { value: 'services',              label: 'Other Services' },
  { value: 'other',                 label: 'Other' },
]

const MASCOT_LINES: Record<Step, { text: string; mood: 'happy' | 'idle' | 'celebrating' }> = {
  0: { text: "Hi! I'm your financial intelligence guide. Let's get you set up — it only takes a minute.", mood: 'happy' },
  1: { text: "Tell me about your business so I can personalise your experience.", mood: 'idle' },
  2: { text: "You're all set! I'll grow smarter as you upload more data. Let's start!", mood: 'celebrating' },
}

// ── Main component ────────────────────────────────────────────────────────
export default function OnboardingWizard() {
  const navigate = useNavigate()
  const { refreshUser } = useAuth()
  const { speak } = useMascot()

  const [step, setStep] = useState<Step>(0)
  const [form, setForm] = useState<CreateOrgPayload>({
    name: '',
    industry: 'retail',
    country_code: 'US',
    base_currency: 'USD',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC',
  })
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  function advanceTo(next: Step) {
    speak({ ...MASCOT_LINES[next], duration: 5000 })
    setStep(next)
  }

  // Show mascot greeting on first render
  React.useEffect(() => {
    speak({ ...MASCOT_LINES[0], duration: 6000 })
  }, [])

  async function handleCreateOrg() {
    if (!form.name.trim()) { setError('Business name is required.'); return }
    setError(null)
    setLoading(true)
    try {
      await createOrg(form)
      await refreshUser()
      advanceTo(2)
    } catch (err: any) {
      const msg = err?.response?.data?.error?.message ?? 'Failed to create organisation.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--color-bg)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 'var(--space-6)',
    }}>
      <div style={{ width: '100%', maxWidth: 520 }}>
        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-8)' }}>
          <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.02em', marginBottom: 'var(--space-4)' }}>
            <span style={{ color: 'var(--color-accent)' }}>Fin</span>Sight
          </div>

          {/* Step indicators */}
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 'var(--space-3)' }}>
            {STEPS.map((label, i) => (
              <React.Fragment key={label}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-2)',
                  opacity: i > step ? 0.35 : 1,
                  transition: 'opacity 0.3s',
                }}>
                  <div style={{
                    width: 26,
                    height: 26,
                    borderRadius: '50%',
                    background: i < step ? 'var(--color-accent)' : i === step ? 'var(--color-accent)' : 'var(--color-surface-2)',
                    border: i === step ? '2px solid var(--color-accent)' : '2px solid var(--color-border)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '12px',
                    fontWeight: 600,
                    color: i <= step ? '#fff' : 'var(--color-text-muted)',
                  }}>
                    {i < step ? '✓' : i + 1}
                  </div>
                  <span style={{ fontSize: 'var(--text-xs)', color: i === step ? 'var(--color-text-primary)' : 'var(--color-text-muted)' }}>
                    {label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div style={{ flex: 1, height: 1, background: 'var(--color-border)', maxWidth: 32 }} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Step content */}
        <div className="card" style={{ padding: 'var(--space-8)' }}>
          {step === 0 && <WelcomeStep onNext={() => advanceTo(1)} />}
          {step === 1 && (
            <OrgStep
              form={form}
              setForm={setForm}
              error={error}
              loading={loading}
              onSubmit={handleCreateOrg}
            />
          )}
          {step === 2 && <DoneStep onDone={() => navigate('/dashboard')} />}
        </div>
      </div>
    </div>
  )
}

// ── Step: Welcome ─────────────────────────────────────────────────────────
function WelcomeStep({ onNext }: { onNext: () => void }) {
  const features = [
    { icon: '◈', title: 'Automatic data extraction', desc: 'Upload invoices, receipts, bank statements — handwritten or digital. We extract and organise everything.' },
    { icon: '◎', title: 'Progressive forecasting', desc: 'Starts with 7-day forecasts. As your data grows, we unlock 30, 90, and 365-day views with higher accuracy.' },
    { icon: '✦', title: 'AI that learns your business', desc: 'The more data you provide, the more personalised and accurate your financial intelligence becomes.' },
  ]

  return (
    <div>
      <h2 style={{ fontSize: 'var(--text-2xl)', fontWeight: 700, marginBottom: 'var(--space-2)' }}>
        Welcome to your financial command centre
      </h2>
      <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-6)', lineHeight: 1.6 }}>
        FinSight replaces manual data entry with intelligent document processing and gives you the financial clarity that used to require an accountant.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', marginBottom: 'var(--space-8)' }}>
        {features.map(({ icon, title, desc }) => (
          <div key={title} style={{ display: 'flex', gap: 'var(--space-4)', alignItems: 'flex-start' }}>
            <div style={{
              width: 36,
              height: 36,
              borderRadius: 'var(--radius-md)',
              background: 'var(--color-accent-dim)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
              flexShrink: 0,
            }}>
              {icon}
            </div>
            <div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--space-1)' }}>{title}</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>{desc}</div>
            </div>
          </div>
        ))}
      </div>

      <button className="btn btn-primary" onClick={onNext} style={{ width: '100%' }}>
        Get started
      </button>
    </div>
  )
}

// ── Step: Org setup ───────────────────────────────────────────────────────
function OrgStep({
  form, setForm, error, loading, onSubmit,
}: {
  form: CreateOrgPayload
  setForm: React.Dispatch<React.SetStateAction<CreateOrgPayload>>
  error: string | null
  loading: boolean
  onSubmit: () => void
}) {
  function update(field: keyof CreateOrgPayload, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  return (
    <div>
      <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--space-2)' }}>
        Tell us about your business
      </h2>
      <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-6)' }}>
        This helps us personalise currency defaults, regional formats, and forecasting models.
      </p>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-3) var(--space-4)',
          marginBottom: 'var(--space-4)',
          fontSize: 'var(--text-sm)',
          color: '#f87171',
        }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
        <div>
          <label style={labelStyle}>Business name</label>
          <input
            className="input"
            type="text"
            placeholder="Acme Ltd"
            value={form.name}
            onChange={(e) => update('name', e.target.value)}
            style={{ width: '100%' }}
          />
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)' }}>
          <div>
            <label style={labelStyle}>Country</label>
            <select className="input" value={form.country_code} onChange={(e) => update('country_code', e.target.value)} style={{ width: '100%' }}>
              {COUNTRIES.map(({ code, name }) => (
                <option key={code} value={code}>{name}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Base currency</label>
            <select className="input" value={form.base_currency} onChange={(e) => update('base_currency', e.target.value)} style={{ width: '100%' }}>
              {CURRENCIES.map(({ code, name }) => (
                <option key={code} value={code}>{code} — {name}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label style={labelStyle}>Industry</label>
          <select className="input" value={form.industry} onChange={(e) => update('industry', e.target.value)} style={{ width: '100%' }}>
            {INDUSTRIES.map(({ value, label }) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <button
          className="btn btn-primary"
          onClick={onSubmit}
          disabled={loading}
          style={{ width: '100%', marginTop: 'var(--space-2)' }}
        >
          {loading ? 'Creating…' : 'Continue'}
        </button>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 'var(--text-sm)',
  color: 'var(--color-text-secondary)',
  marginBottom: 'var(--space-2)',
}

// ── Step: Done ────────────────────────────────────────────────────────────
function DoneStep({ onDone }: { onDone: () => void }) {
  const milestones = [
    { label: '7-day forecast', detail: 'Unlocked immediately — upload a few transactions to activate.' },
    { label: '30-day forecast', detail: 'Unlocks after 14 days of data.' },
    { label: '90-day forecast', detail: 'Unlocks after 30 days of data.' },
    { label: 'AI insights', detail: 'Unlocks after 60 days of data.' },
  ]

  return (
    <div>
      <div style={{ textAlign: 'center', marginBottom: 'var(--space-6)' }}>
        <div style={{ fontSize: 48, marginBottom: 'var(--space-3)' }}>🎉</div>
        <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--space-2)' }}>
          You're all set!
        </h2>
        <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)' }}>
          Your business profile is created. Here's what unlocks as your data grows:
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)', marginBottom: 'var(--space-6)' }}>
        {milestones.map(({ label, detail }, i) => (
          <div key={label} style={{
            display: 'flex',
            gap: 'var(--space-3)',
            padding: 'var(--space-3)',
            background: 'var(--color-surface-2)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--color-border)',
            opacity: i === 0 ? 1 : 0.6,
          }}>
            <div style={{
              width: 28,
              height: 28,
              borderRadius: '50%',
              background: i === 0 ? 'var(--color-accent-dim)' : 'var(--color-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 12,
              color: i === 0 ? 'var(--color-accent)' : 'var(--color-text-muted)',
              flexShrink: 0,
            }}>
              {i + 1}
            </div>
            <div>
              <div style={{ fontSize: 'var(--text-sm)', fontWeight: 600 }}>{label}</div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)', marginTop: 2 }}>{detail}</div>
            </div>
          </div>
        ))}
      </div>

      <button className="btn btn-primary" onClick={onDone} style={{ width: '100%' }}>
        Go to my dashboard
      </button>
    </div>
  )
}
