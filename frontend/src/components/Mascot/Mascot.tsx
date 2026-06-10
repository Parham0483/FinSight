import './Mascot.css'
import { useMascot } from '../../store/mascotContext'
import CheetahSvg from './CheetahSvg'
import MascotPanel from './MascotPanel'
import { useCheetahBehavior } from './useCheetahBehavior'

/**
 * The living mascot: an Asiatic (Iranian) cheetah that roams the lower
 * part of the screen, watches the cursor, blinks, naps, and dashes home
 * when you open the assistant panel. Clicking it toggles the panel.
 */

function SpeechBubble({ text, side }: { text: string; side: 'left' | 'right' }) {
  return (
    <div className={`mascot-bubble bubble-${side}`} role="status" aria-live="polite">
      {text}
    </div>
  )
}

export default function Mascot() {
  const { mood, message, isExpanded, toggleExpanded } = useMascot()
  const { state, figureRef } = useCheetahBehavior({
    paused: Boolean(message) || isExpanded,
    docked: isExpanded,
  })

  const { x, y, facing, behavior, moveMs } = state
  const bubbleSide = x < document.documentElement.clientWidth / 2 ? 'left' : 'right'
  const isMoving = behavior === 'walking' || behavior === 'dashing'

  return (
    <>
      <div
        className="mascot-stage"
        style={{
          transform: `translate3d(${x}px, ${y}px, 0)`,
          transitionDuration: `${moveMs}ms`,
          transitionTimingFunction: behavior === 'dashing' ? 'cubic-bezier(0.3, 0, 0.4, 1)' : 'linear',
        }}
      >
        {message && !isExpanded && <SpeechBubble text={message.text} side={bubbleSide} />}

        <button
          ref={figureRef}
          className={`mascot-figure is-${behavior} mood-${mood} facing-${facing}`}
          onClick={toggleExpanded}
          aria-label={isExpanded ? 'Close AI assistant' : 'Open AI assistant'}
          aria-expanded={isExpanded}
        >
          <span className="mascot-flip">
            <CheetahSvg mood={mood} asleep={behavior === 'sleeping'} />
          </span>
          <span className={`mascot-shadow ${isMoving ? 'moving' : ''}`} aria-hidden="true" />
          {behavior === 'sleeping' && (
            <span className="mascot-zzz" aria-hidden="true">
              <i>z</i><i>z</i><i>z</i>
            </span>
          )}
          {mood === 'celebrating' && <span className="mascot-sparkle" aria-hidden="true">✨</span>}
        </button>
      </div>

      {isExpanded && (
        <div className="mascot-panel-dock">
          <MascotPanel onClose={toggleExpanded} />
        </div>
      )}
    </>
  )
}
