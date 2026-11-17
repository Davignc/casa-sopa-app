import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'

const CHAVE = 'casa-sopa-tema'
function preferencia(): boolean {
  try { const salvo = localStorage.getItem(CHAVE); if (salvo) return salvo === 'escuro' } catch { /* Sem armazenamento, usa a preferência do sistema. */ }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}
export function aplicarTema() { document.documentElement.classList.toggle('dark', preferencia()) }
export function Tema() {
  const [escuro, setEscuro] = useState(preferencia)
  useEffect(() => {
    const atualizar = () => { aplicarTema(); setEscuro(preferencia()) }
    atualizar()
    const sistema = window.matchMedia?.('(prefers-color-scheme: dark)')
    sistema?.addEventListener('change', atualizar)
    window.addEventListener('storage', atualizar)
    return () => { sistema?.removeEventListener('change', atualizar); window.removeEventListener('storage', atualizar) }
  }, [])
  function alternar() {
    const proximo = !escuro
    try { localStorage.setItem(CHAVE, proximo ? 'escuro' : 'claro') } catch { /* A preferência continua disponível nesta página. */ }
    document.documentElement.classList.toggle('dark', proximo)
    setEscuro(proximo)
  }
  return <button type="button" aria-label="Modo escuro" aria-pressed={escuro} title={escuro ? 'Ativar modo claro' : 'Ativar modo escuro'} onClick={alternar} className="inline-flex h-11 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700">{escuro ? <Sun aria-hidden className="h-5 w-5" /> : <Moon aria-hidden className="h-5 w-5" />}<span className="hidden sm:inline">{escuro ? 'Modo claro' : 'Modo escuro'}</span></button>
}
