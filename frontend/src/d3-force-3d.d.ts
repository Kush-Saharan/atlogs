// react-force-graph uses the d3-force-3d engine; it ships no type declarations.
declare module 'd3-force-3d' {
  interface ForceCollide {
    strength: (s: number) => ForceCollide
    radius: (r: number | ((node: unknown) => number)) => ForceCollide
    iterations: (n: number) => ForceCollide
  }
  export function forceCollide(
    radius?: number | ((node: unknown) => number),
  ): ForceCollide

  // Loose typings for the 3D force layout we run for the graph sphere.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  type AnyForce = any
  export function forceSimulation(nodes?: AnyForce, numDimensions?: number): AnyForce
  export function forceManyBody(): AnyForce
  export function forceLink(links?: AnyForce): AnyForce
  export function forceCenter(x?: number, y?: number, z?: number): AnyForce
  export function forceRadial(
    radius?: number,
    x?: number,
    y?: number,
    z?: number,
  ): AnyForce
}
