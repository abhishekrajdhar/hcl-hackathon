"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import type { SkillDelta } from "@/lib/adaptive";

export interface Toast {
  id: number;
  title: string;
  body?: string;
  deltas?: SkillDelta[];
  tone?: "brand" | "success" | "neutral";
}

type NotifyInput = Omit<Toast, "id">;

interface ToastCtx {
  toasts: Toast[];
  notify: (t: NotifyInput) => void;
  dismiss: (id: number) => void;
}

const Ctx = createContext<ToastCtx | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const notify = useCallback(
    (t: NotifyInput) => {
      const id = ++seq.current;
      setToasts((list) => [...list, { ...t, id }]);
      // Auto-dismiss; richer (skill-delta) toasts linger a little longer.
      const ttl = t.deltas?.length ? 9000 : 6000;
      window.setTimeout(() => dismiss(id), ttl);
    },
    [dismiss],
  );

  return <Ctx.Provider value={{ toasts, notify, dismiss }}>{children}</Ctx.Provider>;
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}
