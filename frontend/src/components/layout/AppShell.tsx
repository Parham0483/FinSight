import React from 'react'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import Mascot from '../Mascot/Mascot'

interface AppShellProps {
  children: React.ReactNode
}

export default function AppShell({ children }: AppShellProps) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--color-bg)' }}>
      <Sidebar />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <TopBar />
        <main style={{
          flex: 1,
          padding: 'var(--space-8)',
          overflowY: 'auto',
          maxWidth: 'var(--content-max-width)',
          width: '100%',
          margin: '0 auto',
        }}>
          {children}
        </main>
      </div>
      <Mascot />
    </div>
  )
}
