/** Paleta e tipografia tiradas das telas de referência (azul-marinho + azul royal). */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef3ff', 100: '#dce7ff', 200: '#bfd0ff', 300: '#93adff', 400: '#6283f5',
          500: '#3d5fe3', 600: '#2347c9', 700: '#1c3aa6', 800: '#18318a', 900: '#12297c', 950: '#0b1a55',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'Segoe UI', 'sans-serif'],
        display: ['Poppins', 'Inter', 'system-ui', 'sans-serif'],
      },
      boxShadow: { card: '0 1px 2px rgb(15 23 42 / .04), 0 4px 16px rgb(15 23 42 / .06)' },
    },
  },
  plugins: [],
}
