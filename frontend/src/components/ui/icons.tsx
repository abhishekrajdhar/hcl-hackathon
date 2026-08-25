// Minimal inline icon set (no external icon dependency). Stroke = currentColor.
type P = { className?: string };
const base = (children: React.ReactNode) => ({ className }: P) => (
  <svg
    className={className}
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.8"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden
  >
    {children}
  </svg>
);

export const IconTarget = base(<><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1.5" fill="currentColor" /></>);
export const IconPath = base(<><circle cx="6" cy="19" r="2" /><circle cx="18" cy="5" r="2" /><path d="M8 19h6a4 4 0 0 0 4-4V7M6 17V9a4 4 0 0 1 4-4h6" /></>);
export const IconSpark = base(<><path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" /></>);
export const IconChart = base(<><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>);
export const IconFlag = base(<><path d="M5 21V4M5 4h11l-2 4 2 4H5" /></>);
export const IconBook = base(<><path d="M4 5a2 2 0 0 1 2-2h12v16H6a2 2 0 0 0-2 2zM4 19a2 2 0 0 1 2-2h12" /></>);
export const IconArrow = base(<><path d="M5 12h14M13 6l6 6-6 6" /></>);
export const IconCheck = base(<><path d="M4 12l5 5L20 6" /></>);
export const IconClock = base(<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>);
export const IconActivity = base(<><path d="M3 12h4l3 8 4-16 3 8h4" /></>);
export const IconChat = base(<><path d="M21 15a2 2 0 0 1-2 2H8l-4 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z" /></>);
export const IconClipboard = base(<><rect x="8" y="4" width="8" height="4" rx="1" /><path d="M8 6H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-2" /><path d="M9 13l2 2 4-4" /></>);
export const IconLock = base(<><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>);
export const IconExternal = base(<><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></>);
export const IconSend = base(<><path d="M4 12l16-8-6 16-3-6-7-2z" /></>);
export const IconLogout = base(<><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></>);
export const IconLayers = base(<><path d="M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 17l9 5 9-5" /></>);
export const IconGraph = base(<><circle cx="12" cy="4" r="2" /><circle cx="5" cy="15" r="2" /><circle cx="19" cy="15" r="2" /><circle cx="12" cy="21" r="1.5" /><path d="M12 6v3M11 9.5 6.5 13M13 9.5l4.5 3.5M6.5 16.5 11 20M17.5 16.5 13 20" /></>);
export const IconMic = base(<><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" /></>);
export const IconMicOff = base(<><path d="M9 9V6a3 3 0 0 1 5.1-2.1M15 11.5V6M5 11a7 7 0 0 0 10.9 5.8M12 18v3M9 21h6M3 3l18 18" /></>);
export const IconSpeaker = base(<><path d="M4 9v6h4l5 4V5L8 9H4z" /><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8 8 0 0 1 0 12" /></>);
export const IconSpeakerOff = base(<><path d="M4 9v6h4l5 4V5L8 9H4z" /><path d="M17 9l4 6M21 9l-4 6" /></>);
export const IconStop = base(<><rect x="6" y="6" width="12" height="12" rx="2" /></>);
