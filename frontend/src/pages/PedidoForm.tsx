import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, MapPin, Plus, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { AddressPicker } from '../components/AddressPicker'
import { ClienteSelect } from '../components/ClienteSelect'
import { Alerta, Botao, Campo, Carregando, ChipStatus, ErroConsulta, Pagina_, cn, useAvisos } from '../components/ui'
import { api, mensagemDeErro } from '../lib/api'
import { useAuth } from '../lib/auth'
import { podeAlterarPedido } from '../lib/permissoes'
import { focarErros } from '../lib/acessibilidade'
import { Privacidade } from '../components/Privacidade'
import { FORMAS_PAGAMENTO, moeda } from '../lib/format'
import type { Cliente, ClienteResumo, EnderecoDoCliente, Pagina, Pedido, Produto } from '../lib/types'
import { useInvalidarPedidos } from './Pedidos'

interface Linha {
  id_produto: number
  nome: string
  quantidade: number
}

const centavos = (preco: string) => Math.round(Number(preco) * 100)

/** Mesma conta do servidor: preço do cadastro × quantidade, em centavos (sem erro de arredondamento). */
export function totalEmCentavos(linhas: Linha[], precoDe: (id: number) => string | undefined): number {
  return linhas.reduce((soma, l) => soma + centavos(precoDe(l.id_produto) ?? '0') * l.quantidade, 0)
}

export default function PedidoForm() {
  const { usuario } = useAuth()
  const { id } = useParams()
  const editando = id !== undefined
  const navigate = useNavigate()
  const avisos = useAvisos()
  const invalidar = useInvalidarPedidos()

  const pedido = useQuery({ queryKey: ['pedido', id], queryFn: () => api<Pedido>(`/pedidos/${id}`), enabled: editando })
  const produtos = useQuery({ queryKey: ['produtos-pedido'], queryFn: () => api<Pagina<Produto>>('/produtos', { query: { limit: 100 } }) })

  const [cliente, setCliente] = useState<ClienteResumo | null>(null)
  const [idEndereco, setIdEndereco] = useState<number | null>(null)
  const [outroEndereco, setOutroEndereco] = useState(false)
  const [novoEndereco, setNovoEndereco] = useState<EnderecoDoCliente | null>(null)
  const [linhas, setLinhas] = useState<Linha[]>([])
  const [produtoSel, setProdutoSel] = useState('')
  const [qtd, setQtd] = useState('1')
  const [forma, setForma] = useState<string>(FORMAS_PAGAMENTO[0])
  const [obs, setObs] = useState('')
  const [tentou, setTentou] = useState(false)
  const [falha, setFalha] = useState<string | null>(null)
  const [carregado, setCarregado] = useState(false)

  // Edição: preenche o formulário uma vez com o pedido existente.
  useEffect(() => {
    const p = pedido.data
    if (!p || carregado) return
    setCliente({ id_cliente: p.cliente.id_cliente, nome: p.cliente.nome, telefone: p.cliente.telefone, is_ativo: true, endereco_principal: null, cadastrado_por: p.vendedora })
    setIdEndereco(p.endereco_entrega.id_endereco)
    setLinhas(p.itens.map((i) => ({ id_produto: i.id_produto, nome: i.nome_produto, quantidade: i.quantidade })))
    setForma(FORMAS_PAGAMENTO.find((f) => f.toLowerCase() === p.forma_pagamento.toLowerCase()) ?? p.forma_pagamento)
    setObs(p.observacao ?? '')
    setCarregado(true)
  }, [pedido.data, carregado])

  const detalhe = useQuery({ queryKey: ['cliente', cliente?.id_cliente], queryFn: () => api<Cliente>(`/clientes/${cliente?.id_cliente}`), enabled: !!cliente })
  const enderecos = detalhe.data?.enderecos ?? []

  // Novo pedido: já deixa o endereço principal escolhido.
  useEffect(() => {
    if (editando || !detalhe.data || idEndereco !== null) return
    const e = detalhe.data.enderecos.find((x) => x.principal) ?? detalhe.data.enderecos[0]
    if (e) setIdEndereco(e.id_endereco)
    else setOutroEndereco(true)
  }, [detalhe.data, editando, idEndereco])

  const status = pedido.data?.status
  const somenteLeitura = editando && (status === 'entregue' || status === 'cancelado')
  const travaClienteEItens = editando && status === 'confirmado'

  const catalogo = useMemo(() => new Map((produtos.data?.itens ?? []).map((p) => [p.id_produto, p])), [produtos.data])
  const precoDe = (idProduto: number) => catalogo.get(idProduto)?.preco_unitario ?? pedido.data?.itens.find((i) => i.id_produto === idProduto)?.preco_unitario
  const disponiveis = (produtos.data?.itens ?? []).filter((p) => !linhas.some((l) => l.id_produto === p.id_produto))
  const total = totalEmCentavos(linhas, precoDe)

  function adicionar() {
    const p = catalogo.get(Number(produtoSel))
    const n = Number(qtd)
    if (!p || !Number.isInteger(n) || n < 1) return
    setLinhas([...linhas, { id_produto: p.id_produto, nome: p.nome, quantidade: n }])
    setProdutoSel('')
    setQtd('1')
  }

  const erros = {
    cliente: cliente ? null : 'Escolha o cliente.',
    endereco: outroEndereco ? (novoEndereco ? null : 'Complete o novo endereço.') : idEndereco !== null ? null : 'Escolha o endereço de entrega.',
    itens: linhas.length > 0 ? null : 'Adicione ao menos um produto.',
    obs: obs.length > 255 ? 'No máximo 255 caracteres.' : null,
  }
  const ver = <K extends keyof typeof erros>(k: K) => (tentou ? erros[k] : null)

  const salvar = useMutation({
    mutationFn: async () => {
      if (editando && !podeAlterarPedido(usuario, pedido.data)) throw new Error('Você não tem permissão para alterar este pedido.')
      if (!cliente) throw new Error('Escolha o cliente.')
      // 1) Se o endereço é novo ou veio da busca, liga ao cliente antes de usar.
      let destino = idEndereco
      if (outroEndereco && novoEndereco) {
        const antes = new Set(enderecos.map((e) => e.id_endereco))
        const atualizado = await api<Cliente>(`/clientes/${cliente.id_cliente}/enderecos`, { body: { ...novoEndereco, principal: false } })
        destino = 'id_endereco' in novoEndereco ? novoEndereco.id_endereco : (atualizado.enderecos.find((e) => !antes.has(e.id_endereco))?.id_endereco ?? null)
      }
      if (destino === null) throw new Error('Não foi possível identificar o endereço de entrega.')

      const itens = linhas.map((l) => ({ id_produto: l.id_produto, quantidade: l.quantidade }))
      if (!editando) return api<Pedido>('/pedidos', { body: { id_cliente: cliente.id_cliente, id_endereco: destino, forma_pagamento: forma, itens, observacao: obs.trim() || undefined } })

      // 2) Edição: envia só o que mudou.
      const original = pedido.data
      if (!original) throw new Error('Pedido não carregado.')
      const mudou: Record<string, unknown> = {}
      if (forma.toLowerCase() !== original.forma_pagamento.toLowerCase()) mudou.forma_pagamento = forma
      if ((obs.trim() || null) !== (original.observacao ?? null)) mudou.observacao = obs.trim() || null
      if (destino !== original.endereco_entrega.id_endereco) mudou.id_endereco = destino
      if (!travaClienteEItens) {
        if (cliente.id_cliente !== original.cliente.id_cliente) { mudou.id_cliente = cliente.id_cliente; mudou.id_endereco = destino }
        const antes = JSON.stringify([...original.itens].sort((a, b) => a.id_produto - b.id_produto).map((i) => [i.id_produto, i.quantidade]))
        const depois = JSON.stringify([...itens].sort((a, b) => a.id_produto - b.id_produto).map((i) => [i.id_produto, i.quantidade]))
        if (antes !== depois) mudou.itens = itens
      }
      if (Object.keys(mudou).length === 0) return original
      return api<Pedido>(`/pedidos/${original.id_pedido}`, { method: 'PATCH', body: mudou })
    },
    onSuccess: (p) => {
      invalidar()
      avisos.sucesso(editando ? `Pedido #${p.id_pedido} atualizado.` : `Pedido #${p.id_pedido} registrado.`)
      navigate('/pedidos')
    },
    onError: (e) => setFalha(mensagemDeErro(e)),
  })

  function enviar() {
    setTentou(true)
    setFalha(null)
    if (Object.values(erros).some(Boolean)) return
    salvar.mutate()
  }

  if (editando && pedido.isLoading) return <Carregando />
  if (editando && (pedido.isError || !pedido.data)) return <ErroConsulta erro={pedido.error} onTentar={() => void pedido.refetch()} />
  if (editando && !podeAlterarPedido(usuario, pedido.data)) return <Pagina_ titulo="Pedido com acesso restrito"><Alerta tipo="aviso">Somente a responsável pelo pedido ou uma administradora pode alterá-lo.</Alerta><Botao onClick={() => navigate('/pedidos')}>Voltar aos pedidos</Botao></Pagina_>

  return (
    <Pagina_ titulo={editando ? `Editar pedido #${id}` : 'Novo pedido'}
      acoes={<Botao variante="secundario" icone={<ArrowLeft className="h-4 w-4" />} onClick={() => navigate('/pedidos')}>Voltar</Botao>}>
      <form onSubmit={(e) => { e.preventDefault(); focarErros(e.currentTarget); enviar() }} noValidate className="cartao max-w-3xl space-y-6 p-6">
        <Privacidade contexto="pedido" />
        {editando && status && (
          <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">Situação: <ChipStatus status={status} /></div>
        )}
        {somenteLeitura && <Alerta tipo="info">Pedido {status === 'entregue' ? 'entregue' : 'cancelado'} não pode mais ser alterado. Você ainda pode imprimir o cupom na lista de pedidos.</Alerta>}
        {travaClienteEItens && <Alerta tipo="info">Pedido confirmado (o estoque já foi baixado): só dá para mudar forma de pagamento, endereço e observação. Para mudar produtos, cancele e refaça o pedido.</Alerta>}
        {falha && <Alerta tipo="erro">{falha}</Alerta>}

        <fieldset disabled={somenteLeitura} className="space-y-6">
          <ClienteSelect valor={cliente} onChange={(c) => { setCliente(c); setIdEndereco(null); setOutroEndereco(false); setNovoEndereco(null) }} erro={ver('cliente')} desabilitado={somenteLeitura || travaClienteEItens} />

          {cliente && (
            <section aria-label="Endereço de entrega" className="space-y-3">
              <h2 className="text-sm font-medium text-slate-700">Endereço de entrega <span className="text-rose-500">*</span></h2>
              {detalhe.isLoading && <p className="text-sm text-slate-500">Carregando endereços…</p>}
              {enderecos.length > 0 && (
                <ul className="space-y-2">
                  {enderecos.map((e) => (
                    <li key={e.id_endereco}>
                      <label className={cn('flex cursor-pointer items-start gap-3 rounded-xl border p-3', !outroEndereco && idEndereco === e.id_endereco ? 'border-brand-500 bg-brand-50' : 'border-slate-200 hover:bg-slate-50')}>
                        <input type="radio" name="endereco" className="mt-1" checked={!outroEndereco && idEndereco === e.id_endereco} onChange={() => { setIdEndereco(e.id_endereco); setOutroEndereco(false) }} />
                        <span className="min-w-0 flex-1 text-sm">
                          <span className="block font-medium text-slate-900">{e.endereco_formatado}</span>
                          <span className="text-xs text-slate-500">{[e.principal && 'Principal', e.apelido, e.referencia && `Ref.: ${e.referencia}`].filter(Boolean).join(' · ')}</span>
                        </span>
                        <MapPin className="h-4 w-4 shrink-0 text-slate-300" aria-hidden />
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              {editando && !enderecos.some((e) => e.id_endereco === idEndereco) && idEndereco !== null && !outroEndereco && pedido.data && (
                <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">Endereço atual: {pedido.data.endereco_entrega.endereco_formatado}</p>
              )}
              {!outroEndereco ? (
                <Botao variante="fantasma" pequeno icone={<Plus className="h-4 w-4" />} onClick={() => { setOutroEndereco(true); setIdEndereco(null) }}>Usar outro endereço (buscar um registrado ou cadastrar novo)</Botao>
              ) : (
                <div className="space-y-3 rounded-xl border border-slate-200 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-700">Outro endereço para este pedido</p>
                    {enderecos.length > 0 && <button type="button" className="text-sm text-slate-500 underline" onClick={() => { setOutroEndereco(false); setNovoEndereco(null); setIdEndereco(enderecos.find((e) => e.principal)?.id_endereco ?? enderecos[0]?.id_endereco ?? null) }}>Voltar aos endereços do cliente</button>}
                  </div>
                  <AddressPicker jaVinculados={enderecos.map((e) => e.id_endereco)} onChange={setNovoEndereco} mostrarErros={tentou} />
                  <p className="text-xs text-slate-500">Ao salvar o pedido, este endereço também fica guardado no cadastro do cliente.</p>
                </div>
              )}
              {ver('endereco') && <p role="alert" className="text-xs text-rose-600">{ver('endereco')}</p>}
            </section>
          )}

          {!travaClienteEItens && (
            <section aria-label="Produtos" className="space-y-3 rounded-xl bg-slate-50 p-4">
              <h2 className="text-sm font-semibold text-slate-800">Adicionar produto</h2>
              <div className="flex flex-wrap items-end gap-3">
                <Campo rotulo="Produto" className="min-w-56 flex-1">
                  {(p) => (
                    <select {...p} className="campo" value={produtoSel} onChange={(e) => setProdutoSel(e.target.value)}>
                      <option value="">Selecionar produto…</option>
                      {disponiveis.map((x) => <option key={x.id_produto} value={x.id_produto}>{x.nome} · {moeda(x.preco_unitario)} · estoque {x.estoque_atual}</option>)}
                    </select>
                  )}
                </Campo>
                <Campo rotulo="Qtd." className="w-24">{(p) => <input {...p} className="campo" type="number" min={1} max={100000} value={qtd} onChange={(e) => setQtd(e.target.value)} />}</Campo>
                <Botao variante="secundario" icone={<Plus className="h-4 w-4" />} disabled={!produtoSel || !Number.isInteger(Number(qtd)) || Number(qtd) < 1} onClick={adicionar}>Adicionar item</Botao>
              </div>
              {(produtos.data?.total ?? 0) > 100 && <p className="text-xs text-amber-700">Mostrando os 100 primeiros produtos ativos. Use a busca em Produtos para localizar os demais.</p>}
            </section>
          )}

          <section aria-label="Itens do pedido">
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full">
                <thead className="bg-slate-50"><tr><th className="th">Produto</th><th className="th text-center">Qtd.</th><th className="th text-right">Valor</th><th className="th"><span className="sr-only">Remover</span></th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {linhas.length === 0 && <tr><td colSpan={4} className="td py-6 text-center text-slate-400">Nenhum item adicionado.</td></tr>}
                  {linhas.map((l) => {
                    const p = catalogo.get(l.id_produto)
                    const falta = p && l.quantidade > p.estoque_atual
                    return (
                      <tr key={l.id_produto}>
                        <td className="td">{l.nome}{falta && <span className="ml-2 inline-flex items-center gap-1 text-xs text-amber-700"><AlertTriangle className="h-3.5 w-3.5" aria-hidden />estoque atual: {p.estoque_atual}</span>}</td>
                        <td className="td text-center">{l.quantidade}</td>
                        <td className="td text-right font-medium">{moeda((centavos(precoDe(l.id_produto) ?? '0') * l.quantidade) / 100)}</td>
                        <td className="td text-right">{!travaClienteEItens && <button type="button" aria-label={`Remover ${l.nome}`} onClick={() => setLinhas(linhas.filter((x) => x.id_produto !== l.id_produto))} className="rounded p-1.5 text-rose-500 hover:bg-rose-50"><X className="h-4 w-4" /></button>}</td>
                      </tr>
                    )
                  })}
                </tbody>
                <tfoot><tr className="bg-slate-50"><td className="td font-semibold" colSpan={2}>Total estimado</td><td className="td text-right font-display text-lg font-semibold text-brand-800">{moeda(total / 100)}</td><td /></tr></tfoot>
              </table>
            </div>
            {ver('itens') && <p role="alert" className="mt-1 text-xs text-rose-600">{ver('itens')}</p>}
            <p className="mt-1 text-xs text-slate-500">O valor final é calculado pelo sistema com o preço atual de cada produto. {linhas.some((l) => { const p = catalogo.get(l.id_produto); return p && l.quantidade > p.estoque_atual }) && 'Produtos acima do estoque: o pedido pode ser salvo, mas só será confirmado quando houver estoque.'}</p>
          </section>

          <div className="grid gap-4 sm:grid-cols-2">
            <Campo rotulo="Forma de pagamento" obrigatorio>
              {(p) => (
                <select {...p} className="campo" value={forma} onChange={(e) => setForma(e.target.value)}>
                  {!FORMAS_PAGAMENTO.some((f) => f === forma) && <option>{forma}</option>}
                  {FORMAS_PAGAMENTO.map((f) => <option key={f}>{f}</option>)}
                </select>
              )}
            </Campo>
            <Campo rotulo="Observação" erro={ver('obs')}>{(p) => <input {...p} className={cn('campo', ver('obs') && 'campo-erro')} maxLength={255} placeholder="Opcional" value={obs} onChange={(e) => setObs(e.target.value)} />}</Campo>
          </div>
        </fieldset>

        {!somenteLeitura && (
          <div className="flex justify-end gap-3 border-t border-slate-100 pt-5">
            <Botao variante="secundario" onClick={() => navigate('/pedidos')}>Cancelar</Botao>
            <Botao type="submit" carregando={salvar.isPending}>{editando ? 'Salvar alterações' : 'Registrar pedido'}</Botao>
          </div>
        )}
      </form>
    </Pagina_>
  )
}
