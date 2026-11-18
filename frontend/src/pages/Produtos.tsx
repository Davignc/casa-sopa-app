import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDownToLine, ArrowUpFromLine, Boxes, History, Pencil, Plus, Power, Search } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Alerta, Botao, Campo, Carregando, Chip, Confirmar, ErroConsulta, Interruptor, Modal, Pagina_, Paginacao, Vazio, cn, useAvisos } from '../components/ui'
import { api, mensagemDeErro } from '../lib/api'
import { useAuth } from '../lib/auth'
import { lerPreco, moeda, numero } from '../lib/format'
import { useDebounce } from '../lib/hooks'
import { focarErros } from '../lib/acessibilidade'
import type { MovimentacaoResultado, Pagina, Produto } from '../lib/types'

const POR_PAGINA = 20

export function useInvalidarProdutos() {
  const q = useQueryClient()
  return (id?: number) => {
    for (const chave of ['produtos', 'alertas-estoque', 'movimentacoes', 'resumo-movimentacoes']) void q.invalidateQueries({ queryKey: [chave] })
    if (id) void q.invalidateQueries({ queryKey: ['produto', id] })
  }
}

/* ---------- Cadastro e edição ---------- */

function FormProduto({ produto, onFechar }: { produto: Produto | null; onFechar: () => void }) {
  const avisos = useAvisos()
  const invalidar = useInvalidarProdutos()
  const editando = produto !== null
  const [f, setF] = useState({
    nome: produto?.nome ?? '', descricao: produto?.descricao ?? '',
    preco: produto ? produto.preco_unitario.replace('.', ',') : '', estoque_inicial: '0', estoque_minimo: String(produto?.estoque_minimo ?? '5'),
  })
  const [tentou, setTentou] = useState(false)
  const [falha, setFalha] = useState<string | null>(null)

  const preco = lerPreco(f.preco)
  const erros = {
    nome: f.nome.trim() ? null : 'Informe o nome.',
    descricao: f.descricao.trim() ? null : 'Informe a descrição.',
    preco: preco !== null ? null : 'Informe um preço válido (ex.: 25,90).',
    estoque_inicial: Number.isInteger(Number(f.estoque_inicial)) && Number(f.estoque_inicial) >= 0 ? null : 'Use um número inteiro, 0 ou mais.',
    estoque_minimo: Number.isInteger(Number(f.estoque_minimo)) && Number(f.estoque_minimo) >= 0 && f.estoque_minimo !== '' ? null : 'Use um número inteiro, 0 ou mais.',
  }
  const mostrar = (k: keyof typeof erros) => (tentou ? erros[k] : null)
  const temErro = Object.entries(erros).some(([k, v]) => v && !(editando && k === 'estoque_inicial'))

  const salvar = useMutation({
    mutationFn: () => {
      const comuns = { nome: f.nome.trim(), descricao: f.descricao.trim(), preco_unitario: (preco ?? 0).toFixed(2), estoque_minimo: Number(f.estoque_minimo) }
      return editando
        ? api<Produto>(`/produtos/${produto.id_produto}`, { method: 'PATCH', body: comuns })
        : api<Produto>('/produtos', { body: { ...comuns, estoque_inicial: Number(f.estoque_inicial) } })
    },
    onSuccess: (p) => { invalidar(p.id_produto); avisos.sucesso(editando ? 'Produto atualizado.' : 'Produto cadastrado.'); onFechar() },
    onError: (e) => setFalha(mensagemDeErro(e)),
  })

  function enviar(e: FormEvent) {
    e.preventDefault()
    focarErros(e.currentTarget as HTMLFormElement)
    setTentou(true)
    setFalha(null)
    if (!temErro) salvar.mutate()
  }

  return (
    <Modal aberto onFechar={onFechar} titulo={editando ? 'Editar produto' : '+ Novo produto'}
      rodape={<><Botao variante="secundario" onClick={onFechar}>Cancelar</Botao><Botao type="submit" form="form-produto" carregando={salvar.isPending}>{editando ? 'Salvar' : 'Cadastrar produto'}</Botao></>}>
      <form id="form-produto" onSubmit={enviar} noValidate className="space-y-4">
        {falha && <Alerta tipo="erro">{falha}</Alerta>}
        <Campo rotulo="Nome" obrigatorio erro={mostrar('nome')}>{(p) => <input {...p} className={cn('campo', mostrar('nome') && 'campo-erro')} maxLength={150} placeholder="Rolo saco de lixo 100L c/20" value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />}</Campo>
        <Campo rotulo="Descrição" obrigatorio erro={mostrar('descricao')}>{(p) => <input {...p} className={cn('campo', mostrar('descricao') && 'campo-erro')} maxLength={255} value={f.descricao} onChange={(e) => setF({ ...f, descricao: e.target.value })} />}</Campo>
        <div className="grid gap-4 sm:grid-cols-3">
          <Campo rotulo="Preço (R$)" obrigatorio erro={mostrar('preco')} dica={editando ? 'Vale só para pedidos novos.' : undefined}>{(p) => <input {...p} className={cn('campo', mostrar('preco') && 'campo-erro')} inputMode="decimal" placeholder="0,00" value={f.preco} onChange={(e) => setF({ ...f, preco: e.target.value })} />}</Campo>
          {!editando && <Campo rotulo="Estoque inicial" erro={mostrar('estoque_inicial')}>{(p) => <input {...p} className={cn('campo', mostrar('estoque_inicial') && 'campo-erro')} type="number" min={0} value={f.estoque_inicial} onChange={(e) => setF({ ...f, estoque_inicial: e.target.value })} />}</Campo>}
          <Campo rotulo="Estoque mínimo" obrigatorio erro={mostrar('estoque_minimo')} dica="Avisa quando chegar nesse valor.">{(p) => <input {...p} className={cn('campo', mostrar('estoque_minimo') && 'campo-erro')} type="number" min={0} value={f.estoque_minimo} onChange={(e) => setF({ ...f, estoque_minimo: e.target.value })} />}</Campo>
        </div>
        {editando && <p className="text-xs text-slate-500">A quantidade em estoque muda só por entradas e saídas, para manter o histórico correto.</p>}
      </form>
    </Modal>
  )
}

/* ---------- Entrada e saída de estoque (somente administradora) ---------- */

export function FormMovimento({ tipo, produto, onFechar }: { tipo: 'entrada' | 'saida'; produto: Produto; onFechar: () => void }) {
  const avisos = useAvisos()
  const invalidar = useInvalidarProdutos()
  const entrada = tipo === 'entrada'
  const [qtd, setQtd] = useState('')
  const [origem, setOrigem] = useState<'compra' | 'ajuste_manual'>('compra')
  const [texto, setTexto] = useState('')
  const [tentou, setTentou] = useState(false)

  const n = Number(qtd)
  const valida = Number.isInteger(n) && n >= 1 && n <= 1_000_000
  const faltaEstoque = !entrada && valida && n > produto.estoque_atual
  const erroQtd = tentou ? (!valida ? 'Informe uma quantidade inteira, de 1 em diante.' : faltaEstoque ? `Só há ${produto.estoque_atual} em estoque.` : null) : null
  const erroMotivo = tentou && !entrada && texto.trim().length < 3 ? 'Explique o motivo (mín. 3 letras).' : null

  const salvar = useMutation({
    mutationFn: () =>
      api<MovimentacaoResultado>(entrada ? '/estoque/entradas' : '/estoque/saidas', {
        body: entrada
          ? { id_produto: produto.id_produto, quantidade: n, tipo: origem, observacao: texto.trim() || undefined }
          : { id_produto: produto.id_produto, quantidade: n, motivo: texto.trim() },
      }),
    onSuccess: (r) => { invalidar(produto.id_produto); avisos.sucesso(`${entrada ? 'Entrada' : 'Saída'} registrada. Estoque agora: ${r.produto.estoque_atual}.`); onFechar() },
    onError: avisos.erro,
  })

  function enviar(e: FormEvent) {
    e.preventDefault()
    setTentou(true)
    if (valida && !faltaEstoque && (entrada || texto.trim().length >= 3)) salvar.mutate()
  }
  const depois = valida ? produto.estoque_atual + (entrada ? n : -n) : null

  return (
    <Modal aberto onFechar={onFechar} titulo={entrada ? 'Registrar entrada de estoque' : 'Registrar saída (perda ou ajuste)'} subtitulo={`${produto.nome} · estoque atual: ${produto.estoque_atual}`}
      rodape={<><Botao variante="secundario" onClick={onFechar}>Cancelar</Botao><Botao type="submit" form="form-movimento" carregando={salvar.isPending} variante={entrada ? 'sucesso' : 'perigo'}>{entrada ? 'Registrar entrada' : 'Registrar saída'}</Botao></>}>
      <form id="form-movimento" onSubmit={enviar} noValidate className="space-y-4">
        <Campo rotulo="Quantidade" obrigatorio erro={erroQtd}>{(p) => <input {...p} className={cn('campo', erroQtd && 'campo-erro')} type="number" min={1} value={qtd} onChange={(e) => setQtd(e.target.value)} />}</Campo>
        {entrada && (
          <Campo rotulo="Origem">
            {(p) => <select {...p} className="campo" value={origem} onChange={(e) => setOrigem(e.target.value as typeof origem)}><option value="compra">Compra / recebimento</option><option value="ajuste_manual">Ajuste manual (sobra, contagem)</option></select>}
          </Campo>
        )}
        <Campo rotulo={entrada ? 'Observação' : 'Motivo'} obrigatorio={!entrada} erro={erroMotivo}>
          {(p) => <input {...p} className={cn('campo', erroMotivo && 'campo-erro')} maxLength={150} placeholder={entrada ? 'Ex.: compra do fornecedor X' : 'Ex.: pacote rasgado, doação…'} value={texto} onChange={(e) => setTexto(e.target.value)} />}
        </Campo>
        {depois !== null && !faltaEstoque && <p className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">O estoque ficará com <b className="text-slate-900">{depois}</b> unidades.</p>}
        <p className="text-xs text-slate-500">O seu nome fica registrado junto com a movimentação.</p>
      </form>
    </Modal>
  )
}

/* ---------- Lista ---------- */

const Icone = ({ rotulo, onClick, children, cor = 'text-slate-500 hover:bg-slate-100' }: { rotulo: string; onClick: () => void; children: React.ReactNode; cor?: string }) => (
  <button type="button" aria-label={rotulo} title={rotulo} onClick={(e) => { e.stopPropagation(); onClick() }} className={cn('rounded-lg p-2', cor)}>{children}</button>
)

export default function Produtos() {
  const { ehAdmin } = useAuth()
  const avisos = useAvisos()
  const invalidar = useInvalidarProdutos()
  const [busca, setBusca] = useState('')
  const [soAlerta, setSoAlerta] = useState(false)
  const [inativos, setInativos] = useState(false)
  const [offset, setOffset] = useState(0)
  const [editar, setEditar] = useState<Produto | 'novo' | null>(null)
  const [mov, setMov] = useState<{ tipo: 'entrada' | 'saida'; produto: Produto } | null>(null)
  const [trocar, setTrocar] = useState<Produto | null>(null)
  const termo = useDebounce(busca.trim(), 300)

  const q = useQuery({
    queryKey: ['produtos', termo, soAlerta, inativos, offset],
    queryFn: () => api<Pagina<Produto>>('/produtos', { query: { busca: termo, apenas_alerta: soAlerta, incluir_inativos: inativos, limit: POR_PAGINA, offset } }),
    placeholderData: keepPreviousData,
  })
  const alertas = useQuery({ queryKey: ['alertas-estoque'], queryFn: () => api<Produto[]>('/estoque/alertas') })

  const situacao = useMutation({
    mutationFn: (p: Produto) => (p.is_ativo ? api(`/produtos/${p.id_produto}`, { method: 'DELETE' }) : api(`/produtos/${p.id_produto}/reativar`, { method: 'POST' })),
    onSuccess: (_, p) => { invalidar(p.id_produto); avisos.sucesso(p.is_ativo ? 'Produto inativado.' : 'Produto reativado.'); setTrocar(null) },
    onError: avisos.erro,
  })

  return (
    <Pagina_ titulo="Produtos e estoque" acoes={<Botao icone={<Plus className="h-4 w-4" />} onClick={() => setEditar('novo')}>Novo produto</Botao>}>
      {!!alertas.data?.length && (
        <Alerta tipo="aviso" titulo={`${alertas.data.length} ${alertas.data.length === 1 ? 'produto com estoque baixo' : 'produtos com estoque baixo'}`}>
          {alertas.data.slice(0, 5).map((p) => `${p.nome} (${p.estoque_atual})`).join(' · ')}
          {alertas.data.length > 5 && ` · e mais ${alertas.data.length - 5}`}{' '}
          <button type="button" className="font-semibold underline" onClick={() => { setSoAlerta(true); setOffset(0) }}>Ver só esses</button>
        </Alerta>
      )}

      <div className="flex flex-wrap items-center gap-4">
        <div className="relative min-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input aria-label="Buscar produtos" className="campo pl-9" placeholder="Buscar por nome ou descrição…" value={busca} onChange={(e) => { setBusca(e.target.value); setOffset(0) }} />
        </div>
        <Interruptor marcado={soAlerta} onChange={(v) => { setSoAlerta(v); setOffset(0) }} rotulo="Só estoque baixo" />
        <Interruptor marcado={inativos} onChange={(v) => { setInativos(v); setOffset(0) }} rotulo="Mostrar inativos" />
      </div>

      <div className="cartao overflow-hidden">
        {q.isLoading ? <Carregando /> : q.isError ? <ErroConsulta erro={q.error} onTentar={() => void q.refetch()} /> : q.data && q.data.itens.length === 0 ? (
          <Vazio titulo={termo || soAlerta ? 'Nenhum produto encontrado' : 'Nenhum produto cadastrado'} icone={<Boxes className="h-10 w-10" />}>{termo || soAlerta ? 'Ajuste os filtros.' : 'Clique em “Novo produto” para começar.'}</Vazio>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50"><tr>
                  <th className="th">Produto</th><th className="th">Descrição</th><th className="th text-right">Preço</th>
                  <th className="th text-right">Em estoque</th><th className="th text-right">Mínimo</th><th className="th">Situação</th><th className="th"><span className="sr-only">Ações</span></th>
                </tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {q.data?.itens.map((p) => (
                    <tr key={p.id_produto} className={cn(!p.is_ativo && 'text-slate-400')}>
                      <td className="td font-medium">{p.nome}</td>
                      <td className="td">{p.descricao}</td>
                      <td className="td text-right">{moeda(p.preco_unitario)}</td>
                      <td className="td text-right">
                        <span className={cn('font-semibold', p.alerta_estoque_baixo ? 'text-amber-600' : 'text-slate-900')}>{p.estoque_atual}</span>
                        {p.alerta_estoque_baixo && <Chip cor="ambar" className="ml-2">Baixo</Chip>}
                      </td>
                      <td className="td text-right">{p.estoque_minimo}</td>
                      <td className="td"><Chip cor={p.is_ativo ? 'verde' : 'vermelho'}>{p.is_ativo ? 'Ativo' : 'Inativo'}</Chip></td>
                      <td className="td">
                        <div className="flex justify-end gap-0.5">
                          {ehAdmin && p.is_ativo && <Icone rotulo={`Registrar entrada de ${p.nome}`} cor="text-emerald-600 hover:bg-emerald-50" onClick={() => setMov({ tipo: 'entrada', produto: p })}><ArrowDownToLine className="h-4 w-4" /></Icone>}
                          {ehAdmin && p.is_ativo && <Icone rotulo={`Registrar saída de ${p.nome}`} cor="text-rose-600 hover:bg-rose-50" onClick={() => setMov({ tipo: 'saida', produto: p })}><ArrowUpFromLine className="h-4 w-4" /></Icone>}
                          {ehAdmin && <Link aria-label={`Ver movimentações de ${p.nome}`} title="Ver movimentações" to={`/produtos/${p.id_produto}/movimentacoes`} className="rounded-lg p-2 text-brand-600 hover:bg-brand-50"><History className="h-4 w-4" /></Link>}
                          <Icone rotulo={`Editar ${p.nome}`} onClick={() => setEditar(p)}><Pencil className="h-4 w-4" /></Icone>
                          <Icone rotulo={p.is_ativo ? `Inativar ${p.nome}` : `Reativar ${p.nome}`} cor={p.is_ativo ? 'text-slate-500 hover:bg-slate-100' : 'text-emerald-600 hover:bg-emerald-50'} onClick={() => (p.is_ativo ? setTrocar(p) : situacao.mutate(p))}><Power className="h-4 w-4" /></Icone>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {q.data && <Paginacao pagina={q.data} onMudar={setOffset} rotulo="produtos" />}
          </>
        )}
      </div>
      <p className="text-xs text-slate-400">
        Estoque baixo = quantidade igual ou abaixo do mínimo. {ehAdmin ? 'O ícone de relógio abre o histórico de movimentações do produto, com filtros.' : 'Entradas, saídas e o histórico de movimentações são da administradora.'}
        {' '}Total de unidades em estoque nesta página: {q.data?.itens.reduce((s, p) => s + numero(p.estoque_atual), 0) ?? 0}.
      </p>

      {editar && <FormProduto produto={editar === 'novo' ? null : editar} onFechar={() => setEditar(null)} />}
      {mov && <FormMovimento tipo={mov.tipo} produto={mov.produto} onFechar={() => setMov(null)} />}
      <Confirmar aberto={!!trocar} titulo="Inativar produto?" perigo textoConfirmar="Inativar" carregando={situacao.isPending} onCancelar={() => setTrocar(null)} onConfirmar={() => trocar && situacao.mutate(trocar)}
        mensagem={<>O produto <b>{trocar?.nome}</b> deixa de aparecer na lista e não pode entrar em novos pedidos. O histórico de vendas e movimentações é mantido.</>} />
    </Pagina_>
  )
}
