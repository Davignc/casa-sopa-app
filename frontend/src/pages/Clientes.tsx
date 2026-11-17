import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MapPin, Pencil, Plus, Search, Star, Trash2, Users } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { AddressPicker } from '../components/AddressPicker'
import { Privacidade } from '../components/Privacidade'
import { HistoricoCliente } from '../components/HistoricoCliente'
import { Abas, Alerta, Botao, Campo, Carregando, Chip, Confirmar, ErroConsulta, Interruptor, Modal, Pagina_, Paginacao, Vazio, cn, useAvisos } from '../components/ui'
import { api, mensagemDeErro } from '../lib/api'
import { mascaraTelefone, telefone, telefoneValido } from '../lib/format'
import { useDebounce } from '../lib/hooks'
import { focarErros } from '../lib/acessibilidade'
import type { Cliente, ClienteResumo, Endereco, EnderecoDoCliente, Pagina } from '../lib/types'

const POR_PAGINA = 20

function useInvalidarClientes() {
  const q = useQueryClient()
  return (id?: number) => {
    void q.invalidateQueries({ queryKey: ['clientes'] })
    void q.invalidateQueries({ queryKey: ['clientes-busca'] })
    if (id) void q.invalidateQueries({ queryKey: ['cliente', id] })
  }
}

/* ---------- Novo cliente ---------- */

function NovoCliente({ aberto, onFechar }: { aberto: boolean; onFechar: (criado?: Cliente) => void }) {
  const avisos = useAvisos()
  const invalidar = useInvalidarClientes()
  const [nome, setNome] = useState('')
  const [fone, setFone] = useState('')
  const [comEndereco, setComEndereco] = useState(true)
  const [endereco, setEndereco] = useState<EnderecoDoCliente | null>(null)
  const [tentou, setTentou] = useState(false)
  const [falha, setFalha] = useState<string | null>(null)

  const criar = useMutation({
    mutationFn: () => api<Cliente>('/clientes', { body: { nome: nome.trim(), telefone: fone, enderecos: comEndereco && endereco ? [{ ...endereco, principal: true }] : [] } }),
    onSuccess: (c) => { invalidar(); avisos.sucesso(`Cliente ${c.nome} cadastrado.`); reiniciar(); onFechar(c) },
    onError: (e) => setFalha(mensagemDeErro(e)),
  })

  function reiniciar() { setNome(''); setFone(''); setComEndereco(true); setEndereco(null); setTentou(false); setFalha(null) }

  const erroNome = tentou && !nome.trim() ? 'Informe o nome.' : null
  const erroFone = tentou && !telefoneValido(fone) ? 'Informe DDD + número (10 ou 11 dígitos).' : null

  function enviar(e: FormEvent) {
    e.preventDefault()
    focarErros(e.currentTarget as HTMLFormElement)
    setTentou(true)
    setFalha(null)
    if (!nome.trim() || !telefoneValido(fone)) return
    if (comEndereco && !endereco) return
    criar.mutate()
  }

  return (
    <Modal aberto={aberto} onFechar={() => { reiniciar(); onFechar() }} titulo="+ Cadastrar cliente" largura="max-w-2xl"
      rodape={<>
        <Botao variante="secundario" onClick={() => { reiniciar(); onFechar() }}>Cancelar</Botao>
        <Botao type="submit" form="form-novo-cliente" carregando={criar.isPending}>Cadastrar cliente</Botao>
      </>}>
      <form id="form-novo-cliente" onSubmit={enviar} noValidate className="space-y-5">
        <Privacidade />
        {falha && <Alerta tipo="erro">{falha}</Alerta>}
        <Campo rotulo="Nome completo" obrigatorio erro={erroNome}>
          {(p) => <input {...p} autoComplete="name" className={cn('campo', erroNome && 'campo-erro')} maxLength={150} placeholder="Nome do cliente" value={nome} onChange={(e) => setNome(e.target.value)} />}
        </Campo>
        <Campo rotulo="Telefone / WhatsApp" obrigatorio erro={erroFone}>
          {(p) => <input {...p} type="tel" autoComplete="tel" className={cn('campo', erroFone && 'campo-erro')} inputMode="tel" placeholder="(16) 99999-9999" value={fone} onChange={(e) => setFone(mascaraTelefone(e.target.value))} />}
        </Campo>
        <div className="space-y-3 border-t border-slate-100 pt-4">
          <Interruptor marcado={comEndereco} onChange={setComEndereco} rotulo="Cadastrar o endereço de entrega agora" />
          {comEndereco && <AddressPicker onChange={setEndereco} mostrarErros={tentou} />}
          {comEndereco && tentou && !endereco && <p role="alert" className="text-xs text-rose-600">Escolha um endereço registrado ou preencha um novo (ou desmarque a opção acima).</p>}
        </div>
      </form>
    </Modal>
  )
}

/* ---------- Detalhe do cliente ---------- */

function EditarVinculo({ cliente, endereco, onFechar }: { cliente: Cliente; endereco: Endereco; onFechar: () => void }) {
  const avisos = useAvisos()
  const invalidar = useInvalidarClientes()
  const [v, setV] = useState({ numero: endereco.numero, complemento: endereco.complemento, referencia: endereco.referencia, apelido: endereco.apelido ?? '' })
  const salvar = useMutation({
    mutationFn: () => api(`/clientes/${cliente.id_cliente}/enderecos/${endereco.id_endereco}`, { method: 'PATCH', body: { numero: v.numero.trim(), complemento: v.complemento.trim(), referencia: v.referencia.trim(), apelido: v.apelido.trim() || null } }),
    onSuccess: () => { invalidar(cliente.id_cliente); avisos.sucesso('Endereço atualizado.'); onFechar() },
    onError: avisos.erro,
  })
  return (
    <Modal aberto onFechar={onFechar} titulo="Editar endereço" subtitulo={`${endereco.tipo_logradouro} ${endereco.nome_logradouro} · ${endereco.bairro}`}
      rodape={<><Botao variante="secundario" onClick={onFechar}>Cancelar</Botao><Botao carregando={salvar.isPending} disabled={!v.numero.trim()} onClick={() => salvar.mutate()}>Salvar</Botao></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Campo rotulo="Número" obrigatorio>{(p) => <input {...p} className="campo" maxLength={10} value={v.numero} onChange={(e) => setV({ ...v, numero: e.target.value })} />}</Campo>
        <Campo rotulo="Complemento">{(p) => <input {...p} className="campo" maxLength={50} value={v.complemento} onChange={(e) => setV({ ...v, complemento: e.target.value })} />}</Campo>
        <Campo rotulo="Ponto de referência">{(p) => <input {...p} className="campo" maxLength={50} value={v.referencia} onChange={(e) => setV({ ...v, referencia: e.target.value })} />}</Campo>
        <Campo rotulo="Apelido">{(p) => <input {...p} className="campo" maxLength={50} value={v.apelido} onChange={(e) => setV({ ...v, apelido: e.target.value })} />}</Campo>
      </div>
      <p className="mt-3 text-xs text-slate-500">Para corrigir rua, bairro, cidade ou CEP, cadastre o endereço correto e remova este.</p>
    </Modal>
  )
}

function DetalheCliente({ id, onFechar }: { id: number; onFechar: () => void }) {
  const avisos = useAvisos()
  const invalidar = useInvalidarClientes()
  const [aba, setAba] = useState<'dados' | 'historico'>('dados')
  const [editando, setEditando] = useState(false)
  const [adicionando, setAdicionando] = useState(false)
  const [novoEndereco, setNovoEndereco] = useState<EnderecoDoCliente | null>(null)
  const [tentou, setTentou] = useState(false)
  const [vinculo, setVinculo] = useState<Endereco | null>(null)
  const [remover, setRemover] = useState<Endereco | null>(null)
  const [inativar, setInativar] = useState(false)
  const [form, setForm] = useState({ nome: '', telefone: '' })

  const q = useQuery({ queryKey: ['cliente', id], queryFn: () => api<Cliente>(`/clientes/${id}`) })
  const c = q.data

  const mut = <T,>(fn: () => Promise<T>, ok: string, depois?: () => void) => ({
    mutationFn: fn,
    onSuccess: () => { invalidar(id); avisos.sucesso(ok); depois?.() },
    onError: avisos.erro,
  })
  const dados = useMutation(mut(() => api(`/clientes/${id}`, { method: 'PATCH', body: { nome: form.nome.trim(), telefone: form.telefone } }), 'Dados atualizados.', () => setEditando(false)))
  const situacao = useMutation(mut(() => (c?.is_ativo ? api(`/clientes/${id}`, { method: 'DELETE' }) : api(`/clientes/${id}/reativar`, { method: 'POST' })), c?.is_ativo ? 'Cliente inativado.' : 'Cliente reativado.', () => setInativar(false)))
  const principal = useMutation({
    mutationFn: (e: Endereco) => api(`/clientes/${id}/enderecos/${e.id_endereco}`, { method: 'PATCH', body: { principal: true } }),
    onSuccess: () => { invalidar(id); avisos.sucesso('Endereço principal alterado.') },
    onError: avisos.erro,
  })
  const apagar = useMutation(mut(() => api(`/clientes/${id}/enderecos/${remover?.id_endereco}`, { method: 'DELETE' }), 'Endereço removido.', () => setRemover(null)))
  const incluir = useMutation(mut(() => api(`/clientes/${id}/enderecos`, { body: novoEndereco }), 'Endereço adicionado.', () => { setAdicionando(false); setNovoEndereco(null); setTentou(false) }))

  function comecarEdicao() {
    if (!c) return
    setForm({ nome: c.nome, telefone: mascaraTelefone(c.telefone) })
    setEditando(true)
  }

  function salvarDados(e: FormEvent) {
    e.preventDefault()
    if (form.nome.trim() && telefoneValido(form.telefone)) dados.mutate()
  }

  return (
    <Modal aberto onFechar={onFechar} largura="max-w-3xl" titulo={c ? <span className="flex flex-wrap items-center gap-3">{c.nome}<Chip cor={c.is_ativo ? 'verde' : 'vermelho'}>{c.is_ativo ? 'Ativo' : 'Inativo'}</Chip></span> : 'Cliente'}
      subtitulo={c ? `Código #${c.id_cliente} · cadastrado por ${c.cadastrado_por.nome}` : undefined}>
      {q.isLoading && <Carregando />}
      {q.isError && <ErroConsulta erro={q.error} onTentar={() => void q.refetch()} />}
      {c && (
        <div className="space-y-5">
          <Abas itens={[{ id: 'dados', rotulo: 'Dados e endereços' }, { id: 'historico', rotulo: 'Histórico de compras' }]} valor={aba} onMudar={setAba} />

          {aba === 'historico' && <HistoricoCliente idCliente={c.id_cliente} />}

          {aba === 'dados' && (
            <>
              <section className="space-y-3">
                {editando ? (
                  <form onSubmit={salvarDados} className="grid gap-4 sm:grid-cols-2" noValidate>
                    <Campo rotulo="Nome completo" obrigatorio>{(p) => <input {...p} className="campo" maxLength={150} value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} />}</Campo>
                    <Campo rotulo="Telefone / WhatsApp" obrigatorio erro={form.telefone && !telefoneValido(form.telefone) ? 'Telefone incompleto.' : null}>{(p) => <input {...p} className="campo" value={form.telefone} onChange={(e) => setForm({ ...form, telefone: mascaraTelefone(e.target.value) })} />}</Campo>
                    <div className="flex gap-2 sm:col-span-2"><Botao type="submit" pequeno carregando={dados.isPending}>Salvar</Botao><Botao variante="secundario" pequeno onClick={() => setEditando(false)}>Cancelar</Botao></div>
                  </form>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm text-slate-600">Telefone: <b className="text-slate-900">{telefone(c.telefone)}</b></p>
                    <div className="flex gap-2">
                      <Botao variante="secundario" pequeno icone={<Pencil className="h-4 w-4" />} onClick={comecarEdicao}>Editar dados</Botao>
                      <Botao variante={c.is_ativo ? 'secundario' : 'sucesso'} pequeno onClick={() => (c.is_ativo ? setInativar(true) : situacao.mutate())} carregando={situacao.isPending && !inativar}>{c.is_ativo ? 'Inativar' : 'Reativar'}</Botao>
                    </div>
                  </div>
                )}
              </section>

              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-display text-base font-semibold text-slate-800">Endereços de entrega</h3>
                  {!adicionando && <Botao pequeno variante="fantasma" icone={<Plus className="h-4 w-4" />} onClick={() => setAdicionando(true)}>Adicionar endereço</Botao>}
                </div>
                {c.enderecos.length === 0 && !adicionando && <Alerta tipo="aviso">Este cliente ainda não tem endereço. Adicione um para poder registrar pedidos.</Alerta>}
                <ul className="space-y-2">
                  {c.enderecos.map((e) => (
                    <li key={e.id_endereco} className={cn('rounded-xl border p-4', e.principal ? 'border-brand-300 bg-brand-50/50' : 'border-slate-200')}>
                      <div className="flex flex-wrap items-start gap-3">
                        <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden />
                        <div className="min-w-0 flex-1 text-sm">
                          <p className="font-medium text-slate-900">{e.endereco_formatado}</p>
                          {e.referencia && <p className="text-slate-500">Referência: {e.referencia}</p>}
                          <div className="mt-1 flex flex-wrap gap-1.5">
                            {e.principal && <Chip cor="azul"><Star className="mr-1 h-3 w-3" aria-hidden />Principal</Chip>}
                            {e.apelido && <Chip>{e.apelido}</Chip>}
                          </div>
                        </div>
                        <div className="flex gap-1">
                          {!e.principal && <Botao pequeno variante="fantasma" onClick={() => principal.mutate(e)}>Tornar principal</Botao>}
                          <button type="button" aria-label={`Editar endereço ${e.nome_logradouro}`} onClick={() => setVinculo(e)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><Pencil className="h-4 w-4" /></button>
                          <button type="button" aria-label={`Remover endereço ${e.nome_logradouro}`} onClick={() => setRemover(e)} className="rounded-lg p-2 text-rose-500 hover:bg-rose-50"><Trash2 className="h-4 w-4" /></button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>

                {adicionando && (
                  <div className="space-y-4 rounded-xl border border-slate-200 p-4">
                    <AddressPicker comPrincipal jaVinculados={c.enderecos.map((e) => e.id_endereco)} onChange={setNovoEndereco} mostrarErros={tentou} />
                    <div className="flex gap-2">
                      <Botao pequeno carregando={incluir.isPending} onClick={() => (novoEndereco ? incluir.mutate() : setTentou(true))}>Salvar endereço</Botao>
                      <Botao pequeno variante="secundario" onClick={() => { setAdicionando(false); setNovoEndereco(null); setTentou(false) }}>Cancelar</Botao>
                    </div>
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      )}

      {c && vinculo && <EditarVinculo cliente={c} endereco={vinculo} onFechar={() => setVinculo(null)} />}
      <Confirmar aberto={inativar} titulo="Inativar cliente?" perigo textoConfirmar="Inativar" carregando={situacao.isPending} onCancelar={() => setInativar(false)} onConfirmar={() => situacao.mutate()}
        mensagem={<>O cliente <b>{c?.nome}</b> deixa de aparecer na lista e não recebe novos pedidos. O histórico de pedidos é mantido e você pode reativá-lo depois.</>} />
      <Confirmar aberto={!!remover} titulo="Remover endereço?" perigo textoConfirmar="Remover" carregando={apagar.isPending} onCancelar={() => setRemover(null)} onConfirmar={() => apagar.mutate()}
        mensagem={<>{remover?.endereco_formatado}<br /><span className="text-slate-500">Se já foi usado em pedidos, ele é apenas desativado para preservar o histórico.</span></>} />
    </Modal>
  )
}

/* ---------- Lista ---------- */

export default function Clientes() {
  const [busca, setBusca] = useState('')
  const [inativos, setInativos] = useState(false)
  const [offset, setOffset] = useState(0)
  const [novo, setNovo] = useState(false)
  const [aberto, setAberto] = useState<number | null>(null)
  const termo = useDebounce(busca.trim(), 300)

  const q = useQuery({
    queryKey: ['clientes', termo, inativos, offset],
    queryFn: () => api<Pagina<ClienteResumo>>('/clientes', { query: { busca: termo, incluir_inativos: inativos, limit: POR_PAGINA, offset } }),
    placeholderData: keepPreviousData,
  })

  return (
    <Pagina_ titulo="Clientes" acoes={<Botao icone={<Plus className="h-4 w-4" />} onClick={() => setNovo(true)}>Novo cliente</Botao>}>
      <div className="flex flex-wrap items-center gap-4">
        <div className="relative min-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input aria-label="Buscar clientes" className="campo pl-9" placeholder="Buscar por nome, telefone, código ou endereço…" value={busca} onChange={(e) => { setBusca(e.target.value); setOffset(0) }} />
        </div>
        <Interruptor marcado={inativos} onChange={(v) => { setInativos(v); setOffset(0) }} rotulo="Mostrar inativos" />
      </div>

      <div className="cartao overflow-hidden">
        {q.isLoading ? <Carregando /> : q.isError ? <ErroConsulta erro={q.error} onTentar={() => void q.refetch()} /> : q.data && q.data.itens.length === 0 ? (
          <Vazio titulo={termo ? 'Nenhum cliente encontrado' : 'Nenhum cliente cadastrado'} icone={<Users className="h-10 w-10" />}>
            {termo ? 'Tente outro nome, telefone ou endereço.' : 'Clique em “Novo cliente” para começar.'}
          </Vazio>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50"><tr>
                  <th className="th">Código</th><th className="th">Nome</th><th className="th">Telefone</th><th className="th">Endereço principal</th>
                  <th className="th">Ponto de referência</th><th className="th">Cadastrado por</th><th className="th">Situação</th>
                </tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {q.data?.itens.map((c) => (
                    <tr key={c.id_cliente} tabIndex={0} onClick={() => setAberto(c.id_cliente)} onKeyDown={(e) => e.key === 'Enter' && setAberto(c.id_cliente)}
                      className={cn('cursor-pointer hover:bg-brand-50/50 focus-visible:bg-brand-50', !c.is_ativo && 'text-slate-400')}>
                      <td className="td text-xs text-slate-500">#{c.id_cliente}</td>
                      <td className="td font-medium">{c.nome}</td>
                      <td className="td whitespace-nowrap">{telefone(c.telefone)}</td>
                      <td className="td min-w-64">{c.endereco_principal?.endereco_formatado ?? <span className="text-amber-600">Sem endereço</span>}</td>
                      <td className="td">{c.endereco_principal?.referencia || '—'}</td>
                      <td className="td">{c.cadastrado_por.nome}</td>
                      <td className="td"><Chip cor={c.is_ativo ? 'verde' : 'vermelho'}>{c.is_ativo ? 'Ativo' : 'Inativo'}</Chip></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {q.data && <Paginacao pagina={q.data} onMudar={setOffset} rotulo="clientes" />}
          </>
        )}
      </div>
      <p className="text-xs text-slate-400">Clique em um cliente para ver endereços, editar ou consultar o histórico de compras.</p>

      <NovoCliente aberto={novo} onFechar={(c) => { setNovo(false); if (c) setAberto(c.id_cliente) }} />
      {aberto !== null && <DetalheCliente id={aberto} onFechar={() => setAberto(null)} />}
    </Pagina_>
  )
}
