import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ADMIN, mockApi, renderizar } from '../test/utils'
import Importacoes from './Importacoes'

const previa = { tipo: 'clientes', total_linhas: 1, novos: 1, ignorados: 0, erros: [], amostra: [{ nome: 'Cliente', telefone: '16977776666' }], token: 'previa-segura', concluida: false }

describe('Importar dados', () => {
  it('só confirma depois de analisar e envia o mesmo arquivo com o token', async () => {
    const servidor = mockApi({ 'POST /importacoes/analisar': { body: previa }, 'POST /importacoes/confirmar': { body: { ...previa, concluida: true, token: null } } })
    await renderizar(<Importacoes />, { usuario: ADMIN })
    expect(screen.queryByRole('button', { name: /Confirmar importação/ })).not.toBeInTheDocument()
    const arquivo = new File(['dados'], 'antigos.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    await userEvent.upload(screen.getByLabelText(/Planilha Excel ou CSV/), arquivo)
    await userEvent.click(screen.getByRole('button', { name: 'Analisar planilha' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Confirmar importação de 1 registros' }))
    expect(await screen.findByText('Importação concluída')).toBeInTheDocument()
    expect(servidor.ultima('POST', '/importacoes/confirmar')?.form?.get('token')).toBe('previa-segura')
    expect(servidor.ultima('POST', '/importacoes/confirmar')?.form?.get('arquivo')).toBe(arquivo)
  })

  it('exibe linha inválida e impede confirmação', async () => {
    mockApi({ 'POST /importacoes/analisar': { body: { ...previa, token: null, erros: [{ linha: 3, mensagem: 'Telefone inválido.' }] } } })
    await renderizar(<Importacoes />, { usuario: ADMIN })
    await userEvent.upload(screen.getByLabelText(/Planilha Excel ou CSV/), new File(['dados'], 'dados.csv', { type: 'text/csv' }))
    await userEvent.click(screen.getByRole('button', { name: 'Analisar planilha' }))
    expect(await screen.findByText('Telefone inválido.')).toBeInTheDocument()
    expect(screen.getByText('Linha 3:')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Confirmar importação/ })).not.toBeInTheDocument()
  })

  it('trocar o tipo descarta a prévia anterior', async () => {
    mockApi({ 'POST /importacoes/analisar': { body: previa } })
    await renderizar(<Importacoes />, { usuario: ADMIN })
    await userEvent.upload(screen.getByLabelText(/Planilha Excel ou CSV/), new File(['dados'], 'dados.csv', { type: 'text/csv' }))
    await userEvent.click(screen.getByRole('button', { name: 'Analisar planilha' }))
    expect(await screen.findByRole('button', { name: /Confirmar importação/ })).toBeInTheDocument()
    await userEvent.selectOptions(screen.getByLabelText('Tipo de dados'), 'vendas')
    expect(screen.queryByRole('button', { name: /Confirmar importação/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Analisar planilha' })).toBeDisabled()
  })
})
