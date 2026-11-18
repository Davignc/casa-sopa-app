import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api, getToken, setToken } from './api'
import type { Usuario } from './types'
interface Auth { usuario: Usuario | null; ehAdmin: boolean; carregando: boolean; aviso: string | null; entrar: (email: string, senha: string) => Promise<void>; sair: () => Promise<void> }
const Contexto = createContext<Auth | null>(null)
export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [aviso, setAviso] = useState<string | null>(null)
  const cache = useQueryClient()
  useEffect(() => {
    let ativo = true
    if (getToken()) api<Usuario>('/usuarios/me').then((u) => { if (ativo) setUsuario(u) }).catch(() => { setToken(null) }).finally(() => { if (ativo) setCarregando(false) })
    else setCarregando(false)
    const expirar = () => { setUsuario(null); cache.clear(); setAviso('Sua sessão expirou. Faça login novamente.') }
    window.addEventListener('sessao-expirada', expirar)
    return () => { ativo = false; window.removeEventListener('sessao-expirada', expirar) }
  }, [cache])
  async function entrar(email: string, senha: string) {
    const token = await api<{ access_token: string }>('/auth/login/json', { body: { email, senha } })
    setToken(token.access_token)
    try { const u = await api<Usuario>('/usuarios/me'); cache.clear(); setUsuario(u); setAviso(null) }
    catch (erro) { setToken(null); throw erro }
  }
  async function sair() {
    try { await api('/auth/logout', { method: 'POST' }) }
    finally { setToken(null); cache.clear(); setUsuario(null); setAviso(null) }
  }
  return <Contexto.Provider value={{ usuario, ehAdmin: usuario?.cargo === 'administradora', carregando, aviso, entrar, sair }}>{children}</Contexto.Provider>
}
export function useAuth() { const auth = useContext(Contexto); if (!auth) throw new Error('AuthProvider ausente'); return auth }
