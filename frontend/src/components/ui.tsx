import clsx from 'clsx'
import { createPortal } from 'react-dom'
import { useDialogo } from '../lib/acessibilidade'
import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Info, Loader2, X, XCircle } from 'lucide-react'
import {
  createContext, useCallback, useContext, useId, useMemo, useRef, useState,
  type ButtonHTMLAttributes, type ReactNode,
} from 'react'
import { mensagemDeErro } from '../lib/api'
import { STATUS_ROTULO } from '../lib/format'
import type { Pagina, StatusPedido } from '../lib/types'

export const cn = clsx

/* ---------- Botão ---------- */

type Variante = 'primario' | 'secundario' | 'perigo' | 'fantasma' | 'sucesso'

const VARIANTES: Record<Variante, string> = {
  primario: 'bg-brand-600 text-white hover:bg-brand-700 shadow-sm disabled:bg-brand-300',
  secundario: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:text-slate-400',
  perigo: 'bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300',
  fantasma: 'text-brand-700 hover:bg-brand-50 disabled:text-slate-400',
  sucesso: 'bg-emerald-600 text-white hover:bg-emerald-700 disabled:bg-emerald-300',
}

interface BotaoProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: Variante
  carregando?: boolean
  icone?: ReactNode
  pequeno?: boolean
}

export function Botao({ variante = 'primario', carregando, icone, pequeno, className, children, disabled, type = 'button', ...rest }: BotaoProps) {
  return (
    <button
      type={type}
      disabled={disabled || carregando}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed',
        pequeno ? 'h-9 px-3 text-sm' : 'h-11 px-4 text-sm',
        VARIANTES[variante],
        className,
      )}
      {...rest}
    >
      {carregando ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : icone}
      {children}
    </button>
  )
}

/* ---------- Campos ---------- */

export function Campo({ rotulo, erro, dica, obrigatorio, className, children }: {
  rotulo: string
  erro?: string | null
  dica?: string
  obrigatorio?: boolean
  className?: string
  children: (props: { id: string; 'aria-invalid'?: boolean; 'aria-describedby'?: string; 'aria-required'?: boolean }) => ReactNode
}) {
  const id = useId()
  const descricao = erro ? `${id}-erro` : dica ? `${id}-dica` : undefined
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {rotulo}
        {obrigatorio && <span className="text-rose-500"> *</span>}
      </label>
      {children({ id, 'aria-invalid': erro ? true : undefined, 'aria-describedby': descricao, 'aria-required': obrigatorio || undefined })}
      {erro ? (
        <p id={`${id}-erro`} role="alert" className="mt-1 text-xs text-rose-600">{erro}</p>
      ) : dica ? (
        <p id={`${id}-dica`} className="mt-1 text-xs text-slate-500">{dica}</p>
      ) : null}
    </div>
  )
}

/* ---------- Modal ---------- */

export function Modal({ aberto, onFechar, titulo, subtitulo, largura = 'max-w-lg', children, rodape }: {
  aberto: boolean
  onFechar: () => void
  titulo: ReactNode
  subtitulo?: string
  largura?: string
  children: ReactNode
  rodape?: ReactNode
}) {
  const idTitulo = useId()
  const caixa = useRef<HTMLDivElement>(null)
  useDialogo(aberto, caixa, onFechar)

  if (!aberto) return null
  return createPortal(
    <div data-dialogo className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/60 p-4 sm:items-center" onMouseDown={(e) => e.target === e.currentTarget && onFechar()}>
      <div ref={caixa} role="dialog" tabIndex={-1} aria-modal="true" aria-labelledby={idTitulo} className={cn('my-8 w-full rounded-2xl bg-white shadow-2xl', largura)}>
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-4">
          <div>
            <h2 id={idTitulo} className="font-display text-lg font-semibold text-brand-800">{titulo}</h2>
            {subtitulo && <p className="mt-0.5 text-sm text-slate-500">{subtitulo}</p>}
          </div>
          <button data-fechar type="button" onClick={onFechar} aria-label="Fechar janela" className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
        {rodape && <div className="flex flex-wrap justify-end gap-3 border-t border-slate-100 px-6 py-4">{rodape}</div>}
      </div>
    </div>, document.body
  )
}

export function Confirmar({ aberto, titulo, mensagem, textoConfirmar = 'Confirmar', perigo, carregando, onConfirmar, onCancelar }: {
  aberto: boolean
  titulo: string
  mensagem: ReactNode
  textoConfirmar?: string
  perigo?: boolean
  carregando?: boolean
  onConfirmar: () => void
  onCancelar: () => void
}) {
  return (
    <Modal
      aberto={aberto}
      onFechar={onCancelar}
      titulo={titulo}
      largura="max-w-md"
      rodape={
        <>
          <Botao variante="secundario" onClick={onCancelar} disabled={carregando}>Voltar</Botao>
          <Botao variante={perigo ? 'perigo' : 'primario'} onClick={onConfirmar} carregando={carregando}>{textoConfirmar}</Botao>
        </>
      }
    >
      <div className="text-sm leading-relaxed text-slate-600">{mensagem}</div>
    </Modal>
  )
}

/* ---------- Avisos (toast) ---------- */

type Tipo = 'sucesso' | 'erro' | 'info'
interface Aviso { id: number; tipo: Tipo; texto: string }
interface Avisos { sucesso: (t: string) => void; erro: (e: unknown) => void; info: (t: string) => void }

const ContextoAvisos = createContext<Avisos | null>(null)

export function AvisosProvider({ children }: { children: ReactNode }) {
  const [lista, setLista] = useState<Aviso[]>([])
  const proximo = useRef(1)
  const mostrar = useCallback((tipo: Tipo, texto: string) => {
    const id = proximo.current++
    setLista((l) => [...l.slice(-3), { id, tipo, texto }])
    setTimeout(() => setLista((l) => l.filter((a) => a.id !== id)), tipo === 'erro' ? 8000 : 4500)
  }, [])
  const valor = useMemo<Avisos>(
    () => ({ sucesso: (t) => mostrar('sucesso', t), erro: (e) => mostrar('erro', mensagemDeErro(e)), info: (t) => mostrar('info', t) }),
    [mostrar],
  )
  const icones = { sucesso: CheckCircle2, erro: XCircle, info: Info } as const
  const cores = { sucesso: 'border-emerald-200 bg-emerald-50 text-emerald-800', erro: 'border-rose-200 bg-rose-50 text-rose-800', info: 'border-sky-200 bg-sky-50 text-sky-800' } as const
  return (
    <ContextoAvisos.Provider value={valor}>
      {children}
      {createPortal(<div data-avisos aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-full max-w-sm flex-col gap-2">
        {lista.map((a) => {
          const Icone = icones[a.tipo]
          return (
            <div key={a.id} role={a.tipo === 'erro' ? 'alert' : 'status'} className={cn('pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 text-sm shadow-lg', cores[a.tipo])}>
              <Icone className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
              <span className="flex-1">{a.texto}</span>
              <button type="button" aria-label="Dispensar aviso" onClick={() => setLista((l) => l.filter((x) => x.id !== a.id))}><X className="h-4 w-4 opacity-60" /></button>
            </div>
          )
        })}
      </div>, document.body)}
    </ContextoAvisos.Provider>
  )
}

export function useAvisos(): Avisos {
  const c = useContext(ContextoAvisos)
  if (!c) throw new Error('useAvisos precisa estar dentro de <AvisosProvider>')
  return c
}

/* ---------- Status, chips e alertas ---------- */

const COR_STATUS: Record<StatusPedido, string> = {
  em_aberto: 'bg-amber-100 text-amber-800',
  confirmado: 'bg-sky-100 text-sky-800',
  entregue: 'bg-emerald-100 text-emerald-800',
  cancelado: 'bg-rose-100 text-rose-700',
}
export const COR_DO_GRAFICO: Record<StatusPedido, string> = {
  em_aberto: 'var(--grafico-ambar)', confirmado: 'var(--grafico-ceu)', entregue: 'var(--grafico-verde)', cancelado: 'var(--grafico-rosa)',
}

export function ChipStatus({ status, className }: { status: StatusPedido; className?: string }) {
  return <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium', COR_STATUS[status], className)}>{STATUS_ROTULO[status]}</span>
}

export function Chip({ children, cor = 'slate', className }: { children: ReactNode; cor?: 'slate' | 'verde' | 'vermelho' | 'azul' | 'ambar' | 'roxo'; className?: string }) {
  const cores = {
    slate: 'bg-slate-100 text-slate-600', verde: 'bg-emerald-100 text-emerald-700', vermelho: 'bg-rose-100 text-rose-700',
    azul: 'bg-brand-100 text-brand-700', ambar: 'bg-amber-100 text-amber-800', roxo: 'bg-violet-100 text-violet-700',
  }
  return <span className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium', cores[cor], className)}>{children}</span>
}

export function Alerta({ tipo = 'info', titulo, children, className }: { tipo?: 'info' | 'aviso' | 'erro' | 'sucesso'; titulo?: string; children?: ReactNode; className?: string }) {
  const estilos = {
    info: 'border-sky-200 bg-sky-50 text-sky-900', aviso: 'border-amber-300 bg-amber-50 text-amber-900',
    erro: 'border-rose-200 bg-rose-50 text-rose-900', sucesso: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  }
  const Icone = tipo === 'erro' ? XCircle : tipo === 'sucesso' ? CheckCircle2 : tipo === 'aviso' ? AlertTriangle : Info
  return (
    <div role={tipo === 'erro' || tipo === 'aviso' ? 'alert' : 'status'} className={cn('flex gap-3 rounded-xl border px-4 py-3 text-sm', estilos[tipo], className)}>
      <Icone className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
      <div>
        {titulo && <p className="font-semibold">{titulo}</p>}
        {children && <div className={titulo ? 'mt-0.5' : ''}>{children}</div>}
      </div>
    </div>
  )
}

/* ---------- Estados de carregamento ---------- */

export function Carregando({ texto = 'Carregando…', className }: { texto?: string; className?: string }) {
  return (
    <div role="status" className={cn('flex items-center justify-center gap-2 py-12 text-sm text-slate-500', className)}>
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden /> {texto}
    </div>
  )
}

export function Vazio({ titulo, children, icone }: { titulo: string; children?: ReactNode; icone?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      {icone && <div className="text-slate-300">{icone}</div>}
      <p className="font-medium text-slate-600">{titulo}</p>
      {children && <div className="text-sm text-slate-500">{children}</div>}
    </div>
  )
}

export function ErroConsulta({ erro, onTentar }: { erro: unknown; onTentar?: () => void }) {
  return (
    <div className="p-6">
      <Alerta tipo="erro" titulo="Não foi possível carregar">
        {mensagemDeErro(erro)}
        {onTentar && <button type="button" onClick={onTentar} className="ml-2 font-medium underline">Tentar de novo</button>}
      </Alerta>
    </div>
  )
}

/* ---------- Estrutura de página ---------- */

export function Pagina_({ titulo, acoes, children }: { titulo: string; acoes?: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="font-display text-2xl font-semibold text-brand-900">{titulo}</h1>
        {acoes && <div className="flex flex-wrap items-center gap-2">{acoes}</div>}
      </div>
      {children}
    </div>
  )
}

export function Kpi({ titulo, valor, detalhe, icone, destaque }: { titulo: string; valor: ReactNode; detalhe?: ReactNode; icone: ReactNode; destaque?: 'azul' | 'verde' | 'ambar' | 'roxo' }) {
  const cores = { azul: 'bg-brand-100 text-brand-700', verde: 'bg-emerald-100 text-emerald-700', ambar: 'bg-amber-100 text-amber-700', roxo: 'bg-violet-100 text-violet-700' }
  return (
    <div className="cartao flex items-start gap-4 p-5">
      <div className={cn('rounded-xl p-3', cores[destaque ?? 'azul'])} aria-hidden>{icone}</div>
      <div className="min-w-0">
        <p className="text-sm text-slate-500">{titulo}</p>
        <p className="mt-0.5 truncate font-display text-2xl font-semibold text-slate-900">{valor}</p>
        {detalhe && <p className="mt-0.5 text-xs text-slate-500">{detalhe}</p>}
      </div>
    </div>
  )
}

/* ---------- Abas e paginação ---------- */

export function Abas<T extends string>({ itens, valor, onMudar, rotulo = 'Filtros' }: { itens: { id: T; rotulo: string; contagem?: number }[]; valor: T; onMudar: (id: T) => void; rotulo?: string }) {
  return (
    <div role="tablist" aria-label={rotulo} className="flex flex-wrap gap-2">
      {itens.map((i) => {
        const ativa = i.id === valor
        return (
          <button key={i.id} role="tab" aria-selected={ativa} tabIndex={ativa ? 0 : -1} aria-label={i.contagem !== undefined ? `${i.rotulo}: ${i.contagem}` : undefined} type="button" onClick={() => onMudar(i.id)}
            onKeyDown={(e) => {
              if (!['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(e.key)) return
              e.preventDefault()
              const atual = itens.findIndex((x) => x.id === i.id)
              const indice = e.key === 'Home' ? 0 : e.key === 'End' ? itens.length - 1 : (atual + (e.key === 'ArrowRight' ? 1 : -1) + itens.length) % itens.length
              const proximo = itens[indice]
              if (proximo) { onMudar(proximo.id); (e.currentTarget.parentElement?.children[indice] as HTMLElement)?.focus() }
            }}
            className={cn('inline-flex items-center gap-2 rounded-xl border px-4 py-2 text-sm font-medium transition-colors', ativa ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50')}>
            {i.rotulo}
            {i.contagem !== undefined && (
              <span className={cn('rounded-full px-2 py-0.5 text-xs', ativa ? 'bg-white/25 text-white' : 'bg-slate-100 text-slate-600')}>{i.contagem}</span>
            )}
          </button>
        )
      })}
    </div>
  )
}

export function Paginacao({ pagina, onMudar, rotulo = 'itens' }: { pagina: Pick<Pagina<unknown>, 'total' | 'limit' | 'offset'>; onMudar: (offset: number) => void; rotulo?: string }) {
  const { total, limit, offset } = pagina
  const atual = Math.floor(offset / limit) + 1
  const paginas = Math.max(1, Math.ceil(total / limit))
  const de = total === 0 ? 0 : offset + 1
  const ate = Math.min(offset + limit, total)
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 text-sm text-slate-500">
      <span>{total === 0 ? `Nenhum ${rotulo}` : `${de}–${ate} de ${total} ${rotulo}`}</span>
      {paginas > 1 && (
        <div className="flex items-center gap-2">
          <button type="button" aria-label="Página anterior" disabled={atual <= 1} onClick={() => onMudar(Math.max(0, offset - limit))} className="rounded-lg border border-slate-200 p-1.5 enabled:hover:bg-slate-50 disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button>
          <span>Página {atual} de {paginas}</span>
          <button type="button" aria-label="Próxima página" disabled={atual >= paginas} onClick={() => onMudar(offset + limit)} className="rounded-lg border border-slate-200 p-1.5 enabled:hover:bg-slate-50 disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button>
        </div>
      )}
    </div>
  )
}

export function Interruptor({ marcado, onChange, rotulo }: { marcado: boolean; onChange: (v: boolean) => void; rotulo: string }) {
  return (
    <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-slate-600">
      <input type="checkbox" checked={marcado} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 rounded border-slate-300 text-brand-600" />
      {rotulo}
    </label>
  )
}
