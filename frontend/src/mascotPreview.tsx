// Temporary visual harness for the cheetah mascot — not shipped.
import React, { useEffect } from 'react'
import ReactDOM from 'react-dom/client'
import CheetahSvg from './components/Mascot/CheetahSvg'
import Mascot from './components/Mascot/Mascot'
import { AuthProvider } from './store/authContext'
import { MascotProvider, useMascot } from './store/mascotContext'
import './styles/variables.css'
import './components/Mascot/Mascot.css'
import type { MascotMood } from './types'

/** Exposes the mascot API on window so automation can drive it. */
function MascotBridge() {
  const mascot = useMascot()
  useEffect(() => {
    ;(window as unknown as Record<string, unknown>).__mascot = mascot
  }, [mascot])
  return null
}

const MOODS: MascotMood[] = ['idle', 'thinking', 'happy', 'concerned', 'celebrating']

function Cell({ label, mood, asleep = false, extraClass = '' }: {
  label: string; mood: MascotMood; asleep?: boolean; extraClass?: string
}) {
  return (
    <div style={{ textAlign: 'center' }}>
      <button className={`mascot-figure mood-${mood} ${extraClass}`} style={{ position: 'relative' }}>
        <span className="mascot-flip">
          <CheetahSvg mood={mood} asleep={asleep} />
        </span>
        <span className="mascot-shadow" aria-hidden="true" />
      </button>
      <div style={{ color: '#8b91a8', fontFamily: 'sans-serif', fontSize: 12 }}>{label}</div>
    </div>
  )
}

function Preview() {
  return (
    <div style={{ background: '#0f1117', minHeight: '100vh', padding: 40, display: 'flex', flexWrap: 'wrap', gap: 32 }}>
      {MOODS.map((m) => <Cell key={m} label={m} mood={m} />)}
      <Cell label="asleep" mood="idle" asleep extraClass="is-sleeping" />
      <Cell label="facing-left" mood="idle" extraClass="facing-left" />
      <Cell label="dashing" mood="idle" extraClass="is-dashing facing-right" />
      <Cell label="blinking" mood="idle" extraClass="is-blinking" />
    </div>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <MascotProvider>
        <Preview />
        <MascotBridge />
        <Mascot />
      </MascotProvider>
    </AuthProvider>
  </React.StrictMode>,
)
