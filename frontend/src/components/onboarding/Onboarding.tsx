"use client";

// First contact: the learner describes a goal in their own words and leaves
// with a real roadmap. Three steps, no forms to fill in — the coach reads the
// goal, the time budget and any existing skills out of one sentence, then the
// generator plans the route to it.

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, auth, onboardingApi } from "@/lib/api";
import { IconArrow, IconSpark } from "@/components/ui/icons";
import { clsx } from "@/lib/cn";

type Stage = "describe" | "confirm" | "building";

const EXAMPLES = [
  "I want to become a machine learning engineer. I have about 8 hours a week and I already know Python.",
  "I'd like to move into data engineering — I'm comfortable with SQL but new to Spark.",
  "I want to build with large language models. Around 5 hours a week, and I know some Python.",
];

export function Onboarding() {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("describe");
  const [text, setText] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [goal, setGoal] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  /** Step 1 — the coach reads the sentence and writes the profile. */
  const describe = async (message: string) => {
    const clean = message.trim();
    if (clean.length < 8) return setError("Tell me a little more about what you want to learn.");
    setBusy(true);
    setError(null);
    try {
      const res = await onboardingApi.describeGoal(clean);
      setReply(res.reply);
      // The profile now holds the goal; read it back rather than re-parsing
      // the sentence here, so the UI and the engine agree on what was heard.
      const me = await auth.me();
      const profile = await fetch(`/api/v1/profile/${me.id}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("lpr_token")}` },
      }).then((r) => (r.ok ? r.json() : null));
      setGoal(profile?.profile?.target_role ?? null);
      setStage("confirm");
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "I couldn't reach the coach. Check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  /** Step 2 — plan the route to that goal. */
  const build = async () => {
    if (!goal) return;
    setStage("building");
    setError(null);
    try {
      const me = await auth.me();
      await onboardingApi.generatePath(me.id, goal);
      router.replace("/dashboard");
    } catch (e) {
      setStage("confirm");
      setError(
        e instanceof ApiError
          ? e.message
          : "I couldn't build your roadmap. Please try again.",
      );
    }
  };

  return (
    <main className="relative grid min-h-screen place-items-center px-6 py-16">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 50% 45% at 50% 35%, rgba(41,230,209,0.07), transparent 70%)",
        }}
      />

      <div className="relative w-full max-w-[600px]">
        <Steps stage={stage} />

        <div className="hud hud-bracket mt-6 p-7">
          {stage === "describe" && (
            <>
              <p className="label-meta text-cyan">Step one</p>
              <h1 className="display mt-3 text-[26px] font-semibold leading-tight">
                What do you want to be able to do?
              </h1>
              <p className="mt-3 text-[13px] leading-relaxed text-text-2">
                Describe it in your own words. Mention how much time you have and
                anything you already know — it all counts.
              </p>

              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={4}
                placeholder="I want to become a machine learning engineer…"
                className="mt-5 w-full resize-none border border-line bg-panel-2/60 px-3.5 py-3 text-[13px] leading-relaxed text-text outline-none transition-colors placeholder:text-text-3 focus:border-cyan/60"
              />

              <div className="mt-3 space-y-1.5">
                <p className="label-meta">Or start from one of these</p>
                {EXAMPLES.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => setText(ex)}
                    className="block w-full truncate border border-line px-3 py-2 text-left text-[11px] text-text-2 transition-colors hover:border-cyan/40 hover:text-cyan"
                  >
                    {ex}
                  </button>
                ))}
              </div>

              {error && <Alert>{error}</Alert>}

              <button
                onClick={() => describe(text)}
                disabled={busy}
                className="group mt-5 flex w-full items-center justify-center gap-2.5 border border-cyan/50 bg-cyan/10 px-5 py-3 text-[12px] font-medium tracking-[0.12em] text-cyan transition-all hover:bg-cyan/20 hover:shadow-glow disabled:opacity-40"
              >
                {busy ? "READING…" : "CONTINUE"}
                {!busy && <IconArrow className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />}
              </button>
            </>
          )}

          {stage === "confirm" && (
            <>
              <p className="label-meta text-cyan">Step two</p>
              <h1 className="display mt-3 text-[26px] font-semibold leading-tight">
                Here&apos;s what I heard.
              </h1>

              <div className="mt-5 flex gap-3 border-l-2 border-cyan pl-4">
                <IconSpark className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan" />
                <p className="text-[13px] leading-relaxed text-text">{reply}</p>
              </div>

              {goal ? (
                <p className="mt-5 text-[12px] text-text-2">
                  I&apos;ll map the route to{" "}
                  <span className="text-cyan">{goal}</span> and chart your universe
                  around it. You can refine anything afterwards.
                </p>
              ) : (
                <p className="mt-5 text-[12px] text-coral">
                  I couldn&apos;t pin down a goal from that. Try naming the role or
                  skill you&apos;re aiming for.
                </p>
              )}

              {error && <Alert>{error}</Alert>}

              <div className="mt-6 flex gap-2">
                <button
                  onClick={() => {
                    setStage("describe");
                    setError(null);
                  }}
                  className="border border-line-strong px-4 py-2.5 text-[12px] tracking-wide text-text-2 transition-colors hover:border-cyan/40 hover:text-cyan"
                >
                  REPHRASE
                </button>
                <button
                  onClick={build}
                  disabled={!goal}
                  className="group flex flex-1 items-center justify-center gap-2.5 border border-cyan/50 bg-cyan/10 px-5 py-2.5 text-[12px] font-medium tracking-[0.12em] text-cyan transition-all hover:bg-cyan/20 hover:shadow-glow disabled:opacity-40"
                >
                  BUILD MY ROADMAP
                  <IconArrow className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                </button>
              </div>
            </>
          )}

          {stage === "building" && (
            <div className="py-10 text-center">
              <p className="label-meta text-cyan">Step three</p>
              <h1 className="display mt-3 text-[24px] font-semibold">Charting your universe…</h1>
              <p className="mx-auto mt-3 max-w-sm text-[13px] leading-relaxed text-text-2">
                Finding your position in the skill graph, ordering what&apos;s
                missing by prerequisite, and fitting it to your week.
              </p>
              <div className="mx-auto mt-6 h-px w-40 overflow-hidden bg-line">
                <div className="energy-line h-full w-full" />
              </div>
            </div>
          )}
        </div>

        <button
          onClick={() => router.replace("/dashboard?demo=1")}
          className="label-meta mt-5 block w-full py-2 text-center transition-colors hover:text-cyan"
        >
          Skip — show me a demo universe first
        </button>
      </div>
    </main>
  );
}

function Steps({ stage }: { stage: Stage }) {
  const order: Stage[] = ["describe", "confirm", "building"];
  const at = order.indexOf(stage);
  return (
    <div className="flex items-center gap-2">
      {["Describe", "Confirm", "Build"].map((label, i) => (
        <div key={label} className="flex flex-1 items-center gap-2">
          <span
            className={clsx(
              "h-px flex-1 transition-colors",
              i <= at ? "bg-cyan" : "bg-line",
            )}
          />
          <span className={clsx("label-meta", i <= at ? "text-cyan" : "text-text-3")}>
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

function Alert({ children }: { children: React.ReactNode }) {
  return (
    <p role="alert" className="mt-4 border-l-2 border-coral py-1 pl-3 text-[12px] text-coral">
      {children}
    </p>
  );
}
