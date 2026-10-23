import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-body)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "Menlo", "monospace"],
      },
      colors: {
        // Nhận diện Trường ĐH Thủy lợi (logo khiên xanh/đỏ, tlu.edu.vn)
        tlu: {
          blue: "#1A4896",
          "blue-dark": "#143A7C",
          navy: "#0E2A5E",
          "navy-2": "#17376E",
          "navy-3": "#1E4284",
          "navy-line": "#26477F",
          red: "#A61F26",
          "red-dark": "#8A1A20",
          "red-soft": "#E2575E",
          tint: "#EEF3FB",
          "tint-2": "#D6E1F3",
          line: "#C2D2EC",
          ground: "#F4F6FB",
          border: "#E2E7F0",
          ink: "#0F172A",
          muted: "#5B6478",
          "on-navy": "#DCE5F5",
          "on-navy-2": "#B3C3E3",
          "on-navy-3": "#9BB0D8",
        },
      },
      animation: {
        "fade-up": "fadeUp 0.3s ease forwards",
        "slide-in": "slideIn 0.25s ease forwards",
        "pulse-dot": "pulseDot 1.4s ease-in-out infinite",
        "spin-slow": "spin 2s linear infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        slideIn: {
          "0%": { opacity: "0", transform: "translateX(-6px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
        pulseDot: {
          "0%, 80%, 100%": { transform: "scale(0.6)", opacity: "0.4" },
          "40%": { transform: "scale(1)", opacity: "1" },
        },
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      maxWidth: {
        "chat": "42rem",
      },
      backdropBlur: {
        xs: "2px",
      },
    },
  },
  plugins: [],
};

export default config;