import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { periodoDoPreset } from '../lib/format'
import type { Analise } from '../lib/types'
import { pagina } from '../test/dados'
import { ADMIN, mockApi, renderizar } from '../test/utils'
import Relatorios from './Relatorios'

const ANALISE: Analise = {
  periodo: { inicio: '2026-10-01', fim: '2026-10-30' },
  agrupamento: 'dia',
  totais: { quantidade_pedidos: 3, produtos_vendidos: 6, valor_total: '175.00', comissao_a_receber: '5.89', comissao_pendente: '1.00' },
  serie: [{ inicio: '2026-10-28', pedidos: 3, faturamento: '175.00' }],
  pedidos_por_status: { em_aberto: 1, confirmado: 1, entregue: 2, cancelado: 1 },
  por_forma_pagamento: [{ id: null, nome: 'pix', quantidade: 2, valor: '120.00' }, { id: null, nome: 'dinheiro', quantidade: 1, valor: '55.00' }],
  por_vendedora: [
    { id_usuario: 3, nome: 'Joana', is_ativo: true, comissao_percentual: '5.00', quantidade_pedidos: 1, produtos_vendidos: 4, valor_total: '100.00', comissao_a_receber: '5.00', comissao_pendente: '0.00' },
    { id_usuario: 2, nome: 'Maria', is_ativo: true, comissao_percentual: '10.00', quantidade_pedidos: 2, produtos_vendidos: 2, valor_total: '75.00', comissao_a_receber: '0.89', comissao_pendente: '1.00' },
  ],
  top_produtos: [{ id: 1, nome: 'Saco 50L', quantidade: 5, valor: '50.00' }, { id: 2, nome: 'Saco 100L', quantidade: 3, valor: '125.00' }],
  top_clientes: [{ id: 8, nome: 'Bia Lima', quantidade: 1, valor: '100.00' }],
  por_bairro: [{ id: null, nome: 'Centro', quantidade: 2, valor: '75.00' }],
}
const VENDEDORAS = [
  { id_usuario: 2, nome: 'Maria', email: 'm@x.org', telefone: '16999990001', cargo: 'vendedora', comissao: '10.00', is_ativo: true },
  { id_usuario: 3, nome: 'Joana', email: 'j@x.org', telefone: '16999990002', cargo: 'vendedora', comissao: '5.00', is_ativo: true },
]

async function abrir(extra: Record<string, unknown> = {}) {
  const api = mockApi({
    'GET /relatorios/analise': { body: ANALISE },
    'GET /usuarios': { body: pagina(VENDEDORAS) },
    ...extra,
  } as Parameters<typeof mockApi>[0])
  await renderizar(<Relatorios />, { usuario: ADMIN })
  await screen.findByRole('region', { name: 'Vendas ao longo do tempo' })
  return api
}
const ultima = (api: Awaited<ReturnType<typeof abrir>>) => api.ultima('GET', '/relatorios/analise')?.query

describe('Relatórios: filtros mudam os gráficos', () => {
  it('inclui administradoras, filtra por cargo e limpa a responsável ao trocar de perfil', async () => {
    const api = await abrir({ 'GET /usuarios': { body: pagina([...VENDEDORAS, ADMIN]) } })
    await userEvent.selectOptions(await screen.findByLabelText('Responsável'), String(ADMIN.id_usuario))
    await waitFor(() => expect(ultima(api)?.get('id_vendedora')).toBe(String(ADMIN.id_usuario)))
    await userEvent.selectOptions(screen.getByLabelText('Perfil de usuário'), 'administradora')
    await waitFor(() => expect(ultima(api)?.get('cargo')).toBe('administradora'))
    expect(ultima(api)?.get('id_vendedora')).toBeNull()
    expect(api.ultima('GET', '/usuarios')?.query.get('cargo')).toBe('administradora')
    await userEvent.selectOptions(screen.getByLabelText('Perfil de usuário'), '')
    await waitFor(() => expect(ultima(api)?.get('cargo')).toBeNull())
  })

  it('exporta com o perfil de administradoras selecionado', async () => {
    const api = await abrir({ 'GET /relatorios/vendas/exportar': { texto: 'arquivo' } })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await userEvent.selectOptions(screen.getByLabelText('Perfil de usuário'), 'administradora')
    await userEvent.click(screen.getByRole('button', { name: 'Exportar CSV' }))
    await waitFor(() => expect(api.ultima('GET', '/relatorios/vendas/exportar')?.query.get('cargo')).toBe('administradora'))
  })

  it('começa com os últimos 30 dias, todas as vendedoras e agrupamento automático', async () => {
    const api = await abrir()
    const { inicio, fim } = periodoDoPreset('30')

    const q = ultima(api)
    expect(q?.get('data_inicio')).toBe(inicio)
    expect(q?.get('data_fim')).toBe(fim)
    expect(q?.get('id_vendedora')).toBeNull()
    expect(q?.get('agrupar')).toBeNull()
  })

  it.each([['7 dias', '7'], ['90 dias', '90'], ['Este ano', 'ano']])('"%s" busca o período novo', async (rotulo, preset) => {
    const api = await abrir()
    const antes = api.de('GET', '/relatorios/analise').length

    await userEvent.click(screen.getByRole('button', { name: rotulo }))

    const { inicio, fim } = periodoDoPreset(preset)
    await waitFor(() => expect(ultima(api)?.get('data_inicio')).toBe(inicio))
    expect(ultima(api)?.get('data_fim')).toBe(fim)
    expect(api.de('GET', '/relatorios/analise').length).toBeGreaterThan(antes)
    expect(screen.getByRole('button', { name: rotulo })).toHaveAttribute('aria-pressed', 'true')
  })

  it('escolher uma vendedora refaz os gráficos só com ela', async () => {
    const api = await abrir()

    await userEvent.selectOptions(await screen.findByLabelText('Responsável'), '3')

    await waitFor(() => expect(ultima(api)?.get('id_vendedora')).toBe('3'))
  })

  it('escolher o agrupamento manda para o servidor; "Automático" tira o parâmetro', async () => {
    const api = await abrir()

    await userEvent.selectOptions(screen.getByLabelText('Agrupar por'), 'mes')
    await waitFor(() => expect(ultima(api)?.get('agrupar')).toBe('mes'))

    await userEvent.selectOptions(screen.getByLabelText('Agrupar por'), '')
    await waitFor(() => expect(ultima(api)?.get('agrupar')).toBeNull())
  })

  it('datas livres também refazem a análise', async () => {
    const api = await abrir()

    const { fireEvent } = await import('@testing-library/react')
    fireEvent.change(screen.getByLabelText('Data inicial'), { target: { value: '2026-09-01' } })

    await waitFor(() => expect(ultima(api)?.get('data_inicio')).toBe('2026-09-01'))
    expect(screen.getByRole('button', { name: '30 dias' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('mais de um ano de período é barrado na tela', async () => {
    const api = await abrir()
    const antes = api.chamadas.length
    const { fireEvent } = await import('@testing-library/react')

    fireEvent.change(screen.getByLabelText('Data inicial'), { target: { value: '2024-01-01' } })

    expect(await screen.findByText('O período máximo é de 1 ano.')).toBeInTheDocument()
    await new Promise((r) => setTimeout(r, 50))
    expect(api.chamadas.length).toBe(antes)
  })
})

describe('Relatórios: conteúdo', () => {
  it('mostra os totais do período', async () => {
    await abrir()

    const kpi = (titulo: string) => screen.getByText(titulo, { selector: 'p' }).parentElement as HTMLElement
    expect(kpi('Faturamento')).toHaveTextContent('R$ 175,00')
    expect(kpi('Pedidos')).toHaveTextContent('3')
    expect(kpi('Produtos vendidos')).toHaveTextContent('6')
    expect(kpi('Comissões a receber')).toHaveTextContent('R$ 5,89')
    expect(kpi('Comissões a receber')).toHaveTextContent('+ R$ 1,00 pendentes')
  })

  it('tem um gráfico para cada análise, todos com descrição para leitores de tela', async () => {
    await abrir()

    for (const titulo of ['Vendas ao longo do tempo', 'Situação dos pedidos', 'Vendas por forma de pagamento', 'Vendas por responsável', 'Produtos mais vendidos', 'Clientes que mais compram', 'Vendas por bairro de entrega', 'Vendas e comissões por responsável'])
      expect(screen.getByRole('region', { name: titulo })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Vendas por dia: 3 pedidos/ })).toBeInTheDocument()
  })

  it('a tabela de comissões mostra cada vendedora e o total', async () => {
    await abrir()

    const regiao = screen.getByRole('region', { name: 'Vendas e comissões por responsável' })
    const maria = within(regiao).getByRole('row', { name: /Maria/ })
    expect(maria).toHaveTextContent('10%')
    expect(maria).toHaveTextContent('R$ 75,00')
    expect(maria).toHaveTextContent('R$ 0,89')
    expect(maria).toHaveTextContent('R$ 1,00')
    const total = within(regiao).getByRole('row', { name: /^Total/ })
    expect(total).toHaveTextContent('R$ 175,00')
    expect(total).toHaveTextContent('R$ 5,89')
  })

  it('alterna os produtos mais vendidos entre unidades e valor', async () => {
    await abrir()
    const regiao = screen.getByRole('region', { name: 'Produtos mais vendidos' })

    expect(within(regiao).getByRole('tab', { name: 'Unidades' })).toHaveAttribute('aria-selected', 'true')
    expect(within(regiao).getByRole('img').getAttribute('aria-label')).toMatch(/Saco 50L 5 un\..*Saco 100L 3 un\./)

    await userEvent.click(within(regiao).getByRole('tab', { name: 'Valor' }))

    expect(within(regiao).getByRole('img').getAttribute('aria-label')).toMatch(/Saco 100L R\$ 125,00.*Saco 50L R\$ 50,00/)
  })

  it('período sem vendas mostra os estados vazios, sem quebrar', async () => {
    const vazio: Analise = { ...ANALISE, totais: { ...ANALISE.totais, quantidade_pedidos: 0, produtos_vendidos: 0, valor_total: '0.00', comissao_a_receber: '0.00', comissao_pendente: '0.00' }, serie: [{ inicio: '2026-10-28', pedidos: 0, faturamento: '0.00' }], pedidos_por_status: { em_aberto: 0, confirmado: 0, entregue: 0, cancelado: 0 }, por_forma_pagamento: [], por_vendedora: [], top_produtos: [], top_clientes: [], por_bairro: [] }
    await abrir({ 'GET /relatorios/analise': { body: vazio } })

    expect(screen.getByText('Sem vendas neste período')).toBeInTheDocument()
    expect(screen.getByText('Sem vendas neste período.')).toBeInTheDocument() // tabela
    expect(screen.getAllByText('Sem dados neste período').length).toBeGreaterThan(0)
  })

  it('erro ao carregar oferece tentar de novo', async () => {
    mockApi({ 'GET /relatorios/analise': { status: 500, body: {} }, 'GET /usuarios': { body: pagina(VENDEDORAS) } })
    await renderizar(<Relatorios />, { usuario: ADMIN })

    expect(await screen.findByText('Não foi possível carregar')).toBeInTheDocument()
  })
})

describe('Relatórios: exportar', () => {
  it.each([['Exportar Excel', 'xlsx'], ['Exportar CSV', 'csv']])('"%s" baixa o arquivo com os mesmos filtros da tela', async (botao, formato) => {
    const api = await abrir({ 'GET /relatorios/vendas/exportar': { texto: 'conteudo', headers: { 'content-disposition': `attachment; filename="vendas_20261001_20261030.${formato}"` } } })
    let nome = ''
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) { nome = this.download })
    await userEvent.selectOptions(await screen.findByLabelText('Responsável'), '3')
    await userEvent.selectOptions(screen.getByLabelText('Agrupar por'), 'mes')
    await waitFor(() => expect(ultima(api)?.get('id_vendedora')).toBe('3'))

    await userEvent.click(screen.getByRole('button', { name: botao }))

    await waitFor(() => expect(api.de('GET', '/relatorios/vendas/exportar')).toHaveLength(1))
    const q = api.ultima('GET', '/relatorios/vendas/exportar')?.query
    expect(q?.get('formato')).toBe(formato)
    expect(q?.get('id_vendedora')).toBe('3')
    expect(q?.get('data_inicio')).toBe(periodoDoPreset('30').inicio)
    expect(q?.get('agrupar')).toBeNull() // o agrupamento só vale para os gráficos
    await waitFor(() => expect(nome).toBe(`vendas_20261001_20261030.${formato}`))
  })

  it('erro na exportação aparece como aviso', async () => {
    await abrir({ 'GET /relatorios/vendas/exportar': { status: 422, body: { detail: 'Período muito grande para exportar: reduza o intervalo.' } } })

    await userEvent.click(screen.getByRole('button', { name: 'Exportar Excel' }))

    expect(await screen.findByText('Período muito grande para exportar: reduza o intervalo.')).toBeInTheDocument()
  })
})
