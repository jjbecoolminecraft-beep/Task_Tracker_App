import type { Config } from "tailwindcss";

/**
 * "KB-Standard" design tokens, derived from the attached design system
 * (Knorr-Bremse-style investor site): deep petrol-navy, a mid-blue accent,
 * generous whitespace, geometric type, restrained colour.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          900: "#0A2C45",
          800: "#0E3A5A",
          700: "#14496E",
          600: "#1B5A83",
        },
        primary: {
          DEFAULT: "#1C6EA4",
          600: "#17608F",
          700: "#134E74",
        },
        sky: { DEFAULT: "#4FA3D1", soft: "#E9F2F8" },
        ink: {
          DEFAULT: "#16232B",
          muted: "#5B6975",
          subtle: "#8A97A1",
        },
        line: "#E1E6EA",
        surface: {
          DEFAULT: "#FFFFFF",
          muted: "#F1F4F6",
          sunken: "#F7F9FA",
        },
        success: { DEFAULT: "#2E7D4F", soft: "#E1F0E6" },
        warning: { DEFAULT: "#A9601C", soft: "#FBEEDF" },
        danger: { DEFAULT: "#B42318", soft: "#FCE9E7" },
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        display: ['"Poppins"', '"Inter"', "system-ui", "sans-serif"],
      },
      borderRadius: {
        sm: "4px",
        DEFAULT: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(16,35,43,0.04), 0 1px 3px rgba(16,35,43,0.06)",
        raised: "0 4px 12px rgba(16,35,43,0.08), 0 2px 4px rgba(16,35,43,0.05)",
        overlay: "0 16px 48px rgba(10,44,69,0.18)",
      },
      letterSpacing: {
        label: "0.08em",
      },
      maxWidth: {
        shell: "1180px",
      },
    },
  },
  plugins: [],
} satisfies Config;
