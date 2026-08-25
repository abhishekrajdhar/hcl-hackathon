/**
 * Quiet ground beneath the page. The hero runs the real 3D universe, so this
 * layer stays minimal — one distant wash and a grid that fades out — rather
 * than competing with it.
 */
export function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="world-backdrop absolute inset-0" />
      <div className="world-grid absolute inset-0" />
    </div>
  );
}
