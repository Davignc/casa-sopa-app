import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Usuario } from '../lib/types'
import { pagina } from '../test/dados'
import { ADMIN, mockApi, renderizar, VENDEDORA } from '../test/utils'
import Usuarios from './Usuarios'

const INATIVA: Usuario = { id_usuario: 5, nome: 'Carla Antiga', email: 'carla@x.org', telefone: '16977776666', cargo: 'vendedora', comissao: null, is_ativo: false }

async function abrir(extra: Record<string, unknown> = {}) {
  const api = mockApi({ 'GET /usuarios': { body: pagina([ADMIN, VENDEDORA, INATIVA]) }, ...extra } as Parameters<typeof mockApi>[0])
  await renderizar(<Usuarios />, { usuario: ADMIN })
  await screen.findByRole('row', { name: /Maria Vendedora/ })
  return api
}
const linha = (nome: RegExp) => screen.getByRole('row', { name: nome })

describe('Usuários: lista', () => {
  it('mostra nome, e-mail, telefone, cargo, comissão e situação', async () => {
    await abrir()

    const l = linha(/Maria Vendedora/)
    expect(l).toHaveTextContent('maria@x.org')
    expect(l).toHaveTextContent('(16) 99999-0001')
    expect(l).toHaveTextContent('Vendedora')
    expect(l).toHaveTextContent('10%')
    expect(l).toHaveTextContent('Ativo')
    expect(linha(/Carla Antiga/)).toHaveTextContent('Inativo')
  })

  it('marca quem está logada e não oferece inativar a própria conta', async () => {
    await abrir()

    expect(linha(/Ana Administradora/)).toHaveTextContent('você')
    expect(within(linha(/Ana Administradora/)).queryByRole('button', { name: /Inativar|Reativar/ })).not.toBeInTheDocument()
    expect(within(linha(/Maria Vendedora/)).getByRole('button', { name: 'Inativar Maria Vendedora' })).toBeInTheDocument()
    expect(within(linha(/Carla Antiga/)).getByRole('button', { name: 'Reativar Carla Antiga' })).toBeInTheDocument()
  })

  it('os filtros vão para o servidor', async () => {
    const api = await abrir()

    await userEvent.type(screen.getByLabelText('Buscar usuários'), 'mar')
    await userEvent.selectOptions(screen.getByLabelText('Filtrar por cargo'), 'vendedora')
    await userEvent.selectOptions(screen.getByLabelText('Filtrar por situação'), 'false')

    await waitFor(() => {
      const q = api.ultima('GET', '/usuarios')?.query
      expect(q?.get('busca')).toBe('mar')
      expect(q?.get('cargo')).toBe('vendedora')
      expect(q?.get('is_ativo')).toBe('false')
    })
  })
})

describe('Usuários: cadastro', () => {
  async function abrirNovo(extra: Record<string, unknown> = {}) {
    const api = await abrir(extra)
    await userEvent.click(screen.getByRole('button', { name: 'Novo usuário' }))
    return { api, dialogo: await screen.findByRole('dialog', { name: '+ Novo usuário' }) }
  }
  async function preencher(d: HTMLElement, v: { nome?: string; email?: string; fone?: string; senha?: string; confirmar?: string } = {}) {
    await userEvent.type(within(d).getByLabelText('Nome completo *'), v.nome ?? 'Joana Lima')
    await userEvent.type(within(d).getByLabelText('E-mail *'), v.email ?? 'JOANA@X.org')
    await userEvent.type(within(d).getByLabelText('Telefone *'), v.fone ?? '16999990009')
    await userEvent.type(within(d).getByLabelText('Senha *'), v.senha ?? 'senhaForte123')
    await userEvent.type(within(d).getByLabelText('Confirmar senha'), v.confirmar ?? v.senha ?? 'senhaForte123')
  }

  it('mostra o que falta e não envia', async () => {
    const { api, dialogo } = await abrirNovo()

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar usuário' }))

    for (const msg of ['Informe o nome.', 'Informe um e-mail válido.', 'Informe DDD + número.', 'Mínimo de 8 caracteres.']) expect(await within(dialogo).findByText(msg)).toBeInTheDocument()
    expect(api.de('POST', '/usuarios')).toHaveLength(0)
  })

  it('exige que as duas senhas sejam iguais', async () => {
    const { api, dialogo } = await abrirNovo()
    await preencher(dialogo, { confirmar: 'outraSenha999' })

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar usuário' }))

    expect(await within(dialogo).findByText('As senhas não conferem.')).toBeInTheDocument()
    expect(api.de('POST', '/usuarios')).toHaveLength(0)
  })

  it('senha acima de 72 bytes é recusada (limite do bcrypt)', async () => {
    const { dialogo } = await abrirNovo()
    await preencher(dialogo, { senha: 'a'.repeat(73) })

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar usuário' }))

    expect(await within(dialogo).findByText('Senha longa demais (máx. 72 bytes).')).toBeInTheDocument()
  })

  it('cadastra uma vendedora com comissão', async () => {
    const { api, dialogo } = await abrirNovo({ 'POST /usuarios': { status: 201, body: VENDEDORA } })
    await preencher(dialogo)
    await userEvent.type(within(dialogo).getByLabelText('Comissão (%)'), '7,5')

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar usuário' }))

    await waitFor(() => expect(api.de('POST', '/usuarios')).toHaveLength(1))
    expect(api.ultima('POST', '/usuarios')?.corpo).toEqual({ nome: 'Joana Lima', email: 'joana@x.org', telefone: '(16) 99999-0009', cargo: 'vendedora', comissao: 7.5, senha: 'senhaForte123' })
    expect(await screen.findByText('Usuário cadastrado.')).toBeInTheDocument()
  })

  it('administradora não tem campo de comissão e ele não é enviado', async () => {
    const { api, dialogo } = await abrirNovo({ 'POST /usuarios': { status: 201, body: ADMIN } })
    await preencher(dialogo)
    await userEvent.selectOptions(within(dialogo).getByLabelText('Cargo *'), 'administradora')

    expect(within(dialogo).queryByLabelText('Comissão (%)')).not.toBeInTheDocument()
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar usuário' }))

    await waitFor(() => expect(api.de('POST', '/usuarios')).toHaveLength(1))
    expect(api.ultima('POST', '/usuarios')?.corpo).not.toHaveProperty('comissao')
    expect(api.ultima('POST', '/usuarios')?.corpo).toMatchObject({ cargo: 'administradora' })
  })

  it('comissão fora de 0 a 100 é recusada', async () => {
    const { api, dialogo } = await abrirNovo()
    await preencher(dialogo)
    await userEvent.type(within(dialogo).getByLabelText('Comissão (%)'), '150')

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar usuário' }))

    expect(await within(dialogo).findByText('Use um valor de 0 a 100.')).toBeInTheDocument()
    expect(api.de('POST', '/usuarios')).toHaveLength(0)
  })

  it('e-mail repetido: mostra a mensagem do servidor', async () => {
    const { dialogo } = await abrirNovo({ 'POST /usuarios': { status: 409, body: { detail: 'Já existe um usuário com este e-mail.' } } })
    await preencher(dialogo)

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Cadastrar usuário' }))

    expect(await within(dialogo).findByText('Já existe um usuário com este e-mail.')).toBeInTheDocument()
  })
})

describe('Usuários: edição e situação', () => {
  async function abrirEdicao(nome: string, extra: Record<string, unknown> = {}) {
    const api = await abrir(extra)
    await userEvent.click(within(linha(new RegExp(nome))).getByRole('button', { name: new RegExp(`Editar ${nome}`) }))
    return { api, dialogo: await screen.findByRole('dialog', { name: 'Editar usuário' }) }
  }

  it('vem preenchido e só envia o que mudou', async () => {
    const { api, dialogo } = await abrirEdicao('Maria Vendedora', { 'PATCH /usuarios/2': { body: VENDEDORA } })
    expect(within(dialogo).getByLabelText('Nome completo *')).toHaveValue('Maria Vendedora')
    expect(within(dialogo).getByLabelText('Comissão (%)')).toHaveValue('10')

    await userEvent.clear(within(dialogo).getByLabelText('Comissão (%)'))
    await userEvent.type(within(dialogo).getByLabelText('Comissão (%)'), '12')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(api.de('PATCH', '/usuarios/2')).toHaveLength(1))
    expect(api.ultima('PATCH', '/usuarios/2')?.corpo).toEqual({ comissao: 12 })
  })

  it('nova senha só vai se for preenchida (e avisa que derruba as sessões)', async () => {
    const { api, dialogo } = await abrirEdicao('Maria Vendedora', { 'PATCH /usuarios/2': { body: VENDEDORA } })
    expect(dialogo).toHaveTextContent('encerra as sessões abertas dela')

    await userEvent.type(within(dialogo).getByLabelText('Nova senha'), 'novaSenha12345')
    await userEvent.type(within(dialogo).getByLabelText('Confirmar senha'), 'novaSenha12345')
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(api.de('PATCH', '/usuarios/2')).toHaveLength(1))
    expect(api.ultima('PATCH', '/usuarios/2')?.corpo).toEqual({ senha: 'novaSenha12345' })
  })

  it('sem mudanças, não chama o servidor', async () => {
    const { api, dialogo } = await abrirEdicao('Maria Vendedora')

    await userEvent.click(within(dialogo).getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Editar usuário' })).not.toBeInTheDocument())
    expect(api.de('PATCH', '/usuarios/2')).toHaveLength(0)
  })

  it('a administradora não pode mudar o próprio cargo', async () => {
    const { dialogo } = await abrirEdicao('Ana Administradora')

    expect(within(dialogo).getByLabelText('Cargo *')).toBeDisabled()
    expect(dialogo).toHaveTextContent('Você não pode alterar o seu próprio cargo.')
  })

  it('inativar pede confirmação e avisa que corta o acesso na hora', async () => {
    const api = await abrir({ 'DELETE /usuarios/2': { status: 204 } })

    await userEvent.click(within(linha(/Maria Vendedora/)).getByRole('button', { name: 'Inativar Maria Vendedora' }))
    const confirmar = await screen.findByRole('dialog', { name: 'Inativar usuário?' })
    expect(confirmar).toHaveTextContent('perdem o acesso na hora')
    expect(api.de('DELETE', '/usuarios/2')).toHaveLength(0)
    await userEvent.click(within(confirmar).getByRole('button', { name: 'Inativar' }))

    await waitFor(() => expect(api.de('DELETE', '/usuarios/2')).toHaveLength(1))
    expect(await screen.findByText('Usuário inativado.')).toBeInTheDocument()
  })

  it('reativar é direto', async () => {
    const api = await abrir({ 'POST /usuarios/5/reativar': { body: { ...INATIVA, is_ativo: true } } })

    await userEvent.click(within(linha(/Carla Antiga/)).getByRole('button', { name: 'Reativar Carla Antiga' }))

    await waitFor(() => expect(api.de('POST', '/usuarios/5/reativar')).toHaveLength(1))
  })
})
