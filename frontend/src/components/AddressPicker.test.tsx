import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderizar } from '../test/utils'
import { AddressPicker } from './AddressPicker'

const VARGAS = { id_endereco: 10, cep: '14400000', cidade: 'Franca', bairro: 'Centro', tipo_logradouro: 'Avenida', nome_logradouro: 'Presidente Vargas', descricao: 'Avenida Presidente Vargas - Centro, Franca - CEP 14400-000', quantidade_clientes: 2 }
const FLORES = { id_endereco: 11, cep: '14401111', cidade: 'Franca', bairro: 'Jardim', tipo_logradouro: 'Rua', nome_logradouro: 'Das Flores', descricao: 'Rua Das Flores - Jardim, Franca - CEP 14401-111', quantidade_clientes: 1 }

const SECAO = { name: /Dados deste endereço para este cliente/ }

async function buscar(termo: string) {
  await userEvent.type(screen.getByLabelText(/Buscar por rua, bairro, cidade ou CEP/), termo)
}
const ultimo = (fn: ReturnType<typeof vi.fn>) => fn.mock.calls.at(-1)?.[0]

describe('AddressPicker: buscar endereço já registrado', () => {
  it('começa na busca e NÃO mostra a seção do vínculo antes de escolher um endereço', async () => {
    mockApi({})
    await renderizar(<AddressPicker onChange={vi.fn()} />)

    expect(screen.getByRole('tab', { name: 'Buscar endereço já registrado' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Cadastrar novo endereço' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.queryByRole('region', SECAO)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Número/)).not.toBeInTheDocument()
  })

  it('busca na API e lista os endereços com quantos clientes usam cada um', async () => {
    const api = mockApi({ 'GET /enderecos': { body: [VARGAS, FLORES] } })
    await renderizar(<AddressPicker onChange={vi.fn()} />)

    await buscar('vargas')

    expect(await screen.findByText(VARGAS.descricao)).toBeInTheDocument()
    expect(screen.getByText('2 clientes')).toBeInTheDocument()
    expect(screen.getByText('1 cliente')).toBeInTheDocument()
    expect(api.ultima('GET', '/enderecos')?.query.get('busca')).toBe('vargas')
  })

  it('não busca com menos de 2 letras', async () => {
    const api = mockApi({ 'GET /enderecos': { body: [] } })
    await renderizar(<AddressPicker onChange={vi.fn()} />)

    await buscar('v')
    await new Promise((r) => setTimeout(r, 450))

    expect(api.de('GET', '/enderecos')).toHaveLength(0)
  })

  it('ao escolher um endereço registrado, APARECE a seção com os dados do vínculo', async () => {
    mockApi({ 'GET /enderecos': { body: [VARGAS] } })
    await renderizar(<AddressPicker onChange={vi.fn()} />)
    await buscar('vargas')

    await userEvent.click(await screen.findByRole('button', { name: new RegExp(VARGAS.descricao) }))

    const secao = screen.getByRole('region', SECAO)
    expect(secao).toBeInTheDocument()
    expect(screen.getByLabelText(/Número/)).toBeInTheDocument()
    expect(screen.getByLabelText('Complemento')).toBeInTheDocument()
    expect(screen.getByLabelText('Ponto de referência')).toBeInTheDocument()
    expect(screen.getByLabelText('Apelido do endereço')).toBeInTheDocument()
    expect(screen.getByText('Endereço já registrado no sistema')).toBeInTheDocument()
    expect(screen.queryByLabelText(/Buscar por rua/)).not.toBeInTheDocument()
  })

  it('só entrega o endereço ao formulário quando o número foi informado', async () => {
    mockApi({ 'GET /enderecos': { body: [VARGAS] } })
    const onChange = vi.fn()
    await renderizar(<AddressPicker onChange={onChange} />)
    await buscar('vargas')
    await userEvent.click(await screen.findByRole('button', { name: new RegExp(VARGAS.descricao) }))

    expect(ultimo(onChange)).toBeNull()

    await userEvent.type(screen.getByLabelText(/Número/), '250')
    await userEvent.type(screen.getByLabelText('Ponto de referência'), 'portão azul')
    await userEvent.type(screen.getByLabelText('Apelido do endereço'), 'Casa')

    expect(ultimo(onChange)).toEqual({ id_endereco: 10, numero: '250', complemento: '', referencia: 'portão azul', apelido: 'Casa', principal: false })
  })

  it('"Trocar" volta para a busca e esconde a seção do vínculo', async () => {
    mockApi({ 'GET /enderecos': { body: [VARGAS] } })
    const onChange = vi.fn()
    await renderizar(<AddressPicker onChange={onChange} />)
    await buscar('vargas')
    await userEvent.click(await screen.findByRole('button', { name: new RegExp(VARGAS.descricao) }))
    await userEvent.type(screen.getByLabelText(/Número/), '1')

    await userEvent.click(screen.getByRole('button', { name: 'Trocar' }))

    expect(screen.queryByRole('region', SECAO)).not.toBeInTheDocument()
    expect(screen.getByLabelText(/Buscar por rua/)).toBeInTheDocument()
    expect(ultimo(onChange)).toBeNull()
  })

  it('endereços que o cliente já tem aparecem desabilitados', async () => {
    mockApi({ 'GET /enderecos': { body: [VARGAS, FLORES] } })
    await renderizar(<AddressPicker onChange={vi.fn()} jaVinculados={[10]} />)
    await buscar('franca')

    const ja = await screen.findByRole('button', { name: new RegExp(VARGAS.descricao) })
    expect(ja).toBeDisabled()
    expect(screen.getByText('Já é deste cliente')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: new RegExp(FLORES.descricao) })).toBeEnabled()
  })

  it('sem resultado, oferece cadastrar um novo endereço', async () => {
    mockApi({ 'GET /enderecos': { body: [] } })
    await renderizar(<AddressPicker onChange={vi.fn()} />)
    await buscar('rua inexistente')

    await userEvent.click(await screen.findByRole('button', { name: 'Cadastrar um novo' }))

    expect(screen.getByRole('tab', { name: 'Cadastrar novo endereço' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText(/CEP/)).toBeInTheDocument()
  })

  it('"endereço principal" entra no payload quando marcado', async () => {
    mockApi({ 'GET /enderecos': { body: [VARGAS] } })
    const onChange = vi.fn()
    await renderizar(<AddressPicker onChange={onChange} comPrincipal />)
    await buscar('vargas')
    await userEvent.click(await screen.findByRole('button', { name: new RegExp(VARGAS.descricao) }))
    await userEvent.type(screen.getByLabelText(/Número/), '9')

    await userEvent.click(screen.getByLabelText('Usar como endereço principal do cliente'))

    expect(ultimo(onChange)).toMatchObject({ id_endereco: 10, principal: true })
  })

  it('a opção de principal só existe depois de escolher o endereço', async () => {
    mockApi({})
    await renderizar(<AddressPicker onChange={vi.fn()} comPrincipal />)

    expect(screen.queryByLabelText(/endereço principal/)).not.toBeInTheDocument()
  })
})

describe('AddressPicker: cadastrar novo endereço', () => {
  async function abrirNovo(props: Partial<React.ComponentProps<typeof AddressPicker>> = {}) {
    const onChange = vi.fn()
    mockApi({})
    await renderizar(<AddressPicker onChange={onChange} {...props} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Cadastrar novo endereço' }))
    return onChange
  }

  it('mostra todos os campos do endereço e do vínculo', async () => {
    await abrirNovo()

    for (const rotulo of [/CEP/, /Cidade/, /Tipo/, /Rua/, /Bairro/, /Número/, 'Complemento', 'Ponto de referência', 'Apelido do endereço'])
      expect(screen.getByLabelText(rotulo)).toBeInTheDocument()
  })

  it('só entrega o endereço quando os obrigatórios estão preenchidos', async () => {
    const onChange = await abrirNovo()
    expect(ultimo(onChange)).toBeNull()

    await userEvent.type(screen.getByLabelText(/CEP/), '14400000')
    await userEvent.type(screen.getByLabelText(/Cidade/), 'Franca')
    await userEvent.type(screen.getByLabelText(/Rua/), 'Presidente Vargas')
    await userEvent.type(screen.getByLabelText(/Bairro/), 'Centro')
    expect(ultimo(onChange)).toBeNull() // ainda falta o número

    await userEvent.type(screen.getByLabelText(/Número/), 'S/N')

    expect(ultimo(onChange)).toEqual({
      cep: '14400000', cidade: 'Franca', bairro: 'Centro', tipo_logradouro: 'Rua', nome_logradouro: 'Presidente Vargas',
      numero: 'S/N', complemento: '', referencia: '', apelido: null, principal: false,
    })
  })

  it('aplica a máscara no CEP mas envia só os dígitos', async () => {
    const onChange = await abrirNovo()
    await userEvent.type(screen.getByLabelText(/CEP/), '14400000')
    expect(screen.getByLabelText(/CEP/)).toHaveValue('14400-000')

    await userEvent.type(screen.getByLabelText(/Cidade/), 'Franca')
    await userEvent.type(screen.getByLabelText(/Rua/), 'X')
    await userEvent.type(screen.getByLabelText(/Bairro/), 'Y')
    await userEvent.type(screen.getByLabelText(/Número/), '1')

    expect(ultimo(onChange).cep).toBe('14400000')
  })

  it('CEP incompleto mostra erro depois que o campo perde o foco', async () => {
    await abrirNovo()
    await userEvent.type(screen.getByLabelText(/CEP/), '1440')
    expect(screen.queryByText('CEP deve ter 8 dígitos.')).not.toBeInTheDocument()

    await userEvent.tab()

    expect(screen.getByText('CEP deve ter 8 dígitos.')).toBeInTheDocument()
  })

  it('mostrarErros revela todos os campos pendentes de uma vez', async () => {
    await abrirNovo({ mostrarErros: true })

    for (const msg of ['CEP deve ter 8 dígitos.', 'Informe a cidade.', 'Informe o bairro.', 'Informe o nome da rua.', 'Informe o número (ou S/N).'])
      expect(screen.getByText(msg)).toBeInTheDocument()
  })

  it('o tipo de logradouro escolhido vai no payload', async () => {
    const onChange = await abrirNovo()
    await userEvent.selectOptions(screen.getByLabelText(/Tipo/), 'Avenida')
    await userEvent.type(screen.getByLabelText(/CEP/), '14400000')
    await userEvent.type(screen.getByLabelText(/Cidade/), 'Franca')
    await userEvent.type(screen.getByLabelText(/Rua/), 'Brasil')
    await userEvent.type(screen.getByLabelText(/Bairro/), 'Centro')
    await userEvent.type(screen.getByLabelText(/Número/), '10')

    expect(ultimo(onChange).tipo_logradouro).toBe('Avenida')
  })

  it('o número digitado numa aba continua ao trocar de aba', async () => {
    mockApi({})
    await renderizar(<AddressPicker onChange={vi.fn()} modoInicial="novo" />)
    await userEvent.type(screen.getByLabelText(/Número/), '77')

    await userEvent.click(screen.getByRole('tab', { name: 'Buscar endereço já registrado' }))
    await userEvent.click(screen.getByRole('tab', { name: 'Cadastrar novo endereço' }))

    await waitFor(() => expect(screen.getByLabelText(/Número/)).toHaveValue('77'))
  })
})
