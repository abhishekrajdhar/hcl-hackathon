"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/**
 * Renders children into `document.body`.
 *
 * Necessary because a `position: fixed` overlay is NOT positioned against the
 * viewport when any ancestor establishes a containing block — and
 * `backdrop-filter` does exactly that. Every `.hud` panel in this UI is
 * backdrop-blurred, so a modal rendered inside one would otherwise be laid out
 * against that panel: pinned to the bottom of the card, sized to it, and
 * clipped. Portalling to the body sidesteps the whole class of problem.
 *
 * Mounts only after hydration, since `document` does not exist on the server.
 */
export function Portal({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return createPortal(children, document.body);
}
