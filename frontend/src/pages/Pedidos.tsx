import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock, ClipboardList, Pencil, Plus, Printer, Search, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ClienteSelect } from '../components/ClienteSelect'
import { CupomModal } from '../components/CupomModal'
import { HistoricoCliente } from '../components/HistoricoCliente'
import { Abas, Alerta, Botao, Carregando, ChipStatus, Confirmar, ErroConsulta, Modal, Pagina_, Paginacao, Vazio, cn, useAvisos } from '../components/ui'
import { api } from '../lib/api'
import { useAuth } from '../lib/auth'
import { podeAlterarPedido } from '../lib/permissoes'
import { dataHora, formaPagamento, moeda, STATUS_ROTULO, TRANSICOES } from '../lib/format'
import { useDebounce } from '../lib/hooks'
import type { ClienteResumo, ContagemPedidos, Pagina, Pedido, StatusPedido } from '../lib/types'

const POR_PAGINA = 20
type Aba = 'todos' | StatusPedido

export function useInvalidarPedidos() {
  const q = useQueryClient()
  return () => {
    for (const chave of ['pedidos', 'pedidos-contagem', 'produtos', 'alertas-estoque', 'movimentacoes', 'resumo-movimentacoes', 'historico-cliente', 'pedido'])
      void q.invalidateQueries({ queryKey: [chave] })
  }
}

function textoDaConfirmacao(p: Pedido, novo: StatusPedido) {
  const itens = p.itens.length === 1 ? '1 produto' : `${p.itens.length} produtos`
  if (novo === 'confirmado') return <>O estoque de <b>{itens}</b> será baixado agora. Se faltar algum, o sistema avisa e nada é alterado.</>
  if (novo === 'entregue') return <>Marcar o pedido como entregue. Depois disso ele não pode mais ser alterado nem cancelado.</>
  return p.status === 'confirmado'
    ? <>O pedido será cancelado e o estoque de <b>{itens}</b> volta para a prateleira. Pedido cancelado não pode ser reaberto.</>
    : <>O pedido será cancelado. Pedido cancelado não pode ser reaberto.</>
}

export default function Pedidos() {
  const { usuario } = useAuth()
  const avisos = useAvisos()
  const navigate = useNavigate()
  const invalidar = useInvalidarPedidos()
  const [busca, setBusca] = useState('')
  const [de, setDe] = useState('')
  const [ate, setAte] = useState('')
  const [aba, setAba] = useState<Aba>('todos')
  const [offset, setOffset] = useState(0)
  const [sel, setSel] = useState<number | null>(null)
  const [mudar, setMudar] = useState<{ pedido: Pedido; novo: StatusPedido } | null>(null)
  const [excluir, setExcluir] = useState<Pedido | null>(null)
  const [imprimir, setImprimir] = useState<Pedido | null>(null)
  const [historico, setHistorico] = useState(false)
  const [clienteHistorico, setClienteHistorico] = useState<ClienteResumo | null>(null)
  const termo = useDebounce(busca.trim(), 300)

  const periodoInvalido = !!de && !!ate && de > ate
  const filtros = { busca: termo, data_inicio: de, data_fim: ate }
  const lista = useQuery({
    queryKey: ['pedidos', filtros, aba, offset],
    queryFn: () => api<Pagina<Pedido>>('/pedidos', { query: { ...filtros, status: aba === 'todos' ? undefined : aba, limit: POR_PAGINA, offset } }),
    placeholderData: keepPreviousData,
    enabled: !periodoInvalido,
  })
  const contagem = useQuery({
    queryKey: ['pedidos-contagem', filtros],
    queryFn: () => api<ContagemPedidos>('/pedidos/contagem', { query: filtros }),
    placeholderData: keepPreviousData,
    enabled: !periodoInvalido,
  })

  const trocar = useMutation({
    mutationFn: ({ pedido, novo }: { pedido: Pedido; novo: StatusPedido }) => api<Pedido>(`/pedidos/${pedido.id_pedido}/status`, { body: { status: novo } }),
    onSuccess: (p) => { invalidar(); avisos.sucesso(`Pedido #${p.id_pedido}: ${STATUS_ROTULO[p.status].toLowerCase()}.`); setMudar(null) },
    onError: (e) => { avisos.erro(e); setMudar(null) },
  })
  const apagar = useMutation({
    mutationFn: (p: Pedido) => api(`/pedidos/${p.id_pedido}`, { method: 'DELETE' }),
    onSuccess: () => { invalidar(); avisos.sucesso('Pedido excluído.'); setExcluir(null); setSel(null) },
    onError: (e) => { avisos.erro(e); setExcluir(null) },
  })

  const pedidos = lista.data?.itens ?? []
  const selecionado = pedidos.find((p) => p.id_pedido === sel) ?? null
  const abas: { id: Aba; rotulo: string; contagem?: number }[] = [
    { id: 'todos', rotulo: 'Todos', contagem: contagem.data?.todos },
    { id: 'em_aberto', rotulo: 'Em aberto', contagem: contagem.data?.em_aberto },
    { id: 'confirmado', rotulo: 'Confirmado', contagem: contagem.data?.confirmado },
    { id: 'entregue', rotulo: 'Entregue', contagem: contagem.data?.entregue },
    { id: 'cancelado', rotulo: 'Cancelado', contagem: contagem.data?.cancelado },
  ]
  const pode = (s: StatusPedido) => podeAlterarPedido(usuario, selecionado) && selecionado !== null && TRANSICOES[selecionado.status].includes(s)

  return (
    <Pagina_ titulo="Pedidos">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <Link to="/pedidos/novo" className="inline-flex h-11 items-center gap-2 rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-brand-700"><Plus className="h-4 w-4" aria-hidden />Novo pedido</Link>
          <Botao variante="secundario" icone={<Clock className="h-4 w-4" />} onClick={() => setHistorico(true)}>Histórico de compras</Botao>
        </div>
        <div className="flex flex-wrap gap-2" role="toolbar" aria-label="Ações do pedido selecionado">
          <Botao pequeno variante="secundario" icone={<Pencil className="h-4 w-4" />} disabled={!selecionado || !(pode('confirmado') || pode('entregue'))} title="Alterar o pedido selecionado" onClick={() => selecionado && navigate(`/pedidos/${selecionado.id_pedido}/editar`)}>Alterar</Botao>
          <Botao pequeno variante="secundario" icone={<X className="h-4 w-4" />} disabled={!pode('cancelado')} title="Cancelar o pedido selecionado" onClick={() => selecionado && setMudar({ pedido: selecionado, novo: 'cancelado' })}>Cancelar</Botao>
          <Botao pequeno variante="secundario" icone={<Trash2 className="h-4 w-4" />} disabled={!podeAlterarPedido(usuario, selecionado) || selecionado?.status !== 'em_aberto'} title="Excluir (só pedidos em aberto)" onClick={() => selecionado && setExcluir(selecionado)}>Excluir</Botao>
          <Botao pequeno variante="secundario" icone={<Printer className="h-4 w-4" />} disabled={!selecionado || selecionado.status === 'cancelado'} title="Imprimir o cupom" onClick={() => selecionado && setImprimir(selecionado)}>Imprimir</Botao>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input aria-label="Buscar pedidos" className="campo pl-9" placeholder="Buscar por nome do cliente ou nº do pedido…" value={busca} onChange={(e) => { setBusca(e.target.value); setOffset(0) }} />
        </div>
        <label className="flex items-center gap-2 text-xs text-slate-500">De
          <input type="date" className="campo h-11 w-40" aria-label="Data inicial" value={de} max={ate || undefined} onChange={(e) => { setDe(e.target.value); setOffset(0) }} />
        </label>
        <label className="flex items-center gap-2 text-xs text-slate-500">até
          <input type="date" className="campo h-11 w-40" aria-label="Data final" value={ate} min={de || undefined} onChange={(e) => { setAte(e.target.value); setOffset(0) }} />
        </label>
        {(de || ate) && <Botao pequeno variante="fantasma" onClick={() => { setDe(''); setAte(''); setOffset(0) }}>Limpar datas</Botao>}
      </div>
      {periodoInvalido && <Alerta tipo="aviso">A data inicial não pode ser depois da final.</Alerta>}

      <Abas<Aba> itens={abas} valor={aba} onMudar={(a) => { setAba(a); setOffset(0); setSel(null) }} />

      <div className="cartao overflow-hidden">
        {lista.isLoading ? <Carregando /> : lista.isError ? <ErroConsulta erro={lista.error} onTentar={() => void lista.refetch()} /> : pedidos.length === 0 ? (
          <Vazio titulo="Nenhum pedido encontrado" icone={<ClipboardList className="h-10 w-10" />}>{termo || de || ate || aba !== 'todos' ? 'Ajuste os filtros.' : 'Clique em “Novo pedido” para registrar o primeiro.'}</Vazio>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50"><tr>
                  <th className="th">Pedido</th><th className="th">Cliente</th><th className="th">Pagamento</th><th className="th">Data da venda</th>
                  <th className="th">Responsável</th><th className="th">Situação</th><th className="th text-right">Total</th>
                </tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {pedidos.map((p) => {
                    const destinos = podeAlterarPedido(usuario, p) ? TRANSICOES[p.status] : []
                    return (
                      <tr key={p.id_pedido} onClick={() => setSel(sel === p.id_pedido ? null : p.id_pedido)}
                        className={cn('cursor-pointer', sel === p.id_pedido ? 'bg-brand-50' : 'hover:bg-slate-50', p.status === 'cancelado' && 'text-slate-400')}>
                        <td className="td font-semibold"><button type="button" aria-label={`Selecionar pedido ${p.id_pedido}`} aria-pressed={sel === p.id_pedido} className="rounded px-2 py-1 underline underline-offset-4" onClick={(e) => { e.stopPropagation(); setSel(sel === p.id_pedido ? null : p.id_pedido) }}>#{p.id_pedido}</button></td>
                        <td className="td">{p.cliente.nome}</td>
                        <td className="td">{formaPagamento(p.forma_pagamento)}</td>
                        <td className="td whitespace-nowrap">{dataHora(p.data_venda)}</td>
                        <td className="td">{p.vendedora.nome}</td>
                        <td className="td" onClick={(e) => e.stopPropagation()}>
                          {destinos.length === 0 ? <ChipStatus status={p.status} /> : (
                            <select aria-label={`Situação do pedido ${p.id_pedido}`} value={p.status}
                              onChange={(e) => setMudar({ pedido: p, novo: e.target.value as StatusPedido })}
                              className={cn('cursor-pointer rounded-full border-0 py-1 pl-2.5 pr-7 text-xs font-medium focus:ring-2', p.status === 'em_aberto' ? 'bg-amber-100 text-amber-800' : 'bg-sky-100 text-sky-800')}>
                              <option value={p.status}>{STATUS_ROTULO[p.status]}</option>
                              {destinos.map((d) => <option key={d} value={d}>{STATUS_ROTULO[d]}</option>)}
                            </select>
                          )}
                        </td>
                        <td className="td text-right font-semibold">{moeda(p.valor_total)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {lista.data && <Paginacao pagina={lista.data} onMudar={setOffset} rotulo="pedidos" />}
          </>
        )}
      </div>
      <p className="text-xs text-slate-500">Selecione pelo número do pedido ou clicando na linha. Use Tab para navegar e Enter ou Espaço para selecionar. Apenas a responsável pelo pedido e as administradoras podem editar, excluir e mudar a situação.</p>

      <Confirmar aberto={!!mudar} titulo={mudar ? `${mudar.novo === 'cancelado' ? 'Cancelar' : mudar.novo === 'confirmado' ? 'Confirmar' : 'Entregar'} o pedido #${mudar.pedido.id_pedido}?` : ''}
        perigo={mudar?.novo === 'cancelado'} textoConfirmar={mudar?.novo === 'cancelado' ? 'Cancelar pedido' : mudar?.novo === 'confirmado' ? 'Confirmar pedido' : 'Marcar como entregue'}
        carregando={trocar.isPending} onCancelar={() => setMudar(null)} onConfirmar={() => mudar && trocar.mutate(mudar)}
        mensagem={mudar ? textoDaConfirmacao(mudar.pedido, mudar.novo) : null} />
      <Confirmar aberto={!!excluir} titulo={`Excluir o pedido #${excluir?.id_pedido}?`} perigo textoConfirmar="Excluir" carregando={apagar.isPending} onCancelar={() => setExcluir(null)} onConfirmar={() => excluir && apagar.mutate(excluir)}
        mensagem="Use apenas para pedido lançado por engano. Isso apaga o pedido de vez; para manter o registro, cancele em vez de excluir." />
      {imprimir && <CupomModal pedido={imprimir} onFechar={() => setImprimir(null)} />}
      <Modal aberto={historico} onFechar={() => setHistorico(false)} titulo="Histórico de compras" subtitulo="Veja todos os pedidos de um cliente" largura="max-w-3xl">
        <div className="space-y-4">
          <ClienteSelect valor={clienteHistorico} onChange={setClienteHistorico} />
          {clienteHistorico && <HistoricoCliente idCliente={clienteHistorico.id_cliente} />}
        </div>
      </Modal>
    </Pagina_>
  )
}
