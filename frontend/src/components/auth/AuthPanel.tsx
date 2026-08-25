"use client";

// One panel, two modes. Sign-in and registration differ by a single field and
// a single endpoint, so they share a component rather than drifting apart.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, auth } from "@/lib/api";
import { clsx } from "@/lib/cn";
import { IconArrow } from "@/components/ui/icons";

export type AuthMode = "login" | "signup";

const COPY = {
  login: {
    eyebrow: "Access",
    title: "Re-enter your universe",
    action: "SIGN IN",
    alt: "No account yet?",
    altAction: "Create one",
    altHref: "/signup",
  },
  signup: {
    eyebrow: "New learner",
    title: "Chart your first route",
    action: "CREATE ACCOUNT",
    alt: "Already have an account?",
    altAction: "Sign in",
    altHref: "/login",
  },
} as const;

/** The backend enforces this too; checking here saves a round trip. */
const MIN_PASSWORD = 8;

export function AuthPanel({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const copy = COPY[mode];

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim()) return setError("Enter your email address.");
    if (password.length < MIN_PASSWORD) {
      return setError(`Password must be at least ${MIN_PASSWORD} characters.`);
    }

    setBusy(true);
    try {
      if (mode === "signup") {
        await auth.register(email.trim(), password, fullName.trim() || undefined);
      } else {
        await auth.login(email.trim(), password);
      }
      // Both endpoints return a token, and the API client has already stored it.
      router.replace("/dashboard");
    } catch (err) {
      setError(messageFor(err, mode));
      setBusy(false);
    }
  };

  return (
    <main className="relative grid min-h-screen place-items-center px-6 py-16">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 45% 45% at 50% 40%, rgba(41,230,209,0.07), transparent 70%)",
        }}
      />

      <div className="relative w-full max-w-[380px]">
        <Link href="/" className="mb-10 flex items-center gap-2.5">
          <span className="relative grid h-5 w-5 place-items-center">
            <span className="absolute inset-0 rounded-full border border-cyan/60" />
            <span className="h-1.5 w-1.5 rounded-full bg-cyan shadow-glow" />
          </span>
          <span className="display text-[13px] font-semibold tracking-tight">PATHWISE</span>
        </Link>

        <div className="hud hud-bracket p-7">
          <p className="label-meta text-cyan">{copy.eyebrow}</p>
          <h1 className="display mt-3 text-[26px] font-semibold leading-tight">{copy.title}</h1>

          <form onSubmit={submit} className="mt-7 space-y-4" noValidate>
            {mode === "signup" && (
              <Field
                label="Name"
                type="text"
                value={fullName}
                onChange={setFullName}
                placeholder="Optional"
                autoComplete="name"
              />
            )}
            <Field
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
            <Field
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              placeholder={`At least ${MIN_PASSWORD} characters`}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              required
            />

            {error && (
              <p role="alert" className="border-l-2 border-coral py-1 pl-3 text-[12px] text-coral">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={busy}
              className="group flex w-full items-center justify-center gap-2.5 border border-cyan/50 bg-cyan/10 px-5 py-3 text-[12px] font-medium tracking-[0.12em] text-cyan transition-all hover:bg-cyan/20 hover:shadow-glow disabled:opacity-40"
            >
              {busy ? "WORKING…" : copy.action}
              {!busy && (
                <IconArrow className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
              )}
            </button>
          </form>

          <div className="hud-rule my-6" />

          <div className="flex items-center justify-between gap-3">
            <span className="label-meta">{copy.alt}</span>
            <Link href={copy.altHref} className="label-meta text-cyan hover:underline">
              {copy.altAction}
            </Link>
          </div>
        </div>

        {/* The demo needs no account — it renders the bundled dataset. */}
        <Link
          href="/dashboard?demo=1"
          className="label-meta mt-5 flex items-center justify-center gap-2 py-2 transition-colors hover:text-cyan"
        >
          Explore the demo universe instead
        </Link>
      </div>
    </main>
  );
}

function Field({
  label,
  type,
  value,
  onChange,
  placeholder,
  autoComplete,
  required,
}: {
  label: string;
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="label-meta">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        className={clsx(
          "mt-2 w-full border border-line bg-panel-2/60 px-3 py-2.5 text-[13px] text-text",
          "outline-none transition-colors placeholder:text-text-3 focus:border-cyan/60",
        )}
      />
    </label>
  );
}

/** Turn a transport failure into something a learner can act on. */
function messageFor(err: unknown, mode: AuthMode): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "That email and password don't match an account.";
    if (err.status === 409) return "An account with that email already exists.";
    if (err.status === 422) return err.message || "Check the details above and try again.";
    return err.message || `Something went wrong (${err.status}).`;
  }
  return mode === "signup"
    ? "Couldn't reach the service to create your account."
    : "Couldn't reach the service to sign you in.";
}
