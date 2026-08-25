"use client";

// Lightweight animation primitives for the landing page — no external deps.
// Everything is transform/opacity based and honours prefers-reduced-motion.

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ElementType,
  type ReactNode,
} from "react";
import { clsx } from "@/lib/cn";

/** Observe an element and report when it first scrolls into view. */
export function useInView<T extends HTMLElement>(options?: IntersectionObserverInit) {
  const ref = useRef<T>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          obs.disconnect();
        }
      },
      { threshold: 0.2, rootMargin: "0px 0px -8% 0px", ...options },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [options]);
  return { ref, inView };
}

/** Fade + rise into view on scroll. */
export function Reveal({
  children,
  as: Tag = "div",
  delay = 0,
  className,
  style,
}: {
  children: ReactNode;
  /** Narrowed to HTML tags: with @react-three/fiber's JSX augmentation loaded,
   *  a bare ElementType no longer type-checks for common DOM props. */
  as?: "div" | "section" | "span" | "article" | "aside" | "header" | "footer" | "li";
  delay?: number;
  className?: string;
  style?: CSSProperties;
}) {
  const { ref, inView } = useInView<HTMLElement>();
  return (
    <Tag
      // Callback form: contravariant, so it satisfies every tag in the union.
      ref={(el: HTMLElement | null) => {
        ref.current = el;
      }}
      className={clsx("reveal", inView && "in", className)}
      style={{ ["--reveal-delay" as string]: `${delay}ms`, ...style }}
    >
      {children}
    </Tag>
  );
}

/** Count from 0 → `to` when scrolled into view. */
export function CountUp({
  to,
  duration = 1600,
  suffix = "",
  prefix = "",
  decimals = 0,
  className,
}: {
  to: number;
  duration?: number;
  suffix?: string;
  prefix?: string;
  decimals?: number;
  className?: string;
}) {
  const { ref, inView } = useInView<HTMLSpanElement>();
  const [val, setVal] = useState(0);

  useEffect(() => {
    if (!inView) return;
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVal(to);
      return;
    }
    let raf = 0;
    let start = 0;
    const step = (t: number) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(to * eased);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, duration]);

  return (
    <span ref={ref} className={className}>
      {prefix}
      {val.toFixed(decimals)}
      {suffix}
    </span>
  );
}

/** Pointer-driven 3D tilt for a card. */
export function Tilt({
  children,
  className,
  max = 8,
}: {
  children: ReactNode;
  className?: string;
  max?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  const onMove = (e: React.MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    el.style.transform = `perspective(900px) rotateY(${px * max}deg) rotateX(${-py * max}deg)`;
  };
  const reset = () => {
    if (ref.current) ref.current.style.transform = "perspective(900px) rotateY(0) rotateX(0)";
  };

  return (
    <div
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={reset}
      className={clsx("transition-transform duration-200 ease-out [transform-style:preserve-3d]", className)}
    >
      {children}
    </div>
  );
}

/** A cursor-following radial glow layer. Mount inside a `relative` container. */
export function Spotlight({ className }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    const parent = el?.parentElement;
    if (!el || !parent) return;
    const onMove = (e: MouseEvent) => {
      const r = parent.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    };
    parent.addEventListener("mousemove", onMove);
    return () => parent.removeEventListener("mousemove", onMove);
  }, []);
  return (
    <div
      ref={ref}
      aria-hidden
      className={clsx("pointer-events-none absolute inset-0", className)}
      style={{
        background:
          "radial-gradient(400px circle at var(--mx, 50%) var(--my, 0%), color-mix(in srgb, var(--brand) 18%, transparent), transparent 60%)",
      }}
    />
  );
}
