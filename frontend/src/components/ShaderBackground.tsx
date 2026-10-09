import { Suspense, lazy, useEffect, useState } from 'react'

// The WebGPU engine is large, so the canvas is split into its own async chunk.
// The flat base + scrim below render instantly; the animated canvas fades in
// once its chunk has loaded.
const ShaderCanvas = lazy(() => import('@/components/ShaderCanvas'))

/**
 * App-wide animated background.
 *
 * A single `<Shader>` (shaders.com / WebGPU) renders one canvas; the nested
 * layers blend top-to-bottom on the GPU: a soft white Swirl base, a
 * cursor-reactive ChromaFlow tinted with the coral accent, a FlutedGlass
 * refraction pass, and a faint FilmGrain. It sits fixed behind all content
 * (`-z-10`) and never intercepts input (`pointer-events-none`).
 *
 * Guardrails so it stays professional + readable:
 * - a translucent scrim over the shader keeps text crisp (tune via `scrim`);
 * - `prefers-reduced-motion` renders the flat base only (no animation, no GPU);
 * - the canvas is lazy-loaded, so the base paints immediately;
 * - on browsers without WebGPU the canvas stays empty and the `#EFEFEF` base
 *   shows through — layout is unaffected.
 */
export function ShaderBackground({ scrim = 0.62 }: { scrim?: number }) {
  const reducedMotion = usePrefersReducedMotion()
  const [ready, setReady] = useState(false)
  useEffect(() => setReady(true), [])

  const animate = ready && !reducedMotion

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
      style={{ background: '#EFEFEF' }}
    >
      {animate && (
        <Suspense fallback={null}>
          <ShaderCanvas />
        </Suspense>
      )}

      {/* Readability scrim — mutes the shader toward the page base so content
          stays legible. rgb(239 239 239) === the #EFEFEF base. */}
      <div
        className="absolute inset-0"
        style={{ background: `rgb(239 239 239 / ${scrim})` }}
      />
    </div>
  )
}

function usePrefersReducedMotion() {
  const query = '(prefers-reduced-motion: reduce)'
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches,
  )
  useEffect(() => {
    const mql = window.matchMedia(query)
    const onChange = () => setReduced(mql.matches)
    mql.addEventListener('change', onChange)
    onChange()
    return () => mql.removeEventListener('change', onChange)
  }, [])
  return reduced
}
