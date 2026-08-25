"use client";

import { Badge } from "@/components/ui/Badge";
import {
  IconMic,
  IconMicOff,
  IconSpeaker,
  IconSpeakerOff,
  IconStop,
} from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import type { VoiceCoach } from "@/lib/hooks/useVoiceCoach";

const STATUS_LABEL: Record<string, string> = {
  idle: "Tap the mic and talk",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking — talk to interrupt",
};

/** Mic button, live transcript and the read-replies toggle. */
export function VoiceControls({ voice }: { voice: VoiceCoach }) {
  const { supported, status, interim, error, voiceReplies } = voice;
  const listening = status === "listening";
  const speaking = status === "speaking";

  if (!supported.listen && !supported.speak) {
    return (
      <p className="px-1 text-[11px] text-muted">
        This browser has no speech support, so the coach is text-only here. Chrome or Safari
        can listen and talk.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {supported.listen && (
          <button
            type="button"
            onClick={listening ? voice.stopListening : voice.startListening}
            aria-pressed={listening}
            aria-label={listening ? "Stop listening" : "Speak to your coach"}
            className={clsx(
              "relative grid h-10 w-10 shrink-0 place-items-center rounded-full border transition-colors",
              listening
                ? "border-transparent bg-danger text-white"
                : "border-border bg-surface text-muted hover:text-fg",
            )}
          >
            {listening && (
              <span className="absolute inset-0 animate-ping rounded-full bg-danger/40" />
            )}
            <IconMic className="relative h-4 w-4" />
          </button>
        )}

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium">{STATUS_LABEL[status]}</span>
            {status === "listening" && <Badge tone="danger">live</Badge>}
            {status === "speaking" && <Badge tone="accent">audio</Badge>}
          </div>
          {/* Interim transcript: what the recogniser has heard so far. */}
          <p
            className={clsx(
              "truncate text-[11px]",
              interim ? "text-fg" : "text-muted",
            )}
            aria-live="polite"
          >
            {interim || (listening ? "…" : "Your words appear here as you speak.")}
          </p>
        </div>

        {speaking && (
          <button
            type="button"
            onClick={voice.stopSpeaking}
            className="flex items-center gap-1 rounded-lg border border-border px-2 py-1 text-[11px] text-muted hover:text-fg"
          >
            <IconStop className="h-3 w-3" /> Stop
          </button>
        )}

        {supported.speak && (
          <button
            type="button"
            onClick={() => voice.setVoiceReplies(!voiceReplies)}
            aria-pressed={voiceReplies}
            aria-label={voiceReplies ? "Mute spoken replies" : "Read replies aloud"}
            title={voiceReplies ? "Replies are read aloud" : "Replies are silent"}
            className={clsx(
              "grid h-8 w-8 shrink-0 place-items-center rounded-lg border transition-colors",
              voiceReplies
                ? "border-brand bg-brand-soft text-brand"
                : "border-border bg-surface text-muted hover:text-fg",
            )}
          >
            {voiceReplies ? <IconSpeaker className="h-4 w-4" /> : <IconSpeakerOff className="h-4 w-4" />}
          </button>
        )}
      </div>

      {error && (
        <div className="flex items-start justify-between gap-2 rounded-lg border border-danger/30 bg-danger/10 px-2 py-1.5">
          <p className="text-[11px] text-danger">{error}</p>
          <button
            onClick={voice.dismissError}
            className="text-[11px] text-danger/70 hover:text-danger"
            aria-label="Dismiss"
          >
            ✕
          </button>
        </div>
      )}

      {supported.listen && (
        // Said once, up front: the microphone is not processed on-device.
        <p className="px-1 text-[10px] text-muted">
          <IconMicOff className="mr-1 inline h-3 w-3" />
          Your browser sends microphone audio to its speech service for transcription.
          Replies are synthesised on your device.
        </p>
      )}
    </div>
  );
}
