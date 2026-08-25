import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Every colour is `rgb(var(--x-rgb) / <alpha-value>)` so Tailwind's
        // opacity modifiers (`border-cyan/40`, `bg-panel/70`) actually compose.
        void: "rgb(var(--void-rgb) / <alpha-value>)",
        panel: {
          DEFAULT: "rgb(var(--panel-rgb) / <alpha-value>)",
          2: "rgb(var(--panel-2-rgb) / <alpha-value>)",
          3: "rgb(var(--panel-3-rgb) / <alpha-value>)",
        },
        line: {
          DEFAULT: "rgb(var(--line-rgb) / <alpha-value>)",
          strong: "rgb(var(--line-strong-rgb) / <alpha-value>)",
        },
        cyan: {
          DEFAULT: "rgb(var(--cyan-rgb) / <alpha-value>)",
          dim: "rgb(var(--cyan-dim-rgb) / <alpha-value>)",
        },
        teal: "rgb(var(--teal-rgb) / <alpha-value>)",
        amber: "rgb(var(--amber-rgb) / <alpha-value>)",
        coral: "rgb(var(--coral-rgb) / <alpha-value>)",
        steel: "rgb(var(--steel-rgb) / <alpha-value>)",
        text: {
          DEFAULT: "rgb(var(--text-rgb) / <alpha-value>)",
          2: "rgb(var(--text-2-rgb) / <alpha-value>)",
          3: "rgb(var(--text-3-rgb) / <alpha-value>)",
        },
        state: {
          mastered: "rgb(var(--amber-rgb) / <alpha-value>)",
          active: "rgb(var(--cyan-rgb) / <alpha-value>)",
          weak: "rgb(var(--coral-rgb) / <alpha-value>)",
          locked: "rgb(var(--steel-rgb) / <alpha-value>)",
        },
        // Legacy aliases, so existing components restyle without edits.
        bg: "rgb(var(--void-rgb) / <alpha-value>)",
        surface: {
          DEFAULT: "rgb(var(--panel-rgb) / <alpha-value>)",
          2: "rgb(var(--panel-2-rgb) / <alpha-value>)",
        },
        "surface-2": "rgb(var(--panel-2-rgb) / <alpha-value>)",
        border: "rgb(var(--line-rgb) / <alpha-value>)",
        muted: "rgb(var(--text-2-rgb) / <alpha-value>)",
        fg: "rgb(var(--text-rgb) / <alpha-value>)",
        brand: {
          DEFAULT: "rgb(var(--cyan-rgb) / <alpha-value>)",
          soft: "rgb(var(--cyan-rgb) / 0.12)",
        },
        accent: "rgb(var(--teal-rgb) / <alpha-value>)",
        success: "rgb(var(--amber-rgb) / <alpha-value>)",
        warning: "rgb(var(--cyan-rgb) / <alpha-value>)",
        danger: "rgb(var(--coral-rgb) / <alpha-value>)",
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
