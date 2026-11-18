import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { cn } from './ui'

interface Valor {
  versao: number
  /** Chame depois de trocar a logo para todas as telas recarregarem a imagem. */
  atualizar: () => void
}

const Contexto = createContext<Valor>({ versao: 0, atualizar: () => {} })

export function LogoProvider({ children }: { children: ReactNode }) {
  const [versao, setVersao] = useState(() => Date.now())
  const atualizar = useCallback(() => setVersao(Date.now()), [])
  const valor = useMemo(() => ({ versao, atualizar }), [versao, atualizar])
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>
}

export const useLogo = () => useContext(Contexto)

export function urlDaLogo(versao: number) {
  return `/sistema/logo?v=${versao}`
}

export function Logo({ className, alt = 'Logo da Casa da Sopa de Restinga' }: { className?: string; alt?: string }) {
  const { versao } = useLogo()
  return <img src={urlDaLogo(versao)} alt={alt} className={cn('object-contain', className)} />
}
