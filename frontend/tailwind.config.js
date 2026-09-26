/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        paper: '#FBF8F1',
        leaf: { DEFAULT: '#1F5C3A', dark: '#154029', light: '#E3EFE6' },
        amber: { warn: '#B45309', soft: '#FEF3C7' },
        ink: '#1F2933',
      },
      fontSize: { base: ['1.0625rem', '1.6'] },
    },
  },
  plugins: [],
}
