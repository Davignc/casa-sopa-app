import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { dataHora, formaPagamento, moeda, numero } from '../lib/format'
import type { Pagina, Pedido } from '../lib/types'
import { Carregando, ChipStatus, ErroConsulta, Vazio } from './ui'

/** Compras de um cliente (botão "Histórico de compras"). */
export function HistoricoCliente({ idCliente }: { idCliente: number }) {
  const q = useQuery({
    queryKey: ['historico-cliente', idCliente],
    queryFn: () => api<Pagina<Pedido>>('/pedidos', { query: { id_cliente: idCliente, limit: 50 } }),
  })
  if (q.isLoading) return <Carregando />
  if (q.isError) return <ErroConsulta erro={q.error} onTentar={() => void q.refetch()} />
  const pedidos = q.data?.itens ?? []
  if (pedidos.length === 0) return <Vazio titulo="Este cliente ainda não fez pedidos." />

  const validos = pedidos.filter((p) => p.status === 'confirmado' || p.status === 'entregue')
  const gasto = validos.reduce((s, p) => s + numero(p.valor_total), 0)
  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-600">
        <b>{q.data?.total}</b> {q.data?.total === 1 ? 'pedido' : 'pedidos'} · total em compras confirmadas e entregues: <b>{moeda(gasto)}</b>
        {(q.data?.total ?? 0) > pedidos.length && <span className="text-slate-400"> (mostrando os {pedidos.length} mais recentes)</span>}
      </p>
      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full">
          <thead className="bg-slate-50"><tr><th className="th">Pedido</th><th className="th">Data</th><th className="th">Pagamento</th><th className="th">Situação</th><th className="th text-right">Total</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {pedidos.map((p) => (
              <tr key={p.id_pedido} className={p.status === 'cancelado' ? 'text-slate-400' : ''}>
                <td className="td font-medium"><Link className="text-brand-700 underline" to={`/pedidos/${p.id_pedido}/editar`}>#{p.id_pedido}</Link></td>
                <td className="td">{dataHora(p.data_venda)}</td>
                <td className="td">{formaPagamento(p.forma_pagamento)}</td>
                <td className="td"><ChipStatus status={p.status} /></td>
                <td className="td text-right font-medium">{moeda(p.valor_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
