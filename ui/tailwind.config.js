/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        studio: {
          bg: '#0F0F0F',
          panel: '#161616',
          card: '#121212',
          border: '#262626',
          borderLight: '#333333',
          hover: '#1F1F1F',
          text: '#E5E5E5',
          textMuted: '#999999',
          textDim: '#555555',
          accent: '#3B82F6',
          gold: '#F59E0B',
          emerald: '#10B981',
          crimson: '#EF4444'
        }
      },
      borderRadius: {
        none: '0px',
        sm: '2px',
        DEFAULT: '2px',
        md: '2px',
        lg: '2px',
        xl: '2px',
        '2xl': '2px',
        full: '2px',
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Display"', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
      }
    },
  },
  plugins: [],
};

