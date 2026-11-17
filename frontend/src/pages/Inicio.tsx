import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ClipboardList, DollarSign, PackageCheck, Percent, Plus, ShoppingBag, Truck, Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { GraficoRosca, GraficoSerie } from '../components/graficos'
import { Carregando, ChipStatus, Chip, COR_DO_GRAFICO, ErroConsulta, Kpi, Pagina_, Vazio } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { dataHora, dataDoDia, moeda, STATUS_ROTULO } from '../lib/format'
import type { Analise, ContagemPedidos, Dashboard, Pagina, Pedido, Produto, StatusPedido } from '../lib/types'

const ATALHO = 'inline-flex h-11 items-center gap-2 rounded-lg px-4 text-sm font-medium transition-colors'

function EstoqueBaixo() {
  const q = useQuery({ queryKey: ['alertas-estoque'], queryFn: () => api<Produto[]>('/estoque/alertas') })
  return (
    <section className="cartao p-5" aria-label="Estoque baixo">
      <h2 className="mb-3 flex items-center gap-2 font-display text-base font-semibold text-slate-800"><AlertTriangle className="h-5 w-5 text-amber-500" aria-hidden />Estoque baixo</h2>
      {q.isLoading ? <Carregando /> : q.isError ? <ErroConsulta erro={q.error} /> : q.data?.length === 0 ? (
        <Vazio titulo="Tudo certo por aqui">Nenhum produto no estoque mínimo.</Vazio>
      ) : (
        <ul className="divide-y divide-slate-100">
          {q.data?.slice(0, 6).map((p) => (
            <li key={p.id_produto} className="flex items-center justify-between gap-3 py-2 text-sm">
              <span className="truncate font-medium text-slate-800">{p.nome}</span>
              <span className="shrink-0 text-slate-500">{p.estoque_atual} un. <Chip cor="ambar" className="ml-1">mín. {p.estoque_minimo}</Chip></span>
            </li>
          ))}
        </ul>
      )}
      {(q.data?.length ?? 0) > 6 && <Link to="/produtos" className="mt-2 inline-block text-sm font-medium text-brand-700 underline">Ver todos ({q.data?.length})</Link>}
    </section>
  )
}

function UltimosPedidos() {
  const q = useQuery({ queryKey: ['pedidos', 'ultimos'], queryFn: () => api<Pagina<Pedido>>('/pedidos', { query: { limit: 5 } }) })
  return (
    <section className="cartao p-5" aria-label="Últimos pedidos">
      <div className="mb-3 flex items-center justify-between"><h2 className="font-display text-base font-semibold text-slate-800">Últimos pedidos</h2><Link to="/pedidos" className="text-sm font-medium text-brand-700 underline">Ver todos</Link></div>
      {q.isLoading ? <Carregando /> : q.isError ? <ErroConsulta erro={q.error} /> : q.data?.itens.length === 0 ? (
        <Vazio titulo="Nenhum pedido ainda" />
      ) : (
        <ul className="divide-y divide-slate-100">
          {q.data?.itens.map((p) => (
            <li key={p.id_pedido} className="flex items-center gap-3 py-2.5 text-sm">
              <span className="w-10 font-semibold text-slate-500">#{p.id_pedido}</span>
              <span className="min-w-0 flex-1"><span className="block truncate font-medium text-slate-800">{p.cliente.nome}</span><span className="text-xs text-slate-500">{dataHora(p.data_venda)}</span></span>
              <ChipStatus status={p.status} />
              <span className="w-24 text-right font-semibold">{moeda(p.valor_total)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

function PainelAdmin() {
  const resumo = useQuery({ queryKey: ['dashboard'], queryFn: () => api<Dashboard>('/relatorios/dashboard') })
  const analise = useQuery({ queryKey: ['analise-inicio'], queryFn: () => api<Analise>('/relatorios/analise') })
  const d = resumo.data
  return (
    <>
      {resumo.isError && <ErroConsulta erro={resumo.error} onTentar={() => void resumo.refetch()} />}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi titulo="Faturamento (30 dias)" valor={d ? moeda(d.faturamento) : '—'} icone={<DollarSign className="h-6 w-6" />} destaque="verde" detalhe={d ? `${dataDoDia(d.periodo.inicio)} a ${dataDoDia(d.periodo.fim)}` : undefined} />
        <Kpi titulo="Pedidos vendidos" valor={d?.total_pedidos ?? '—'} icone={<ClipboardList className="h-6 w-6" />} detalhe="Confirmados e entregues" />
        <Kpi titulo="Produtos vendidos" valor={d?.produtos_vendidos ?? '—'} icone={<ShoppingBag className="h-6 w-6" />} destaque="roxo" />
        <Kpi titulo="Comissões a receber" valor={d ? moeda(d.comissoes) : '—'} icone={<Percent className="h-6 w-6" />} destaque="ambar" detalhe={d ? `+ ${moeda(d.comissoes_pendentes)} em pedidos ainda não entregues` : undefined} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <section className="cartao p-5 lg:col-span-2" aria-label="Vendas dos últimos 30 dias">
          <div className="mb-3 flex items-center justify-between"><h2 className="font-display text-base font-semibold text-slate-800">Vendas dos últimos 30 dias</h2><Link to="/relatorios" className="text-sm font-medium text-brand-700 underline">Análise completa</Link></div>
          {analise.isLoading ? <Carregando /> : analise.isError ? <ErroConsulta erro={analise.error} /> : analise.data && <GraficoSerie dados={analise.data.serie} agrupamento={analise.data.agrupamento} />}
        </section>
        <section className="cartao p-5" aria-label="Situação dos pedidos">
          <h2 className="mb-3 font-display text-base font-semibold text-slate-800">Situação dos pedidos</h2>
          {analise.data ? <GraficoRosca dados={(Object.keys(STATUS_ROTULO) as StatusPedido[]).map((s) => ({ nome: STATUS_ROTULO[s], valor: analise.data.pedidos_por_status[s], cor: COR_DO_GRAFICO[s] }))} /> : <Carregando />}
        </section>
      </div>
    </>
  )
}

function PainelVendedora() {
  const c = useQuery({ queryKey: ['pedidos-contagem', 'inicio'], queryFn: () => api<ContagemPedidos>('/pedidos/contagem') })
  return (
    <>
      <div className="flex flex-wrap gap-3">
        <Link to="/pedidos/novo" className={`${ATALHO} bg-brand-600 text-white shadow-sm hover:bg-brand-700`}><Plus className="h-4 w-4" aria-hidden />Novo pedido</Link>
        <Link to="/clientes" className={`${ATALHO} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`}><Users className="h-4 w-4" aria-hidden />Clientes</Link>
        <Link to="/produtos" className={`${ATALHO} border border-slate-300 bg-white text-slate-700 hover:bg-slate-50`}><PackageCheck className="h-4 w-4" aria-hidden />Produtos</Link>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi titulo="Pedidos em aberto" valor={c.data?.em_aberto ?? '—'} icone={<ClipboardList className="h-6 w-6" />} destaque="ambar" detalhe="Aguardando confirmação" />
        <Kpi titulo="Confirmados" valor={c.data?.confirmado ?? '—'} icone={<Truck className="h-6 w-6" />} destaque="azul" detalhe="Aguardando entrega" />
        <Kpi titulo="Entregues" valor={c.data?.entregue ?? '—'} icone={<PackageCheck className="h-6 w-6" />} destaque="verde" />
      </div>
    </>
  )
}

export default function Inicio() {
  const { usuario, ehAdmin } = useAuth()
  const primeiro = usuario?.nome.split(' ')[0] ?? ''
  return (
    <Pagina_ titulo={`Olá, ${primeiro}!`}>
      {ehAdmin ? <PainelAdmin /> : <PainelVendedora />}
      <div className="grid gap-4 lg:grid-cols-2"><UltimosPedidos /><EstoqueBaixo /></div>
    </Pagina_>
  )
}
