// Browser speech I/O for the voice coach: the microphone end (speech-to-text)
// and the speaker end (text-to-speech).
//
// Both use the platform's own Web Speech API rather than a cloud service, so
// the feature needs no API key, no extra dependency and no backend route — it
// matches the way the rest of the app defaults to providers that work offline.
// The seam below is deliberately narrow (start/stop/speak/cancel) so a
// server-side provider — Whisper for transcription, a TTS endpoint for audio —
// can be dropped in later without touching the hook or the UI.
//
// PRIVACY: Chrome's SpeechRecognition is not on-device. It streams microphone
// audio to Google's servers for transcription. Safari behaves similarly.
// `speechSynthesis` output, by contrast, is generated locally. The UI says so
// before the microphone is ever opened.

export type SpeechErrorKind =
  | "not-supported"
  | "not-allowed"
  | "no-speech"
  | "audio-capture"
  | "network"
  | "aborted"
  | "unknown";

/** A transcription result. `isFinal` marks the end of an utterance. */
export interface Transcript {
  text: string;
  isFinal: boolean;
}

export interface RecognizerHandlers {
  onTranscript: (t: Transcript) => void;
  onError: (kind: SpeechErrorKind, message: string) => void;
  /** Fired when recognition stops for any reason, including a normal finish. */
  onEnd: () => void;
}

export interface Recognizer {
  start: () => void;
  stop: () => void;
  abort: () => void;
}

// --- minimal structural types ----------------------------------------------
// The Web Speech API is not in TypeScript's DOM lib, so the shapes actually
// used are declared here rather than pulling in a dependency for them.

interface SpeechRecognitionAlternativeLike {
  transcript: string;
}
interface SpeechRecognitionResultLike {
  readonly length: number;
  isFinal: boolean;
  [index: number]: SpeechRecognitionAlternativeLike;
}
interface SpeechRecognitionResultListLike {
  readonly length: number;
  [index: number]: SpeechRecognitionResultLike;
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: SpeechRecognitionResultListLike;
}
interface SpeechRecognitionErrorEventLike {
  error: string;
  message?: string;
}
interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function recognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** True when this browser can transcribe microphone audio. */
export function canListen(): boolean {
  return recognitionCtor() !== null;
}

/** True when this browser can speak. */
export function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

function errorKind(raw: string): SpeechErrorKind {
  switch (raw) {
    case "not-allowed":
    case "service-not-allowed":
      return "not-allowed";
    case "no-speech":
      return "no-speech";
    case "audio-capture":
      return "audio-capture";
    case "network":
      return "network";
    case "aborted":
      return "aborted";
    default:
      return "unknown";
  }
}

export const ERROR_MESSAGE: Record<SpeechErrorKind, string> = {
  "not-supported": "This browser can't listen. Chrome or Safari support voice; you can still type.",
  "not-allowed": "I need microphone permission to listen. Enable it in your browser settings.",
  "no-speech": "I didn't catch anything — try again.",
  "audio-capture": "No microphone found. Check that one is connected.",
  network: "Speech recognition needs a network connection and couldn't reach the service.",
  aborted: "Listening stopped.",
  unknown: "Something went wrong while listening.",
};

/**
 * Create a recognizer, or null when unsupported.
 *
 * `continuous` is off: one press captures one utterance and stops, which is
 * the right shape for a turn-taking coach and avoids holding the microphone
 * open. Interim results are on so the UI can show words as they are spoken.
 */
export function createRecognizer(
  handlers: RecognizerHandlers,
  lang = "en-US",
): Recognizer | null {
  const Ctor = recognitionCtor();
  if (!Ctor) return null;

  const rec = new Ctor();
  rec.lang = lang;
  rec.continuous = false;
  rec.interimResults = true;
  rec.maxAlternatives = 1;

  rec.onresult = (event) => {
    // Only the results added since the last event are new.
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      const alternative = result[0];
      if (!alternative) continue;
      handlers.onTranscript({
        text: alternative.transcript.trim(),
        isFinal: result.isFinal,
      });
    }
  };
  rec.onerror = (event) => {
    const kind = errorKind(event.error);
    handlers.onError(kind, event.message || ERROR_MESSAGE[kind]);
  };
  rec.onend = () => handlers.onEnd();

  return {
    start: () => rec.start(),
    stop: () => rec.stop(),
    abort: () => rec.abort(),
  };
}

/**
 * Strip anything that reads badly aloud.
 *
 * The coach's replies are prose, but they carry percentages, arrows and the
 * occasional URL from the catalogue — all of which a synthesiser either
 * mangles or reads out character by character.
 */
export function toSpeakable(text: string): string {
  return (
    text
      .replace(/https?:\/\/\S+/g, "the link on screen")
      .replace(/\s*→\s*/g, " to ")
      .replace(/(\d+)\s*%/g, "$1 percent")
      // "1 skill(s)" is fine to read but not to hear. The count is right there,
      // so agree the noun with it instead of voicing the parenthesis.
      .replace(/(\d+)(\s+)([A-Za-z]+)\(s\)/g, (_m, n: string, gap: string, noun: string) =>
        `${n}${gap}${noun}${Number(n) === 1 ? "" : "s"}`,
      )
      .replace(/\(s\)/g, "s")
      .replace(/[*_`#]/g, "")
      .replace(/\s+/g, " ")
      .trim()
  );
}

export interface Speaker {
  speak: (text: string, onDone?: () => void) => void;
  cancel: () => void;
  isSpeaking: () => boolean;
}

/** Create a speaker, or null when the browser has no synthesiser. */
export function createSpeaker(lang = "en-US"): Speaker | null {
  if (!canSpeak()) return null;
  const synth = window.speechSynthesis;

  /**
   * Prefer a natural local voice for the language, falling back to whatever
   * the platform offers. The list loads asynchronously in Chrome, so this is
   * resolved per utterance rather than cached at construction.
   */
  const pickVoice = (): SpeechSynthesisVoice | null => {
    const voices = synth.getVoices();
    if (!voices.length) return null;
    const sameLang = voices.filter((v) => v.lang.replace("_", "-").startsWith(lang.slice(0, 2)));
    const pool = sameLang.length ? sameLang : voices;
    return pool.find((v) => v.localService) ?? pool[0] ?? null;
  };

  return {
    speak: (text, onDone) => {
      const speakable = toSpeakable(text);
      if (!speakable) {
        onDone?.();
        return;
      }
      synth.cancel(); // never let two replies overlap
      const utterance = new SpeechSynthesisUtterance(speakable);
      utterance.lang = lang;
      const voice = pickVoice();
      if (voice) utterance.voice = voice;
      utterance.rate = 1.0;
      utterance.pitch = 1.0;
      utterance.onend = () => onDone?.();
      // A synthesis error must not leave the UI stuck in "speaking".
      utterance.onerror = () => onDone?.();
      synth.speak(utterance);
    },
    cancel: () => synth.cancel(),
    isSpeaking: () => synth.speaking,
  };
}
