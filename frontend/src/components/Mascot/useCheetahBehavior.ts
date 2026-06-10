import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Autonomous behaviour engine for the cheetah mascot.
 *
 * A timer-driven state machine picks what the cheetah does next:
 * idle → look around → walk somewhere → dash (it IS a cheetah) → sit.
 * After long user inactivity it curls up and sleeps; it wakes when the
 * cursor comes close. Eyes follow the cursor and blinks are randomised
 * so it never looks mechanical.
 *
 * Roaming is confined to the lower band of the viewport so the mascot
 * feels grounded and never covers primary content ("smart" movement).
 */

export type CheetahBehavior = 'idle' | 'walking' | 'dashing' | 'sitting' | 'sleeping'
export type CheetahFacing = 'left' | 'right'

export interface CheetahState {
  x: number
  y: number
  facing: CheetahFacing
  behavior: CheetahBehavior
  moveMs: number
}

interface BehaviorOptions {
  /** Stop roaming (message bubble visible) */
  paused: boolean
  /** Return to home corner and stay (assistant panel open) */
  docked: boolean
}

const FIGURE_SIZE = 112
const EDGE_MARGIN = 16
const HOME_OFFSET = 24
const WALK_SPEED_PX_S = 90
const DASH_SPEED_PX_S = 620
const MIN_MOVE_MS = 280
const MAX_MOVE_MS = 5000
const SLEEP_AFTER_IDLE_MS = 60_000
const WAKE_DISTANCE_PX = 150
const PUPIL_RANGE_PX = 2.6
const BLINK_MS = 130

const randBetween = (min: number, max: number) => min + Math.random() * (max - min)

const homePosition = () => ({
  x: window.innerWidth - FIGURE_SIZE - HOME_OFFSET,
  y: window.innerHeight - FIGURE_SIZE - HOME_OFFSET,
})

/** Random point in the lower band of the viewport. */
const roamTarget = () => {
  const minY = Math.max(EDGE_MARGIN, window.innerHeight * 0.55)
  return {
    x: randBetween(EDGE_MARGIN, Math.max(EDGE_MARGIN, window.innerWidth - FIGURE_SIZE - EDGE_MARGIN)),
    y: randBetween(minY, Math.max(minY, window.innerHeight - FIGURE_SIZE - EDGE_MARGIN)),
  }
}

const clampToViewport = (x: number, y: number) => ({
  x: Math.min(Math.max(x, EDGE_MARGIN), Math.max(EDGE_MARGIN, window.innerWidth - FIGURE_SIZE - EDGE_MARGIN)),
  y: Math.min(Math.max(y, EDGE_MARGIN), Math.max(EDGE_MARGIN, window.innerHeight - FIGURE_SIZE - EDGE_MARGIN)),
})

export function useCheetahBehavior({ paused, docked }: BehaviorOptions) {
  const [state, setState] = useState<CheetahState>(() => ({
    ...homePosition(),
    facing: 'left',
    behavior: 'idle',
    moveMs: 0,
  }))

  const figureRef = useRef<HTMLButtonElement>(null)
  const stateRef = useRef(state)
  stateRef.current = state

  const pausedRef = useRef(paused)
  pausedRef.current = paused
  const dockedRef = useRef(docked)
  dockedRef.current = docked

  const decideTimer = useRef<number | undefined>(undefined)
  const blinkTimer = useRef<number | undefined>(undefined)
  const lastActivityRef = useRef(Date.now())
  const lookRafRef = useRef(0)
  const mouseRef = useRef({ x: 0, y: 0 })
  const reducedMotionRef = useRef(
    typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )

  const schedule = useCallback((fn: () => void, ms: number) => {
    window.clearTimeout(decideTimer.current)
    decideTimer.current = window.setTimeout(fn, ms)
  }, [])

  /** Move to a target; arrival flows back into the decision loop. */
  const moveTo = useCallback(
    (tx: number, ty: number, behavior: 'walking' | 'dashing', onArrive: () => void) => {
      const current = stateRef.current
      const distance = Math.hypot(tx - current.x, ty - current.y)
      if (distance < 4) {
        onArrive()
        return
      }
      const speed = behavior === 'dashing' ? DASH_SPEED_PX_S : WALK_SPEED_PX_S
      const moveMs = Math.min(Math.max((distance / speed) * 1000, MIN_MOVE_MS), MAX_MOVE_MS)
      const facing: CheetahFacing = tx < current.x ? 'left' : 'right'
      setState((prev) => ({ ...prev, x: tx, y: ty, facing, behavior, moveMs }))
      schedule(onArrive, moveMs + 80)
    },
    [schedule],
  )

  const settle = useCallback(
    (behavior: 'idle' | 'sitting', nextDecisionMs: number, decideFn: () => void) => {
      setState((prev) => ({ ...prev, behavior, moveMs: 0 }))
      schedule(decideFn, nextDecisionMs)
    },
    [schedule],
  )

  const decide = useCallback(function decideNext() {
    if (dockedRef.current || pausedRef.current || reducedMotionRef.current) {
      schedule(decideNext, 1500)
      return
    }

    if (Date.now() - lastActivityRef.current > SLEEP_AFTER_IDLE_MS) {
      setState((prev) => ({ ...prev, behavior: 'sleeping', moveMs: 0 }))
      // Sleeping has no scheduled exit — wake is event-driven (cursor proximity)
      return
    }

    const roll = Math.random()
    if (roll < 0.35) {
      const target = roamTarget()
      moveTo(target.x, target.y, 'walking', () =>
        settle('idle', randBetween(2000, 5000), decideNext),
      )
    } else if (roll < 0.5) {
      const target = roamTarget()
      moveTo(target.x, target.y, 'dashing', () =>
        settle('idle', randBetween(2500, 5000), decideNext),
      )
    } else if (roll < 0.72) {
      settle('sitting', randBetween(5000, 9000), decideNext)
    } else {
      settle('idle', randBetween(2000, 6000), decideNext)
    }
  }, [moveTo, schedule, settle])

  const wake = useCallback(() => {
    lastActivityRef.current = Date.now()
    if (stateRef.current.behavior === 'sleeping') {
      setState((prev) => ({ ...prev, behavior: 'idle', moveMs: 0 }))
      schedule(decide, 1200)
    }
  }, [decide, schedule])

  // ── Decision loop bootstrap ──────────────────────────────
  useEffect(() => {
    schedule(decide, 2500)
    return () => window.clearTimeout(decideTimer.current)
  }, [decide, schedule])

  // ── Dock at home when the panel opens ────────────────────
  useEffect(() => {
    if (!docked) return
    const home = homePosition()
    moveTo(home.x, home.y, 'dashing', () => {
      setState((prev) => ({ ...prev, behavior: 'sitting', facing: 'left', moveMs: 0 }))
    })
  }, [docked, moveTo])

  // ── Eye tracking + sleep/wake via cursor ─────────────────
  useEffect(() => {
    const updateLook = () => {
      lookRafRef.current = 0
      const figure = figureRef.current
      if (!figure || stateRef.current.behavior === 'sleeping') return
      const rect = figure.getBoundingClientRect()
      const cx = rect.left + rect.width / 2
      const cy = rect.top + rect.height * 0.38 // eye line, not figure centre
      const dx = mouseRef.current.x - cx
      const dy = mouseRef.current.y - cy
      const distance = Math.hypot(dx, dy) || 1
      const scale = Math.min(distance / 120, 1) * PUPIL_RANGE_PX
      figure.style.setProperty('--look-x', `${(dx / distance) * scale}px`)
      figure.style.setProperty('--look-y', `${(dy / distance) * scale}px`)
    }

    const onMouseMove = (e: MouseEvent) => {
      lastActivityRef.current = Date.now()
      mouseRef.current = { x: e.clientX, y: e.clientY }
      if (!lookRafRef.current) {
        lookRafRef.current = window.requestAnimationFrame(updateLook)
      }
      if (stateRef.current.behavior === 'sleeping') {
        const figure = figureRef.current
        if (!figure) return
        const rect = figure.getBoundingClientRect()
        const distance = Math.hypot(
          e.clientX - (rect.left + rect.width / 2),
          e.clientY - (rect.top + rect.height / 2),
        )
        if (distance < WAKE_DISTANCE_PX) wake()
      }
    }

    const onActivity = () => {
      lastActivityRef.current = Date.now()
    }

    window.addEventListener('mousemove', onMouseMove, { passive: true })
    window.addEventListener('keydown', onActivity, { passive: true })
    window.addEventListener('scroll', onActivity, { passive: true })
    return () => {
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('keydown', onActivity)
      window.removeEventListener('scroll', onActivity)
      window.cancelAnimationFrame(lookRafRef.current)
    }
  }, [wake])

  // ── Randomised blinking (sometimes a double blink) ───────
  useEffect(() => {
    let cancelled = false
    const blinkOnce = () => {
      const figure = figureRef.current
      if (figure && stateRef.current.behavior !== 'sleeping') {
        figure.classList.add('is-blinking')
        window.setTimeout(() => figure.classList.remove('is-blinking'), BLINK_MS)
        if (Math.random() < 0.2) {
          window.setTimeout(() => {
            if (!cancelled) figure.classList.add('is-blinking')
          }, BLINK_MS + 90)
          window.setTimeout(() => {
            if (!cancelled) figure.classList.remove('is-blinking')
          }, BLINK_MS * 2 + 90)
        }
      }
      if (!cancelled) {
        blinkTimer.current = window.setTimeout(blinkOnce, randBetween(2200, 6000))
      }
    }
    blinkTimer.current = window.setTimeout(blinkOnce, randBetween(1500, 3000))
    return () => {
      cancelled = true
      window.clearTimeout(blinkTimer.current)
    }
  }, [])

  // ── Keep the cheetah on screen when the window resizes ───
  useEffect(() => {
    const onResize = () => {
      setState((prev) => {
        const clamped = clampToViewport(prev.x, prev.y)
        if (clamped.x === prev.x && clamped.y === prev.y) return prev
        return { ...prev, ...clamped, moveMs: 0 }
      })
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return { state, figureRef, wake }
}
