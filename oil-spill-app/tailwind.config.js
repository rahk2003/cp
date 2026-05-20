/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        navy: {
          DEFAULT: "#0B1E3F",
          50: "#E7EBF2",
          100: "#C5CDDD",
          200: "#8A9DBA",
          300: "#506C97",
          400: "#1F3866",
          500: "#0B1E3F",
          600: "#091933",
          700: "#061327",
          800: "#040D1B",
          900: "#02060D",
        },
        teal: {
          DEFAULT: "#0FA4A4",
          50: "#E0F7F7",
          100: "#B3EBEB",
          200: "#80DEDE",
          300: "#4DD0D0",
          400: "#1AC3C3",
          500: "#0FA4A4",
          600: "#0C8484",
          700: "#096363",
          800: "#064343",
          900: "#032222",
        },
        ocean: {
          50: "#F0F7FB",
          100: "#D9EAF2",
          200: "#B3D5E5",
          300: "#8DC0D8",
          400: "#67ACCB",
          500: "#4097BE",
          600: "#337998",
          700: "#265B72",
          800: "#1A3C4C",
          900: "#0D1E26",
        },
      },
      fontFamily: {
        display: ["Manrope", "Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        arabic: ["Cairo", "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "monospace"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pulse-slow": {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.5s ease-out forwards",
        "pulse-slow": "pulse-slow 3s ease-in-out infinite",
        shimmer: "shimmer 3s linear infinite",
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(to right, rgba(11, 30, 63, 0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(11, 30, 63, 0.04) 1px, transparent 1px)",
        "noise":
          "url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.4'/%3E%3C/svg%3E\")",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
