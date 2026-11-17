import { useQuery } from '@tanstack/react-query'
import { Check, Search, X } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { api } from '../lib/api'
import { telefone } from '../lib/format'
import { useDebounce } from '../lib/hooks'
import type { ClienteResumo, Pagina } from '../lib/types'
import { Campo, cn } from './ui'

interface Props {
  valor: ClienteResumo | null
  onChange: (c: ClienteResumo | null) => void
  erro?: string | null
  desabilitado?: boolean
  rotulo?: string
}

/** Busca cliente por nome, telefone, código ou endereço (RF14 / tela de novo pedido). */
export function ClienteSelect({ valor, onChange, erro, desabilitado, rotulo = 'Cliente' }: Props) {
  const [texto, setTexto] = useState('')
  const [aberto, setAberto] = useState(false)
  const [ativo, setAtivo] = useState(0)
  const caixa = useRef<HTMLDivElement>(null)
  const idLista = useId()
  const termo = useDebounce(texto.trim(), 250)

  const consulta = useQuery({
    queryKey: ['clientes-busca', termo],
    queryFn: () => api<Pagina<ClienteResumo>>('/clientes', { query: { busca: termo, limit: 8 } }),
    enabled: aberto && !valor,
  })
  const itens = consulta.data?.itens ?? []

  useEffect(() => setAtivo(0), [termo])
  useEffect(() => {
    const fora = (e: MouseEvent) => !caixa.current?.contains(e.target as Node) && setAberto(false)
    document.addEventListener('mousedown', fora)
    return () => document.removeEventListener('mousedown', fora)
  }, [])

  function escolher(c: ClienteResumo) {
    onChange(c)
    setAberto(false)
    setTexto('')
  }

  function teclas(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setAberto(true); setAtivo((a) => aberto ? Math.max(0, Math.min(a + 1, itens.length - 1)) : 0) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setAtivo((a) => Math.max(a - 1, 0)) }
    else if (e.key === 'Enter' && aberto && itens[ativo]) { e.preventDefault(); escolher(itens[ativo]) }
    else if (e.key === 'Escape' && aberto) { e.preventDefault(); e.stopPropagation(); setAberto(false) }
    else if (e.key === 'Tab') setAberto(false)
  }

  return (
    <Campo rotulo={rotulo} obrigatorio erro={erro}>
      {(p) =>
        valor ? (
          <div className="flex items-center gap-3 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2">
            <Check className="h-5 w-5 shrink-0 text-emerald-600" aria-hidden />
            <div className="min-w-0 flex-1 text-sm">
              <p id={p.id} className="truncate font-medium text-slate-900">{valor.nome}</p>
              <p className="truncate text-xs text-slate-500">{telefone(valor.telefone)} · código #{valor.id_cliente}</p>
            </div>
            {!desabilitado && (
              <button type="button" aria-label="Trocar cliente" onClick={() => onChange(null)} className="rounded p-1.5 text-slate-500 hover:bg-white"><X className="h-4 w-4" /></button>
            )}
          </div>
        ) : (
          <div ref={caixa} className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
            <input {...p} role="combobox" aria-expanded={aberto} aria-controls={aberto ? idLista : undefined} aria-activedescendant={aberto && itens[ativo] ? `${idLista}-${itens[ativo].id_cliente}` : undefined} aria-autocomplete="list" autoComplete="off"
              className={cn('campo pl-9', erro && 'campo-erro')} placeholder="Buscar por nome, telefone, código ou endereço…" disabled={desabilitado}
              value={texto} onFocus={() => setAberto(true)} onChange={(e) => { setTexto(e.target.value); setAberto(true) }} onKeyDown={teclas} />
            {aberto && (
              <ul id={idLista} role="listbox" aria-label="Clientes encontrados" className="absolute z-20 mt-1 max-h-72 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl">
                {consulta.isFetching && <li className="px-4 py-3 text-sm text-slate-500">Buscando…</li>}
                {!consulta.isFetching && itens.length === 0 && <li className="px-4 py-3 text-sm text-slate-500">Nenhum cliente encontrado.</li>}
                {itens.map((c, i) => (
                  <li key={c.id_cliente} role="presentation">
                    <button id={`${idLista}-${c.id_cliente}`} tabIndex={-1} type="button" role="option" aria-selected={i === ativo} onMouseDown={(e) => e.preventDefault()} onMouseEnter={() => setAtivo(i)} onClick={() => escolher(c)}
                      className={cn('block w-full px-4 py-2.5 text-left', i === ativo ? 'bg-brand-50' : 'hover:bg-slate-50')}>
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="truncate text-sm font-medium text-slate-900">{c.nome}</span>
                        <span className="shrink-0 text-xs text-slate-500">#{c.id_cliente}</span>
                      </span>
                      <span className="block truncate text-xs text-slate-500">{telefone(c.telefone)}{c.endereco_principal ? ` · ${c.endereco_principal.endereco_formatado}` : ''}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      }
    </Campo>
  )
}
