import { lazy, Suspense, type ReactNode } from 'react'
import { HashRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Carregando } from './components/ui'
import { useAuth } from './lib/auth'
import Login from './pages/Login'
import NaoEncontrada from './pages/NaoEncontrada'
import Recuperacao from './pages/Recuperacao'

// Carregadas sob demanda: o login abre rápido, sem baixar os gráficos.
const Inicio = lazy(() => import('./pages/Inicio'))
const Clientes = lazy(() => import('./pages/Clientes'))
const Pedidos = lazy(() => import('./pages/Pedidos'))
const PedidoForm = lazy(() => import('./pages/PedidoForm'))
const Produtos = lazy(() => import('./pages/Produtos'))
const MovimentacoesProduto = lazy(() => import('./pages/MovimentacoesProduto'))
const Relatorios = lazy(() => import('./pages/Relatorios'))
const Usuarios = lazy(() => import('./pages/Usuarios'))
const Configuracoes = lazy(() => import('./pages/Configuracoes'))
const Importacoes = lazy(() => import('./pages/Importacoes'))

/** Só a administradora. O servidor também confere: isto só evita mostrar telas sem acesso. */
export function SoAdmin({ children }: { children: ReactNode }) {
  const { ehAdmin } = useAuth()
  return ehAdmin ? <>{children}</> : <NaoEncontrada restrita />
}

export function Rotas() {
  const { usuario, carregando } = useAuth()
  const local = useLocation()
  if (local.pathname === '/redefinir-senha') return <Recuperacao />
  if (carregando) return <Carregando texto="Entrando…" className="min-h-screen" />
  if (!usuario) return <Login />
  return (
    <Suspense fallback={<Carregando />}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Inicio />} />
          <Route path="clientes" element={<Clientes />} />
          <Route path="pedidos" element={<Pedidos />} />
          <Route path="pedidos/novo" element={<PedidoForm />} />
          <Route path="pedidos/:id/editar" element={<PedidoForm />} />
          <Route path="produtos" element={<Produtos />} />
          <Route path="produtos/:id/movimentacoes" element={<SoAdmin><MovimentacoesProduto /></SoAdmin>} />
          <Route path="relatorios" element={<SoAdmin><Relatorios /></SoAdmin>} />
          <Route path="importacoes" element={<SoAdmin><Importacoes /></SoAdmin>} />
          <Route path="usuarios" element={<SoAdmin><Usuarios /></SoAdmin>} />
          <Route path="configuracoes" element={<SoAdmin><Configuracoes /></SoAdmin>} />
          <Route path="login" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NaoEncontrada />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <HashRouter>
      <Rotas />
    </HashRouter>
  )
}
