import type { Config } from "tailwindcss";

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
        background: "#0d1117",
        surface: "#161b22",
        "surface-2": "#1c2128",
        border: "#30363d",
        muted: "#8b949e",
        foreground: "#e6edf3",
        bull: "#22c55e",
        bear: "#ef4444",
        brand: {
          DEFAULT: "#22c55e",
          dark: "#16a34a",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
