import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { periodoDoPreset } from '../lib/format'
import type { Movimentacao } from '../lib/types'
import { pagina, produto } from '../test/dados'
import { ADMIN, mockApi, renderizar } from '../test/utils'
import MovimentacoesProduto from './MovimentacoesProduto'

const BAIXO = produto(3, 'Rolo 30L', '8.00', 3)
const mov = (id: number, extra: Partial<Movimentacao>): Movimentacao => ({
  id_movimentacao: id, id_produto: 3, nome_produto: 'Rolo 30L', tipo_movimentacao: 'entrada', quantidade: 1, tipo_referencia: 'compra',
  id_venda: null, observacao: null, data_movimentacao: '2026-10-28T12:00:00Z', ...extra,
})
const MOVS = [
  mov(1, { quantidade: 50, observacao: 'Estoque inicial [por Ana]', tipo_referencia: 'ajuste_manual' }),
  mov(2, { tipo_movimentacao: 'saida', quantidade: 7, tipo_referencia: 'venda', id_venda: 12, observacao: 'Pedido #12' }),
  mov(3, { tipo_movimentacao: 'entrada', quantidade: 20, tipo_referencia: 'compra' }),
]
const RESUMO = {
  periodo_inicio: '2026-10-01', periodo_fim: '2026-10-30', agrupamento: 'dia', total_entradas: 70, total_saidas: 7, saldo_do_periodo: 63,
  serie: [{ inicio: '2026-10-28', entradas: 70, saidas: 7 }],
}

function rotas(extra: Record<string, unknown> = {}) {
  return {
    'GET /produtos/3': { body: BAIXO },
    'GET /estoque/movimentacoes/resumo': { body: RESUMO },
    'GET /estoque/movimentacoes': ({ query }: { query: URLSearchParams }) => {
      const tipo = query.get('tipo')
      return { body: pagina(tipo ? MOVS.filter((m) => m.tipo_movimentacao === tipo) : MOVS) }
    },
    ...extra,
  } as Parameters<typeof mockApi>[0]
}
async function abrir(extra: Record<string, unknown> = {}) {
  const api = mockApi(rotas(extra))
  await renderizar(<MovimentacoesProduto />, { usuario: ADMIN, rota: '/produtos/3/movimentacoes', caminho: '/produtos/:id/movimentacoes' })
  await screen.findByRole('row', { name: /Pedido #12/ })
  return api
}

describe('Movimentações do produto', () => {
  it('mostra o produto, o estoque atual e o alerta', async () => {
    await abrir()

    expect(screen.getByRole('heading', { name: 'Movimentações: Rolo 30L' })).toBeInTheDocument()
    expect(screen.getByText('Estoque baixo')).toBeInTheDocument()
    expect(screen.getByText(/Em estoque agora:/).parentElement).toHaveTextContent('Mínimo: 5')
  })

  it('começa nos últimos 30 dias, para este produto, na tabela e no gráfico', async () => {
    const api = await abrir()
    const { inicio, fim } = periodoDoPreset('30')

    for (const caminho of ['/estoque/movimentacoes', '/estoque/movimentacoes/resumo']) {
      const q = api.ultima('GET', caminho)?.query
      expect(q?.get('id_produto')).toBe('3')
      expect(q?.get('data_inicio')).toBe(inicio)
      expect(q?.get('data_fim')).toBe(fim)
    }
  })

  it('mostra os totais do período', async () => {
    await abrir()

    const cartoes = screen.getAllByText(/Entradas no período|Saídas no período|Saldo do período/).map((e) => e.parentElement?.textContent)
    expect(cartoes.join('|')).toContain('Entradas no período70')
    expect(cartoes.join('|')).toContain('Saídas no período7')
    expect(cartoes.join('|')).toContain('Saldo do período+63')
  })

  it('a tabela mostra tipo, quantidade com sinal e a origem, com link para o pedido', async () => {
    await abrir()

    expect(screen.getByRole('row', { name: /Entrada.*\+50.*Ajuste manual/ })).toBeInTheDocument()
    const venda = screen.getByRole('row', { name: /Pedido #12/ })
    expect(venda).toHaveTextContent('Saída')
    expect(venda).toHaveTextContent('−7')
    expect(within(venda).getByRole('link', { name: 'Pedido #12' })).toHaveAttribute('href', '/pedidos/12/editar')
    expect(screen.getByRole('row', { name: /\+20.*Compra \/ recebimento/ })).toBeInTheDocument()
  })

  it('trocar o período atualiza a tabela E o gráfico', async () => {
    const api = await abrir()
    const antesLista = api.de('GET', '/estoque/movimentacoes').length
    const antesResumo = api.de('GET', '/estoque/movimentacoes/resumo').length

    await userEvent.click(screen.getByRole('button', { name: '7 dias' }))

    const { inicio } = periodoDoPreset('7')
    await waitFor(() => expect(api.ultima('GET', '/estoque/movimentacoes')?.query.get('data_inicio')).toBe(inicio))
    await waitFor(() => expect(api.ultima('GET', '/estoque/movimentacoes/resumo')?.query.get('data_inicio')).toBe(inicio))
    expect(api.de('GET', '/estoque/movimentacoes').length).toBeGreaterThan(antesLista)
    expect(api.de('GET', '/estoque/movimentacoes/resumo').length).toBeGreaterThan(antesResumo)
    expect(screen.getByRole('button', { name: '7 dias' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('aceita datas livres', async () => {
    const api = await abrir()

    fireEvent.change(screen.getByLabelText('Data inicial'), { target: { value: '2026-09-01' } })

    await waitFor(() => expect(api.ultima('GET', '/estoque/movimentacoes')?.query.get('data_inicio')).toBe('2026-09-01'))
    expect(api.ultima('GET', '/estoque/movimentacoes/resumo')?.query.get('data_inicio')).toBe('2026-09-01')
  })

  it('período invertido avisa e não consulta o servidor com ele', async () => {
    const api = await abrir()
    const antes = api.chamadas.length

    fireEvent.change(screen.getByLabelText('Data inicial'), { target: { value: '2999-01-01' } })

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await new Promise((r) => setTimeout(r, 50))
    expect(api.chamadas.length).toBe(antes)
  })

  it('o filtro de tipo vale para a tabela, mas o gráfico continua mostrando entradas e saídas', async () => {
    const api = await abrir()

    await userEvent.click(screen.getByRole('tab', { name: 'Saídas' }))

    await waitFor(() => expect(api.ultima('GET', '/estoque/movimentacoes')?.query.get('tipo')).toBe('saida'))
    expect(api.ultima('GET', '/estoque/movimentacoes/resumo')?.query.get('tipo')).toBeNull()
    await waitFor(() => expect(screen.queryByRole('row', { name: /\+20/ })).not.toBeInTheDocument())
    expect(screen.getByRole('row', { name: /Pedido #12/ })).toBeInTheDocument()
  })

  it('o gráfico tem descrição para leitores de tela', async () => {
    await abrir()

    expect(await screen.findByRole('img', { name: 'Entradas e saídas de estoque' })).toBeInTheDocument()
  })

  it('sem movimentações no filtro, orienta a mudar o período', async () => {
    mockApi(rotas({ 'GET /estoque/movimentacoes': { body: pagina([]) }, 'GET /estoque/movimentacoes/resumo': { body: { ...RESUMO, total_entradas: 0, total_saidas: 0, saldo_do_periodo: 0, serie: [{ inicio: '2026-10-28', entradas: 0, saidas: 0 }] } } }))
    await renderizar(<MovimentacoesProduto />, { usuario: ADMIN, rota: '/produtos/3/movimentacoes', caminho: '/produtos/:id/movimentacoes' })

    expect(await screen.findByText('Nenhuma movimentação neste filtro')).toBeInTheDocument()
    expect(screen.getByText('Sem movimentações neste período')).toBeInTheDocument()
  })

  it('produto inexistente mostra o erro', async () => {
    mockApi(rotas({ 'GET /produtos/3': { status: 404, body: { detail: 'Produto não encontrado.' } } }))
    await renderizar(<MovimentacoesProduto />, { usuario: ADMIN, rota: '/produtos/3/movimentacoes', caminho: '/produtos/:id/movimentacoes' })

    expect(await screen.findByText('Produto não encontrado.')).toBeInTheDocument()
  })

  it('tem atalhos para registrar entrada e saída', async () => {
    await abrir()

    await userEvent.click(screen.getByRole('button', { name: 'Entrada' }))

    expect(await screen.findByRole('dialog', { name: 'Registrar entrada de estoque' })).toBeInTheDocument()
  })
})
