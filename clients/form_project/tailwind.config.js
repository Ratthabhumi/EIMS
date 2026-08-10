/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          blue: '#0078D4',
          gray: '#F3F2F1',
          dark: '#323130'
        }
      }
    },
  },
  plugins: [],
}