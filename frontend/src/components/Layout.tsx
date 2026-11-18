import { useQuery } from '@tanstack/react-query'
import { BarChart3, Boxes, ClipboardList, Home, LogOut, Menu, Settings, Users, UserCog, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useDialogo } from '../lib/acessibilidade'
import { Tema } from './Tema'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { inicial } from '../lib/format'
import type { Produto, StatusBackup } from '../lib/types'
import { Logo } from './Logo'
import { Alerta, Botao, Chip, cn } from './ui'

interface Item { para: string; rotulo: string; icone: ReactNode; admin?: boolean; fim?: boolean; selo?: number }

function Menu_({ itens, aoNavegar }: { itens: Item[]; aoNavegar: () => void }) {
  return (
    <nav aria-label="Principal" className="flex-1 space-y-1 px-3 py-4">
      {itens.map((i) => (
        <NavLink key={i.para} to={i.para} end={i.fim} onClick={aoNavegar}
          className={({ isActive }) => cn('flex items-center gap-3 rounded-xl px-3 py-2.5 text-[15px] font-medium transition-colors', isActive ? 'bg-white/15 text-white' : 'text-white/75 hover:bg-white/10 hover:text-white')}>
          <span aria-hidden>{i.icone}</span>
          <span className="flex-1">{i.rotulo}</span>
          {i.admin && <span className="rounded bg-violet-700 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-white">Admin</span>}
          {!!i.selo && <span aria-label={`${i.selo} com estoque baixo`} className="rounded-full bg-amber-400 px-2 py-0.5 text-xs font-bold text-amber-950">{i.selo}</span>}
        </NavLink>
      ))}
    </nav>
  )
}

export function Layout() {
  const { usuario, ehAdmin, sair } = useAuth()
  const [aberto, setAberto] = useState(false)
  const local = useLocation()
  const menu = useRef<HTMLElement>(null)
  useDialogo(aberto, menu, () => setAberto(false))
  useEffect(() => { document.getElementById('conteudo-principal')?.focus() }, [local.pathname])
  useEffect(() => {
    const media = window.matchMedia?.('(min-width: 1024px)')
    const fechar = () => { if (media?.matches) setAberto(false) }
    media?.addEventListener('change', fechar)
    return () => media?.removeEventListener('change', fechar)
  }, [])

  // RF23: o alerta de estoque baixo fica sempre visível no menu.
  const alertas = useQuery({ queryKey: ['alertas-estoque'], queryFn: () => api<Produto[]>('/estoque/alertas'), refetchInterval: 60_000 })
  // RNF03: falha ou ausência de backup precisa chamar a atenção da administradora.
  const backup = useQuery({ queryKey: ['backup'], queryFn: () => api<StatusBackup>('/sistema/backup'), enabled: ehAdmin, refetchInterval: 300_000 })

  const itens: Item[] = [
    { para: '/', rotulo: 'Início', icone: <Home className="h-5 w-5" />, fim: true },
    { para: '/clientes', rotulo: 'Clientes', icone: <Users className="h-5 w-5" /> },
    { para: '/pedidos', rotulo: 'Pedidos', icone: <ClipboardList className="h-5 w-5" /> },
    { para: '/produtos', rotulo: 'Produtos', icone: <Boxes className="h-5 w-5" />, selo: alertas.data?.length },
    ...(ehAdmin
      ? [
          { para: '/relatorios', rotulo: 'Relatórios', icone: <BarChart3 className="h-5 w-5" />, admin: true },
          { para: '/usuarios', rotulo: 'Usuários', icone: <UserCog className="h-5 w-5" />, admin: true },
          { para: '/configuracoes', rotulo: 'Configurações', icone: <Settings className="h-5 w-5" />, admin: true },
        ]
      : []),
  ]

  const barra = (
    <div className="flex h-full flex-col bg-gradient-to-b from-brand-900 to-brand-950">
      <div className="flex items-center gap-3 border-b border-white/10 px-5 py-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-full bg-white p-1"><Logo className="h-full w-full" alt="" /></span>
        <div className="leading-tight">
          <p className="font-display text-base font-semibold text-white">Casa da Sopa</p>
          <p className="text-sm text-brand-200">de Restinga</p>
        </div>
      </div>
      <Menu_ itens={itens} aoNavegar={() => setAberto(false)} />
      <div className="border-t border-white/10 p-3">
        <button type="button" onClick={() => void sair()} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-white/75 hover:bg-white/10 hover:text-white">
          <LogOut className="h-5 w-5" aria-hidden /> Sair / Logout
        </button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen lg:pl-64">
      <a href="#conteudo-principal" onClick={(e) => { e.preventDefault(); document.getElementById('conteudo-principal')?.focus() }} className="pular-conteudo">Pular para o conteúdo</a>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">{barra}</aside>
      {aberto && createPortal(
        <div data-dialogo className="fixed inset-0 z-40">
          <div className="absolute inset-0 bg-slate-900/60" onClick={() => setAberto(false)} aria-hidden />
          <aside ref={menu} role="dialog" tabIndex={-1} aria-modal="true" aria-label="Menu principal" id="menu-movel" className="absolute inset-y-0 left-0 w-72 max-w-[85vw]">
            {barra}
            <button type="button" aria-label="Fechar menu" onClick={() => setAberto(false)} className="absolute right-3 top-4 rounded-lg p-1.5 text-white/80 hover:bg-white/10"><X className="h-5 w-5" /></button>
          </aside>
        </div>, document.body
      )}

      <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-6">
        <button type="button" aria-label="Abrir menu" aria-expanded={aberto} aria-controls={aberto ? 'menu-movel' : undefined} onClick={() => setAberto(true)} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"><Menu className="h-6 w-6" /></button>
        <span className="hidden lg:block" />
        <div className="flex items-center gap-3">
          <Tema />
          <div className="text-right leading-tight">
            <p className="text-sm font-semibold text-slate-800">{usuario?.nome}</p>
            <Chip cor={ehAdmin ? 'roxo' : 'azul'} className="mt-0.5 !py-0.5 text-[11px]">{ehAdmin ? 'Administradora' : 'Vendedora'}</Chip>
          </div>
          <span aria-hidden className="flex h-10 w-10 items-center justify-center rounded-full bg-pink-600 font-semibold text-white">{inicial(usuario?.nome ?? '')}</span>
          <Botao variante="secundario" pequeno icone={<LogOut className="h-4 w-4" />} onClick={() => void sair()}>Sair</Botao>
        </div>
      </header>

      <main id="conteudo-principal" tabIndex={-1} className="mx-auto max-w-[1400px] space-y-4 px-4 py-6 sm:px-6" key={local.pathname.split('/')[1]}>
        {ehAdmin && backup.data?.alerta && (
          <Alerta tipo="aviso" titulo="Atenção ao backup do banco de dados">
            {backup.data.motivo_alerta}{' '}
            <NavLink to="/configuracoes" className="font-semibold underline">Abrir configurações</NavLink>
          </Alerta>
        )}
        <Outlet />
      </main>
    </div>
  )
}
