import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderizar, VENDEDORA } from '../test/utils'
import { CupomModal } from './CupomModal'

const PEDIDO = { id_pedido: 5, cliente: { nome: 'Ana Souza' } }
const PDF = { texto: '%PDF-1.4', headers: { 'content-type': 'application/pdf', 'content-disposition': 'inline; filename="pedido-5-cliente.pdf"' } }

describe('CupomModal', () => {
  it('oferece as quatro vias e começa em "todas"', async () => {
    mockApi({})
    await renderizar(<CupomModal pedido={PEDIDO} onFechar={() => {}} />, { usuario: VENDEDORA })

    expect(screen.getByRole('dialog', { name: 'Cupom do pedido #5' })).toHaveTextContent('Ana Souza')
    expect(screen.getByRole('radio', { name: /Todas as vias/ })).toBeChecked()
    for (const nome of [/Via da ONG/, /Via do entregador/, /Via do cliente/]) expect(screen.getByRole('radio', { name: nome })).not.toBeChecked()
  })

  it('"Abrir para imprimir" pede a via escolhida e abre o PDF numa nova aba', async () => {
    const api = mockApi({ 'GET /pedidos/5/cupom': PDF })
    const abrir = vi.spyOn(window, 'open').mockReturnValue({} as Window)
    await renderizar(<CupomModal pedido={PEDIDO} onFechar={() => {}} />, { usuario: VENDEDORA })

    await userEvent.click(screen.getByRole('radio', { name: /Via do cliente/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Abrir para imprimir' }))

    await waitFor(() => expect(abrir).toHaveBeenCalled())
    expect(api.ultima('GET', '/pedidos/5/cupom')?.query.get('via')).toBe('cliente')
    expect(api.ultima('GET', '/pedidos/5/cupom')?.headers.get('authorization')).toBe('Bearer token-de-teste')
    expect(abrir).toHaveBeenCalledWith(expect.stringMatching(/^blob:/), '_blank', 'noopener')
  })

  it('se o navegador bloquear a janela, orienta a baixar o PDF', async () => {
    mockApi({ 'GET /pedidos/5/cupom': PDF })
    vi.spyOn(window, 'open').mockReturnValue(null)
    await renderizar(<CupomModal pedido={PEDIDO} onFechar={() => {}} />, { usuario: VENDEDORA })

    await userEvent.click(screen.getByRole('button', { name: 'Abrir para imprimir' }))

    expect(await screen.findByText(/bloqueou a nova janela/)).toBeInTheDocument()
  })

  it('"Baixar PDF" salva o arquivo com o nome que o servidor sugeriu', async () => {
    mockApi({ 'GET /pedidos/5/cupom': PDF })
    let nome = ''
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      nome = this.download
    })
    await renderizar(<CupomModal pedido={PEDIDO} onFechar={() => {}} />, { usuario: VENDEDORA })

    await userEvent.click(screen.getByRole('button', { name: 'Baixar PDF' }))

    await waitFor(() => expect(nome).toBe('pedido-5-cliente.pdf'))
  })

  it('pedido cancelado: mostra a recusa do servidor', async () => {
    mockApi({ 'GET /pedidos/5/cupom': { status: 409, body: { detail: 'Pedido cancelado não gera cupom.' } } })
    await renderizar(<CupomModal pedido={PEDIDO} onFechar={() => {}} />, { usuario: VENDEDORA })

    await userEvent.click(screen.getByRole('button', { name: 'Abrir para imprimir' }))

    expect(await screen.findByText('Pedido cancelado não gera cupom.')).toBeInTheDocument()
  })

  it('Escape e "Fechar" fecham o modal', async () => {
    mockApi({})
    const fechar = vi.fn()
    await renderizar(<CupomModal pedido={PEDIDO} onFechar={fechar} />, { usuario: VENDEDORA })

    await userEvent.keyboard('{Escape}')
    await userEvent.click(screen.getByRole('button', { name: 'Fechar' }))

    expect(fechar).toHaveBeenCalledTimes(2)
  })
})
