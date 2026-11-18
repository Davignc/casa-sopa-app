import { useEffect, useState } from 'react'
export function useDebounce<T>(valor: T, atraso: number): T {
  const [atual, setAtual] = useState(valor)
  useEffect(() => { const t = setTimeout(() => setAtual(valor), atraso); return () => clearTimeout(t) }, [valor, atraso])
  return atual
}
