import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { register } from '../../api/auth'
import { useMascot } from '../../store/mascotContext'

export default function Register() {
  const { speak } = useMascot()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({})
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setFieldErrors({})

    if (password !== passwordConfirm) {
      setFieldErrors({ password_confirm: ['Passwords do not match.'] })
      return
    }

    setLoading(true)
    try {
      await register(email, password, passwordConfirm, fullName)
      speak({ text: "Account created! Check your email to verify, then sign in.", mood: 'happy', duration: 5000 })
      setDone(true)
    } catch (err: any) {
      const apiErr = err?.response?.data?.error
      if (apiErr?.field_errors && Object.keys(apiErr.field_errors).length > 0) {
        setFieldErrors(apiErr.field_errors)
      } else {
        setError(apiErr?.message ?? 'Registration failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (done) {
    return (
      <div style={{
        minHeight: '100vh',
        background: 'var(--color-bg)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-6)',
      }}>
        <div style={{ width: '100%', maxWidth: 400, textAlign: 'center' }}>
          <div style={{ fontSize: 48, marginBottom: 'var(--space-4)' }}>✉️</div>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--space-3)' }}>
            Check your inbox
          </h2>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 'var(--text-sm)', marginBottom: 'var(--space-6)' }}>
            We sent a verification link to <strong style={{ color: 'var(--color-text-primary)' }}>{email}</strong>.
            Click it to activate your account.
          </p>
          <Link to="/login" className="btn btn-primary" style={{ display: 'inline-block' }}>
            Go to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--color-bg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 'var(--space-6)',
    }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-8)' }}>
          <div style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-0.02em', marginBottom: 'var(--space-2)' }}>
            <span style={{ color: 'var(--color-accent)' }}>Fin</span>Sight
          </div>
          <p style={{ color: 'var(--color-text-muted)', fontSize: 'var(--text-sm)' }}>
            Create your account
          </p>
        </div>

        <div className="card" style={{ padding: 'var(--space-6)' }}>
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

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <Field
              label="Full name"
              type="text"
              autoComplete="name"
              placeholder="Jane Smith"
              value={fullName}
              onChange={setFullName}
              errors={fieldErrors.full_name}
            />
            <Field
              label="Email"
              type="email"
              autoComplete="email"
              placeholder="you@company.com"
              value={email}
              onChange={setEmail}
              errors={fieldErrors.email}
            />
            <Field
              label="Password"
              type="password"
              autoComplete="new-password"
              placeholder="8+ characters"
              value={password}
              onChange={setPassword}
              errors={fieldErrors.password}
            />
            <Field
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              placeholder="••••••••"
              value={passwordConfirm}
              onChange={setPasswordConfirm}
              errors={fieldErrors.password_confirm}
            />

            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading}
              style={{ width: '100%', marginTop: 'var(--space-2)' }}
            >
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>
        </div>

        <p style={{ textAlign: 'center', marginTop: 'var(--space-4)', fontSize: 'var(--text-sm)', color: 'var(--color-text-muted)' }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: 'var(--color-accent)', textDecoration: 'none' }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}

function Field({
  label, type, autoComplete, placeholder, value, onChange, errors,
}: {
  label: string
  type: string
  autoComplete: string
  placeholder: string
  value: string
  onChange: (v: string) => void
  errors?: string[]
}) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)', marginBottom: 'var(--space-2)' }}>
        {label}
      </label>
      <input
        className="input"
        type={type}
        autoComplete={autoComplete}
        required
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: '100%', borderColor: errors?.length ? 'rgba(239,68,68,0.5)' : undefined }}
      />
      {errors?.map((e) => (
        <p key={e} style={{ marginTop: 'var(--space-1)', fontSize: '12px', color: '#f87171' }}>{e}</p>
      ))}
    </div>
  )
}
