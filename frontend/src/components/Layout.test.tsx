import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { getToken } from '../lib/api'
import { ADMIN, mockApi, renderizar, VENDEDORA } from '../test/utils'
import { SoAdmin } from '../App'
import { Layout } from './Layout'

const BAIXO = (n: number) => ({ id_produto: n, nome: `Produto ${n}`, descricao: 'd', preco_unitario: '1.00', estoque_atual: 1, estoque_minimo: 5, is_ativo: true, alerta_estoque_baixo: true })
const BACKUP_OK = { alerta: false, motivo_alerta: null }
const BACKUP_RUIM = { alerta: true, motivo_alerta: 'O último backup falhou: pg_dump não encontrado.' }

describe('Layout e menu', () => {
  it('a administradora vê as áreas administrativas com a etiqueta Admin', async () => {
    mockApi({ 'GET /usuarios/me': { body: ADMIN }, 'GET /estoque/alertas': { body: [] }, 'GET /sistema/backup': { body: BACKUP_OK } })
    await renderizar(<Layout />, { usuario: ADMIN })

    const menu = screen.getByRole('navigation', { name: 'Principal' })
    for (const nome of ['Início', 'Clientes', 'Pedidos', 'Produtos', 'Relatórios', 'Usuários', 'Configurações'])
      expect(menu).toHaveTextContent(nome)
    expect(screen.getAllByText('Admin')).toHaveLength(3)
    expect(screen.getAllByText('Administradora').length).toBeGreaterThan(0)
  })

  it('a vendedora NÃO vê relatórios, usuários nem configurações e nem consulta o backup', async () => {
    const api = mockApi({ 'GET /usuarios/me': { body: VENDEDORA }, 'GET /estoque/alertas': { body: [] }, 'GET /sistema/backup': { body: BACKUP_OK } })
    await renderizar(<Layout />, { usuario: VENDEDORA })

    const menu = screen.getByRole('navigation', { name: 'Principal' })
    for (const nome of ['Início', 'Clientes', 'Pedidos', 'Produtos']) expect(menu).toHaveTextContent(nome)
    for (const nome of ['Relatórios', 'Usuários', 'Configurações']) expect(menu).not.toHaveTextContent(nome)
    expect(screen.queryByText('Admin')).not.toBeInTheDocument()
    await waitFor(() => expect(api.de('GET', '/estoque/alertas')).toHaveLength(1))
    expect(api.de('GET', '/sistema/backup')).toHaveLength(0)
  })

  it('mostra no menu quantos produtos estão com estoque baixo', async () => {
    mockApi({ 'GET /usuarios/me': { body: VENDEDORA }, 'GET /estoque/alertas': { body: [BAIXO(1), BAIXO(2), BAIXO(3)] } })
    await renderizar(<Layout />, { usuario: VENDEDORA })

    expect(await screen.findByLabelText('3 com estoque baixo')).toHaveTextContent('3')
  })

  it('avisa a administradora quando o backup falhou', async () => {
    mockApi({ 'GET /usuarios/me': { body: ADMIN }, 'GET /estoque/alertas': { body: [] }, 'GET /sistema/backup': { body: BACKUP_RUIM } })
    await renderizar(<Layout />, { usuario: ADMIN })

    expect(await screen.findByText('Atenção ao backup do banco de dados')).toBeInTheDocument()
    expect(screen.getByText(/pg_dump não encontrado/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Abrir configurações' })).toHaveAttribute('href', '/configuracoes')
  })

  it('sem alerta de backup, não mostra aviso', async () => {
    const api = mockApi({ 'GET /usuarios/me': { body: ADMIN }, 'GET /estoque/alertas': { body: [] }, 'GET /sistema/backup': { body: BACKUP_OK } })
    await renderizar(<Layout />, { usuario: ADMIN })
    await waitFor(() => expect(api.de('GET', '/sistema/backup')).toHaveLength(1))

    expect(screen.queryByText('Atenção ao backup do banco de dados')).not.toBeInTheDocument()
  })

  it('"Sair" encerra a sessão no servidor e apaga o token', async () => {
    const api = mockApi({ 'GET /usuarios/me': { body: VENDEDORA }, 'GET /estoque/alertas': { body: [] }, 'POST /auth/logout': { status: 204 } })
    await renderizar(<Layout />, { usuario: VENDEDORA })

    await userEvent.click(screen.getAllByRole('button', { name: /Sair/ })[0] as HTMLElement)

    await waitFor(() => expect(api.de('POST', '/auth/logout')).toHaveLength(1))
    await waitFor(() => expect(getToken()).toBeNull())
  })

  it('mostra o nome e o cargo de quem está logada', async () => {
    mockApi({ 'GET /usuarios/me': { body: VENDEDORA }, 'GET /estoque/alertas': { body: [] } })
    await renderizar(<Layout />, { usuario: VENDEDORA })

    expect(screen.getByText('Maria Vendedora')).toBeInTheDocument()
    expect(screen.getByText('Vendedora')).toBeInTheDocument()
  })
})

describe('SoAdmin (proteção das telas)', () => {
  it('a vendedora vê "área restrita" no lugar da tela', async () => {
    mockApi({ 'GET /usuarios/me': { body: VENDEDORA } })
    await renderizar(<SoAdmin><p>conteúdo secreto</p></SoAdmin>, { usuario: VENDEDORA })

    expect(screen.getByText('Área restrita à administradora')).toBeInTheDocument()
    expect(screen.queryByText('conteúdo secreto')).not.toBeInTheDocument()
  })

  it('a administradora vê a tela', async () => {
    mockApi({ 'GET /usuarios/me': { body: ADMIN } })
    await renderizar(<SoAdmin><p>conteúdo secreto</p></SoAdmin>, { usuario: ADMIN })

    expect(screen.getByText('conteúdo secreto')).toBeInTheDocument()
  })
})
