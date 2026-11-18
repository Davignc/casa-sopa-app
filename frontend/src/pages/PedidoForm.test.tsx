import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { CLIENTE, CLIENTE_RESUMO, END1, endereco, pagina, PROD_A, PROD_B, pedido } from '../test/dados'
import { mockApi, renderizar, VENDEDORA } from '../test/utils'
import PedidoForm, { totalEmCentavos } from './PedidoForm'

const BASE = {
  'GET /produtos': { body: pagina([PROD_A, PROD_B]) },
  'GET /clientes': { body: pagina([CLIENTE_RESUMO]) },
  'GET /clientes/7': { body: CLIENTE },
}

async function novo(extra: Record<string, never> | Record<string, unknown> = {}) {
  const api = mockApi({ ...BASE, ...extra } as Parameters<typeof mockApi>[0])
  await renderizar(<PedidoForm />, { usuario: VENDEDORA, rota: '/pedidos/novo', caminho: '/pedidos/novo' })
  await screen.findByRole('option', { name: /Saco 50L/ }) // a lista de produtos chega depois da tela
  return api
}

async function escolherCliente() {
  await userEvent.type(screen.getByPlaceholderText(/Buscar por nome, telefone/), 'ana')
  await userEvent.click(await screen.findByRole('option', { name: /Ana Souza/ }))
  await screen.findByRole('radio', { name: /Rua 1, 1/ })
}

async function adicionar(produto: string, qtd: string) {
  await userEvent.selectOptions(screen.getByLabelText('Produto'), produto)
  const q = screen.getByLabelText('Qtd.')
  await userEvent.clear(q)
  await userEvent.type(q, qtd)
  await userEvent.click(screen.getByRole('button', { name: 'Adicionar item' }))
}

describe('totalEmCentavos', () => {
  it('soma em centavos, sem erro de ponto flutuante', () => {
    const preco = (id: number) => ({ 1: '0.10', 2: '0.20', 3: '33.33' })[id as 1]
    expect(totalEmCentavos([{ id_produto: 1, nome: '', quantidade: 1 }, { id_produto: 2, nome: '', quantidade: 1 }], preco)).toBe(30)
    expect(totalEmCentavos([{ id_produto: 3, nome: '', quantidade: 3 }], preco)).toBe(9999)
    expect(totalEmCentavos([{ id_produto: 99, nome: '', quantidade: 2 }], () => undefined)).toBe(0)
  })
})

describe('Novo pedido', () => {
  it('calcula o total estimado enquanto os itens são adicionados', async () => {
    await novo()
    await escolherCliente()

    await adicionar('1', '2')
    await adicionar('2', '3')

    const tabela = screen.getByRole('table')
    expect(within(tabela).getByText('Saco 50L')).toBeInTheDocument()
    expect(within(tabela).getByText('R$ 20,00')).toBeInTheDocument()
    expect(within(tabela).getByText('R$ 77,70')).toBeInTheDocument()
    expect(within(tabela).getByText('R$ 97,70')).toBeInTheDocument() // total
    expect(screen.getByText(/O valor final é calculado pelo sistema/)).toBeInTheDocument()
  })

  it('o produto já adicionado some da lista (não dá para repetir) e o item pode ser removido', async () => {
    await novo()
    await escolherCliente()
    await adicionar('1', '2')

    expect(within(screen.getByLabelText('Produto')).queryByRole('option', { name: /Saco 50L/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Remover Saco 50L' }))

    expect(within(screen.getByLabelText('Produto')).getByRole('option', { name: /Saco 50L/ })).toBeInTheDocument()
    expect(screen.getByText('Nenhum item adicionado.')).toBeInTheDocument()
  })

  it('só habilita "Adicionar item" com produto e quantidade válidos', async () => {
    await novo()
    const botao = screen.getByRole('button', { name: 'Adicionar item' })
    expect(botao).toBeDisabled()

    await userEvent.selectOptions(screen.getByLabelText('Produto'), '1')
    expect(botao).toBeEnabled()

    await userEvent.clear(screen.getByLabelText('Qtd.'))
    await userEvent.type(screen.getByLabelText('Qtd.'), '0')
    expect(botao).toBeDisabled()
  })

  it('avisa quando a quantidade passa do estoque, mas deixa salvar (a baixa é na confirmação)', async () => {
    await novo()
    await escolherCliente()

    await adicionar('2', '50') // estoque do Saco 100L: 20

    expect(screen.getByText(/estoque atual: 20/)).toBeInTheDocument()
    expect(screen.getByText(/só será confirmado quando houver estoque/)).toBeInTheDocument()
  })

  it('não envia nada e mostra o que falta quando o formulário está incompleto', async () => {
    const api = await novo()

    await userEvent.click(screen.getByRole('button', { name: 'Registrar pedido' }))

    expect(await screen.findByText('Escolha o cliente.')).toBeInTheDocument()
    expect(screen.getByText('Adicione ao menos um produto.')).toBeInTheDocument()
    expect(api.de('POST', '/pedidos')).toHaveLength(0)
  })

  it('já deixa o endereço principal do cliente selecionado', async () => {
    await novo()
    await escolherCliente()

    expect(screen.getByRole('radio', { name: /Rua 1, 1/ })).toBeChecked()
    expect(screen.getByRole('radio', { name: /Rua 2, 2/ })).not.toBeChecked()
  })

  it('registra o pedido enviando só produtos e quantidades (o preço e o total são do servidor)', async () => {
    const api = await novo({ 'POST /pedidos': { status: 201, body: pedido(31) } })
    await escolherCliente()
    await adicionar('1', '2')
    await adicionar('2', '3')
    await userEvent.type(screen.getByLabelText('Observação'), 'Entregar à tarde')

    await userEvent.click(screen.getByRole('button', { name: 'Registrar pedido' }))

    await waitFor(() => expect(api.de('POST', '/pedidos')).toHaveLength(1))
    const corpo = api.ultima('POST', '/pedidos')?.corpo as Record<string, unknown>
    expect(corpo).toEqual({
      id_cliente: 7, id_endereco: 1, forma_pagamento: 'PIX', observacao: 'Entregar à tarde',
      itens: [{ id_produto: 1, quantidade: 2 }, { id_produto: 2, quantidade: 3 }],
    })
    expect(JSON.stringify(corpo)).not.toMatch(/preco|valor_total|subtotal|status|id_usuario/)
  })

  it('usa o endereço escolhido da lista do cliente', async () => {
    const api = await novo({ 'POST /pedidos': { status: 201, body: pedido(31) } })
    await escolherCliente()
    await userEvent.click(screen.getByRole('radio', { name: /Rua 2, 2/ }))
    await adicionar('1', '1')

    await userEvent.click(screen.getByRole('button', { name: 'Registrar pedido' }))

    await waitFor(() => expect(api.ultima('POST', '/pedidos')?.corpo).toMatchObject({ id_endereco: 2 }))
  })

  it('mostra o erro do servidor (ex.: produto inativado) sem perder o que foi digitado', async () => {
    await novo({ 'POST /pedidos': { status: 422, body: { detail: 'O produto «Saco 50L» está inativo.' } } })
    await escolherCliente()
    await adicionar('1', '2')

    await userEvent.click(screen.getByRole('button', { name: 'Registrar pedido' }))

    expect(await screen.findByText('O produto «Saco 50L» está inativo.')).toBeInTheDocument()
    expect(screen.getByText('Saco 50L')).toBeInTheDocument() // o item continua na tabela
  })

  describe('endereço de entrega', () => {
    it('buscar um endereço já registrado: liga ao cliente (com os dados do vínculo) e usa no pedido', async () => {
      const FLORES = { id_endereco: 11, cep: '14401111', cidade: 'Franca', bairro: 'Jardim', tipo_logradouro: 'Rua', nome_logradouro: 'Das Flores', descricao: 'Rua Das Flores - Jardim, Franca - CEP 14401-111', quantidade_clientes: 3 }
      const api = await novo({ 'GET /enderecos': { body: [FLORES] }, 'POST /clientes/7/enderecos': { status: 201, body: CLIENTE }, 'POST /pedidos': { status: 201, body: pedido(31) } })
      await escolherCliente()
      await adicionar('1', '1')

      await userEvent.click(screen.getByRole('button', { name: /Usar outro endereço/ }))
      await userEvent.type(screen.getByLabelText(/Buscar por rua/), 'flores')
      await userEvent.click(await screen.findByRole('button', { name: /Rua Das Flores - Jardim/ }))
      await userEvent.type(screen.getByLabelText('Número *'), '55')
      await userEvent.type(screen.getByLabelText('Ponto de referência'), 'perto da praça')
      await userEvent.click(screen.getByRole('button', { name: 'Registrar pedido' }))

      await waitFor(() => expect(api.de('POST', '/pedidos')).toHaveLength(1))
      expect(api.ultima('POST', '/clientes/7/enderecos')?.corpo).toEqual({ id_endereco: 11, numero: '55', complemento: '', referencia: 'perto da praça', apelido: null, principal: false })
      expect(api.ultima('POST', '/pedidos')?.corpo).toMatchObject({ id_cliente: 7, id_endereco: 11 })
      // primeiro liga o endereço ao cliente, depois cria o pedido
      const ordem = api.chamadas.filter((c) => c.metodo === 'POST').map((c) => c.caminho)
      expect(ordem).toEqual(['/clientes/7/enderecos', '/pedidos'])
    })

    it('cadastrar um endereço novo: cria o vínculo e usa o id que o servidor devolveu', async () => {
      const comNovo = { ...CLIENTE, enderecos: [...CLIENTE.enderecos, endereco(3, { nome_logradouro: 'Brasil' })] }
      const api = await novo({ 'POST /clientes/7/enderecos': { status: 201, body: comNovo }, 'POST /pedidos': { status: 201, body: pedido(31) } })
      await escolherCliente()
      await adicionar('1', '1')

      await userEvent.click(screen.getByRole('button', { name: /Usar outro endereço/ }))
      await userEvent.click(screen.getByRole('tab', { name: 'Cadastrar novo endereço' }))
      await userEvent.type(screen.getByLabelText('CEP *'), '14500000')
      await userEvent.type(screen.getByLabelText('Cidade *'), 'Franca')
      await userEvent.type(screen.getByLabelText('Rua *'), 'Brasil')
      await userEvent.type(screen.getByLabelText('Bairro *'), 'Centro')
      await userEvent.type(screen.getByLabelText('Número *'), '10')
      await userEvent.click(screen.getByRole('button', { name: 'Registrar pedido' }))

      await waitFor(() => expect(api.de('POST', '/pedidos')).toHaveLength(1))
      expect(api.ultima('POST', '/clientes/7/enderecos')?.corpo).toMatchObject({ cep: '14500000', nome_logradouro: 'Brasil', numero: '10', principal: false })
      expect(api.ultima('POST', '/pedidos')?.corpo).toMatchObject({ id_endereco: 3 })
    })

    it('com o endereço novo incompleto, não envia nada', async () => {
      const api = await novo()
      await escolherCliente()
      await adicionar('1', '1')
      await userEvent.click(screen.getByRole('button', { name: /Usar outro endereço/ }))

      await userEvent.click(screen.getByRole('button', { name: 'Registrar pedido' }))

      expect(await screen.findByText('Complete o novo endereço.')).toBeInTheDocument()
      expect(api.de('POST', '/clientes/7/enderecos')).toHaveLength(0)
      expect(api.de('POST', '/pedidos')).toHaveLength(0)
    })

    it('dá para voltar aos endereços do cliente', async () => {
      await novo()
      await escolherCliente()
      await userEvent.click(screen.getByRole('button', { name: /Usar outro endereço/ }))

      await userEvent.click(screen.getByRole('button', { name: 'Voltar aos endereços do cliente' }))

      expect(screen.getByRole('radio', { name: /Rua 1, 1/ })).toBeChecked()
    })

    it('cliente sem endereço já abre a escolha de endereço', async () => {
      const semEndereco = { ...CLIENTE, enderecos: [], endereco_principal: null }
      await novo({ 'GET /clientes/7': { body: semEndereco } })
      await userEvent.type(screen.getByPlaceholderText(/Buscar por nome, telefone/), 'ana')
      await userEvent.click(await screen.findByRole('option', { name: /Ana Souza/ }))

      expect(await screen.findByRole('tab', { name: 'Buscar endereço já registrado' })).toBeInTheDocument()
      expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    })
  })
})

describe('Editar pedido', () => {
  async function editar(p: ReturnType<typeof pedido>, extra: Record<string, unknown> = {}) {
    const api = mockApi({ ...BASE, [`GET /pedidos/${p.id_pedido}`]: { body: p }, [`PATCH /pedidos/${p.id_pedido}`]: { body: p }, ...extra } as Parameters<typeof mockApi>[0])
    await renderizar(<PedidoForm />, { usuario: VENDEDORA, rota: `/pedidos/${p.id_pedido}/editar`, caminho: '/pedidos/:id/editar' })
    await screen.findByText('Ana Souza')
    await screen.findByRole('radio', { name: /Rua 1, 1/ })
    return api
  }

  it('em aberto: carrega o pedido e deixa mudar tudo', async () => {
    await editar(pedido(9))

    expect(screen.getByRole('heading', { name: 'Editar pedido #9' })).toBeInTheDocument()
    expect(screen.getByText('Saco 50L')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Trocar cliente' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remover Saco 50L' })).toBeInTheDocument()
    expect(screen.getByLabelText(/^Forma de pagamento/)).toHaveValue('PIX')
  })

  it('envia só o que mudou: trocar os produtos', async () => {
    const api = await editar(pedido(9))

    await userEvent.click(screen.getByRole('button', { name: 'Remover Saco 100L' }))
    await userEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))

    await waitFor(() => expect(api.de('PATCH', '/pedidos/9')).toHaveLength(1))
    expect(api.ultima('PATCH', '/pedidos/9')?.corpo).toEqual({ itens: [{ id_produto: 1, quantidade: 2 }] })
  })

  it('envia só o que mudou: forma de pagamento e observação (e limpar a observação manda null)', async () => {
    const api = await editar(pedido(9, 'em_aberto', { observacao: 'antiga' }))

    await userEvent.selectOptions(screen.getByLabelText(/^Forma de pagamento/), 'Dinheiro')
    await userEvent.clear(screen.getByLabelText('Observação'))
    await userEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))

    await waitFor(() => expect(api.de('PATCH', '/pedidos/9')).toHaveLength(1))
    expect(api.ultima('PATCH', '/pedidos/9')?.corpo).toEqual({ forma_pagamento: 'Dinheiro', observacao: null })
  })

  it('sem nenhuma mudança, não chama o servidor', async () => {
    const api = await editar(pedido(9))

    await userEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))

    await waitFor(() => expect(screen.queryByRole('button', { name: 'Salvar alterações' })).not.toBeInTheDocument() || true)
    expect(api.de('PATCH', '/pedidos/9')).toHaveLength(0)
  })

  it('confirmado: o cliente e os produtos ficam travados e só pagamento, endereço e observação mudam', async () => {
    const api = await editar(pedido(9, 'confirmado'))

    expect(screen.getByText(/Pedido confirmado \(o estoque já foi baixado\)/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Trocar cliente' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Remover/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Produtos' })).not.toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText(/^Forma de pagamento/), 'Dinheiro')
    await userEvent.click(screen.getByRole('radio', { name: /Rua 2, 2/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Salvar alterações' }))

    await waitFor(() => expect(api.de('PATCH', '/pedidos/9')).toHaveLength(1))
    expect(api.ultima('PATCH', '/pedidos/9')?.corpo).toEqual({ forma_pagamento: 'Dinheiro', id_endereco: 2 })
  })

  it.each(['entregue', 'cancelado'] as const)('%s: somente leitura, sem botão de salvar', async (status) => {
    await editar(pedido(9, status))

    expect(screen.getByText(/não pode mais ser alterado/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Salvar alterações' })).not.toBeInTheDocument()
    expect(screen.getByLabelText(/^Forma de pagamento/)).toBeDisabled()
  })

  it('mostra erro quando o pedido não existe', async () => {
    mockApi({ ...BASE, 'GET /pedidos/404': { status: 404, body: { detail: 'Pedido não encontrado.' } } } as Parameters<typeof mockApi>[0])
    await renderizar(<PedidoForm />, { usuario: VENDEDORA, rota: '/pedidos/404/editar', caminho: '/pedidos/:id/editar' })

    expect(await screen.findByText('Pedido não encontrado.')).toBeInTheDocument()
  })
})

void END1
