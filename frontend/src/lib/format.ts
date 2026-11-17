import type { Agrupamento, StatusPedido } from './types'
export const soDigitos = (v: string) => v.replace(/\D/g, '')
export const numero = (v: unknown) => Number(v ?? 0)
export const moeda = (v: unknown) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(numero(v)).replace(/\u00a0/g, ' ')
export const emailValido = (v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim())
export const telefoneValido = (v: string) => /^\d{10,11}$/.test(soDigitos(v))
export const cepValido = (v: string) => /^\d{8}$/.test(soDigitos(v))
export function mascaraTelefone(v: string) { const d = soDigitos(v).slice(0, 11); if (d.length <= 2) return d; const corte = d.length > 10 ? 7 : 6; return `(${d.slice(0, 2)}) ${d.slice(2, corte)}${d.length > corte ? `-${d.slice(corte)}` : ''}` }
export const telefone = mascaraTelefone
export function mascaraCep(v: string) { const d = soDigitos(v).slice(0, 8); return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d }
export const inicial = (v: string) => v.trim().charAt(0).toUpperCase()
export function lerPreco(v: string): number | null {
  const t = v.trim()
  if (!/^(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,2})?$/.test(t) && !/^\d+(?:\.\d{1,2})?$/.test(t)) return null
  const agrupado = /^\d{1,3}(?:\.\d{3})+$/.test(t)
  const valor = Number(t.includes(',') ? t.replace(/\./g, '').replace(',', '.') : agrupado ? t.replace(/\./g, '') : t)
  return Number.isFinite(valor) && valor >= 0 && valor <= 99999999.99 ? valor : null
}
export const STATUS_ROTULO: Record<StatusPedido, string> = { em_aberto: 'Em aberto', confirmado: 'Confirmado', entregue: 'Entregue', cancelado: 'Cancelado' }
export const TRANSICOES: Record<StatusPedido, StatusPedido[]> = { em_aberto: ['confirmado', 'cancelado'], confirmado: ['entregue', 'cancelado'], entregue: [], cancelado: [] }
export const FORMAS_PAGAMENTO = ['PIX', 'Dinheiro', 'Cartão de crédito', 'Cartão de débito', 'Transferência'] as const
export const formaPagamento = (v: string) => FORMAS_PAGAMENTO.find((f) => f.toLowerCase() === v.toLowerCase()) ?? v
export const TIPOS_LOGRADOURO = ['Rua', 'Avenida', 'Alameda', 'Travessa', 'Praça', 'Rodovia', 'Estrada', 'Outro']
export const dataDoDia = (v: string) => v ? v.slice(0, 10).split('-').reverse().join('/') : '—'
export const dataHora = (v: string | null | undefined) => v ? new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', timeZone: 'America/Sao_Paulo' }).format(new Date(v)).replace(',', '') : '—'
export const hoje = () => new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Sao_Paulo', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
export function somarDias(v: string, dias: number) { const d = new Date(`${v}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + dias); return d.toISOString().slice(0, 10) }
export const PRESETS = [{ id: '7', rotulo: '7 dias' }, { id: '30', rotulo: '30 dias' }, { id: '90', rotulo: '90 dias' }, { id: 'ano', rotulo: 'Este ano' }]
export function periodoDoPreset(preset: string) { const fim = hoje(); return { inicio: preset === 'ano' ? `${fim.slice(0, 4)}-01-01` : somarDias(fim, 1 - Number(preset)), fim } }
export const rotuloDoBalde = (v: string, a: Agrupamento) => a === 'mes' ? `${v.slice(5, 7)}/${v.slice(0, 4)}` : `${v.slice(8, 10)}/${v.slice(5, 7)}`
export const rotuloLongoDoBalde = (v: string, a: Agrupamento) => a === 'semana' ? `Semana de ${dataDoDia(v)}` : a === 'mes' ? rotuloDoBalde(v, a) : dataDoDia(v)
export function tamanho(v: number) { if (v < 1024) return `${v} B`; const formato = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 }); if (v < 1024 ** 2) return `${formato.format(v / 1024)} KB`; return `${formato.format(v / 1024 ** 2)} MB` }
