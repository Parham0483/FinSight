import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props { children: ReactNode }
interface State { error: Error | null }

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children
    return (
      <div style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0f1117',
        padding: 32,
      }}>
        <div style={{
          maxWidth: 560,
          background: '#1a1d27',
          border: '1px solid rgba(239,68,68,0.3)',
          borderRadius: 12,
          padding: 32,
        }}>
          <div style={{ color: '#f87171', fontWeight: 700, fontSize: 16, marginBottom: 12 }}>
            Something went wrong
          </div>
          <pre style={{
            color: '#e2e8f0',
            fontSize: 13,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            lineHeight: 1.6,
            margin: 0,
          }}>
            {error.message}
          </pre>
        </div>
      </div>
    )
  }
}
