import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { CLIENTE_RESUMO, pagina, pedido } from '../test/dados'
import { mockApi, renderizar, VENDEDORA } from '../test/utils'
import Pedidos from './Pedidos'

const LISTA = [
  pedido(1, 'em_aberto', { valor_total: '39.00' }),
  pedido(2, 'confirmado', { valor_total: '36.00', forma_pagamento: 'dinheiro' }),
  pedido(3, 'entregue', { valor_total: '44.00' }),
  pedido(4, 'cancelado', { valor_total: '40.00' }),
]
const CONTAGEM = { todos: 4, em_aberto: 1, confirmado: 1, entregue: 1, cancelado: 1 }

function rotas(extra: Record<string, unknown> = {}) {
  return {
    'GET /pedidos': ({ query }: { query: URLSearchParams }) => {
      const status = query.get('status')
      const itens = status ? LISTA.filter((p) => p.status === status) : LISTA
      return { body: pagina(itens) }
    },
    'GET /pedidos/contagem': { body: CONTAGEM },
    ...extra,
  } as Parameters<typeof mockApi>[0]
}

async function abrir(extra: Record<string, unknown> = {}) {
  const api = mockApi(rotas(extra))
  await renderizar(<Pedidos />, { usuario: VENDEDORA })
  await screen.findByRole('row', { name: /#1 / })
  return api
}
const linha = (n: number) => screen.getByRole('row', { name: new RegExp(`#${n} `) })
const botao = (nome: string) => screen.getByRole('button', { name: nome })

describe('Pedidos: lista', () => {
  it('mostra cada pedido com cliente, pagamento, data, vendedora, situação e total', async () => {
    await abrir()

    const l = linha(2)
    expect(l).toHaveTextContent('Ana Souza')
    expect(l).toHaveTextContent('Dinheiro')
    expect(l).toHaveTextContent('28/10 09:00')
    expect(l).toHaveTextContent('Maria Vendedora')
    expect(l).toHaveTextContent('R$ 36,00')
    expect(within(linha(3)).getByText('Entregue')).toBeInTheDocument()
  })

  it('as abas mostram a contagem de cada situação', async () => {
    await abrir()

    expect(await screen.findByRole('tab', { name: 'Todos: 4' })).toBeInTheDocument()
    for (const nome of ['Em aberto: 1', 'Confirmado: 1', 'Entregue: 1', 'Cancelado: 1']) expect(screen.getByRole('tab', { name: nome })).toBeInTheDocument()
  })

  it('clicar numa aba filtra pela situação no servidor', async () => {
    const api = await abrir()

    await userEvent.click(screen.getByRole('tab', { name: /^Confirmado/ }))

    await waitFor(() => expect(api.ultima('GET', '/pedidos')?.query.get('status')).toBe('confirmado'))
    await waitFor(() => expect(screen.queryByRole('row', { name: /#1 / })).not.toBeInTheDocument())
    expect(linha(2)).toBeInTheDocument()
  })

  it('a busca e as datas valem para a lista e para a contagem das abas', async () => {
    const api = await abrir()

    await userEvent.type(screen.getByLabelText('Buscar pedidos'), 'ana')
    fireEvent.change(screen.getByLabelText('Data inicial'), { target: { value: '2026-10-01' } })
    fireEvent.change(screen.getByLabelText('Data final'), { target: { value: '2026-10-31' } })

    await waitFor(() => {
      const q = api.ultima('GET', '/pedidos/contagem')?.query
      expect(q?.get('busca')).toBe('ana')
      expect(q?.get('data_inicio')).toBe('2026-10-01')
      expect(q?.get('data_fim')).toBe('2026-10-31')
    })
    expect(api.ultima('GET', '/pedidos')?.query.get('busca')).toBe('ana')
  })

  it('avisa quando a data inicial é depois da final e não consulta o servidor com isso', async () => {
    const api = await abrir()
    const antes = api.de('GET', '/pedidos').length

    fireEvent.change(screen.getByLabelText('Data inicial'), { target: { value: '2026-10-20' } })
    fireEvent.change(screen.getByLabelText('Data final'), { target: { value: '2026-10-10' } })

    expect(await screen.findByText('A data inicial não pode ser depois da final.')).toBeInTheDocument()
    await new Promise((r) => setTimeout(r, 100))
    expect(api.de('GET', '/pedidos').every((c) => !(c.query.get('data_inicio') === '2026-10-20' && c.query.get('data_fim') === '2026-10-10'))).toBe(true)
    expect(api.de('GET', '/pedidos').length).toBeGreaterThanOrEqual(antes)
  })

  it('lista vazia mostra orientação', async () => {
    mockApi(rotas({ 'GET /pedidos': { body: pagina([]) }, 'GET /pedidos/contagem': { body: { todos: 0, em_aberto: 0, confirmado: 0, entregue: 0, cancelado: 0 } } }))
    await renderizar(<Pedidos />, { usuario: VENDEDORA })

    expect(await screen.findByText('Nenhum pedido encontrado')).toBeInTheDocument()
    expect(screen.getByText(/Novo pedido/, { selector: 'div' })).toBeInTheDocument()
  })

  it('erro ao carregar oferece tentar de novo', async () => {
    mockApi(rotas({ 'GET /pedidos': { status: 500, body: {} } }))
    await renderizar(<Pedidos />, { usuario: VENDEDORA })

    expect(await screen.findByText('Não foi possível carregar')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Tentar de novo' })).toBeInTheDocument()
  })
})

describe('Pedidos: ações do pedido selecionado', () => {
  it('sem seleção, as ações ficam desabilitadas', async () => {
    await abrir()

    for (const nome of ['Alterar', 'Cancelar', 'Excluir', 'Imprimir']) expect(botao(nome)).toBeDisabled()
  })

  it.each([
    [1, { Alterar: true, Cancelar: true, Excluir: true, Imprimir: true }],
    [2, { Alterar: true, Cancelar: true, Excluir: false, Imprimir: true }],
    [3, { Alterar: false, Cancelar: false, Excluir: false, Imprimir: true }],
    [4, { Alterar: false, Cancelar: false, Excluir: false, Imprimir: false }],
  ])('pedido #%i habilita só o que a regra permite', async (id, esperado) => {
    await abrir()

    await userEvent.click(linha(id))

    for (const [nome, ligado] of Object.entries(esperado)) {
      if (ligado) expect(botao(nome)).toBeEnabled()
      else expect(botao(nome)).toBeDisabled()
    }
    expect(within(linha(id)).getByRole('button', { name: `Selecionar pedido ${id}` })).toHaveAttribute('aria-pressed', 'true')
  })

  it('clicar de novo na linha tira a seleção', async () => {
    await abrir()
    await userEvent.click(linha(1))
    await userEvent.click(linha(1))

    expect(botao('Alterar')).toBeDisabled()
  })

  it('só pedido que ainda pode mudar tem seletor de situação', async () => {
    await abrir()

    expect(within(linha(1)).getByRole('combobox', { name: 'Situação do pedido 1' })).toBeInTheDocument()
    expect(within(linha(2)).getByRole('combobox', { name: 'Situação do pedido 2' })).toBeInTheDocument()
    expect(within(linha(3)).queryByRole('combobox')).not.toBeInTheDocument()
    expect(within(linha(4)).queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('o seletor oferece só as transições permitidas', async () => {
    await abrir()

    const emAberto = within(linha(1)).getByRole('combobox')
    const confirmado = within(linha(2)).getByRole('combobox')

    expect(within(emAberto).getAllByRole('option').map((o) => o.textContent)).toEqual(['Em aberto', 'Confirmado', 'Cancelado'])
    expect(within(confirmado).getAllByRole('option').map((o) => o.textContent)).toEqual(['Confirmado', 'Entregue', 'Cancelado'])
  })
})

describe('Pedidos: mudar a situação', () => {
  it('confirmar pede confirmação, avisa que baixa o estoque e envia só o novo status', async () => {
    const api = await abrir({ 'POST /pedidos/1/status': { body: pedido(1, 'confirmado') } })

    await userEvent.selectOptions(within(linha(1)).getByRole('combobox'), 'confirmado')

    const dialogo = await screen.findByRole('dialog', { name: 'Confirmar o pedido #1?' })
    expect(dialogo).toHaveTextContent('estoque')
    expect(dialogo).toHaveTextContent('baixado')
    expect(api.de('POST', '/pedidos/1/status')).toHaveLength(0) // ainda não enviou

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Confirmar pedido' }))

    await waitFor(() => expect(api.de('POST', '/pedidos/1/status')).toHaveLength(1))
    expect(api.ultima('POST', '/pedidos/1/status')?.corpo).toEqual({ status: 'confirmado' })
    expect(await screen.findByText('Pedido #1: confirmado.')).toBeInTheDocument()
  })

  it('cancelar um pedido confirmado avisa que o estoque volta', async () => {
    const api = await abrir({ 'POST /pedidos/2/status': { body: pedido(2, 'cancelado') } })

    await userEvent.click(linha(2))
    await userEvent.click(botao('Cancelar'))

    const dialogo = await screen.findByRole('dialog', { name: 'Cancelar o pedido #2?' })
    expect(dialogo).toHaveTextContent('volta para a prateleira')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cancelar pedido' }))
    await waitFor(() => expect(api.ultima('POST', '/pedidos/2/status')?.corpo).toEqual({ status: 'cancelado' }))
  })

  it('cancelar um pedido em aberto não fala em estoque', async () => {
    await abrir()

    await userEvent.selectOptions(within(linha(1)).getByRole('combobox'), 'cancelado')

    const dialogo = await screen.findByRole('dialog', { name: 'Cancelar o pedido #1?' })
    expect(dialogo).not.toHaveTextContent('prateleira')
    expect(dialogo).toHaveTextContent('não pode ser reaberto')
  })

  it('marcar como entregue avisa que é definitivo', async () => {
    await abrir()

    await userEvent.selectOptions(within(linha(2)).getByRole('combobox'), 'entregue')

    expect(await screen.findByRole('dialog', { name: 'Entregar o pedido #2?' })).toHaveTextContent('não pode mais ser alterado')
  })

  it('"Voltar" desiste sem chamar o servidor', async () => {
    const api = await abrir()
    await userEvent.selectOptions(within(linha(1)).getByRole('combobox'), 'confirmado')

    await userEvent.click(await screen.findByRole('button', { name: 'Voltar' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(api.de('POST', '/pedidos/1/status')).toHaveLength(0)
  })

  it('falta de estoque: mostra o que o servidor explicou e nada muda', async () => {
    await abrir({ 'POST /pedidos/1/status': { status: 409, body: { detail: 'Não dá para confirmar: «Saco 100L» (disponível 2, pedido 3).' } } })

    await userEvent.selectOptions(within(linha(1)).getByRole('combobox'), 'confirmado')
    await userEvent.click(await screen.findByRole('button', { name: 'Confirmar pedido' }))

    expect(await screen.findByText(/«Saco 100L» \(disponível 2, pedido 3\)/)).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('Pedidos: excluir, imprimir, histórico', () => {
  it('excluir pede confirmação e só vale para pedido em aberto', async () => {
    const api = await abrir({ 'DELETE /pedidos/1': { status: 204 } })

    await userEvent.click(linha(1))
    await userEvent.click(botao('Excluir'))
    const dialogo = await screen.findByRole('dialog', { name: 'Excluir o pedido #1?' })
    expect(dialogo).toHaveTextContent('cancele em vez de excluir')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Excluir' }))

    await waitFor(() => expect(api.de('DELETE', '/pedidos/1')).toHaveLength(1))
    expect(await screen.findByText('Pedido excluído.')).toBeInTheDocument()
  })

  it('"Imprimir" abre as opções do cupom do pedido selecionado', async () => {
    await abrir()

    await userEvent.click(linha(2))
    await userEvent.click(botao('Imprimir'))

    expect(await screen.findByRole('dialog', { name: 'Cupom do pedido #2' })).toBeInTheDocument()
  })

  it('"Novo pedido" leva ao formulário', async () => {
    await abrir()

    expect(screen.getByRole('link', { name: /Novo pedido/ })).toHaveAttribute('href', '/pedidos/novo')
  })

  it('"Histórico de compras" mostra os pedidos de um cliente escolhido', async () => {
    const api = await abrir({
      'GET /clientes': { body: pagina([CLIENTE_RESUMO]) },
    })
    const original = api.chamadas.length

    await userEvent.click(botao('Histórico de compras'))
    const dialogo = await screen.findByRole('dialog', { name: 'Histórico de compras' })
    await userEvent.type(within(dialogo).getByRole('combobox'), 'ana')
    await userEvent.click(await within(dialogo).findByRole('option', { name: /Ana Souza/ }))

    await waitFor(() => expect(api.chamadas.slice(original).some((c) => c.caminho === '/pedidos' && c.query.get('id_cliente') === '7')).toBe(true))
    expect(await within(dialogo).findByText(/pedidos? · total em compras/)).toBeInTheDocument()
    void vi
  })
})
