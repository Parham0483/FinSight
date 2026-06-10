# Mascot — the Asiatic (Iranian) Cheetah

A living companion character that guides users through the platform. The
design is a chibi-style **Asiatic cheetah** (*Acinonyx jubatus venaticus*),
the critically endangered subspecies whose entire remaining wild population
lives in Iran — also the inspiration for Iran's 2014 World Cup kit mascot.

## Design references (why it reads as an Iranian cheetah)

| Feature | Real-animal reference |
|---|---|
| Black **tear marks** from inner eye corners down past the muzzle | The cheetah's most recognisable facial feature; helps with sun glare in the wild |
| **Pale buff/sand coat**, small solid spots | Asiatic cheetahs are paler and lighter-spotted than African cheetahs |
| Short spiky **mane on the crown/nape** | Distinctive of the Asiatic subspecies, prominent in cubs |
| **Amber eyes**, black-ringed tail tip | Standard cheetah anatomy |
| **Dashing** as its fast movement | Fastest land animal — the mascot sprints, it doesn't hover |
| Stage-coloured **neckerchief** | Product tie-in: picks up `--mascot-color-primary` so the maturity theme shows on the character |

## Architecture

| File | Responsibility |
|---|---|
| `CheetahSvg.tsx` | The character artwork — parts grouped by class for animation, mood-driven faces, all colours from `--cheetah-*` tokens |
| `useCheetahBehavior.ts` | Autonomy engine — roaming state machine (idle/walk/dash/sit/sleep), cursor-tracking eyes, randomised blinking, inactivity sleep + proximity wake, viewport clamping |
| `Mascot.tsx` | Assembly — positions the stage, renders bubble/panel/zzz/sparkle, exposes the click target |
| `MascotPanel.tsx` | Expanded assistant panel (maturity stage, capabilities) |
| `Mascot.css` | Every visual animation: gaits, tail swish, ear twitch, breathing, blink, glow per mood |

## Behaviour rules

- Roams only the **lower band of the viewport** so it never covers content.
- **Eyes follow the cursor** everywhere (CSS vars `--look-x/--look-y`, rAF-throttled).
- Blinks at randomised 2.2–6 s intervals, with occasional double blinks.
- After **60 s of user inactivity** it falls asleep (zzz); moving the cursor
  within 150 px wakes it.
- A visible **speech message pauses roaming**; the bubble flips sides near
  screen edges.
- Opening the panel makes it **dash home** to the bottom-right and sit.
- Honours `prefers-reduced-motion`: no roaming, no gait/idle animations.

## Visual preview harness

`frontend/mascot-preview.html` (+ `src/mascotPreview.tsx`) renders every
mood/behaviour state in a grid plus a fully live mascot — handy when
tweaking the artwork or behaviour. Run `npx vite` and open
`/mascot-preview.html`. It is dev-only: `vite build` bundles `index.html`
only, so none of it ships.

## Re-skinning

All character colours live in `src/styles/variables.css` under `--cheetah-*`.
Moods (`idle | thinking | happy | concerned | celebrating`) change the face
and aura glow, never the fur — the cheetah always stays a cheetah.
