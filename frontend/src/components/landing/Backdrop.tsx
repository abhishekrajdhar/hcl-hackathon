// Fixed animated gradient blobs behind the whole page. Purely decorative.
export function Backdrop() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0 bg-bg" />
      <div className="animate-blob absolute -left-32 -top-24 h-[36rem] w-[36rem] rounded-full bg-brand/25 blur-[100px]" />
      <div
        className="animate-blob absolute -right-32 top-40 h-[32rem] w-[32rem] rounded-full bg-accent/25 blur-[100px]"
        style={{ animationDelay: "-6s" }}
      />
      <div
        className="animate-blob absolute bottom-0 left-1/3 h-[30rem] w-[30rem] rounded-full bg-brand/15 blur-[110px]"
        style={{ animationDelay: "-12s" }}
      />
      <div className="bg-grid absolute inset-0 opacity-[0.35] [mask-image:radial-gradient(ellipse_at_center,#000_20%,transparent_75%)]" />
    </div>
  );
}
