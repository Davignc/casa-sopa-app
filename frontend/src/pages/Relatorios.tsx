import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { DollarSign, Download, Loader2, Percent, ShoppingBag, ClipboardList } from 'lucide-react'
import { useMemo, useState } from 'react'
import { FiltroPeriodo, periodoInicial, type ValorPeriodo } from '../components/FiltroPeriodo'
import { CORES, GraficoRanking, GraficoRosca, GraficoSerie } from '../components/graficos'
import { Abas, Botao, Carregando, COR_DO_GRAFICO, ErroConsulta, Kpi, Pagina_, useAvisos } from '../components/ui'
import { api, baixar, salvarBlob } from '../lib/api'
import { dataDoDia, formaPagamento, moeda, numero, STATUS_ROTULO } from '../lib/format'
import type { Analise, Pagina, StatusPedido, Usuario } from '../lib/types'

type Medida = 'quantidade' | 'valor'

function Cartao({ titulo, aside, children, className = '' }: { titulo: string; aside?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`cartao p-5 ${className}`} aria-label={titulo}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><h2 className="font-display text-base font-semibold text-slate-800">{titulo}</h2>{aside}</div>
      {children}
    </section>
  )
}

export default function Relatorios() {
  const avisos = useAvisos()
  const [periodo, setPeriodo] = useState<ValorPeriodo>(periodoInicial('30'))
  const [vendedora, setVendedora] = useState('')
  const [cargo, setCargo] = useState('')
  const [agrupar, setAgrupar] = useState('')
  const [medida, setMedida] = useState<Medida>('quantidade')
  const [exportando, setExportando] = useState<'xlsx' | 'csv' | null>(null)

  const filtros = { data_inicio: periodo.inicio, data_fim: periodo.fim, id_vendedora: vendedora || undefined, cargo: cargo || undefined, agrupar: agrupar || undefined }
  const vendedoras = useQuery({ queryKey: ['usuarios-relatorio', cargo], queryFn: async () => {
    const usuarios: Usuario[] = []
    let offset = 0
    while (true) {
      const pagina = await api<Pagina<Usuario>>('/usuarios', { query: { cargo: cargo || undefined, limit: 100, offset } })
      usuarios.push(...pagina.itens)
      offset += pagina.itens.length
      if (!pagina.itens.length || offset >= pagina.total) return usuarios
    }
  } })
  // placeholderData: ao mudar um filtro os gráficos antigos ficam na tela até os novos chegarem.
  const q = useQuery({ queryKey: ['analise', filtros], queryFn: () => api<Analise>('/relatorios/analise', { query: filtros }), placeholderData: keepPreviousData })

  const a = q.data
  const produtos = useMemo(() => {
    const itens = [...(a?.top_produtos ?? [])]
    if (medida === 'valor') itens.sort((x, y) => numero(y.valor) - numero(x.valor))
    return itens.map((i) => ({ nome: i.nome, valor: medida === 'valor' ? numero(i.valor) : i.quantidade }))
  }, [a, medida])

  async function exportar(formato: 'xlsx' | 'csv') {
    setExportando(formato)
    try {
      const { blob, nome } = await baixar('/relatorios/vendas/exportar', { formato, ...filtros, agrupar: undefined })
      salvarBlob(blob, nome)
    } catch (e) {
      avisos.erro(e)
    } finally {
      setExportando(null)
    }
  }

  return (
    <Pagina_ titulo="Relatórios e gráficos"
      acoes={<>
        <Botao variante="secundario" icone={exportando === 'xlsx' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} disabled={exportando !== null} onClick={() => void exportar('xlsx')}>Exportar Excel</Botao>
        <Botao variante="secundario" icone={exportando === 'csv' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} disabled={exportando !== null} onClick={() => void exportar('csv')}>Exportar CSV</Botao>
      </>}>
      <div className="cartao space-y-3 p-4">
        <FiltroPeriodo valor={periodo} onChange={setPeriodo} />
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-xs text-slate-500">Perfil de usuário
            <select className="campo mt-1 h-10 w-52" value={cargo} onChange={(e) => { setCargo(e.target.value); setVendedora('') }}>
              <option value="">Todos os usuários</option><option value="vendedora">Só vendedoras</option><option value="administradora">Só administradoras</option>
            </select>
          </label>
          <label className="text-xs text-slate-500">Responsável
            <select className="campo mt-1 h-10 w-52" value={vendedora} onChange={(e) => setVendedora(e.target.value)}>
              <option value="">Todas</option>
              {vendedoras.data?.map((v) => <option key={v.id_usuario} value={v.id_usuario}>{v.nome} · {v.cargo === 'administradora' ? 'Administradora' : 'Vendedora'}{v.is_ativo ? '' : ' (inativa)'}</option>)}
            </select>
          </label>
          <label className="text-xs text-slate-500">Agrupar por
            <select className="campo mt-1 h-10 w-40" value={agrupar} onChange={(e) => setAgrupar(e.target.value)}>
              <option value="">Automático</option><option value="dia">Dia</option><option value="semana">Semana</option><option value="mes">Mês</option>
            </select>
          </label>
          {q.isFetching && <span role="status" className="flex items-center gap-2 pb-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" aria-hidden />Atualizando…</span>}
          {a && !q.isFetching && <span className="pb-2 text-sm text-slate-500">{dataDoDia(a.periodo.inicio)} a {dataDoDia(a.periodo.fim)} · por {a.agrupamento === 'mes' ? 'mês' : a.agrupamento}</span>}
        </div>
      </div>

      {q.isLoading ? <Carregando /> : q.isError && !a ? <ErroConsulta erro={q.error} onTentar={() => void q.refetch()} /> : a && (
        <div className={q.isFetching ? 'opacity-70 transition-opacity' : 'transition-opacity'}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi titulo="Faturamento" valor={moeda(a.totais.valor_total)} icone={<DollarSign className="h-6 w-6" />} destaque="verde" />
            <Kpi titulo="Pedidos" valor={a.totais.quantidade_pedidos} icone={<ClipboardList className="h-6 w-6" />} detalhe="Confirmados e entregues" />
            <Kpi titulo="Produtos vendidos" valor={a.totais.produtos_vendidos} icone={<ShoppingBag className="h-6 w-6" />} destaque="roxo" />
            <Kpi titulo="Comissões a receber" valor={moeda(a.totais.comissao_a_receber)} icone={<Percent className="h-6 w-6" />} destaque="ambar" detalhe={`+ ${moeda(a.totais.comissao_pendente)} pendentes`} />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <Cartao titulo="Vendas ao longo do tempo" className="lg:col-span-2"><GraficoSerie dados={a.serie} agrupamento={a.agrupamento} /></Cartao>
            <Cartao titulo="Situação dos pedidos">
              <GraficoRosca dados={(Object.keys(STATUS_ROTULO) as StatusPedido[]).map((s) => ({ nome: STATUS_ROTULO[s], valor: a.pedidos_por_status[s], cor: COR_DO_GRAFICO[s] }))} />
            </Cartao>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <Cartao titulo="Vendas por forma de pagamento"><GraficoRosca formato={moeda} dados={a.por_forma_pagamento.map((f) => ({ nome: formaPagamento(f.nome), valor: numero(f.valor) }))} /></Cartao>
            <Cartao titulo="Vendas por responsável"><GraficoRanking cor={CORES.roxo} dados={a.por_vendedora.map((v) => ({ nome: v.nome, valor: numero(v.valor_total) }))} /></Cartao>
            <Cartao titulo="Produtos mais vendidos" aside={<Abas<Medida> itens={[{ id: 'quantidade', rotulo: 'Unidades' }, { id: 'valor', rotulo: 'Valor' }]} valor={medida} onMudar={setMedida} />}>
              <GraficoRanking dados={produtos} formato={medida === 'valor' ? moeda : (v) => `${v} un.`} rotuloSerie={medida === 'valor' ? 'Valor' : 'Unidades'} cor={CORES.verde} />
            </Cartao>
            <Cartao titulo="Clientes que mais compram"><GraficoRanking cor={CORES.ceu} dados={a.top_clientes.map((c) => ({ nome: c.nome, valor: numero(c.valor) }))} /></Cartao>
            <Cartao titulo="Vendas por bairro de entrega" className="lg:col-span-2"><GraficoRanking cor={CORES.ambar} dados={a.por_bairro.map((b) => ({ nome: b.nome, valor: numero(b.valor) }))} /></Cartao>
          </div>

          <Cartao titulo="Vendas e comissões por responsável" className="mt-4">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50"><tr><th className="th">Responsável</th><th className="th text-right">%</th><th className="th text-right">Pedidos</th><th className="th text-right">Produtos</th><th className="th text-right">Vendido</th><th className="th text-right">A receber</th><th className="th text-right">Pendente</th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {a.por_vendedora.length === 0 && <tr><td colSpan={7} className="td py-6 text-center text-slate-400">Sem vendas neste período.</td></tr>}
                  {a.por_vendedora.map((v) => (
                    <tr key={v.id_usuario}>
                      <td className="td font-medium">{v.nome}<span className="block text-xs text-slate-500">{v.cargo === 'administradora' ? 'Administradora' : 'Vendedora'}</span></td><td className="td text-right">{v.comissao_percentual ? `${numero(v.comissao_percentual)}%` : '—'}</td>
                      <td className="td text-right">{v.quantidade_pedidos}</td><td className="td text-right">{v.produtos_vendidos}</td><td className="td text-right">{moeda(v.valor_total)}</td>
                      <td className="td text-right font-semibold text-emerald-700">{moeda(v.comissao_a_receber)}</td><td className="td text-right text-amber-700">{moeda(v.comissao_pendente)}</td>
                    </tr>
                  ))}
                </tbody>
                {a.por_vendedora.length > 0 && <tfoot><tr className="bg-slate-50 font-semibold"><td className="td">Total</td><td className="td" /><td className="td text-right">{a.totais.quantidade_pedidos}</td><td className="td text-right">{a.totais.produtos_vendidos}</td><td className="td text-right">{moeda(a.totais.valor_total)}</td><td className="td text-right text-emerald-700">{moeda(a.totais.comissao_a_receber)}</td><td className="td text-right text-amber-700">{moeda(a.totais.comissao_pendente)}</td></tr></tfoot>}
              </table>
            </div>
            <p className="mt-3 text-xs text-slate-500">Conta pedidos confirmados e entregues, pela data da venda. Comissão = valor × percentual atual da vendedora: “a receber” sobre os entregues, “pendente” sobre os confirmados. Pedidos em aberto e cancelados não entram.</p>
          </Cartao>
        </div>
      )}
    </Pagina_>
  )
}
