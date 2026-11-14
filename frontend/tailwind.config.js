/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: '#1C2620',   // main background - warm stockroom charcoal
          light: '#28332C',     // surface / cards
          lighter: '#3A463D',   // borders / dividers
        },
        paper: '#F3EFE3',        // primary text - warm off-white
        muted: '#9CA79B',         // secondary text
        amber: {
          DEFAULT: '#E8A33D',    // primary accent - price-tag gold
          dark: '#C9862A',
        },
        sage: '#8FB573',          // full / ok status
        rust: {
          DEFAULT: '#D1654A',    // critical / out-of-stock
          dark: '#8B3A28',
        },
        sand: '#D9CBB3',          // low-stock amber-tan
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['"Inter"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
    },
  },
  plugins: [],
}
