import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { getToken } from '../lib/api'
import { mockApi, renderizar, VENDEDORA } from '../test/utils'
import Login from './Login'

const preencher = async (email: string, senha: string) => {
  await userEvent.type(screen.getByLabelText(/E-mail/), email)
  await userEvent.type(screen.getByLabelText(/^Senha/), senha)
}

describe('Login', () => {
  it('valida os campos antes de chamar o servidor', async () => {
    const api = mockApi({})
    await renderizar(<Login />)

    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText('Informe um e-mail válido.')).toBeInTheDocument()
    expect(screen.getByText('Informe a senha.')).toBeInTheDocument()
    expect(api.chamadas).toHaveLength(0)
  })

  it('entra com sucesso: guarda o token e carrega o usuário', async () => {
    const api = mockApi({
      'POST /auth/login/json': { body: { access_token: 'tok123', token_type: 'bearer' } },
      'GET /usuarios/me': { body: VENDEDORA },
    })
    await renderizar(<Login />)
    await preencher(' maria@x.org ', 'senhaForte123')

    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    await waitFor(() => expect(getToken()).toBe('tok123'))
    expect(api.ultima('POST', '/auth/login/json')?.corpo).toEqual({ email: 'maria@x.org', senha: 'senhaForte123' })
    expect(api.ultima('POST', '/auth/login/json')?.headers.get('authorization')).toBeNull()
    await waitFor(() => expect(api.ultima('GET', '/usuarios/me')?.headers.get('authorization')).toBe('Bearer tok123'))
  })

  it('senha errada: mostra a mensagem e limpa a senha', async () => {
    mockApi({ 'POST /auth/login/json': { status: 401, body: { detail: 'E-mail ou senha incorretos.' } } })
    await renderizar(<Login />)
    await preencher('maria@x.org', 'errada123')

    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText('E-mail ou senha incorretos.')).toBeInTheDocument()
    expect(screen.getByLabelText(/^Senha/)).toHaveValue('')
    expect(getToken()).toBeNull()
  })

  it('bloqueio por muitas tentativas mostra o aviso do servidor', async () => {
    mockApi({ 'POST /auth/login/json': { status: 429, headers: { 'retry-after': '900' }, body: { detail: 'Muitas tentativas. Tente novamente em 15 minuto(s).' } } })
    await renderizar(<Login />)
    await preencher('maria@x.org', 'qualquer123')

    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText('Muitas tentativas. Tente novamente em 15 minuto(s).')).toBeInTheDocument()
  })

  it('servidor fora do ar mostra mensagem amigável', async () => {
    const { vi } = await import('vitest')
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    await renderizar(<Login />)
    await preencher('maria@x.org', 'qualquer123')

    await userEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByText(/conectar ao servidor/)).toBeInTheDocument()
  })

  it('a senha fica escondida e pode ser mostrada', async () => {
    mockApi({})
    await renderizar(<Login />)
    const campo = screen.getByLabelText(/^Senha/)
    expect(campo).toHaveAttribute('type', 'password')

    await userEvent.click(screen.getByRole('button', { name: 'Mostrar senha' }))

    expect(campo).toHaveAttribute('type', 'text')
  })

  it('mostra a logo da ONG (vinda do servidor)', async () => {
    mockApi({})
    await renderizar(<Login />)

    const logos = screen.getAllByAltText('Casa da Sopa de Restinga')
    expect(logos[0]).toHaveAttribute('src', expect.stringMatching(/^\/sistema\/logo\?v=\d+$/))
  })
})
