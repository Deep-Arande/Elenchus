import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

// Design tokens from AGENTS.md section 10.2, driven by CSS variables in
// app/globals.css (so light/dark switch via the `.dark` class).
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        border: "var(--border)",
        accent: "var(--accent)",
        status: {
          checked: "var(--status-checked)",
          evidence: "var(--status-evidence)",
          insufficient: "var(--status-insufficient)",
        },
        stance: {
          supports: "var(--stance-supports)",
          contradicts: "var(--stance-contradicts)",
          context: "var(--stance-context)",
        },
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        lg: "var(--radius)",
      },
      fontFamily: {
        serif: ["var(--font-serif)", "ui-serif", "Georgia", "serif"],
        sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        deva: ["var(--font-deva)", "var(--font-sans)", "sans-serif"],
      },
      maxWidth: {
        reading: "70ch",
      },
    },
  },
  plugins: [animate],
};

export default config;
