"use client";

import { Component, type ReactNode } from "react";

/**
 * Keeps a WebGL failure contained.
 *
 * The universe is now the first thing on the page, so anything that throws
 * inside the canvas — a lost context, a driver quirk, a bad model — would
 * otherwise blank the whole dashboard. The learner's data lives in the panels
 * around it and stays perfectly usable, so a broken scene should cost them the
 * scene and nothing else.
 */
export class SceneBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    // Surfaced in the console rather than swallowed: this is worth fixing, it
    // is just not worth taking the page down for.
    console.error("Learning Universe scene failed:", error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="grid h-full place-items-center px-6 text-center">
        <div>
          <p className="label-meta text-coral">Scene unavailable</p>
          <p className="mt-3 max-w-xs text-[13px] leading-relaxed text-text-2">
            The 3D view couldn&apos;t start on this device. Everything else on
            your dashboard still works — the Knowledge Graph below shows the
            same skills in 2D.
          </p>
          <a
            href="#graph"
            className="label-meta mt-5 inline-block text-cyan hover:underline"
          >
            Open the knowledge graph
          </a>
        </div>
      </div>
    );
  }
}
