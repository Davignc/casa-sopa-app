import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/poppins/600.css'
import '@fontsource/poppins/700.css'
import './index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { LogoProvider } from './components/Logo'
import { AvisosProvider } from './components/ui'
import { ApiError } from './lib/api'
import { AuthProvider } from './lib/auth'
import { aplicarTema } from './components/Tema'

aplicarTema()

const cliente = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      // Erros 4xx (permissão, validação) não melhoram tentando de novo.
      retry: (tentativas, erro) => !(erro instanceof ApiError && erro.status < 500 && erro.status !== 0) && tentativas < 2,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={cliente}>
      <LogoProvider>
        <AvisosProvider>
          <AuthProvider>
            <App />
          </AuthProvider>
        </AvisosProvider>
      </LogoProvider>
    </QueryClientProvider>
  </StrictMode>,
)
