/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // GreenOps brand palette
        brand: {
          50:  '#edfdf4',
          100: '#d3f9e4',
          200: '#aaf2cb',
          300: '#6ee7aa',
          400: '#34d578',
          500: '#10be5c',
          600: '#069a49',
          700: '#05793b',
          800: '#076030',
          900: '#074f29',
          950: '#032c16',
        },
        surface: {
          50:  '#f8faf8',
          100: '#f0f4f0',
          200: '#e1eae1',
          300: '#c9d9c9',
          400: '#a8c0a8',
          500: '#87a587',
          600: '#6a8a6a',
          700: '#557055',
          800: '#455b45',
          900: '#3a4c3a',
          950: '#1e281e',
        },
        dark: {
          50:  '#f4f7f4',
          100: '#e5eae5',
          200: '#cdd7cd',
          300: '#aabdaa',
          400: '#7f9a7f',
          500: '#5f7d5f',
          600: '#4b644b',
          700: '#3d523d',
          800: '#344434',
          900: '#2c392c',
          950: '#151e15',
          bg:  '#0d1210',
          card: '#131a12',
          border: '#1e2a1e',
          muted: '#243124',
        },
      },
      fontFamily: {
        sans: ['DM Sans', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        display: ['Syne', 'DM Sans', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'counter': 'counter 1.5s ease-out',
        'shimmer': 'shimmer 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      backdropBlur: {
        xs: '2px',
      },
      boxShadow: {
        'glow': '0 0 20px rgba(16, 190, 92, 0.15)',
        'glow-lg': '0 0 40px rgba(16, 190, 92, 0.2)',
        'card': '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.6)',
        'card-hover': '0 8px 25px rgba(0,0,0,0.5)',
      },
    },
  },
  plugins: [],
}
