import os
import json

package_json = {
  "name": "training-assessment-system",
  "private": True,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev:frontend": "vite",
    "dev:backend": "tsx watch server/index.ts",
    "dev": "npm run dev:backend & npm run dev:frontend",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview"
  },
  "dependencies": {
    "@hookform/resolvers": "^3.3.4",
    "cors": "^2.8.5",
    "express": "^4.18.2",
    "lucide-react": "^0.330.0",
    "qrcode.react": "^3.1.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-hook-form": "^7.50.1",
    "react-router-dom": "^6.22.0",
    "sqlite": "^5.1.1",
    "sqlite3": "^5.1.7",
    "xlsx": "^0.18.5",
    "zod": "^3.22.4"
  },
  "devDependencies": {
    "@types/cors": "^2.8.17",
    "@types/express": "^4.17.21",
    "@types/node": "^20.11.19",
    "@types/react": "^18.2.56",
    "@types/react-dom": "^18.2.19",
    "@typescript-eslint/eslint-plugin": "^7.0.2",
    "@typescript-eslint/parser": "^7.0.2",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.17",
    "eslint": "^8.56.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.5",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "tsx": "^4.7.1",
    "typescript": "^5.2.2",
    "vite": "^5.1.4"
  }
}

files = {
    'package.json': json.dumps(package_json, indent=2),
    'tsconfig.json': '''{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src", "server"],
  "references": [{ "path": "./tsconfig.node.json" }]
}''',
    'tsconfig.node.json': '''{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}''',
    'vite.config.ts': '''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    },
  },
})''',
    'tailwind.config.js': '''/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        microsoft: {
          blue: '#0078D4',
          gray: '#F3F2F1',
          dark: '#323130'
        }
      }
    },
  },
  plugins: [],
}''',
    'postcss.config.js': '''export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}''',
    'index.html': '''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Microsoft Onsite Training Assessment</title>
  </head>
  <body class="bg-microsoft-gray text-microsoft-dark">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>'''
}

for filepath, content in files.items():
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else '.', exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print('Base files created')
