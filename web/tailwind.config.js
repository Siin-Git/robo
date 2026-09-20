/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        surface: "var(--surface)",
        "surface-subtle": "var(--surface-subtle)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        "text-primary": "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-muted": "var(--text-muted)",
        brand: "var(--brand)",
        "brand-hover": "var(--brand-hover)",
        "brand-soft": "var(--brand-soft)",
        positive: "var(--positive)",
        "positive-soft": "var(--positive-soft)",
        negative: "var(--negative)",
        "negative-soft": "var(--negative-soft)",
        warning: "var(--warning)",
        "warning-soft": "var(--warning-soft)",
      },
      borderRadius: {
        card: "var(--radius-card)",
        control: "var(--radius-control)",
      },
      fontFamily: {
        sans: ["Pretendard", "Inter", "Noto Sans KR", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
