import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { ClienteResumo } from '../lib/types'
import { CLIENTE, CLIENTE_RESUMO, END2, endereco, pagina, pedido } from '../test/dados'
import { mockApi, renderizar, VENDEDORA } from '../test/utils'
import Clientes from './Clientes'

const SEM_ENDERECO: ClienteResumo = { ...CLIENTE_RESUMO, id_cliente: 8, nome: 'Bia Lima', telefone: '16988880002', endereco_principal: null }
const FLORES = { id_endereco: 11, cep: '14401111', cidade: 'Franca', bairro: 'Jardim', tipo_logradouro: 'Rua', nome_logradouro: 'Das Flores', descricao: 'Rua Das Flores - Jardim, Franca - CEP 14401-111', quantidade_clientes: 3 }

function rotas(extra: Record<string, unknown> = {}) {
  return {
    'GET /clientes': { body: pagina([CLIENTE_RESUMO, SEM_ENDERECO]) },
    'GET /clientes/7': { body: CLIENTE },
    ...extra,
  } as Parameters<typeof mockApi>[0]
}
async function abrir(extra: Record<string, unknown> = {}) {
  const api = mockApi(rotas(extra))
  await renderizar(<Clientes />, { usuario: VENDEDORA })
  await screen.findByRole('row', { name: /Ana Souza/ })
  return api
}

describe('Clientes: lista', () => {
  it('mostra código, nome, telefone, endereço principal, referência e quem cadastrou', async () => {
    await abrir()

    const l = screen.getByRole('row', { name: /Ana Souza/ })
    expect(l).toHaveTextContent('#7')
    expect(l).toHaveTextContent('(16) 99999-0001')
    expect(l).toHaveTextContent('Rua 1, 1 - Centro, Franca')
    expect(l).toHaveTextContent('portão azul')
    expect(l).toHaveTextContent('Maria Vendedora')
    expect(l).toHaveTextContent('Ativo')
  })

  it('cliente sem endereço aparece destacado', async () => {
    await abrir()

    expect(screen.getByRole('row', { name: /Bia Lima/ })).toHaveTextContent('Sem endereço')
  })

  it('a busca e "mostrar inativos" vão para o servidor', async () => {
    const api = await abrir()

    await userEvent.type(screen.getByLabelText('Buscar clientes'), 'ana')
    await userEvent.click(screen.getByLabelText('Mostrar inativos'))

    await waitFor(() => {
      const q = api.ultima('GET', '/clientes')?.query
      expect(q?.get('busca')).toBe('ana')
      expect(q?.get('incluir_inativos')).toBe('true')
    })
  })

  it('lista vazia orienta o primeiro cadastro', async () => {
    mockApi(rotas({ 'GET /clientes': { body: pagina([]) } }))
    await renderizar(<Clientes />, { usuario: VENDEDORA })

    expect(await screen.findByText('Nenhum cliente cadastrado')).toBeInTheDocument()
  })

  it('a paginação pede a próxima página', async () => {
    const api = await abrir({ 'GET /clientes': { body: pagina([CLIENTE_RESUMO], { total: 45, limit: 20 }) } })

    await userEvent.click(await screen.findByRole('button', { name: 'Próxima página' }))

    await waitFor(() => expect(api.ultima('GET', '/clientes')?.query.get('offset')).toBe('20'))
  })
})

describe('Clientes: novo cliente', () => {
  async function abrirNovo(extra: Record<string, unknown> = {}) {
    const api = await abrir(extra)
    await userEvent.click(screen.getByRole('button', { name: 'Novo cliente' }))
    return { api, dialogo: await screen.findByRole('dialog', { name: '+ Cadastrar cliente' }) }
  }
  const campos = (d: HTMLElement) => ({ nome: within(d).getByLabelText('Nome completo *'), fone: within(d).getByLabelText('Telefone / WhatsApp *') })

  it('mostra o que falta e não envia o cadastro incompleto', async () => {
    const { api, dialogo } = await abrirNovo()

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar cliente' }))

    expect(await within(dialogo).findByText('Informe o nome.')).toBeInTheDocument()
    expect(within(dialogo).getByText('Informe DDD + número (10 ou 11 dígitos).')).toBeInTheDocument()
    expect(within(dialogo).getByText(/Escolha um endereço registrado ou preencha um novo/)).toBeInTheDocument()
    expect(api.de('POST', '/clientes')).toHaveLength(0)
  })

  it('aplica a máscara no telefone', async () => {
    const { dialogo } = await abrirNovo()

    await userEvent.type(campos(dialogo).fone, '16999991111')

    expect(campos(dialogo).fone).toHaveValue('(16) 99999-1111')
  })

  it('cadastra sem endereço quando a opção é desmarcada', async () => {
    const { api, dialogo } = await abrirNovo({ 'POST /clientes': { status: 201, body: CLIENTE } })

    await userEvent.type(campos(dialogo).nome, 'Joana Lima')
    await userEvent.type(campos(dialogo).fone, '16999991111')
    await userEvent.click(within(dialogo).getByLabelText('Cadastrar o endereço de entrega agora'))
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar cliente' }))

    await waitFor(() => expect(api.de('POST', '/clientes')).toHaveLength(1))
    expect(api.ultima('POST', '/clientes')?.corpo).toEqual({ nome: 'Joana Lima', telefone: '(16) 99999-1111', enderecos: [] })
    expect(await screen.findByText('Cliente Ana Souza cadastrado.')).toBeInTheDocument()
  })

  it('cadastra com um endereço NOVO, que vira o principal', async () => {
    const { api, dialogo } = await abrirNovo({ 'POST /clientes': { status: 201, body: CLIENTE } })

    await userEvent.type(campos(dialogo).nome, 'Joana Lima')
    await userEvent.type(campos(dialogo).fone, '16999991111')
    await userEvent.click(within(dialogo).getByRole('tab', { name: 'Cadastrar novo endereço' }))
    await userEvent.type(within(dialogo).getByLabelText('CEP *'), '14400000')
    await userEvent.type(within(dialogo).getByLabelText('Cidade *'), 'Franca')
    await userEvent.type(within(dialogo).getByLabelText('Rua *'), 'Presidente Vargas')
    await userEvent.type(within(dialogo).getByLabelText('Bairro *'), 'Centro')
    await userEvent.type(within(dialogo).getByLabelText('Número *'), '100')
    await userEvent.type(within(dialogo).getByLabelText('Ponto de referência'), 'casa amarela')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar cliente' }))

    await waitFor(() => expect(api.de('POST', '/clientes')).toHaveLength(1))
    expect(api.ultima('POST', '/clientes')?.corpo).toEqual({
      nome: 'Joana Lima', telefone: '(16) 99999-1111',
      enderecos: [{ cep: '14400000', cidade: 'Franca', bairro: 'Centro', tipo_logradouro: 'Rua', nome_logradouro: 'Presidente Vargas', numero: '100', complemento: '', referencia: 'casa amarela', apelido: null, principal: true }],
    })
  })

  it('cadastra reaproveitando um endereço JÁ REGISTRADO (com os dados só deste cliente)', async () => {
    const { api, dialogo } = await abrirNovo({ 'GET /enderecos': { body: [FLORES] }, 'POST /clientes': { status: 201, body: CLIENTE } })

    await userEvent.type(campos(dialogo).nome, 'Joana Lima')
    await userEvent.type(campos(dialogo).fone, '16999991111')
    await userEvent.type(within(dialogo).getByLabelText(/Buscar por rua/), 'flores')
    await userEvent.click(await within(dialogo).findByRole('button', { name: /Rua Das Flores - Jardim/ }))
    expect(within(dialogo).getByRole('region', { name: /Dados deste endereço para este cliente/ })).toBeInTheDocument()
    await userEvent.type(within(dialogo).getByLabelText('Número *'), '55')
    await userEvent.type(within(dialogo).getByLabelText('Complemento'), 'fundos')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar cliente' }))

    await waitFor(() => expect(api.de('POST', '/clientes')).toHaveLength(1))
    expect(api.ultima('POST', '/clientes')?.corpo).toEqual({
      nome: 'Joana Lima', telefone: '(16) 99999-1111',
      enderecos: [{ id_endereco: 11, numero: '55', complemento: 'fundos', referencia: '', apelido: null, principal: true }],
    })
  })

  it('telefone repetido: mostra a mensagem do servidor e mantém o formulário', async () => {
    const { dialogo } = await abrirNovo({ 'POST /clientes': { status: 409, body: { detail: 'Já existe um cliente com este telefone.' } } })
    await userEvent.type(campos(dialogo).nome, 'Joana')
    await userEvent.type(campos(dialogo).fone, '16999990001')
    await userEvent.click(within(dialogo).getByLabelText('Cadastrar o endereço de entrega agora'))

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar cliente' }))

    expect(await within(dialogo).findByText('Já existe um cliente com este telefone.')).toBeInTheDocument()
    expect(campos(dialogo).nome).toHaveValue('Joana')
  })
})

describe('Clientes: detalhe, endereços e histórico', () => {
  async function abrirDetalhe(extra: Record<string, unknown> = {}) {
    const api = await abrir(extra)
    await userEvent.click(screen.getByRole('row', { name: /Ana Souza/ }))
    const dialogo = await screen.findByRole('dialog', { name: /Ana Souza/ })
    await within(dialogo).findByText('Endereços de entrega')
    return { api, dialogo }
  }

  it('mostra os dados, quem cadastrou e os endereços com o principal destacado', async () => {
    const { dialogo } = await abrirDetalhe()

    expect(dialogo).toHaveTextContent('Código #7 · cadastrado por Maria Vendedora')
    expect(dialogo).toHaveTextContent('(16) 99999-0001')
    expect(dialogo).toHaveTextContent('Rua 1, 1 - Centro, Franca')
    expect(dialogo).toHaveTextContent('Referência: portão azul')
    expect(within(dialogo).getByText('Principal')).toBeInTheDocument()
    expect(within(dialogo).getAllByRole('button', { name: 'Tornar principal' })).toHaveLength(1) // só o endereço 2
  })

  it('"Tornar principal" muda o endereço principal', async () => {
    const { api, dialogo } = await abrirDetalhe({ 'PATCH /clientes/7/enderecos/2': { body: CLIENTE } })

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Tornar principal' }))

    await waitFor(() => expect(api.de('PATCH', '/clientes/7/enderecos/2')).toHaveLength(1))
    expect(api.ultima('PATCH', '/clientes/7/enderecos/2')?.corpo).toEqual({ principal: true })
  })

  it('edita número, complemento, referência e apelido do endereço', async () => {
    const { api, dialogo } = await abrirDetalhe({ 'PATCH /clientes/7/enderecos/2': { body: CLIENTE } })

    await userEvent.click(within(dialogo).getByRole('button', { name: `Editar endereço ${END2.nome_logradouro}` }))
    const editar = await screen.findByRole('dialog', { name: 'Editar endereço' })
    expect(editar).toHaveTextContent('cadastre o endereço correto e remova este')
    await userEvent.clear(within(editar).getByLabelText('Número *'))
    await userEvent.type(within(editar).getByLabelText('Número *'), '99B')
    await userEvent.type(within(editar).getByLabelText('Apelido'), 'Trabalho')
    await userEvent.click(within(editar).getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(api.de('PATCH', '/clientes/7/enderecos/2')).toHaveLength(1))
    expect(api.ultima('PATCH', '/clientes/7/enderecos/2')?.corpo).toEqual({ numero: '99B', complemento: '', referencia: '', apelido: 'Trabalho' })
  })

  it('remover endereço pede confirmação e explica o que acontece com o histórico', async () => {
    const { api, dialogo } = await abrirDetalhe({ 'DELETE /clientes/7/enderecos/2': { body: CLIENTE } })

    await userEvent.click(within(dialogo).getByRole('button', { name: `Remover endereço ${END2.nome_logradouro}` }))
    const confirmar = await screen.findByRole('dialog', { name: 'Remover endereço?' })
    expect(confirmar).toHaveTextContent('apenas desativado para preservar o histórico')
    expect(api.de('DELETE', '/clientes/7/enderecos/2')).toHaveLength(0)
    await userEvent.click(within(confirmar).getByRole('button', { name: 'Remover' }))

    await waitFor(() => expect(api.de('DELETE', '/clientes/7/enderecos/2')).toHaveLength(1))
  })

  it('endereço compartilhado e usado em pedidos: mostra a recusa do servidor', async () => {
    const { dialogo } = await abrirDetalhe({ 'DELETE /clientes/7/enderecos/2': { status: 409, body: { detail: 'Este endereço já foi usado em pedidos e é compartilhado com outro cliente, por isso não pode ser removido.' } } })

    await userEvent.click(within(dialogo).getByRole('button', { name: `Remover endereço ${END2.nome_logradouro}` }))
    await userEvent.click(within(await screen.findByRole('dialog', { name: 'Remover endereço?' })).getByRole('button', { name: 'Remover' }))

    expect(await screen.findByText(/compartilhado com outro cliente/)).toBeInTheDocument()
  })

  it('adicionar endereço: busca um já registrado, mostra a seção do vínculo e envia com a opção de principal', async () => {
    const { api, dialogo } = await abrirDetalhe({ 'GET /enderecos': { body: [FLORES] }, 'POST /clientes/7/enderecos': { status: 201, body: CLIENTE } })

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Adicionar endereço' }))
    await userEvent.type(within(dialogo).getByLabelText(/Buscar por rua/), 'flores')
    await userEvent.click(await within(dialogo).findByRole('button', { name: /Rua Das Flores - Jardim/ }))
    expect(within(dialogo).getByRole('region', { name: /Dados deste endereço para este cliente/ })).toBeInTheDocument()
    await userEvent.type(within(dialogo).getByLabelText('Número *'), '12')
    await userEvent.click(within(dialogo).getByLabelText('Usar como endereço principal do cliente'))
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Salvar endereço' }))

    await waitFor(() => expect(api.de('POST', '/clientes/7/enderecos')).toHaveLength(1))
    expect(api.ultima('POST', '/clientes/7/enderecos')?.corpo).toEqual({ id_endereco: 11, numero: '12', complemento: '', referencia: '', apelido: null, principal: true })
  })

  it('na busca, os endereços que o cliente já tem não podem ser escolhidos de novo', async () => {
    const { dialogo } = await abrirDetalhe({ 'GET /enderecos': { body: [{ ...FLORES, id_endereco: 1, descricao: 'Rua 1 - Centro, Franca - CEP 14400-000' }] } })

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Adicionar endereço' }))
    await userEvent.type(within(dialogo).getByLabelText(/Buscar por rua/), 'rua')

    expect(await within(dialogo).findByRole('button', { name: /Rua 1 - Centro/ })).toBeDisabled()
  })

  it('o histórico de compras lista os pedidos do cliente', async () => {
    const { api, dialogo } = await abrirDetalhe({ 'GET /pedidos': { body: pagina([pedido(5, 'entregue'), pedido(6, 'cancelado')]) } })

    await userEvent.click(within(dialogo).getByRole('tab', { name: 'Histórico de compras' }))

    expect(await within(dialogo).findByText((_, el) => el?.tagName === 'P' && /2 pedidos · total em compras/.test(el.textContent ?? ''))).toBeInTheDocument()
    expect(api.ultima('GET', '/pedidos')?.query.get('id_cliente')).toBe('7')
    expect(within(dialogo).getByRole('link', { name: '#5' })).toHaveAttribute('href', '/pedidos/5/editar')
    expect(within(dialogo).getByRole('row', { name: /#6/ })).toHaveTextContent('Cancelado')
  })

  it('edita nome e telefone', async () => {
    const { api, dialogo } = await abrirDetalhe({ 'PATCH /clientes/7': { body: CLIENTE } })

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Editar dados' }))
    const nome = within(dialogo).getByLabelText('Nome completo *')
    await userEvent.clear(nome)
    await userEvent.type(nome, 'Ana Souza Lima')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(api.de('PATCH', '/clientes/7')).toHaveLength(1))
    expect(api.ultima('PATCH', '/clientes/7')?.corpo).toEqual({ nome: 'Ana Souza Lima', telefone: '(16) 99999-0001' })
  })

  it('inativar pede confirmação e explica que o histórico fica', async () => {
    const { api, dialogo } = await abrirDetalhe({ 'DELETE /clientes/7': { status: 204 } })

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Inativar' }))
    const confirmar = await screen.findByRole('dialog', { name: 'Inativar cliente?' })
    expect(confirmar).toHaveTextContent('histórico de pedidos é mantido')
    expect(api.de('DELETE', '/clientes/7')).toHaveLength(0)
    await userEvent.click(within(confirmar).getByRole('button', { name: 'Inativar' }))

    await waitFor(() => expect(api.de('DELETE', '/clientes/7')).toHaveLength(1))
  })

  it('cliente sem endereço mostra um aviso', async () => {
    mockApi(rotas({ 'GET /clientes/7': { body: { ...CLIENTE, enderecos: [], endereco_principal: null } } }))
    await renderizar(<Clientes />, { usuario: VENDEDORA })
    await userEvent.click(await screen.findByRole('row', { name: /Ana Souza/ }))

    expect(await screen.findByText(/ainda não tem endereço/)).toBeInTheDocument()
  })
})

void endereco
