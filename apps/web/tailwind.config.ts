import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

// Phase 0 baseline. The full design-token mapping (colours, radius, fonts from
// AGENTS.md section 10.2) lands in Phase 5 via styles/tokens.css.
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [animate],
};

export default config;
