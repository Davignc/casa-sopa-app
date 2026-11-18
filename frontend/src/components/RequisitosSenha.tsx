import { Check, Circle } from 'lucide-react'
import { requisitosSenha } from '../lib/senha'
import { cn } from './ui'

export function RequisitosSenha({ senha, id }: { senha: string; id: string }) {
  const requisitos = requisitosSenha(senha)
  return (
    <div id={id} className="mt-2 text-xs text-slate-500">
      <p className="mb-1 font-medium">Requisitos da senha</p>
      <ul className="space-y-1">
        {requisitos.map(({ rotulo, atendido }) => (
          <li key={rotulo} className={cn('flex items-start gap-1.5', atendido && 'text-emerald-700')}>
            {atendido ? <Check className="h-3.5 w-3.5 shrink-0" aria-hidden /> : <Circle className="h-3.5 w-3.5 shrink-0" aria-hidden />}
            <span><span className="sr-only">{atendido ? 'Atendido: ' : 'Pendente: '}</span>{rotulo}</span>
          </li>
        ))}
      </ul>
      <p role="status" aria-live="polite" className="mt-2 font-medium">
        {senha ? (requisitos.every((r) => r.atendido) ? 'Senha atende aos requisitos.' : 'Senha ainda não atende aos requisitos.') : 'Preencha a senha para atender aos requisitos.'}
      </p>
    </div>
  )
}
