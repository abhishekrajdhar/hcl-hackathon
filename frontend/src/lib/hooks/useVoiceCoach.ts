"use client";

// The voice loop around the existing coach:
//
//   speak → transcribe → (the unchanged /chat pipeline) → reply → synthesise
//
// Deliberately additive: this hook owns only the microphone and the speaker.
// Intent detection, tools, grounding and conversation memory stay exactly where
// they were, on the backend, so voice and typing produce identical answers.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ERROR_MESSAGE,
  canListen,
  canSpeak,
  createRecognizer,
  createSpeaker,
  type Recognizer,
  type SpeechErrorKind,
  type Speaker,
} from "@/lib/voice/speech";

export type VoiceStatus = "idle" | "listening" | "thinking" | "speaking";

export interface VoiceCoach {
  supported: { listen: boolean; speak: boolean };
  status: VoiceStatus;
  /** Live transcript while the learner speaks; "" when not listening. */
  interim: string;
  error: string | null;
  /** Whether replies are read aloud. */
  voiceReplies: boolean;
  setVoiceReplies: (on: boolean) => void;
  startListening: () => void;
  stopListening: () => void;
  /** Stop a reply mid-sentence. */
  stopSpeaking: () => void;
  dismissError: () => void;
}

export function useVoiceCoach({
  onUtterance,
  sending,
}: {
  /** Called once per completed utterance — wired to the chat hook's `send`. */
  onUtterance: (text: string) => void;
  /** True while the backend turn is in flight. */
  sending: boolean;
}): VoiceCoach & { speakReply: (text: string) => void } {
  const [supported, setSupported] = useState({ listen: false, speak: false });
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [voiceReplies, setVoiceReplies] = useState(true);

  const recognizerRef = useRef<Recognizer | null>(null);
  const speakerRef = useRef<Speaker | null>(null);
  const finalRef = useRef("");
  // `onUtterance` is a fresh closure each render; the recognizer is built once,
  // so it reads the callback through a ref instead of capturing a stale one.
  const utteranceRef = useRef(onUtterance);
  utteranceRef.current = onUtterance;

  // Capability detection has to run in the browser, not during SSR.
  useEffect(() => {
    setSupported({ listen: canListen(), speak: canSpeak() });
    speakerRef.current = createSpeaker();
    return () => speakerRef.current?.cancel();
  }, []);

  const stopSpeaking = useCallback(() => {
    speakerRef.current?.cancel();
    setStatus((s) => (s === "speaking" ? "idle" : s));
  }, []);

  const startListening = useCallback(() => {
    if (!canListen()) {
      setError(ERROR_MESSAGE["not-supported"]);
      return;
    }
    // Barge-in: talking over the coach interrupts it rather than being mixed
    // with it — and it also stops the microphone hearing the coach's own voice.
    speakerRef.current?.cancel();

    setError(null);
    setInterim("");
    finalRef.current = "";

    const recognizer = createRecognizer({
      onTranscript: ({ text, isFinal }) => {
        if (isFinal) finalRef.current = `${finalRef.current} ${text}`.trim();
        else setInterim(text);
      },
      onError: (kind: SpeechErrorKind, message) => {
        // A silent take is not worth an error banner.
        if (kind !== "aborted" && kind !== "no-speech") setError(message);
        setStatus("idle");
        setInterim("");
      },
      onEnd: () => {
        setInterim("");
        const utterance = finalRef.current.trim();
        finalRef.current = "";
        if (utterance) {
          setStatus("thinking");
          utteranceRef.current(utterance);
        } else {
          setStatus("idle");
        }
      },
    });

    if (!recognizer) {
      setError(ERROR_MESSAGE["not-supported"]);
      return;
    }
    recognizerRef.current = recognizer;
    try {
      recognizer.start();
      setStatus("listening");
    } catch {
      // start() throws if called while already running; treat as a no-op.
      setStatus("listening");
    }
  }, []);

  const stopListening = useCallback(() => {
    recognizerRef.current?.stop();
  }, []);

  const speakReply = useCallback(
    (text: string) => {
      if (!voiceReplies || !speakerRef.current) {
        setStatus("idle");
        return;
      }
      setStatus("speaking");
      speakerRef.current.speak(text, () => setStatus("idle"));
    },
    [voiceReplies],
  );

  // The turn finished without a reply to read (an error bubble, say) — don't
  // leave the indicator stuck on "thinking".
  useEffect(() => {
    if (!sending) setStatus((s) => (s === "thinking" ? "idle" : s));
  }, [sending]);

  // Turning replies off mid-sentence should stop the current one too.
  useEffect(() => {
    if (!voiceReplies) speakerRef.current?.cancel();
  }, [voiceReplies]);

  return {
    supported,
    status,
    interim,
    error,
    voiceReplies,
    setVoiceReplies,
    startListening,
    stopListening,
    stopSpeaking,
    dismissError: () => setError(null),
    speakReply,
  };
}
