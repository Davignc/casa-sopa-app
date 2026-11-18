import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { afterEach, describe, expect, it } from 'vitest'
import { ADMIN, VENDEDORA, mockApi, renderizar } from '../test/utils'
import { pagina, pedido } from '../test/dados'
import Pedidos from '../pages/Pedidos'
import PedidoForm from '../pages/PedidoForm'
import { Layout } from './Layout'
import { Privacidade } from './Privacidade'
import { Tema } from './Tema'
import { Abas, Modal } from './ui'

afterEach(() => { localStorage.clear(); document.documentElement.classList.remove('dark') })

describe('Acessibilidade', () => {
  it('navega nas abas com setas, Home e End e mantém um único ponto de Tab', async () => {
    function Exemplo() { const [valor, setValor] = useState('a'); return <Abas itens={[{ id: 'a', rotulo: 'A' }, { id: 'b', rotulo: 'B' }, { id: 'c', rotulo: 'C' }]} valor={valor} onMudar={setValor} /> }
    render(<Exemplo />)
    await userEvent.tab()
    expect(screen.getByRole('tab', { name: 'A' })).toHaveFocus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'B' })).toHaveFocus()
    expect(screen.getByRole('tab', { name: 'B' })).toHaveAttribute('aria-selected', 'true')
    await userEvent.keyboard('{End}')
    expect(screen.getByRole('tab', { name: 'C' })).toHaveFocus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'A' })).toHaveFocus()
    await userEvent.keyboard('{Home}')
    expect(screen.getAllByRole('tab').filter((e) => e.tabIndex === 0)).toHaveLength(1)
  })

  it('Escape fecha somente o diálogo mais recente e restaura o foco', async () => {
    function Exemplo() {
      const [filho, setFilho] = useState(false)
      return <Modal aberto titulo="Principal" onFechar={() => { throw new Error('O diálogo principal deve continuar aberto') }}><button onClick={() => setFilho(true)}>Abrir confirmação</button><Modal aberto={filho} titulo="Confirmação" onFechar={() => setFilho(false)}><input aria-label="Campo do filho" /></Modal></Modal>
    }
    render(<Exemplo />)
    await userEvent.click(screen.getByText('Abrir confirmação'))
    expect(screen.getByLabelText('Campo do filho')).toHaveFocus()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Confirmação' })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: 'Principal' })).toBeInTheDocument()
    expect(screen.getByText('Abrir confirmação')).toHaveFocus()
  })

  it('menu móvel prende o foco, fecha com Escape e devolve o foco ao botão', async () => {
    mockApi({ 'GET /estoque/alertas': { body: [] } })
    await renderizar(<Layout />, { usuario: VENDEDORA })
    const abrir = screen.getByRole('button', { name: 'Abrir menu' })
    await userEvent.click(abrir)
    const menu = screen.getByRole('dialog', { name: 'Menu principal' })
    for (let i = 0; i < 12; i++) { await userEvent.tab(); expect(menu.contains(document.activeElement)).toBe(true) }
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(abrir).toHaveFocus()
    await userEvent.click(screen.getByRole('link', { name: 'Pular para o conteúdo' }))
    expect(screen.getByRole('main')).toHaveFocus()
  })

  it('salva o modo escuro e restaura a preferência ao montar novamente', async () => {
    const tela = render(<Tema />)
    await userEvent.click(screen.getByRole('button', { name: 'Modo escuro' }))
    expect(document.documentElement).toHaveClass('dark')
    expect(localStorage.getItem('casa-sopa-tema')).toBe('escuro')
    tela.unmount()
    render(<Tema />)
    expect(screen.getByRole('button', { name: 'Modo escuro' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Modo escuro' }))
    expect(document.documentElement).not.toHaveClass('dark')
  })

  it('apresenta a finalidade e os direitos sobre dados sem exigir consentimento genérico', async () => {
    render(<Privacidade />)
    expect(screen.getByText(/Nome e telefone identificam/)).toBeInTheDocument()
    await userEvent.click(screen.getByText('Como cuidar dos dados e solicitar atendimento'))
    expect(screen.getByText(/Para solicitar acesso, correção ou exclusão/)).toBeVisible()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
  })
})

describe('Autoria dos pedidos na interface', () => {
  it.each([['vendedora', VENDEDORA, false], ['administradora', ADMIN, true]] as const)('%s recebe somente as ações autorizadas em pedido alheio', async (_, usuario, autorizado) => {
    const alheio = pedido(17, 'em_aberto', { vendedora: { id_usuario: 88, nome: 'Outra responsável' } })
    const api = mockApi({ 'GET /pedidos': { body: pagina([alheio]) }, 'GET /pedidos/contagem': { body: { todos: 1, em_aberto: 1, confirmado: 0, entregue: 0, cancelado: 0 } } })
    await renderizar(<Pedidos />, { usuario })
    const selecionar = await screen.findByRole('button', { name: 'Selecionar pedido 17' })
    selecionar.focus()
    await userEvent.keyboard('{Enter}')
    expect(selecionar).toHaveAttribute('aria-pressed', 'true')
    for (const nome of ['Alterar', 'Cancelar', 'Excluir']) {
      const botao = screen.getByRole('button', { name: nome })
      if (autorizado) expect(botao).toBeEnabled(); else expect(botao).toBeDisabled()
    }
    const linha = selecionar.closest('tr')!
    if (autorizado) expect(within(linha).getByRole('combobox')).toBeInTheDocument()
    else expect(within(linha).queryByRole('combobox')).not.toBeInTheDocument()
    expect(api.chamadas.filter((c) => c.metodo !== 'GET')).toHaveLength(0)
  })

  it('bloqueia a URL de edição de pedido alheio', async () => {
    const api = mockApi({ 'GET /pedidos/17': { body: pedido(17, 'em_aberto', { vendedora: { id_usuario: 88, nome: 'Outra' } }) }, 'GET /produtos': { body: pagina([]) } })
    await renderizar(<PedidoForm />, { usuario: VENDEDORA, rota: '/pedidos/17/editar', caminho: '/pedidos/:id/editar' })
    await waitFor(() => expect(screen.getByText('Pedido com acesso restrito')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Salvar alterações' })).not.toBeInTheDocument()
    expect(api.chamadas.some((c) => c.metodo === 'PATCH')).toBe(false)
  })
})
