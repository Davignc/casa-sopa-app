import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { pagina, produto, PROD_A } from '../test/dados'
import { ADMIN, mockApi, renderizar, VENDEDORA } from '../test/utils'
import Produtos from './Produtos'

const BAIXO = produto(3, 'Rolo 30L', '8.00', 3)
const INATIVO = produto(4, 'Cesto', '5.00', 10, { is_ativo: false })

function rotas(extra: Record<string, unknown> = {}) {
  return {
    'GET /produtos': ({ query }: { query: URLSearchParams }) => {
      if (query.get('apenas_alerta') === 'true') return { body: pagina([BAIXO]) }
      return { body: pagina(query.get('incluir_inativos') === 'true' ? [PROD_A, BAIXO, INATIVO] : [PROD_A, BAIXO]) }
    },
    'GET /estoque/alertas': { body: [BAIXO] },
    ...extra,
  } as Parameters<typeof mockApi>[0]
}
async function abrir(usuario = ADMIN, extra: Record<string, unknown> = {}) {
  const api = mockApi(rotas(extra))
  await renderizar(<Produtos />, { usuario })
  await screen.findByRole('row', { name: /Saco 50L/ })
  return api
}
const linha = (nome: RegExp) => screen.getByRole('row', { name: nome })

describe('Produtos: lista e alertas', () => {
  it('mostra nome, descrição, preço, estoque, mínimo e situação', async () => {
    await abrir()

    const l = linha(/Saco 50L/)
    expect(l).toHaveTextContent('Saco 50L (pacote)')
    expect(l).toHaveTextContent('R$ 10,00')
    expect(l).toHaveTextContent('100')
    expect(l).toHaveTextContent('Ativo')
  })

  it('destaca o estoque baixo na linha e num aviso no topo', async () => {
    await abrir()

    expect(await screen.findByText('1 produto com estoque baixo')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Rolo 30L (3)')
    expect(within(linha(/Rolo 30L/)).getByText('Baixo')).toBeInTheDocument()
    expect(within(linha(/Saco 50L/)).queryByText('Baixo')).not.toBeInTheDocument()
  })

  it('"Ver só esses" filtra pelo servidor', async () => {
    const api = await abrir()

    await userEvent.click(await screen.findByRole('button', { name: 'Ver só esses' }))

    await waitFor(() => expect(api.ultima('GET', '/produtos')?.query.get('apenas_alerta')).toBe('true'))
    expect(screen.getByLabelText('Só estoque baixo')).toBeChecked()
    await waitFor(() => expect(screen.queryByRole('row', { name: /Saco 50L/ })).not.toBeInTheDocument())
  })

  it('a busca e "mostrar inativos" vão para o servidor; inativo pode ser reativado', async () => {
    const api = await abrir(ADMIN, { 'POST /produtos/4/reativar': { body: { ...INATIVO, is_ativo: true } } })

    await userEvent.type(screen.getByLabelText('Buscar produtos'), 'rolo')
    await userEvent.click(screen.getByLabelText('Mostrar inativos'))

    await waitFor(() => {
      const q = api.ultima('GET', '/produtos')?.query
      expect(q?.get('busca')).toBe('rolo')
      expect(q?.get('incluir_inativos')).toBe('true')
    })
    await userEvent.clear(screen.getByLabelText('Buscar produtos'))
    const inativo = await screen.findByRole('row', { name: /Cesto/ })
    expect(inativo).toHaveTextContent('Inativo')
    expect(within(inativo).queryByRole('button', { name: /Registrar entrada/ })).not.toBeInTheDocument()

    await userEvent.click(within(inativo).getByRole('button', { name: 'Reativar Cesto' }))
    await waitFor(() => expect(api.de('POST', '/produtos/4/reativar')).toHaveLength(1))
  })

  it('preserva o foco e o clique de reativação enquanto a busca atualiza', async () => {
    const api = await abrir(ADMIN, { 'POST /produtos/4/reativar': { body: { ...INATIVO, is_ativo: true } } })
    const usuario = userEvent.setup()
    await usuario.click(screen.getByLabelText('Mostrar inativos'))
    const botao = await screen.findByRole('button', { name: 'Reativar Cesto' })

    await usuario.pointer({ target: botao, keys: '[MouseLeft>]' })
    // A busca pode atualizar entre pressionar e soltar o botão do mouse.
    fireEvent.change(screen.getByLabelText('Buscar produtos'), { target: { value: 'cesto' } })
    await waitFor(() => expect(api.ultima('GET', '/produtos')?.query.get('busca')).toBe('cesto'))

    expect(screen.getByRole('button', { name: 'Reativar Cesto' })).toBe(botao)
    expect(botao).toHaveFocus()
    await usuario.pointer({ keys: '[/MouseLeft]' })
    await waitFor(() => expect(api.de('POST', '/produtos/4/reativar')).toHaveLength(1))
  })
})

describe('Produtos: o que cada cargo vê', () => {
  it('a administradora tem entrada, saída e movimentações em cada produto', async () => {
    await abrir(ADMIN)

    const l = linha(/Saco 50L/)
    expect(within(l).getByRole('button', { name: 'Registrar entrada de Saco 50L' })).toBeInTheDocument()
    expect(within(l).getByRole('button', { name: 'Registrar saída de Saco 50L' })).toBeInTheDocument()
    expect(within(l).getByRole('link', { name: 'Ver movimentações de Saco 50L' })).toHaveAttribute('href', '/produtos/1/movimentacoes')
  })

  it('a vendedora gerencia o cadastro mas NÃO mexe no estoque nem vê o histórico', async () => {
    await abrir(VENDEDORA)

    const l = linha(/Saco 50L/)
    expect(within(l).getByRole('button', { name: 'Editar Saco 50L' })).toBeInTheDocument()
    expect(within(l).getByRole('button', { name: 'Inativar Saco 50L' })).toBeInTheDocument()
    expect(within(l).queryByRole('button', { name: /Registrar entrada/ })).not.toBeInTheDocument()
    expect(within(l).queryByRole('button', { name: /Registrar saída/ })).not.toBeInTheDocument()
    expect(within(l).queryByRole('link', { name: /movimentações/ })).not.toBeInTheDocument()
    expect(screen.getByText(/são da administradora/)).toBeInTheDocument()
  })
})

describe('Produtos: saída de estoque', () => {
  async function abrirSaida() {
    const api = await abrir(ADMIN, { 'POST /estoque/saidas': { status: 201, body: { movimentacao: {}, produto: { ...BAIXO, estoque_atual: 1 } } } })
    await userEvent.click(within(linha(/Rolo 30L/)).getByRole('button', { name: 'Registrar saída de Rolo 30L' }))
    return { api, dialogo: await screen.findByRole('dialog', { name: /Registrar saída/ }) }
  }

  it('mostra o produto e o estoque atual', async () => {
    const { dialogo } = await abrirSaida()

    expect(dialogo).toHaveTextContent('Rolo 30L · estoque atual: 3')
  })

  it('recusa saída maior que o estoque, sem chamar o servidor', async () => {
    const { api, dialogo } = await abrirSaida()

    await userEvent.type(within(dialogo).getByLabelText('Quantidade *'), '5')
    await userEvent.type(within(dialogo).getByLabelText('Motivo *'), 'Pacote rasgado')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Registrar saída' }))

    expect(await within(dialogo).findByText('Só há 3 em estoque.')).toBeInTheDocument()
    expect(api.de('POST', '/estoque/saidas')).toHaveLength(0)
  })

  it('exige o motivo', async () => {
    const { api, dialogo } = await abrirSaida()

    await userEvent.type(within(dialogo).getByLabelText('Quantidade *'), '1')
    await userEvent.type(within(dialogo).getByLabelText('Motivo *'), 'ab')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Registrar saída' }))

    expect(await within(dialogo).findByText('Explique o motivo (mín. 3 letras).')).toBeInTheDocument()
    expect(api.de('POST', '/estoque/saidas')).toHaveLength(0)
  })

  it('mostra como o estoque vai ficar e envia a saída com o motivo', async () => {
    const { api, dialogo } = await abrirSaida()

    await userEvent.type(within(dialogo).getByLabelText('Quantidade *'), '2')
    expect(dialogo).toHaveTextContent('O estoque ficará com 1 unidades.')
    await userEvent.type(within(dialogo).getByLabelText('Motivo *'), 'Pacote rasgado')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Registrar saída' }))

    await waitFor(() => expect(api.de('POST', '/estoque/saidas')).toHaveLength(1))
    expect(api.ultima('POST', '/estoque/saidas')?.corpo).toEqual({ id_produto: 3, quantidade: 2, motivo: 'Pacote rasgado' })
    expect(await screen.findByText('Saída registrada. Estoque agora: 1.')).toBeInTheDocument()
  })

  it.each(['0', '-1', '1.5', ''])('quantidade "%s" não é aceita', async (valor) => {
    const { api, dialogo } = await abrirSaida()

    if (valor) await userEvent.type(within(dialogo).getByLabelText('Quantidade *'), valor)
    await userEvent.type(within(dialogo).getByLabelText('Motivo *'), 'Perda')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Registrar saída' }))

    expect(await within(dialogo).findByText('Informe uma quantidade inteira, de 1 em diante.')).toBeInTheDocument()
    expect(api.de('POST', '/estoque/saidas')).toHaveLength(0)
  })
})

describe('Produtos: entrada de estoque', () => {
  async function abrirEntrada() {
    const api = await abrir(ADMIN, { 'POST /estoque/entradas': { status: 201, body: { movimentacao: {}, produto: { ...BAIXO, estoque_atual: 13 } } } })
    await userEvent.click(within(linha(/Rolo 30L/)).getByRole('button', { name: 'Registrar entrada de Rolo 30L' }))
    return { api, dialogo: await screen.findByRole('dialog', { name: 'Registrar entrada de estoque' }) }
  }

  it('envia a entrada como compra, com a observação', async () => {
    const { api, dialogo } = await abrirEntrada()

    await userEvent.type(within(dialogo).getByLabelText('Quantidade *'), '10')
    expect(dialogo).toHaveTextContent('O estoque ficará com 13 unidades.')
    await userEvent.type(within(dialogo).getByLabelText('Observação'), 'Compra do fornecedor X')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Registrar entrada' }))

    await waitFor(() => expect(api.de('POST', '/estoque/entradas')).toHaveLength(1))
    expect(api.ultima('POST', '/estoque/entradas')?.corpo).toEqual({ id_produto: 3, quantidade: 10, tipo: 'compra', observacao: 'Compra do fornecedor X' })
  })

  it('pode ser um ajuste manual e a observação é opcional', async () => {
    const { api, dialogo } = await abrirEntrada()

    await userEvent.type(within(dialogo).getByLabelText('Quantidade *'), '4')
    await userEvent.selectOptions(within(dialogo).getByLabelText('Origem'), 'ajuste_manual')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Registrar entrada' }))

    await waitFor(() => expect(api.de('POST', '/estoque/entradas')).toHaveLength(1))
    expect(api.ultima('POST', '/estoque/entradas')?.corpo).toEqual({ id_produto: 3, quantidade: 4, tipo: 'ajuste_manual' })
  })
})

describe('Produtos: cadastro e edição', () => {
  it('cadastro vazio mostra o que falta e não envia', async () => {
    const api = await abrir()

    await userEvent.click(screen.getByRole('button', { name: 'Novo produto' }))
    const dialogo = await screen.findByRole('dialog', { name: '+ Novo produto' })
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar produto' }))

    for (const msg of ['Informe o nome.', 'Informe a descrição.', 'Informe um preço válido (ex.: 25,90).']) expect(await within(dialogo).findByText(msg)).toBeInTheDocument()
    expect(api.de('POST', '/produtos')).toHaveLength(0)
  })

  it.each([
    ['25,90', '25.90'], ['25.90', '25.90'], ['1.250,00', '1250.00'], ['10', '10.00'],
  ])('preço digitado "%s" é enviado como %s (nunca 100x maior)', async (digitado, enviado) => {
    const api = await abrir(ADMIN, { 'POST /produtos': { status: 201, body: produto(9, 'Novo', enviado, 0) } })
    await userEvent.click(screen.getByRole('button', { name: 'Novo produto' }))
    const dialogo = await screen.findByRole('dialog', { name: '+ Novo produto' })

    await userEvent.type(within(dialogo).getByLabelText('Nome *'), 'Rolo 50L')
    await userEvent.type(within(dialogo).getByLabelText('Descrição *'), 'Pacote com 10')
    await userEvent.type(within(dialogo).getByLabelText('Preço (R$) *'), digitado)
    await userEvent.clear(within(dialogo).getByLabelText('Estoque inicial'))
    await userEvent.type(within(dialogo).getByLabelText('Estoque inicial'), '10')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar produto' }))

    await waitFor(() => expect(api.de('POST', '/produtos')).toHaveLength(1))
    expect(api.ultima('POST', '/produtos')?.corpo).toEqual({ nome: 'Rolo 50L', descricao: 'Pacote com 10', preco_unitario: enviado, estoque_minimo: 5, estoque_inicial: 10 })
  })

  it('preço inválido é recusado', async () => {
    const api = await abrir()
    await userEvent.click(screen.getByRole('button', { name: 'Novo produto' }))
    const dialogo = await screen.findByRole('dialog', { name: '+ Novo produto' })
    await userEvent.type(within(dialogo).getByLabelText('Nome *'), 'X')
    await userEvent.type(within(dialogo).getByLabelText('Descrição *'), 'Y')
    await userEvent.type(within(dialogo).getByLabelText('Preço (R$) *'), '12,345')

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar produto' }))

    expect(await within(dialogo).findByText('Informe um preço válido (ex.: 25,90).')).toBeInTheDocument()
    expect(api.de('POST', '/produtos')).toHaveLength(0)
  })

  it('editar: vem preenchido, não mexe no estoque e envia o preço certo', async () => {
    const api = await abrir(ADMIN, { 'PATCH /produtos/1': { body: PROD_A } })

    await userEvent.click(within(linha(/Saco 50L/)).getByRole('button', { name: 'Editar Saco 50L' }))
    const dialogo = await screen.findByRole('dialog', { name: 'Editar produto' })
    expect(within(dialogo).getByLabelText('Nome *')).toHaveValue('Saco 50L')
    expect(within(dialogo).getByLabelText('Preço (R$) *')).toHaveValue('10,00')
    expect(within(dialogo).queryByLabelText('Estoque inicial')).not.toBeInTheDocument()
    expect(dialogo).toHaveTextContent('muda só por entradas e saídas')

    await userEvent.clear(within(dialogo).getByLabelText('Preço (R$) *'))
    await userEvent.type(within(dialogo).getByLabelText('Preço (R$) *'), '12,50')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(api.de('PATCH', '/produtos/1')).toHaveLength(1))
    expect(api.ultima('PATCH', '/produtos/1')?.corpo).toEqual({ nome: 'Saco 50L', descricao: 'Saco 50L (pacote)', preco_unitario: '12.50', estoque_minimo: 5 })
  })

  it('inativar pede confirmação', async () => {
    const api = await abrir(ADMIN, { 'DELETE /produtos/1': { status: 204 } })

    await userEvent.click(within(linha(/Saco 50L/)).getByRole('button', { name: 'Inativar Saco 50L' }))
    const dialogo = await screen.findByRole('dialog', { name: 'Inativar produto?' })
    expect(api.de('DELETE', '/produtos/1')).toHaveLength(0)
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Inativar' }))

    await waitFor(() => expect(api.de('DELETE', '/produtos/1')).toHaveLength(1))
  })
})
