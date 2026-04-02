/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        accent: {
          DEFAULT: '#8b5cf6',
          hover: '#7c3aed',
        },
      },
    },
  },
  plugins: [],
}
