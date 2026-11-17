import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, waitFor, type RenderResult } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'
import { LogoProvider } from '../components/Logo'
import { AvisosProvider } from '../components/ui'
import { setToken } from '../lib/api'
import { AuthProvider, useAuth } from '../lib/auth'
import type { Usuario } from '../lib/types'

export interface Chamada {
  metodo: string
  caminho: string
  query: URLSearchParams
  corpo: unknown
  form?: FormData
  headers: Headers
}
interface Resposta {
  status?: number
  body?: unknown
  headers?: Record<string, string>
  /** Resposta que não é JSON (PDF, planilha). */
  texto?: string
}
type Rota = Resposta | ((c: Chamada) => Resposta | Promise<Resposta>)

let usuarioLogado: Usuario | null = null

const escapar = (t: string) => t.replace(/[.+?^${}()|[\]\\]/g, '\\$&')

/** Troca o fetch por um servidor falso. Rotas: "GET /clientes", "GET /clientes/*" (curinga de 1 trecho). */
export function mockApi(rotas: Record<string, Rota>) {
  const chamadas: Chamada[] = []
  // Por padrão, /usuarios/me responde com quem está logado no teste (ou 401 se ninguém estiver).
  const todas: Record<string, Rota> = { 'GET /usuarios/me': () => (usuarioLogado ? { body: usuarioLogado } : { status: 401, body: { detail: 'Faça login para continuar.' } }), ...rotas }
  const exatas = new Map(Object.entries(todas).filter(([k]) => !k.includes('*')))
  const curingas = Object.entries(todas)
    .filter(([k]) => k.includes('*'))
    .map(([k, v]) => [new RegExp(`^${escapar(k).replace(/\\\*/g, '[^/]+')}$`), v] as const)

  vi.spyOn(globalThis, 'fetch').mockImplementation(async (entrada, init) => {
    const url = new URL(String(entrada), 'http://localhost')
    const headers = new Headers(init?.headers)
    const form = init?.body instanceof FormData ? init.body : undefined
    const corpo = typeof init?.body === 'string' ? JSON.parse(init.body) : undefined
    const chamada: Chamada = { metodo: (init?.method ?? 'GET').toUpperCase(), caminho: url.pathname, query: url.searchParams, corpo, form, headers }
    chamadas.push(chamada)
    const chave = `${chamada.metodo} ${chamada.caminho}`
    const rota = exatas.get(chave) ?? curingas.find(([re]) => re.test(chave))?.[1]
    if (!rota) return new Response(JSON.stringify({ detail: `MOCK AUSENTE: ${chave}` }), { status: 599 })
    const r = typeof rota === 'function' ? await rota(chamada) : rota
    const status = r.status ?? 200
    if (r.texto !== undefined) return new Response(r.texto, { status, headers: r.headers })
    const semCorpo = status === 204 || status === 304
    return new Response(semCorpo ? null : JSON.stringify(r.body ?? {}), { status, headers: { 'content-type': 'application/json', ...r.headers } })
  })

  return {
    chamadas,
    de: (metodo: string, caminho: string) => chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho),
    ultima: (metodo: string, caminho: string) => chamadas.filter((c) => c.metodo === metodo && c.caminho === caminho).at(-1),
  }
}

export const ADMIN: Usuario = { id_usuario: 1, nome: 'Ana Administradora', email: 'ana@x.org', telefone: '16988887777', cargo: 'administradora', comissao: null, is_ativo: true }
export const VENDEDORA: Usuario = { id_usuario: 2, nome: 'Maria Vendedora', email: 'maria@x.org', telefone: '16999990001', cargo: 'vendedora', comissao: '10.00', is_ativo: true }

export const comoUsuario = (u: Usuario): Record<string, Rota> => ({ 'GET /usuarios/me': { body: u } })

function Pronto({ children }: { children: ReactElement }) {
  const { carregando } = useAuth()
  return carregando ? <p>autenticando…</p> : children
}

interface Opcoes {
  usuario?: Usuario
  /** Endereço inicial (ex.: "/pedidos/7/editar"). */
  rota?: string
  /** Padrão da rota que contém o elemento (ex.: "/pedidos/:id/editar"). */
  caminho?: string
}

/** Renderiza dentro de todos os provedores, com o usuário já logado (token + /usuarios/me). */
export async function renderizar(ui: ReactElement, { usuario, rota = '/', caminho = '*' }: Opcoes = {}): Promise<RenderResult> {
  usuarioLogado = usuario ?? null
  setToken(usuario ? 'token-de-teste' : null)
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 }, mutations: { retry: false } } })
  const resultado = render(
    <QueryClientProvider client={cliente}>
      <LogoProvider>
        <AvisosProvider>
          <AuthProvider>
            <MemoryRouter initialEntries={[rota]}>
              <Pronto>
                <Routes><Route path={caminho} element={ui} /></Routes>
              </Pronto>
            </MemoryRouter>
          </AuthProvider>
        </AvisosProvider>
      </LogoProvider>
    </QueryClientProvider>,
  )
  await waitFor(() => expect(resultado.queryByText('autenticando…')).not.toBeInTheDocument())
  return resultado
}
