/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "./ui/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    screens: {
      md: "480px",
      lg: "1020px",
      xl: "1280px",
    },
    extend: {
      colors: {
        // Semantic colors mapped to CSS variables
        background: "var(--background)",
        foreground: "var(--foreground)",
        muted: "var(--muted)",
        "muted-foreground": "var(--muted-foreground)",
        border: "var(--border)",
        primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
        success: "var(--success)",
        error: "var(--error)",
        warning: "var(--warning)",
        card: "var(--card)",

        // Passport App design system colors
        "passport-black": "#000000",
        "passport-gray": {
          50: "#F9FAFB",
          100: "#F3F4F6",
          200: "#E5E7EB",
          300: "#D1D5DB",
          400: "#9CA3AF",
          500: "#6B7280",
          600: "#4B5563",
          700: "#374151",
          800: "#1F2937",
          900: "#111827",
        },
        "passport-mint": "#10B981",

        // Legacy colors for gradual migration
        purple: {
          softpurple: "#6B7280",
          gitcoinpurple: "#000000",
          darkpurple: "#111827",
        },
        yellow: "#FFF8DB",
        green: {
          jade: "#10B981",
        },
        blue: {
          darkblue: "#111827",
        },
        gray: {
          lightgray: "#E5E7EB",
          purplegray: "#6B7280",
          bluegray: "#F3F4F6",
          extralightgray: "#F9FAFB",
        },
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'card-hover': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        'modal': '0 25px 50px -12px rgb(0 0 0 / 0.25)',
      },
      borderRadius: {
        'card': '12px',
        'modal': '16px',
        'button': '12px',
      },
    },
    fontSize: {
      xs: ["12px", "1.5em"],
      sm: ["14px", "1.5em"],
      base: ["16px", "1.5em"],
      lg: ["18px", "1.5em"],
      xl: ["20px", "1.5em"],
      "2xl": ["24px", "1.5em"],
      "3xl": ["30px", "1.5em"],
      "4xl": ["36px", "1.5em"],
      "5xl": ["48px", "1.5em"],
    },
    fontFamily: {
      sans: ["Inter", "system-ui", "sans-serif"],
      heading: ["Inter", "system-ui", "sans-serif"],
      // Legacy font families - now pointing to Inter
      miriamlibre: ["Inter", "system-ui", "sans-serif"],
      librefranklin: ["Inter", "system-ui", "sans-serif"],
      body: ["Inter", "system-ui", "sans-serif"],
    },
    minHeight: {
      default: "100vh",
    },
  },
  plugins: [],
};
