import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, renderizar } from '../test/utils'
import Login from './Login'
import Recuperacao from './Recuperacao'

describe('Recuperação de senha', () => {
  it('abre pelo login e envia o e-mail cadastrado', async () => {
    const servidor = mockApi({ 'POST /auth/recuperar-senha': { status: 202, body: { detail: 'Confira seu e-mail e o spam.' } } })
    await renderizar(<Login />)
    await userEvent.click(screen.getByRole('button', { name: 'Esqueci minha senha' }))
    await userEvent.type(screen.getByLabelText(/E-mail cadastrado/), 'pessoa@example.org')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link de recuperação' }))
    expect(await screen.findByText('Confira seu e-mail e o spam.')).toBeInTheDocument()
    expect(servidor.ultima('POST', '/auth/recuperar-senha')?.corpo).toEqual({ email: 'pessoa@example.org' })
  })

  it('mostra a indisponibilidade sem prometer envio', async () => {
    mockApi({ 'POST /auth/recuperar-senha': { status: 503, body: { detail: 'Recuperação indisponível.' } } })
    await renderizar(<Recuperacao />)
    await userEvent.type(screen.getByLabelText(/E-mail cadastrado/), 'pessoa@example.org')
    await userEvent.click(screen.getByRole('button', { name: 'Enviar link de recuperação' }))
    expect(await screen.findByText('Recuperação indisponível.')).toBeInTheDocument()
  })

  it('confere confirmação e salva a nova senha com o token do link', async () => {
    const servidor = mockApi({ 'POST /auth/redefinir-senha': { status: 204 } })
    await renderizar(<Recuperacao />, { rota: '/redefinir-senha?token=link-temporario' })
    await userEvent.type(screen.getByLabelText(/^Nova senha/), 'NovaSenha123')
    await userEvent.type(screen.getByLabelText(/Confirmar nova senha/), 'outraSenha')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar nova senha' }))
    expect(await screen.findByText('As senhas não conferem.')).toBeInTheDocument()
    expect(servidor.de('POST', '/auth/redefinir-senha')).toHaveLength(0)
    await userEvent.clear(screen.getByLabelText(/Confirmar nova senha/))
    await userEvent.type(screen.getByLabelText(/Confirmar nova senha/), 'NovaSenha123')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar nova senha' }))
    expect(await screen.findByText('Senha redefinida. Entre novamente com a nova senha.')).toBeInTheDocument()
    expect(servidor.ultima('POST', '/auth/redefinir-senha')?.corpo).toEqual({ token: 'link-temporario', senha: 'NovaSenha123' })
  })
})
