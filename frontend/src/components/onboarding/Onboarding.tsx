"use client";

// First contact: the learner describes a goal in their own words and leaves
// with a real roadmap. Three steps, no forms to fill in — the coach reads the
// goal, the time budget and any existing skills out of one sentence, then the
// generator plans the route to it.

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, auth, onboardingApi } from "@/lib/api";
import type { CareerSuggestion } from "@/lib/api/onboarding";
import { IconArrow, IconSpark } from "@/components/ui/icons";
import { clsx } from "@/lib/cn";

type Stage = "describe" | "discover" | "resume" | "confirm" | "building";

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
  const [signals, setSignals] = useState("");
  const [careers, setCareers] = useState<CareerSuggestion[] | null>(null);
  const [resume, setResume] = useState("");

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

  /** The uncertain branch: signals in, ranked directions out. */
  const discover = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await onboardingApi.discoverCareers([], signals);
      setCareers(res.careers);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't fetch career directions.");
    } finally {
      setBusy(false);
    }
  };

  /** Choosing a career re-enters the normal flow as a goal sentence, so the
   *  profile is written by the same path a typed goal takes. */
  const chooseCareer = (career: CareerSuggestion) => {
    setCareers(null);
    setStage("describe");
    void describe(`I want to become a ${career.title.toLowerCase()}.`);
  };

  /** Resume intake: the extractor reads goal, hours and skills from the text. */
  const submitResume = async () => {
    if (resume.trim().length < 40) {
      return setError("Paste a little more — a few lines about your background and skills.");
    }
    setBusy(true);
    setError(null);
    try {
      const me = await auth.me();
      await onboardingApi.ingestResume(me.id, resume.trim());
      const profile = await fetch(`/api/v1/profile/${me.id}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("lpr_token")}` },
      }).then((r) => (r.ok ? r.json() : null));
      const heardGoal = profile?.profile?.target_role ?? null;
      const skills = (profile?.skills ?? [])
        .map((sk: { skill?: { name?: string } }) => sk.skill?.name)
        .filter(Boolean);
      setGoal(heardGoal);
      setReply(
        heardGoal
          ? `From your background I picked up ${skills.length ? skills.join(", ") : "your experience"}` +
              ` and a goal of ${heardGoal}.`
          : `I read ${skills.length ? skills.join(", ") : "your background"} from that — but not a goal. ` +
              "Tell me what you're aiming for and I'll chart the route.",
      );
      setStage("confirm");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't read that — try again.");
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
      // A goal the graph cannot map yet is not a wall — it is exactly what
      // career discovery is for. Pivot there with the goal as the signal,
      // instead of stranding the learner on an error under a "Got it".
      if (e instanceof ApiError && e.code === "goal_unresolved") {
        setSignals(goal);
        setCareers(null);
        setStage("discover");
        setError("I couldn't map that goal exactly — here are close directions instead.");
        void discoverWith(goal);
        return;
      }
      setStage("confirm");
      setError(
        e instanceof ApiError
          ? e.message
          : "I couldn't build your roadmap. Please try again.",
      );
    }
  };

  /** Discovery seeded with a specific phrase (used by the pivot above). */
  const discoverWith = async (seed: string) => {
    try {
      const res = await onboardingApi.discoverCareers([], seed);
      setCareers(res.careers);
    } catch {
      /* the discover stage's own button remains as the retry */
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

              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => { setStage("discover"); setError(null); }}
                  className="flex-1 border border-line px-3 py-2 text-[11px] text-text-2 transition-colors hover:border-cyan/40 hover:text-cyan"
                >
                  Not sure what to aim for?
                </button>
                <button
                  onClick={() => { setStage("resume"); setError(null); }}
                  className="flex-1 border border-line px-3 py-2 text-[11px] text-text-2 transition-colors hover:border-cyan/40 hover:text-cyan"
                >
                  Paste my resume instead
                </button>
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

          {stage === "discover" && (
            <>
              <p className="label-meta text-cyan">Career discovery</p>
              <h1 className="display mt-3 text-[26px] font-semibold leading-tight">
                Let&apos;s find a direction.
              </h1>
              <p className="mt-3 text-[13px] leading-relaxed text-text-2">
                Tell me what you enjoy — building things, language, images,
                numbers, anything. I&apos;ll rank career directions by fit, with
                the evidence for each.
              </p>

              <textarea
                value={signals}
                onChange={(e) => setSignals(e.target.value)}
                rows={3}
                placeholder="I like writing, languages and chatbots…"
                className="mt-5 w-full resize-none border border-line bg-panel-2/60 px-3.5 py-3 text-[13px] leading-relaxed text-text outline-none transition-colors placeholder:text-text-3 focus:border-cyan/60"
              />

              {error && <Alert>{error}</Alert>}

              {careers ? (
                <div className="mt-5 space-y-2">
                  {careers.map((c) => (
                    <button
                      key={c.slug}
                      onClick={() => chooseCareer(c)}
                      className="group block w-full border border-line p-4 text-left transition-colors hover:border-cyan/50"
                    >
                      <div className="flex items-baseline justify-between gap-3">
                        <span className="display text-[15px] font-semibold text-text group-hover:text-cyan">
                          {c.title}
                        </span>
                        {c.score > 0 && <span className="label-meta text-cyan">fit {c.score}</span>}
                      </div>
                      <p className="mt-1.5 text-[12px] leading-relaxed text-text-2">{c.pitch}</p>
                      {c.reasons[0] && (
                        <p className="mt-1.5 text-[11px] text-teal">{c.reasons[0]}</p>
                      )}
                    </button>
                  ))}
                  <p className="label-meta pt-1">Pick one and I&apos;ll chart the route to it.</p>
                </div>
              ) : (
                <button
                  onClick={discover}
                  disabled={busy}
                  className="group mt-5 flex w-full items-center justify-center gap-2.5 border border-cyan/50 bg-cyan/10 px-5 py-3 text-[12px] font-medium tracking-[0.12em] text-cyan transition-all hover:bg-cyan/20 hover:shadow-glow disabled:opacity-40"
                >
                  {busy ? "RANKING…" : "SUGGEST DIRECTIONS"}
                  {!busy && <IconArrow className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />}
                </button>
              )}

              <button
                onClick={() => { setStage("describe"); setCareers(null); setError(null); }}
                className="label-meta mt-4 block w-full py-1 text-center transition-colors hover:text-cyan"
              >
                Back — I&apos;ll describe it myself
              </button>
            </>
          )}

          {stage === "resume" && (
            <>
              <p className="label-meta text-cyan">Resume intake</p>
              <h1 className="display mt-3 text-[26px] font-semibold leading-tight">
                Paste your background.
              </h1>
              <p className="mt-3 text-[13px] leading-relaxed text-text-2">
                A resume, a LinkedIn summary, or a few lines about yourself.
                I&apos;ll read the skills, the time you have and the goal out of it
                — and only what&apos;s actually there.
              </p>

              <textarea
                value={resume}
                onChange={(e) => setResume(e.target.value)}
                rows={8}
                placeholder={"Backend developer, 3 years.\nSkills: Python, SQL, Docker.\nI want to move into machine learning. About 6 hours a week."}
                className="mt-5 w-full resize-none border border-line bg-panel-2/60 px-3.5 py-3 text-[12px] leading-relaxed text-text outline-none transition-colors placeholder:text-text-3 focus:border-cyan/60"
              />

              {error && <Alert>{error}</Alert>}

              <button
                onClick={submitResume}
                disabled={busy}
                className="group mt-5 flex w-full items-center justify-center gap-2.5 border border-cyan/50 bg-cyan/10 px-5 py-3 text-[12px] font-medium tracking-[0.12em] text-cyan transition-all hover:bg-cyan/20 hover:shadow-glow disabled:opacity-40"
              >
                {busy ? "READING…" : "READ MY BACKGROUND"}
                {!busy && <IconArrow className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />}
              </button>

              <button
                onClick={() => { setStage("describe"); setError(null); }}
                className="label-meta mt-4 block w-full py-1 text-center transition-colors hover:text-cyan"
              >
                Back — I&apos;ll describe it myself
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
  const normalised = stage === "discover" || stage === "resume" ? "describe" : stage;
  const at = order.indexOf(normalised);
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
