import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        display: [
          "Space Grotesk",
          "Inter Display",
          "Inter",
          "-apple-system",
          "sans-serif",
        ],
      },
      colors: {
        // Soft Lovable/AssetWise palette
        ink: {
          50: "#fafaf9",
          100: "#f4f4f3",
          200: "#e7e7e6",
          300: "#d1d1d0",
          500: "#71716f",
          700: "#3c3c3b",
          900: "#111110",
          950: "#0a0a09",
        },
      },
      backgroundImage: {
        "hero-dots":
          "radial-gradient(circle at center, rgba(0,0,0,0.09) 1px, transparent 1px)",
      },
      backgroundSize: {
        "dot-grid": "16px 16px",
      },
      borderRadius: {
        xl: "0.9rem",
        "2xl": "1.25rem",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 200ms ease-out",
      },
    },
  },
  plugins: [],
} satisfies Config;
