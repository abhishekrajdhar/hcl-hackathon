import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // World surfaces
        void: "var(--void)",
        panel: { DEFAULT: "var(--panel)", 2: "var(--panel-2)", 3: "var(--panel-3)" },
        line: { DEFAULT: "var(--line)", strong: "var(--line-strong)" },
        // Signal colours — these carry meaning, see globals.css
        cyan: { DEFAULT: "var(--cyan)", dim: "var(--cyan-dim)" },
        teal: "var(--teal)",
        amber: "var(--amber)",
        coral: "var(--coral)",
        steel: "var(--steel)",
        text: { DEFAULT: "var(--text)", 2: "var(--text-2)", 3: "var(--text-3)" },
        state: {
          mastered: "var(--state-mastered)",
          active: "var(--state-active)",
          weak: "var(--state-weak)",
          locked: "var(--state-locked)",
        },
        // Legacy aliases, kept so existing components restyle automatically
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        border: "var(--border)",
        muted: "var(--muted)",
        fg: "var(--fg)",
        brand: { DEFAULT: "var(--brand)", soft: "var(--brand-soft)" },
        accent: "var(--accent)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
      },
      // Machined, not pillowy: the whole UI drops to near-square corners.
      borderRadius: { xl: "5px", "2xl": "6px" },
      boxShadow: {
        card: "0 20px 50px -32px rgba(0,0,0,0.85)",
        hud: "0 0 0 1px rgba(41,230,209,0.06), 0 24px 60px -30px rgba(0,0,0,0.9)",
        glow: "0 0 24px -4px rgba(41,230,209,0.35)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
export default config;
