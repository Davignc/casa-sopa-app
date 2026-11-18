import { useEffect, useRef, type RefObject } from 'react'

const pilha: HTMLElement[] = []
const estadosOriginais = new Map<HTMLElement, boolean>()
let overflowOriginal = ''
const seletor = 'a[href], button:not(:disabled), input:not(:disabled):not([type="hidden"]), select:not(:disabled), textarea:not(:disabled), summary, [tabindex]:not([tabindex="-1"])'

function isolarDialogoAtual() {
  const atual = pilha.at(-1)
  const raiz = atual?.closest('[data-dialogo]') ?? atual
  for (const filho of document.body.children) {
    if (!(filho instanceof HTMLElement)) continue
    if (!estadosOriginais.has(filho)) estadosOriginais.set(filho, filho.inert)
    filho.inert = atual ? filho !== raiz && !filho.hasAttribute('data-avisos') : (estadosOriginais.get(filho) ?? false)
  }
  document.body.style.overflow = atual ? 'hidden' : overflowOriginal
  if (!atual) estadosOriginais.clear()
}

export function focarErros(formulario: HTMLFormElement) {
  // A validação atualiza o React antes de procurar o primeiro campo com erro.
  setTimeout(() => {
    if (!formulario.isConnected) return
    const erro = formulario.querySelector<HTMLElement>('[aria-invalid="true"], [role="alert"]')
    if (!erro) return
    if (!erro.matches('input, select, textarea, button, [tabindex]')) erro.tabIndex = -1
    erro.focus()
  }, 0)
}
export function useDialogo(aberto: boolean, caixa: RefObject<HTMLElement | null>, onFechar: () => void) {
  const fechar = useRef(onFechar)
  fechar.current = onFechar
  useEffect(() => {
    const elemento = caixa.current
    if (!aberto || !elemento) return
    const anterior = document.activeElement as HTMLElement | null
    if (!pilha.length) overflowOriginal = document.body.style.overflow
    pilha.push(elemento)
    isolarDialogoAtual()
    const focaveis = () => [...elemento.querySelectorAll<HTMLElement>(seletor)].filter((e) => !e.closest('[hidden], [inert], fieldset:disabled') && e.getAttribute('aria-hidden') !== 'true')
    const campos = focaveis()
    const primeiro = campos.find((e) => e.matches('input, select, textarea')) ?? campos.find((e) => !e.hasAttribute('data-fechar')) ?? campos[0] ?? elemento
    primeiro.focus()
    const tecla = (e: KeyboardEvent) => {
      if (pilha.at(-1) !== elemento || e.defaultPrevented) return
      if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); fechar.current(); return }
      if (e.key !== 'Tab') return
      const lista = focaveis(), primeiro = lista[0], ultimo = lista.at(-1)
      if (!primeiro || !ultimo) { e.preventDefault(); elemento.focus(); return }
      if (!elemento.contains(document.activeElement) || (e.shiftKey && document.activeElement === primeiro)) { e.preventDefault(); (e.shiftKey ? ultimo : primeiro).focus() }
      else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus() }
    }
    document.addEventListener('keydown', tecla)
    return () => {
      pilha.splice(pilha.indexOf(elemento), 1)
      document.removeEventListener('keydown', tecla)
      isolarDialogoAtual()
      if (anterior?.isConnected && !anterior.closest('[inert]')) anterior.focus()
    }
  }, [aberto, caixa])
}
