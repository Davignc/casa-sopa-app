import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil, Plus, Power, Search, UserCog } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Alerta, Botao, Campo, Carregando, Chip, Confirmar, ErroConsulta, Modal, Pagina_, Paginacao, Vazio, cn, useAvisos } from '../components/ui'
import { api, mensagemDeErro } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Privacidade } from '../components/Privacidade'
import { emailValido, mascaraTelefone, telefone, telefoneValido } from '../lib/format'
import { useDebounce } from '../lib/hooks'
import { focarErros } from '../lib/acessibilidade'
import type { Cargo, Pagina, Usuario } from '../lib/types'

const POR_PAGINA = 20
const bytes = (t: string) => new TextEncoder().encode(t).length

function FormUsuario({ usuario, ehEu, onFechar }: { usuario: Usuario | null; ehEu: boolean; onFechar: () => void }) {
  const avisos = useAvisos()
  const cache = useQueryClient()
  const editando = usuario !== null
  const [f, setF] = useState({
    nome: usuario?.nome ?? '', email: usuario?.email ?? '', telefone: usuario ? mascaraTelefone(usuario.telefone) : '',
    cargo: (usuario?.cargo ?? 'vendedora') as Cargo, comissao: usuario?.comissao ? String(Number(usuario.comissao)).replace('.', ',') : '', senha: '', confirmar: '',
  })
  const [tentou, setTentou] = useState(false)
  const [falha, setFalha] = useState<string | null>(null)

  const comissao = f.comissao.trim() === '' ? null : Number(f.comissao.replace(',', '.'))
  const erros = {
    nome: f.nome.trim() ? null : 'Informe o nome.',
    email: emailValido(f.email) ? null : 'Informe um e-mail válido.',
    telefone: telefoneValido(f.telefone) ? null : 'Informe DDD + número.',
    comissao: f.cargo !== 'vendedora' || comissao === null || (Number.isFinite(comissao) && comissao >= 0 && comissao <= 100) ? null : 'Use um valor de 0 a 100.',
    senha: !f.senha && editando ? null : f.senha.length < 8 ? 'Mínimo de 8 caracteres.' : bytes(f.senha) > 72 ? 'Senha longa demais (máx. 72 bytes).' : null,
    confirmar: f.senha !== f.confirmar ? 'As senhas não conferem.' : null,
  }
  const ver = (k: keyof typeof erros) => (tentou ? erros[k] : null)

  const salvar = useMutation({
    mutationFn: () => {
      const comuns = { nome: f.nome.trim(), email: f.email.trim().toLowerCase(), telefone: f.telefone, cargo: f.cargo, comissao: f.cargo === 'vendedora' ? comissao : null }
      if (!editando) return api<Usuario>('/usuarios', { body: { ...comuns, comissao: comuns.comissao ?? undefined, senha: f.senha } })
      const mudou: Record<string, unknown> = {}
      if (comuns.nome !== usuario.nome) mudou.nome = comuns.nome
      if (comuns.email !== usuario.email) mudou.email = comuns.email
      if (comuns.telefone.replace(/\D/g, '') !== usuario.telefone) mudou.telefone = comuns.telefone
      if (comuns.cargo !== usuario.cargo) mudou.cargo = comuns.cargo
      if (comuns.cargo === 'vendedora' && (comuns.comissao ?? null) !== (usuario.comissao ? Number(usuario.comissao) : null)) mudou.comissao = comuns.comissao
      if (f.senha) mudou.senha = f.senha
      return Object.keys(mudou).length ? api<Usuario>(`/usuarios/${usuario.id_usuario}`, { method: 'PATCH', body: mudou }) : Promise.resolve(usuario)
    },
    onSuccess: () => {
      void cache.invalidateQueries({ queryKey: ['usuarios'] })
      void cache.invalidateQueries({ queryKey: ['usuarios-vendedoras'] })
      avisos.sucesso(editando ? 'Usuário atualizado.' : 'Usuário cadastrado.')
      onFechar()
    },
    onError: (e) => setFalha(mensagemDeErro(e)),
  })

  function enviar(e: FormEvent) {
    e.preventDefault()
    focarErros(e.currentTarget as HTMLFormElement)
    setTentou(true)
    setFalha(null)
    if (Object.values(erros).some(Boolean)) return
    salvar.mutate()
  }

  return (
    <Modal aberto onFechar={onFechar} titulo={editando ? 'Editar usuário' : '+ Novo usuário'} largura="max-w-xl"
      rodape={<><Botao variante="secundario" onClick={onFechar}>Cancelar</Botao><Botao type="submit" form="form-usuario" carregando={salvar.isPending}>{editando ? 'Salvar' : 'Cadastrar usuário'}</Botao></>}>
      <form id="form-usuario" onSubmit={enviar} noValidate className="space-y-4">
        <Privacidade contexto="usuario" />
        {falha && <Alerta tipo="erro">{falha}</Alerta>}
        <Campo rotulo="Nome completo" obrigatorio erro={ver('nome')}>{(p) => <input {...p} className={cn('campo', ver('nome') && 'campo-erro')} maxLength={150} value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} />}</Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="E-mail" obrigatorio erro={ver('email')}>{(p) => <input {...p} className={cn('campo', ver('email') && 'campo-erro')} type="email" autoComplete="off" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />}</Campo>
          <Campo rotulo="Telefone" obrigatorio erro={ver('telefone')}>{(p) => <input {...p} className={cn('campo', ver('telefone') && 'campo-erro')} inputMode="tel" value={f.telefone} onChange={(e) => setF({ ...f, telefone: mascaraTelefone(e.target.value) })} />}</Campo>
          <Campo rotulo="Cargo" obrigatorio dica={ehEu ? 'Você não pode alterar o seu próprio cargo.' : undefined}>
            {(p) => <select {...p} className="campo" disabled={ehEu} value={f.cargo} onChange={(e) => setF({ ...f, cargo: e.target.value as Cargo })}><option value="vendedora">Vendedora</option><option value="administradora">Administradora</option></select>}
          </Campo>
          {f.cargo === 'vendedora' && <Campo rotulo="Comissão (%)" erro={ver('comissao')} dica="Opcional. De 0 a 100.">{(p) => <input {...p} className={cn('campo', ver('comissao') && 'campo-erro')} inputMode="decimal" placeholder="Ex.: 10" value={f.comissao} onChange={(e) => setF({ ...f, comissao: e.target.value })} />}</Campo>}
        </div>
        <div className="grid gap-4 border-t border-slate-100 pt-4 sm:grid-cols-2">
          <Campo rotulo={editando ? 'Nova senha' : 'Senha'} obrigatorio={!editando} erro={ver('senha')} dica={editando ? 'Deixe em branco para manter. Trocar a senha encerra as sessões abertas dela.' : 'Mínimo de 8 caracteres.'}>
            {(p) => <input {...p} className={cn('campo', ver('senha') && 'campo-erro')} type="password" autoComplete="new-password" value={f.senha} onChange={(e) => setF({ ...f, senha: e.target.value })} />}
          </Campo>
          <Campo rotulo="Confirmar senha" erro={ver('confirmar')}>{(p) => <input {...p} className={cn('campo', ver('confirmar') && 'campo-erro')} type="password" autoComplete="new-password" value={f.confirmar} onChange={(e) => setF({ ...f, confirmar: e.target.value })} />}</Campo>
        </div>
      </form>
    </Modal>
  )
}

export default function Usuarios() {
  const { usuario: eu } = useAuth()
  const avisos = useAvisos()
  const cache = useQueryClient()
  const [busca, setBusca] = useState('')
  const [cargo, setCargo] = useState('')
  const [situacaoFiltro, setSituacaoFiltro] = useState('')
  const [offset, setOffset] = useState(0)
  const [editar, setEditar] = useState<Usuario | 'novo' | null>(null)
  const [inativar, setInativar] = useState<Usuario | null>(null)
  const termo = useDebounce(busca.trim(), 300)

  const q = useQuery({
    queryKey: ['usuarios', termo, cargo, situacaoFiltro, offset],
    queryFn: () => api<Pagina<Usuario>>('/usuarios', { query: { busca: termo, cargo, is_ativo: situacaoFiltro, limit: POR_PAGINA, offset } }),
    placeholderData: keepPreviousData,
  })
  const trocar = useMutation({
    mutationFn: (u: Usuario) => (u.is_ativo ? api(`/usuarios/${u.id_usuario}`, { method: 'DELETE' }) : api(`/usuarios/${u.id_usuario}/reativar`, { method: 'POST' })),
    onSuccess: (_, u) => { void cache.invalidateQueries({ queryKey: ['usuarios'] }); avisos.sucesso(u.is_ativo ? 'Usuário inativado.' : 'Usuário reativado.'); setInativar(null) },
    onError: (e) => { avisos.erro(e); setInativar(null) },
  })

  return (
    <Pagina_ titulo="Usuários" acoes={<Botao icone={<Plus className="h-4 w-4" />} onClick={() => setEditar('novo')}>Novo usuário</Botao>}>
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <input aria-label="Buscar usuários" className="campo pl-9" placeholder="Buscar por nome ou e-mail…" value={busca} onChange={(e) => { setBusca(e.target.value); setOffset(0) }} />
        </div>
        <select aria-label="Filtrar por cargo" className="campo w-44" value={cargo} onChange={(e) => { setCargo(e.target.value); setOffset(0) }}><option value="">Todos os cargos</option><option value="administradora">Administradoras</option><option value="vendedora">Vendedoras</option></select>
        <select aria-label="Filtrar por situação" className="campo w-40" value={situacaoFiltro} onChange={(e) => { setSituacaoFiltro(e.target.value); setOffset(0) }}><option value="">Todas</option><option value="true">Ativos</option><option value="false">Inativos</option></select>
      </div>

      <div className="cartao overflow-hidden">
        {q.isLoading ? <Carregando /> : q.isError ? <ErroConsulta erro={q.error} onTentar={() => void q.refetch()} /> : q.data && q.data.itens.length === 0 ? (
          <Vazio titulo="Nenhum usuário encontrado" icone={<UserCog className="h-10 w-10" />} />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50"><tr><th className="th">Nome</th><th className="th">E-mail</th><th className="th">Telefone</th><th className="th">Cargo</th><th className="th text-right">Comissão</th><th className="th">Situação</th><th className="th"><span className="sr-only">Ações</span></th></tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {q.data?.itens.map((u) => {
                    const sou = u.id_usuario === eu?.id_usuario
                    return (
                      <tr key={u.id_usuario} className={cn(!u.is_ativo && 'text-slate-400')}>
                        <td className="td font-medium">{u.nome}{sou && <Chip cor="azul" className="ml-2">você</Chip>}</td>
                        <td className="td">{u.email}</td><td className="td whitespace-nowrap">{telefone(u.telefone)}</td>
                        <td className="td"><Chip cor={u.cargo === 'administradora' ? 'roxo' : 'azul'}>{u.cargo === 'administradora' ? 'Administradora' : 'Vendedora'}</Chip></td>
                        <td className="td text-right">{u.comissao ? `${Number(u.comissao)}%` : '—'}</td>
                        <td className="td"><Chip cor={u.is_ativo ? 'verde' : 'vermelho'}>{u.is_ativo ? 'Ativo' : 'Inativo'}</Chip></td>
                        <td className="td">
                          <div className="flex justify-end gap-0.5">
                            <button type="button" aria-label={`Editar ${u.nome}`} title="Editar" onClick={() => setEditar(u)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><Pencil className="h-4 w-4" /></button>
                            {!sou && <button type="button" aria-label={u.is_ativo ? `Inativar ${u.nome}` : `Reativar ${u.nome}`} title={u.is_ativo ? 'Inativar' : 'Reativar'} onClick={() => (u.is_ativo ? setInativar(u) : trocar.mutate(u))} className={cn('rounded-lg p-2', u.is_ativo ? 'text-slate-500 hover:bg-slate-100' : 'text-emerald-600 hover:bg-emerald-50')}><Power className="h-4 w-4" /></button>}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {q.data && <Paginacao pagina={q.data} onMudar={setOffset} rotulo="usuários" />}
          </>
        )}
      </div>

      {editar && <FormUsuario usuario={editar === 'novo' ? null : editar} ehEu={editar !== 'novo' && editar.id_usuario === eu?.id_usuario} onFechar={() => setEditar(null)} />}
      <Confirmar aberto={!!inativar} titulo="Inativar usuário?" perigo textoConfirmar="Inativar" carregando={trocar.isPending} onCancelar={() => setInativar(null)} onConfirmar={() => inativar && trocar.mutate(inativar)}
        mensagem={<><b>{inativar?.nome}</b> não conseguirá mais entrar no sistema, e as sessões abertas dela perdem o acesso na hora. Os pedidos e o histórico continuam registrados.</>} />
    </Pagina_>
  )
}
