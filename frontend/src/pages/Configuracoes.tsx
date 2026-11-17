import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { DatabaseBackup, ImagePlus, RotateCcw, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Logo, useLogo } from '../components/Logo'
import { Alerta, Botao, Carregando, Chip, Confirmar, ErroConsulta, Pagina_, useAvisos } from '../components/ui'
import { api, mensagemDeErro } from '../lib/api'
import { dataHora, tamanho } from '../lib/format'
import type { StatusBackup } from '../lib/types'

export const TIPOS_DE_LOGO = ['image/png', 'image/jpeg', 'image/webp']
export const LIMITE_DA_LOGO = 2 * 1024 * 1024

/** Confere o arquivo antes de enviar (o servidor confere de novo, pelo conteúdo). */
export function validarLogo(arquivo: { type: string; size: number }): string | null {
  if (!TIPOS_DE_LOGO.includes(arquivo.type)) return 'Use uma imagem PNG, JPG ou WebP.'
  if (arquivo.size > LIMITE_DA_LOGO) return 'A imagem passa de 2 MB. Escolha uma menor.'
  if (arquivo.size === 0) return 'O arquivo está vazio.'
  return null
}

function CartaoLogo() {
  const avisos = useAvisos()
  const { atualizar } = useLogo()
  const cache = useQueryClient()
  const entrada = useRef<HTMLInputElement>(null)
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [previa, setPrevia] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [restaurar, setRestaurar] = useState(false)

  const situacao = useQuery({ queryKey: ['logo-situacao'], queryFn: () => api<{ personalizada: boolean }>('/sistema/logo/situacao') })

  useEffect(() => {
    if (!arquivo) return setPrevia(null)
    const url = URL.createObjectURL(arquivo)
    setPrevia(url)
    return () => URL.revokeObjectURL(url)
  }, [arquivo])

  const depois = (msg: string) => {
    void cache.invalidateQueries({ queryKey: ['logo-situacao'] })
    atualizar()
    avisos.sucesso(msg)
  }
  const enviar = useMutation({
    mutationFn: () => {
      const form = new FormData()
      form.append('arquivo', arquivo as File)
      return api('/sistema/logo', { method: 'POST', form })
    },
    onSuccess: () => { depois('Logo atualizada em todo o sistema.'); setArquivo(null); if (entrada.current) entrada.current.value = '' },
    onError: (e) => setErro(mensagemDeErro(e)),
  })
  const voltar = useMutation({
    mutationFn: () => api('/sistema/logo', { method: 'DELETE' }),
    onSuccess: () => { depois('Logo padrão restaurada.'); setRestaurar(false) },
    onError: (e) => { avisos.erro(e); setRestaurar(false) },
  })

  function escolher(f: File | undefined) {
    setErro(null)
    if (!f) return setArquivo(null)
    const problema = validarLogo(f)
    if (problema) { setErro(problema); setArquivo(null); return }
    setArquivo(f)
  }

  return (
    <section className="cartao space-y-5 p-6" aria-label="Logo da ONG">
      <div><h2 className="font-display text-lg font-semibold text-brand-900">Logo da ONG</h2><p className="text-sm text-slate-500">Aparece no menu, na tela de entrada e no cupom impresso.</p></div>
      <div className="grid gap-6 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Logo atual</p>
          <div className="flex h-44 items-center justify-center rounded-xl border border-slate-200 bg-white p-3"><Logo className="max-h-full" /></div>
          <p className="mt-2 text-xs text-slate-500">{situacao.data?.personalizada ? 'Logo personalizada' : 'Logo padrão do sistema'}</p>
        </div>
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Nova logo</p>
          <div className="flex h-44 items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-3">
            {previa ? <img src={previa} alt="Prévia da nova logo" className="max-h-full object-contain" /> : <div className="text-center text-sm text-slate-400"><ImagePlus className="mx-auto mb-1 h-8 w-8" aria-hidden />Escolha uma imagem</div>}
          </div>
          <p className="mt-2 text-xs text-slate-500">PNG, JPG ou WebP, até 2 MB. Fundo transparente fica melhor.</p>
        </div>
      </div>
      <input ref={entrada} type="file" accept="image/png,image/jpeg,image/webp" aria-label="Escolher arquivo da logo" className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-4 file:py-2 file:font-medium file:text-brand-700 hover:file:bg-brand-100" onChange={(e) => escolher(e.target.files?.[0])} />
      {erro && <Alerta tipo="erro">{erro}</Alerta>}
      <div className="flex flex-wrap gap-3">
        <Botao icone={<Upload className="h-4 w-4" />} disabled={!arquivo} carregando={enviar.isPending} onClick={() => { setErro(null); enviar.mutate() }}>Salvar nova logo</Botao>
        {situacao.data?.personalizada && <Botao variante="secundario" icone={<RotateCcw className="h-4 w-4" />} onClick={() => setRestaurar(true)}>Restaurar logo padrão</Botao>}
      </div>
      <Confirmar aberto={restaurar} titulo="Restaurar a logo padrão?" textoConfirmar="Restaurar" carregando={voltar.isPending} onCancelar={() => setRestaurar(false)} onConfirmar={() => voltar.mutate()} mensagem="A logo enviada será removida e a original do sistema volta a aparecer." />
    </section>
  )
}

function CartaoBackup() {
  const avisos = useAvisos()
  const cache = useQueryClient()
  const q = useQuery({ queryKey: ['backup'], queryFn: () => api<StatusBackup>('/sistema/backup') })
  const agora = useMutation({
    mutationFn: () => api<StatusBackup>('/sistema/backup', { method: 'POST' }),
    onSuccess: () => { void cache.invalidateQueries({ queryKey: ['backup'] }); avisos.sucesso('Backup concluído.') },
    onError: (e) => { void cache.invalidateQueries({ queryKey: ['backup'] }); avisos.erro(e) },
  })
  const s = q.data
  const chip = !s ? null : s.ultimo_status === 'ok' ? <Chip cor="verde">Último backup: sucesso</Chip> : s.ultimo_status === 'erro' ? <Chip cor="vermelho">Último backup: falhou</Chip> : <Chip cor="ambar">Nenhum backup ainda</Chip>
  return (
    <section className="cartao space-y-4 p-6" aria-label="Backup do banco de dados">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="font-display text-lg font-semibold text-brand-900">Backup do banco de dados</h2><p className="text-sm text-slate-500">Cópia de segurança semanal de todos os dados do sistema.</p></div>
        <Botao icone={<DatabaseBackup className="h-4 w-4" />} carregando={agora.isPending} onClick={() => agora.mutate()}>Fazer backup agora</Botao>
      </div>
      {q.isLoading && <Carregando />}
      {q.isError && <ErroConsulta erro={q.error} onTentar={() => void q.refetch()} />}
      {s && (
        <>
          {s.alerta && <Alerta tipo="aviso" titulo="Atenção">{s.motivo_alerta}</Alerta>}
          <dl className="grid gap-x-8 gap-y-2 text-sm sm:grid-cols-2">
            <div><dt className="text-slate-500">Situação</dt><dd className="mt-0.5">{chip}</dd></div>
            <div><dt className="text-slate-500">Backup automático</dt><dd className="mt-0.5 font-medium">{s.habilitado ? 'Ligado (semanal)' : 'Desligado'}</dd></div>
            <div><dt className="text-slate-500">Última tentativa</dt><dd className="mt-0.5 font-medium">{dataHora(s.ultima_tentativa)}</dd></div>
            <div><dt className="text-slate-500">Último com sucesso</dt><dd className="mt-0.5 font-medium">{dataHora(s.ultimo_sucesso)}</dd></div>
            <div><dt className="text-slate-500">Próximo automático</dt><dd className="mt-0.5 font-medium">{dataHora(s.proxima_execucao)}</dd></div>
            <div><dt className="text-slate-500">Cópias mantidas</dt><dd className="mt-0.5 font-medium">{s.retencao}</dd></div>
          </dl>
          {s.mensagem && <p className="text-xs text-slate-500">{s.mensagem}</p>}
          {s.arquivos.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-slate-200">
              <table className="w-full"><thead className="bg-slate-50"><tr><th className="th">Arquivo</th><th className="th">Criado em</th><th className="th text-right">Tamanho</th></tr></thead>
                <tbody className="divide-y divide-slate-100">{s.arquivos.map((a) => <tr key={a.nome}><td className="td font-mono text-xs">{a.nome}</td><td className="td">{dataHora(a.criado_em)}</td><td className="td text-right">{tamanho(a.tamanho_bytes)}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          <p className="text-xs text-slate-500">Os backups ficam na pasta do servidor e contêm todos os dados. Copie-os também para um pen drive ou nuvem e guarde com cuidado.</p>
        </>
      )}
    </section>
  )
}

export default function Configuracoes() {
  return (
    <Pagina_ titulo="Configurações">
      <div className="grid gap-6 xl:grid-cols-2"><CartaoLogo /><CartaoBackup /></div>
    </Pagina_>
  )
}
