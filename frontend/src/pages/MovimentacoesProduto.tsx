import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ArrowDownToLine, ArrowLeft, ArrowUpFromLine, Scale } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { FiltroPeriodo, periodoInicial, type ValorPeriodo } from '../components/FiltroPeriodo'
import { GraficoMovimentacoes } from '../components/graficos'
import { Abas, Alerta, Botao, Carregando, Chip, ErroConsulta, Kpi, Pagina_, Paginacao, Vazio } from '../components/ui'
import { api } from '../lib/api'
import { dataHora, dataDoDia } from '../lib/format'
import type { Movimentacao, Pagina, Produto, ResumoMovimentacoes } from '../lib/types'
import { FormMovimento } from './Produtos'

const POR_PAGINA = 20
type Tipo = 'todas' | 'entrada' | 'saida'

function origem(m: Movimentacao) {
  if (m.tipo_referencia === 'venda') return m.id_venda ? <Link className="text-brand-700 underline" to={`/pedidos/${m.id_venda}/editar`}>Pedido #{m.id_venda}</Link> : 'Venda'
  return m.tipo_referencia === 'compra' ? 'Compra / recebimento' : 'Ajuste manual'
}

export default function MovimentacoesProduto() {
  const { id } = useParams()
  const idProduto = Number(id)
  const [periodo, setPeriodo] = useState<ValorPeriodo>(periodoInicial('30'))
  const [tipo, setTipo] = useState<Tipo>('todas')
  const [offset, setOffset] = useState(0)
  const [mov, setMov] = useState<'entrada' | 'saida' | null>(null)

  const produto = useQuery({ queryKey: ['produto', idProduto], queryFn: () => api<Produto>(`/produtos/${idProduto}`), enabled: Number.isInteger(idProduto) && idProduto > 0 })
  const filtros = { id_produto: idProduto, data_inicio: periodo.inicio, data_fim: periodo.fim }
  const resumo = useQuery({
    queryKey: ['resumo-movimentacoes', filtros],
    queryFn: () => api<ResumoMovimentacoes>('/estoque/movimentacoes/resumo', { query: filtros }),
    placeholderData: keepPreviousData,
    enabled: !!produto.data,
  })
  const lista = useQuery({
    queryKey: ['movimentacoes', filtros, tipo, offset],
    queryFn: () => api<Pagina<Movimentacao>>('/estoque/movimentacoes', { query: { ...filtros, tipo: tipo === 'todas' ? undefined : tipo, limit: POR_PAGINA, offset } }),
    placeholderData: keepPreviousData,
    enabled: !!produto.data,
  })

  if (produto.isLoading) return <Carregando />
  if (produto.isError || !produto.data) return <ErroConsulta erro={produto.error} onTentar={() => void produto.refetch()} />
  const p = produto.data
  const r = resumo.data

  return (
    <Pagina_ titulo={`Movimentações: ${p.nome}`}
      acoes={<>
        <Link to="/produtos" className="inline-flex h-11 items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 hover:bg-slate-50"><ArrowLeft className="h-4 w-4" aria-hidden />Voltar</Link>
        {p.is_ativo && <Botao variante="sucesso" icone={<ArrowDownToLine className="h-4 w-4" />} onClick={() => setMov('entrada')}>Entrada</Botao>}
        {p.is_ativo && <Botao variante="perigo" icone={<ArrowUpFromLine className="h-4 w-4" />} onClick={() => setMov('saida')}>Saída</Botao>}
      </>}>
      <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
        <span>Em estoque agora: <b className="text-slate-900">{p.estoque_atual}</b></span><span aria-hidden>·</span>
        <span>Mínimo: <b className="text-slate-900">{p.estoque_minimo}</b></span>
        {p.alerta_estoque_baixo && <Chip cor="ambar">Estoque baixo</Chip>}
        {!p.is_ativo && <Chip cor="vermelho">Inativo</Chip>}
      </div>

      <div className="cartao p-4">
        <FiltroPeriodo valor={periodo} onChange={(v) => { setPeriodo(v); setOffset(0) }} />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi titulo="Entradas no período" valor={r?.total_entradas ?? '—'} icone={<ArrowDownToLine className="h-6 w-6" />} destaque="verde" detalhe={r ? `${dataDoDia(r.periodo_inicio)} a ${dataDoDia(r.periodo_fim)}` : undefined} />
        <Kpi titulo="Saídas no período" valor={r?.total_saidas ?? '—'} icone={<ArrowUpFromLine className="h-6 w-6" />} destaque="ambar" />
        <Kpi titulo="Saldo do período" valor={r ? `${r.saldo_do_periodo > 0 ? '+' : ''}${r.saldo_do_periodo}` : '—'} icone={<Scale className="h-6 w-6" />} detalhe="Entradas menos saídas" />
      </div>

      <section className="cartao p-5" aria-label="Gráfico de movimentações">
        <h2 className="mb-3 font-display text-base font-semibold text-slate-800">Entradas e saídas {r && <span className="text-sm font-normal text-slate-500">por {r.agrupamento === 'mes' ? 'mês' : r.agrupamento}</span>}</h2>
        {resumo.isError ? <ErroConsulta erro={resumo.error} /> : r ? <GraficoMovimentacoes serie={r.serie} agrupamento={r.agrupamento} /> : <Carregando />}
      </section>

      <section className="cartao overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 p-4">
          <h2 className="font-display text-base font-semibold text-slate-800">Histórico</h2>
          <Abas<Tipo> itens={[{ id: 'todas', rotulo: 'Todas' }, { id: 'entrada', rotulo: 'Entradas' }, { id: 'saida', rotulo: 'Saídas' }]} valor={tipo} onMudar={(t) => { setTipo(t); setOffset(0) }} />
        </div>
        {lista.isLoading ? <Carregando /> : lista.isError ? <ErroConsulta erro={lista.error} onTentar={() => void lista.refetch()} /> : lista.data && lista.data.itens.length === 0 ? (
          <Vazio titulo="Nenhuma movimentação neste filtro">Mude o período ou o tipo.</Vazio>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50"><tr><th className="th">Data</th><th className="th">Tipo</th><th className="th text-right">Quantidade</th><th className="th">Origem</th><th className="th">Observação</th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {lista.data?.itens.map((m) => (
                    <tr key={m.id_movimentacao}>
                      <td className="td whitespace-nowrap">{dataHora(m.data_movimentacao)}</td>
                      <td className="td"><Chip cor={m.tipo_movimentacao === 'entrada' ? 'verde' : 'vermelho'}>{m.tipo_movimentacao === 'entrada' ? 'Entrada' : 'Saída'}</Chip></td>
                      <td className={`td text-right font-semibold ${m.tipo_movimentacao === 'entrada' ? 'text-emerald-600' : 'text-rose-600'}`}>{m.tipo_movimentacao === 'entrada' ? '+' : '−'}{m.quantidade}</td>
                      <td className="td">{origem(m)}</td>
                      <td className="td text-slate-500">{m.observacao ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {lista.data && <Paginacao pagina={lista.data} onMudar={setOffset} rotulo="movimentações" />}
          </>
        )}
      </section>
      {!p.is_ativo && <Alerta tipo="info">Este produto está inativo: não recebe novas movimentações, mas o histórico continua disponível.</Alerta>}
      {mov && <FormMovimento tipo={mov} produto={p} onFechar={() => setMov(null)} />}
    </Pagina_>
  )
}
