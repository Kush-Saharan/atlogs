import { ChromaFlow, FilmGrain, FlutedGlass, Shader, Swirl } from 'shaders/react'

/**
 * The WebGPU shader stack, isolated in its own module so it can be lazy-loaded
 * (the shaders engine is large — keeping it out of the main bundle). A single
 * `<Shader>` renders one canvas; children are blended top-to-bottom on the GPU.
 */
export default function ShaderCanvas() {
  return (
    <Shader className="absolute inset-0 h-full w-full">
      <Swirl colorA="#ffffff" colorB="#f0f0f0" detail={1.7} />
      <ChromaFlow
        baseColor="#ffffff"
        upColor="#ff5f03"
        downColor="#ff5f03"
        leftColor="#ff5f03"
        rightColor="#ff5f03"
        momentum={13}
        radius={3.5}
      />
      <FlutedGlass
        aberration={0.61}
        angle={31}
        frequency={8}
        highlight={0.12}
        highlightSoftness={0}
        lightAngle={-90}
        refraction={4}
        shape="rounded"
        softness={1}
        speed={0.15}
      />
      <FilmGrain strength={0.05} />
    </Shader>
  )
}
