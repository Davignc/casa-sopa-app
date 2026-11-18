import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { Analise, Dashboard } from '../lib/types'
import { pagina, pedido, produto } from '../test/dados'
import { ADMIN, mockApi, renderizar, VENDEDORA } from '../test/utils'
import Inicio from './Inicio'

const DASH: Dashboard = {
  periodo: { inicio: '2026-10-01', fim: '2026-10-30' }, total_pedidos: 3, produtos_vendidos: 6, faturamento: '175.00', comissoes: '5.89', comissoes_pendentes: '1.00',
  pedidos_por_status: { em_aberto: 1, confirmado: 1, entregue: 2, cancelado: 1 },
}
const ANALISE = { periodo: DASH.periodo, agrupamento: 'dia', totais: {}, serie: [{ inicio: '2026-10-28', pedidos: 3, faturamento: '175.00' }], pedidos_por_status: DASH.pedidos_por_status } as unknown as Analise
const BAIXO = produto(3, 'Rolo 30L', '8.00', 3)

const comuns = { 'GET /pedidos': { body: pagina([pedido(1), pedido(2, 'entregue')]) }, 'GET /estoque/alertas': { body: [BAIXO] } }

describe('Início: administradora', () => {
  async function abrir() {
    const api = mockApi({ ...comuns, 'GET /relatorios/dashboard': { body: DASH }, 'GET /relatorios/analise': { body: ANALISE } } as Parameters<typeof mockApi>[0])
    await renderizar(<Inicio />, { usuario: ADMIN })
    await screen.findByText('R$ 175,00')
    return api
  }

  it('cumprimenta pelo primeiro nome e mostra o resumo do mês', async () => {
    await abrir()

    expect(screen.getByRole('heading', { name: 'Olá, Ana!' })).toBeInTheDocument()
    const kpi = (titulo: string) => screen.getByText(titulo, { selector: 'p' }).parentElement as HTMLElement
    expect(kpi('Faturamento (30 dias)')).toHaveTextContent('R$ 175,00')
    expect(kpi('Pedidos vendidos')).toHaveTextContent('3')
    expect(kpi('Produtos vendidos')).toHaveTextContent('6')
    expect(kpi('Comissões a receber')).toHaveTextContent('R$ 5,89')
    expect(kpi('Comissões a receber')).toHaveTextContent('R$ 1,00')
  })

  it('mostra os gráficos de vendas e de situação dos pedidos', async () => {
    await abrir()

    expect(await screen.findByRole('img', { name: /Vendas por dia: 3 pedidos/ })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Situação dos pedidos' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Análise completa' })).toHaveAttribute('href', '/relatorios')
  })

  it('lista o estoque baixo e os últimos pedidos', async () => {
    await abrir()

    const estoque = await screen.findByRole('region', { name: 'Estoque baixo' })
    expect(estoque).toHaveTextContent('Rolo 30L')
    expect(estoque).toHaveTextContent('mín. 5')
    const ultimos = screen.getByRole('region', { name: 'Últimos pedidos' })
    expect(ultimos).toHaveTextContent('#1')
    expect(ultimos).toHaveTextContent('Ana Souza')
  })
})

describe('Início: vendedora', () => {
  it('NÃO consulta relatórios e mostra o andamento dos pedidos', async () => {
    const api = mockApi({ ...comuns, 'GET /pedidos/contagem': { body: { todos: 9, em_aberto: 4, confirmado: 3, entregue: 2, cancelado: 0 } } } as Parameters<typeof mockApi>[0])
    await renderizar(<Inicio />, { usuario: VENDEDORA })
    await screen.findByText('Pedidos em aberto')

    const kpi = (titulo: string) => screen.getByText(titulo, { selector: 'p' }).parentElement as HTMLElement
    await waitFor(() => expect(kpi('Pedidos em aberto')).toHaveTextContent('4'))
    expect(kpi('Confirmados')).toHaveTextContent('3')
    expect(kpi('Entregues')).toHaveTextContent('2')
    expect(api.chamadas.some((c) => c.caminho.startsWith('/relatorios'))).toBe(false)
    expect(screen.getByRole('heading', { name: 'Olá, Maria!' })).toBeInTheDocument()
  })

  it('tem atalhos para novo pedido, clientes e produtos', async () => {
    mockApi({ ...comuns, 'GET /pedidos/contagem': { body: { todos: 0, em_aberto: 0, confirmado: 0, entregue: 0, cancelado: 0 } } } as Parameters<typeof mockApi>[0])
    await renderizar(<Inicio />, { usuario: VENDEDORA })

    expect(await screen.findByRole('link', { name: 'Novo pedido' })).toHaveAttribute('href', '/pedidos/novo')
    expect(screen.getByRole('link', { name: 'Clientes' })).toHaveAttribute('href', '/clientes')
    expect(screen.getByRole('link', { name: 'Produtos' })).toHaveAttribute('href', '/produtos')
  })

  it('sem estoque baixo, diz que está tudo certo', async () => {
    mockApi({ ...comuns, 'GET /estoque/alertas': { body: [] }, 'GET /pedidos/contagem': { body: { todos: 0, em_aberto: 0, confirmado: 0, entregue: 0, cancelado: 0 } } } as Parameters<typeof mockApi>[0])
    await renderizar(<Inicio />, { usuario: VENDEDORA })

    expect(await screen.findByText('Tudo certo por aqui')).toBeInTheDocument()
  })
})
