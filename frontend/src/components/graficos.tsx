import { Area, Bar, BarChart, CartesianGrid, ComposedChart, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { moeda, numero, rotuloDoBalde, rotuloLongoDoBalde } from '../lib/format'
import type { Agrupamento } from '../lib/types'
import { Vazio } from './ui'

export const CORES = { azul: 'var(--grafico-azul)', azulClaro: '#93adff', verde: 'var(--grafico-verde)', rosa: 'var(--grafico-rosa)', ambar: 'var(--grafico-ambar)', roxo: 'var(--grafico-roxo)', ceu: 'var(--grafico-ceu)' }
export const PALETA = [CORES.azul, CORES.verde, CORES.ambar, CORES.roxo, CORES.ceu, CORES.rosa, 'var(--grafico-turquesa)', 'var(--grafico-cinza)']

const COMPACTO = new Intl.NumberFormat('pt-BR', { notation: 'compact', style: 'currency', currency: 'BRL', maximumFractionDigits: 1 })
const compactoMoeda = (v: number) => COMPACTO.format(v).replace(/\u00a0/g, ' ')
const inteiro = (v: number) => new Intl.NumberFormat('pt-BR').format(v)

const EIXO = { fontSize: 12, fill: '#64748b' }

function Moldura({ altura, rotulo, children }: { altura: number; rotulo: string; children: React.ReactNode }) {
  return (
    <div role="img" aria-label={rotulo} style={{ height: altura }} className="w-full">
      <ResponsiveContainer width="100%" height="100%" minWidth={0}>
        {children as React.ReactElement}
      </ResponsiveContainer>
    </div>
  )
}

interface PayloadTooltip { name?: string; value?: number | string; color?: string; payload?: Record<string, unknown> }

function CaixaTooltip({ active, payload, titulo, formatos }: { active?: boolean; payload?: PayloadTooltip[]; titulo?: (p: Record<string, unknown>) => string; formatos?: Record<string, (v: number) => string> }) {
  if (!active || !payload?.length) return null
  const base = payload[0]?.payload ?? {}
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-lg">
      {titulo && <p className="mb-1 font-semibold text-slate-700">{titulo(base)}</p>}
      {payload.map((p) => (
        <p key={String(p.name)} className="flex items-center gap-2 text-slate-600">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} aria-hidden />
          {p.name}: <b className="text-slate-900">{(formatos?.[String(p.name)] ?? String)(numero(p.value))}</b>
        </p>
      ))}
    </div>
  )
}

/* Vendas ao longo do tempo: faturamento (área) e pedidos (barras). */
export function GraficoSerie({ dados, agrupamento, altura = 300 }: { dados: { inicio: string; pedidos: number; faturamento: string }[]; agrupamento: Agrupamento; altura?: number }) {
  const total = dados.reduce((s, d) => s + d.pedidos, 0)
  if (total === 0) return <Vazio titulo="Sem vendas neste período">Confirme pedidos para ver o gráfico.</Vazio>
  const pontos = dados.map((d) => ({ inicio: d.inicio, rotulo: rotuloDoBalde(d.inicio, agrupamento), Faturamento: numero(d.faturamento), Pedidos: d.pedidos }))
  return (
    <Moldura altura={altura} rotulo={`Vendas por ${agrupamento}: ${total} pedidos`}>
      <ComposedChart data={pontos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gradFat" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={CORES.azul} stopOpacity={0.35} />
            <stop offset="95%" stopColor={CORES.azul} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="rotulo" tick={EIXO} tickLine={false} axisLine={{ stroke: '#cbd5e1' }} minTickGap={20} />
        <YAxis yAxisId="v" tick={EIXO} tickLine={false} axisLine={false} tickFormatter={compactoMoeda} width={62} />
        <YAxis yAxisId="p" orientation="right" tick={EIXO} tickLine={false} axisLine={false} allowDecimals={false} width={30} />
        <Tooltip content={<CaixaTooltip titulo={(p) => rotuloLongoDoBalde(String(p.inicio), agrupamento)} formatos={{ Faturamento: moeda, Pedidos: inteiro }} />} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        <Bar yAxisId="p" dataKey="Pedidos" fill={CORES.ambar} radius={[4, 4, 0, 0]} maxBarSize={22} opacity={0.85} />
        <Area yAxisId="v" type="monotone" dataKey="Faturamento" stroke={CORES.azul} strokeWidth={2.5} fill="url(#gradFat)" />
      </ComposedChart>
    </Moldura>
  )
}

/* Rosca com legenda (situação dos pedidos, formas de pagamento). */
export function GraficoRosca({ dados, altura = 240, formato = inteiro }: { dados: { nome: string; valor: number; cor?: string }[]; altura?: number; formato?: (v: number) => string }) {
  const visiveis = dados.filter((d) => d.valor > 0)
  const total = visiveis.reduce((s, d) => s + d.valor, 0)
  if (total === 0) return <Vazio titulo="Sem dados neste período" />
  return (
    <div>
      <Moldura altura={altura} rotulo={`Distribuição: ${visiveis.map((d) => `${d.nome} ${formato(d.valor)}`).join(', ')}`}>
        <PieChart>
          <Pie data={visiveis} dataKey="valor" nameKey="nome" innerRadius="58%" outerRadius="85%" paddingAngle={2} stroke="none">
            {visiveis.map((d, i) => <Cell key={d.nome} fill={d.cor ?? PALETA[i % PALETA.length]} />)}
          </Pie>
          <Tooltip content={<CaixaTooltip formatos={Object.fromEntries(visiveis.map((d) => [d.nome, formato]))} />} />
        </PieChart>
      </Moldura>
      <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-600">
        {visiveis.map((d, i) => (
          <li key={d.nome} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: d.cor ?? PALETA[i % PALETA.length] }} aria-hidden />
            <span className="truncate">{d.nome}</span>
            <b className="ml-auto text-slate-800">{formato(d.valor)}</b>
          </li>
        ))}
      </ul>
    </div>
  )
}

/* Ranking em barras horizontais (produtos, clientes, bairros, vendedoras). */
export function GraficoRanking({ dados, formato = moeda, cor = CORES.azul, rotuloSerie = 'Valor' }: { dados: { nome: string; valor: number }[]; formato?: (v: number) => string; cor?: string; rotuloSerie?: string }) {
  if (dados.length === 0) return <Vazio titulo="Sem dados neste período" />
  const altura = Math.max(120, dados.length * 38 + 20)
  return (
    <Moldura altura={altura} rotulo={`Ranking: ${dados.map((d) => `${d.nome} ${formato(d.valor)}`).join(', ')}`}>
      <BarChart data={dados} layout="vertical" margin={{ top: 0, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
        <XAxis type="number" tick={EIXO} tickLine={false} axisLine={false} tickFormatter={(v: number) => (formato === moeda ? compactoMoeda(v) : inteiro(v))} />
        <YAxis type="category" dataKey="nome" width={118} tick={EIXO} tickLine={false} axisLine={false} tickFormatter={(t: string) => (t.length > 17 ? `${t.slice(0, 16)}…` : t)} />
        <Tooltip cursor={{ fill: '#f1f5f9' }} content={<CaixaTooltip titulo={(p) => String(p.nome)} formatos={{ [rotuloSerie]: formato }} />} />
        <Bar dataKey="valor" name={rotuloSerie} fill={cor} radius={[0, 6, 6, 0]} barSize={20} />
      </BarChart>
    </Moldura>
  )
}

/* Entradas x saídas de estoque ao longo do tempo. */
export function GraficoMovimentacoes({ serie, agrupamento, altura = 260 }: { serie: { inicio: string; entradas: number; saidas: number }[]; agrupamento: Agrupamento; altura?: number }) {
  if (serie.every((p) => p.entradas === 0 && p.saidas === 0)) return <Vazio titulo="Sem movimentações neste período" />
  const pontos = serie.map((p) => ({ inicio: p.inicio, rotulo: rotuloDoBalde(p.inicio, agrupamento), Entradas: p.entradas, Saídas: p.saidas }))
  return (
    <Moldura altura={altura} rotulo="Entradas e saídas de estoque">
      <BarChart data={pontos} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="rotulo" tick={EIXO} tickLine={false} axisLine={{ stroke: '#cbd5e1' }} minTickGap={20} />
        <YAxis tick={EIXO} tickLine={false} axisLine={false} allowDecimals={false} width={40} />
        <Tooltip cursor={{ fill: '#f1f5f9' }} content={<CaixaTooltip titulo={(p) => rotuloLongoDoBalde(String(p.inicio), agrupamento)} formatos={{ Entradas: inteiro, Saídas: inteiro }} />} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="Entradas" fill={CORES.verde} radius={[4, 4, 0, 0]} maxBarSize={22} />
        <Bar dataKey="Saídas" fill={CORES.rosa} radius={[4, 4, 0, 0]} maxBarSize={22} />
      </BarChart>
    </Moldura>
  )
}
