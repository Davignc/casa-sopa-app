import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { ClienteResumo } from '../lib/types'
import { mockApi, renderizar } from '../test/utils'
import { ClienteSelect } from './ClienteSelect'

const ana: ClienteResumo = { id_cliente: 7, nome: 'Ana Souza', telefone: '16999990001', is_ativo: true, cadastrado_por: { id_usuario: 2, nome: 'Maria' },
  endereco_principal: { id_endereco: 1, cep: '14400000', cidade: 'Franca', bairro: 'Centro', tipo_logradouro: 'Rua', nome_logradouro: 'X', numero: '1', complemento: '', referencia: '', apelido: null, principal: true, endereco_formatado: 'Rua X, 1 - Centro, Franca - CEP 14400-000' } }
const bia: ClienteResumo = { ...ana, id_cliente: 8, nome: 'Bia Lima', telefone: '16988880002', endereco_principal: null }

function Caixa({ inicial = null }: { inicial?: ClienteResumo | null }) {
  const [c, setC] = useState<ClienteResumo | null>(inicial)
  return <><ClienteSelect valor={c} onChange={setC} /><output data-testid="escolhido">{c?.nome ?? 'ninguém'}</output></>
}

describe('ClienteSelect', () => {
  it('busca por nome, telefone, código ou endereço e mostra os resultados', async () => {
    const api = mockApi({ 'GET /clientes': { body: { itens: [ana, bia], total: 2, limit: 8, offset: 0 } } })
    await renderizar(<Caixa />)

    await userEvent.type(screen.getByRole('combobox'), 'ana')

    expect(await screen.findByRole('option', { name: /Ana Souza/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Ana Souza/ })).toHaveTextContent('(16) 99999-0001')
    expect(screen.getByRole('option', { name: /Ana Souza/ })).toHaveTextContent('Rua X, 1 - Centro')
    expect(screen.getByRole('option', { name: /Bia Lima/ })).toBeInTheDocument()
    // a busca digitada sai depois de uma pequena pausa (não consulta a cada tecla)
    await waitFor(() => expect(api.ultima('GET', '/clientes')?.query.get('busca')).toBe('ana'))
    expect(api.ultima('GET', '/clientes')?.query.get('limit')).toBe('8')
  })

  it('escolher com o clique mostra o cliente selecionado e permite trocar', async () => {
    mockApi({ 'GET /clientes': { body: { itens: [ana], total: 1, limit: 8, offset: 0 } } })
    await renderizar(<Caixa />)
    await userEvent.click(screen.getByRole('combobox'))

    await userEvent.click(await screen.findByRole('option', { name: /Ana Souza/ }))

    expect(screen.getByTestId('escolhido')).toHaveTextContent('Ana Souza')
    expect(screen.getByText(/código #7/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Trocar cliente' }))
    expect(screen.getByTestId('escolhido')).toHaveTextContent('ninguém')
    expect(screen.getByRole('combobox')).toBeInTheDocument()
  })

  it('funciona só com o teclado: setas e Enter', async () => {
    mockApi({ 'GET /clientes': { body: { itens: [ana, bia], total: 2, limit: 8, offset: 0 } } })
    await renderizar(<Caixa />)
    await userEvent.type(screen.getByRole('combobox'), 'a')
    await screen.findByRole('option', { name: /Bia Lima/ })

    await userEvent.keyboard('{ArrowDown}{Enter}')

    expect(screen.getByTestId('escolhido')).toHaveTextContent('Bia Lima')
  })

  it('Escape fecha a lista', async () => {
    mockApi({ 'GET /clientes': { body: { itens: [ana], total: 1, limit: 8, offset: 0 } } })
    await renderizar(<Caixa />)
    await userEvent.type(screen.getByRole('combobox'), 'a')
    await screen.findByRole('option', { name: /Ana/ })

    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
  })

  it('avisa quando nada é encontrado', async () => {
    mockApi({ 'GET /clientes': { body: { itens: [], total: 0, limit: 8, offset: 0 } } })
    await renderizar(<Caixa />)

    await userEvent.type(screen.getByRole('combobox'), 'zzz')

    expect(await screen.findByText('Nenhum cliente encontrado.')).toBeInTheDocument()
  })

  it('não permite trocar quando está desabilitado', async () => {
    mockApi({})
    await renderizar(<ClienteSelect valor={ana} onChange={() => {}} desabilitado />)

    expect(screen.getByText('Ana Souza')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Trocar cliente' })).not.toBeInTheDocument()
  })

  it('mostra a mensagem de erro do formulário', async () => {
    mockApi({})
    await renderizar(<ClienteSelect valor={null} onChange={() => {}} erro="Escolha o cliente." />)

    expect(screen.getByRole('alert')).toHaveTextContent('Escolha o cliente.')
  })
})
