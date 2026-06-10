import type { MascotMood } from '../../types'

/**
 * Asiatic (Iranian) cheetah character.
 *
 * Design references — what makes it read as a cheetah, not a generic cat:
 *  - Black "tear marks" running from the inner eye corners down past the
 *    muzzle (the cheetah's signature feature).
 *  - Pale buff/sand coat with small solid spots (Asiatic cheetahs are
 *    paler and lighter-spotted than African ones).
 *  - A short spiky mane on the crown/nape (distinctive of the Asiatic
 *    subspecies, especially cubs).
 *  - Amber eyes, black-tipped ringed tail.
 *
 * All colours come from CSS variables (--cheetah-*) so the character can
 * be re-skinned from variables.css. Animated groups (tail, ears, head,
 * eyes, pupils) carry class names targeted by Mascot.css.
 */

interface CheetahSvgProps {
  mood: MascotMood
  asleep: boolean
}

const FUR = 'var(--cheetah-fur)'
const FUR_LIGHT = 'var(--cheetah-fur-light)'
const FUR_DARK = 'var(--cheetah-fur-dark)'
const SPOT = 'var(--cheetah-spot)'
const LINE = 'var(--cheetah-line)'
const IRIS = 'var(--cheetah-iris)'

const BODY_SPOTS: ReadonlyArray<readonly [number, number, number]> = [
  [36, 86, 2], [43, 79, 1.8], [50, 76, 1.5], [70, 75, 1.5],
  [77, 80, 2], [84, 89, 1.8], [33, 96, 1.6], [87, 98, 1.6],
]

const FOREHEAD_SPOTS: ReadonlyArray<readonly [number, number, number]> = [
  [52, 21, 1.4], [60, 17, 1.4], [68, 21, 1.4], [45, 28, 1.2], [75, 28, 1.2],
]

function Tail() {
  return (
    <g className="cheetah-tail">
      <path
        d="M84 99 C 103 100, 113 90, 109 73"
        stroke={FUR}
        strokeWidth="8"
        strokeLinecap="round"
        fill="none"
      />
      {/* Tail rings + black tip */}
      <path d="M104 84 q 6 1 8 -3" stroke={SPOT} strokeWidth="3" strokeLinecap="round" fill="none" />
      <circle cx="109" cy="73" r="5" fill={LINE} />
    </g>
  )
}

function Body() {
  return (
    <g className="cheetah-body">
      <ellipse cx="60" cy="90" rx="28" ry="21" fill={FUR} />
      <ellipse cx="60" cy="97" rx="17" ry="12" fill={FUR_LIGHT} />
      {BODY_SPOTS.map(([cx, cy, r]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} fill={SPOT} opacity="0.85" />
      ))}
      {/* Front paws with toe lines */}
      <ellipse cx="42" cy="108" rx="9.5" ry="6" fill={FUR} />
      <ellipse cx="78" cy="108" rx="9.5" ry="6" fill={FUR} />
      <path d="M39 105.5 v4.5 M45 105.5 v4.5 M75 105.5 v4.5 M81 105.5 v4.5" stroke={LINE} strokeWidth="1.1" opacity="0.3" strokeLinecap="round" />
    </g>
  )
}

function Ears() {
  return (
    <>
      <g className="cheetah-ear cheetah-ear-left">
        <circle cx="35" cy="21" r="11" fill={FUR} />
        <circle cx="36" cy="22" r="5.5" fill="var(--cheetah-ear-inner)" />
      </g>
      <g className="cheetah-ear cheetah-ear-right">
        <circle cx="85" cy="21" r="11" fill={FUR} />
        <circle cx="84" cy="22" r="5.5" fill="var(--cheetah-ear-inner)" />
      </g>
    </>
  )
}

function Eyes({ mood, asleep }: CheetahSvgProps) {
  // Sleeping: gently closed lids
  if (asleep) {
    return (
      <g className="cheetah-eyes-closed">
        <path d="M39 41 Q46 46 53 41" stroke={LINE} strokeWidth="2.4" strokeLinecap="round" fill="none" />
        <path d="M67 41 Q74 46 81 41" stroke={LINE} strokeWidth="2.4" strokeLinecap="round" fill="none" />
      </g>
    )
  }

  // Celebrating: happy ^ ^ arcs
  if (mood === 'celebrating') {
    return (
      <g className="cheetah-eyes-closed">
        <path d="M39 42 Q46 34 53 42" stroke={LINE} strokeWidth="2.6" strokeLinecap="round" fill="none" />
        <path d="M67 42 Q74 34 81 42" stroke={LINE} strokeWidth="2.6" strokeLinecap="round" fill="none" />
      </g>
    )
  }

  return (
    <>
      {mood === 'concerned' && (
        <g className="cheetah-brows">
          <path d="M40 29.5 L52 32.5" stroke={LINE} strokeWidth="2" strokeLinecap="round" />
          <path d="M80 29.5 L68 32.5" stroke={LINE} strokeWidth="2" strokeLinecap="round" />
        </g>
      )}
      <g className="cheetah-eye">
        <ellipse cx="46" cy="40" rx="7.2" ry="8" fill="#fff" />
        <g className="cheetah-iris-group">
          <circle cx="46" cy="41" r="4.8" fill={IRIS} />
          <circle cx="46" cy="41" r="2.7" fill={LINE} />
        </g>
        <circle cx="43.8" cy="37.5" r="1.5" fill="#fff" opacity="0.95" />
        <circle cx="48.5" cy="43" r="0.8" fill="#fff" opacity="0.7" />
      </g>
      <g className="cheetah-eye">
        <ellipse cx="74" cy="40" rx="7.2" ry="8" fill="#fff" />
        <g className="cheetah-iris-group">
          <circle cx="74" cy="41" r="4.8" fill={IRIS} />
          <circle cx="74" cy="41" r="2.7" fill={LINE} />
        </g>
        <circle cx="71.8" cy="37.5" r="1.5" fill="#fff" opacity="0.95" />
        <circle cx="76.5" cy="43" r="0.8" fill="#fff" opacity="0.7" />
      </g>
    </>
  )
}

function Mouth({ mood, asleep }: CheetahSvgProps) {
  if (asleep) {
    return <path d="M56.5 60 Q60 62 63.5 60" stroke={LINE} strokeWidth="1.6" strokeLinecap="round" fill="none" />
  }
  switch (mood) {
    case 'happy':
      return <path d="M53 58.5 Q60 65 67 58.5" stroke={LINE} strokeWidth="2" strokeLinecap="round" fill="none" />
    case 'celebrating':
      return (
        <g>
          <path d="M53.5 58.5 Q60 68 66.5 58.5 Z" fill="var(--cheetah-mouth)" />
          <ellipse cx="60" cy="62.5" rx="3" ry="2" fill="var(--cheetah-tongue)" />
        </g>
      )
    case 'concerned':
      return <path d="M55 62 Q60 58.5 65 62" stroke={LINE} strokeWidth="1.8" strokeLinecap="round" fill="none" />
    case 'thinking':
      return <circle cx="60.5" cy="60.5" r="1.9" fill="none" stroke={LINE} strokeWidth="1.6" />
    default:
      // Idle: little cat "w" mouth
      return <path d="M55.5 59 Q57.7 61.5 60 59 Q62.3 61.5 64.5 59" stroke={LINE} strokeWidth="1.6" strokeLinecap="round" fill="none" />
  }
}

function Head({ mood, asleep }: CheetahSvgProps) {
  return (
    <g className="cheetah-head">
      {/* Short spiky mane on the crown — Asiatic cheetah trait */}
      <path d="M44 16 L48 7 L52 14 L56 4 L60 12 L64 4 L68 14 L72 7 L76 16 Z" fill={FUR_DARK} />
      <Ears />
      <circle cx="60" cy="42" r="28" fill={FUR} />
      {FOREHEAD_SPOTS.map(([cx, cy, r]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={r} fill={SPOT} opacity="0.8" />
      ))}
      <ellipse className="cheetah-blush" cx="37" cy="50" rx="5" ry="3" />
      <ellipse className="cheetah-blush" cx="83" cy="50" rx="5" ry="3" />
      {/* Muzzle */}
      <ellipse cx="60" cy="56" rx="12.5" ry="8.5" fill={FUR_LIGHT} />
      {/* Signature tear marks — inner eye corner down around the muzzle */}
      <path className="cheetah-tear" d="M52.5 45 Q53.5 53 47.5 61" stroke={LINE} strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <path className="cheetah-tear" d="M67.5 45 Q66.5 53 72.5 61" stroke={LINE} strokeWidth="2.4" strokeLinecap="round" fill="none" />
      <Eyes mood={mood} asleep={asleep} />
      {/* Nose + philtrum */}
      <path d="M56.5 51.5 L63.5 51.5 L60 55.5 Z" fill={LINE} stroke={LINE} strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M60 55.5 V58" stroke={LINE} strokeWidth="1.4" strokeLinecap="round" />
      <Mouth mood={mood} asleep={asleep} />
      {/* Whisker dots */}
      <g fill={LINE} opacity="0.45">
        <circle cx="51" cy="57" r="0.7" />
        <circle cx="49" cy="60" r="0.7" />
        <circle cx="69" cy="57" r="0.7" />
        <circle cx="71" cy="60" r="0.7" />
      </g>
    </g>
  )
}

export default function CheetahSvg({ mood, asleep }: CheetahSvgProps) {
  return (
    <svg
      className={`mascot-svg mood-${mood}`}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <Tail />
      <Body />
      <Head mood={mood} asleep={asleep} />
      {/* Stage-coloured neckerchief ties the character to the product theme */}
      <g className="cheetah-scarf">
        <path d="M40 65 Q60 75 80 65 L78 73 Q60 81 42 73 Z" fill="var(--mascot-color-primary)" />
        <path d="M78 66 l8 -4 l-2 9 Z" fill="var(--mascot-color-primary)" opacity="0.85" />
      </g>
      {/* Thinking dots */}
      {mood === 'thinking' && !asleep && (
        <g className="cheetah-think-dots" fill={LINE} opacity="0.5">
          <circle cx="94" cy="30" r="1.6" />
          <circle cx="100" cy="22" r="2.1" />
          <circle cx="106" cy="13" r="2.6" />
        </g>
      )}
    </svg>
  )
}
