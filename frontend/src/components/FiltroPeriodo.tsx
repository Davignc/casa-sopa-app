import { useState } from 'react'
import { PRESETS, hoje, periodoDoPreset, somarDias } from '../lib/format'
import { cn } from './ui'

export interface ValorPeriodo {
  preset: string
  inicio: string
  fim: string
}

export const periodoInicial = (preset = '30'): ValorPeriodo => ({ preset, ...periodoDoPreset(preset) })

const MAX_DIAS = 366

/** Atalhos (7/30/90 dias, este ano) ou datas livres. Só avisa o pai quando o período é válido. */
export function FiltroPeriodo({ valor, onChange, className }: { valor: ValorPeriodo; onChange: (v: ValorPeriodo) => void; className?: string }) {
  const [inicio, setInicio] = useState(valor.inicio)
  const [fim, setFim] = useState(valor.fim)
  const [erro, setErro] = useState<string | null>(null)

  function aplicar(novoInicio: string, novoFim: string) {
    setInicio(novoInicio)
    setFim(novoFim)
    if (!novoInicio || !novoFim) return setErro(null)
    if (novoInicio > novoFim) return setErro('A data inicial não pode ser depois da final.')
    if (novoFim > hoje()) return setErro('A data final não pode estar no futuro.')
    if (novoFim > somarDias(novoInicio, MAX_DIAS - 1)) return setErro('O período máximo é de 1 ano.')
    setErro(null)
    onChange({ preset: 'custom', inicio: novoInicio, fim: novoFim })
  }

  return (
    <div className={cn('flex flex-wrap items-end gap-3', className)}>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Período">
        {PRESETS.map((p) => (
          <button key={p.id} type="button" aria-pressed={valor.preset === p.id}
            onClick={() => { const v = periodoInicial(p.id); setInicio(v.inicio); setFim(v.fim); setErro(null); onChange(v) }}
            className={cn('h-10 rounded-lg border px-3 text-sm font-medium transition-colors', valor.preset === p.id ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50')}>
            {p.rotulo}
          </button>
        ))}
      </div>
      <label className="text-xs text-slate-500">De
        <input type="date" aria-label="Data inicial" className="campo mt-1 h-10 w-40" value={inicio} max={fim || hoje()} onChange={(e) => aplicar(e.target.value, fim)} />
      </label>
      <label className="text-xs text-slate-500">até
        <input type="date" aria-label="Data final" className="campo mt-1 h-10 w-40" value={fim} max={hoje()} onChange={(e) => aplicar(inicio, e.target.value)} />
      </label>
      {erro && <p role="alert" className="basis-full text-xs text-rose-600">{erro}</p>}
    </div>
  )
}
