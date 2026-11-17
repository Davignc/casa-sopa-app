import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { StatusBackup } from '../lib/types'
import { ADMIN, mockApi, renderizar } from '../test/utils'
import Configuracoes, { LIMITE_DA_LOGO, validarLogo } from './Configuracoes'

const BACKUP_OK: StatusBackup = {
  habilitado: true, ultimo_status: 'ok', ultima_tentativa: '2026-10-25T06:00:00Z', ultimo_sucesso: '2026-10-25T06:00:00Z',
  mensagem: 'Backup casa_sopa_20261025_060000.dump gerado (123456 bytes).', proxima_execucao: '2026-11-01T06:00:00Z', alerta: false, motivo_alerta: null,
  retencao: 8, arquivos: [{ nome: 'casa_sopa_20261025_060000.dump', tamanho_bytes: 123456, criado_em: '2026-10-25T06:00:00Z' }],
}
const png = (nome = 'logo.png', tipo = 'image/png', tamanho = 1000) => new File([new Uint8Array(tamanho)], nome, { type: tipo })

async function abrir(extra: Record<string, unknown> = {}, situacao = { personalizada: false }) {
  const api = mockApi({ 'GET /sistema/logo/situacao': { body: situacao }, 'GET /sistema/backup': { body: BACKUP_OK }, ...extra } as Parameters<typeof mockApi>[0])
  await renderizar(<Configuracoes />, { usuario: ADMIN })
  await screen.findByText('casa_sopa_20261025_060000.dump')
  return api
}

describe('validarLogo', () => {
  it.each([
    [{ type: 'image/png', size: 1000 }, null], [{ type: 'image/jpeg', size: 1000 }, null], [{ type: 'image/webp', size: LIMITE_DA_LOGO }, null],
    [{ type: 'image/gif', size: 1000 }, 'Use uma imagem PNG, JPG ou WebP.'],
    [{ type: 'image/svg+xml', size: 1000 }, 'Use uma imagem PNG, JPG ou WebP.'],
    [{ type: 'application/pdf', size: 1000 }, 'Use uma imagem PNG, JPG ou WebP.'],
    [{ type: '', size: 1000 }, 'Use uma imagem PNG, JPG ou WebP.'],
    [{ type: 'image/png', size: LIMITE_DA_LOGO + 1 }, 'A imagem passa de 2 MB. Escolha uma menor.'],
    [{ type: 'image/png', size: 0 }, 'O arquivo está vazio.'],
  ])('%j -> %s', (arquivo, esperado) => {
    expect(validarLogo(arquivo)).toBe(esperado)
  })
})

describe('Configurações: logo', () => {
  it('mostra a logo atual e começa sem nada para salvar', async () => {
    await abrir()

    const cartao = screen.getByRole('region', { name: 'Logo da ONG' })
    expect(within(cartao).getByAltText('Logo da Casa da Sopa de Restinga')).toHaveAttribute('src', expect.stringMatching(/^\/sistema\/logo\?v=\d+$/))
    expect(within(cartao).getByText('Logo padrão do sistema')).toBeInTheDocument()
    expect(within(cartao).getByRole('button', { name: 'Salvar nova logo' })).toBeDisabled()
    expect(within(cartao).queryByRole('button', { name: 'Restaurar logo padrão' })).not.toBeInTheDocument()
  })

  it('escolher um arquivo mostra a prévia antes de salvar', async () => {
    await abrir()

    await userEvent.upload(screen.getByLabelText('Escolher arquivo da logo'), png())

    expect(await screen.findByAltText('Prévia da nova logo')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Salvar nova logo' })).toBeEnabled()
  })

  it('envia o arquivo, avisa e atualiza a logo em todo o sistema', async () => {
    const api = await abrir({ 'POST /sistema/logo': { body: { personalizada: true } } })
    const antes = screen.getAllByAltText('Logo da Casa da Sopa de Restinga')[0]?.getAttribute('src')
    await new Promise((r) => setTimeout(r, 5)) // garante um carimbo de tempo diferente
    await userEvent.upload(screen.getByLabelText('Escolher arquivo da logo'), png('minha-logo.png'))

    await userEvent.click(screen.getByRole('button', { name: 'Salvar nova logo' }))

    await waitFor(() => expect(api.de('POST', '/sistema/logo')).toHaveLength(1))
    const arquivo = api.ultima('POST', '/sistema/logo')?.form?.get('arquivo') as File
    expect(arquivo.name).toBe('minha-logo.png')
    expect(await screen.findByText('Logo atualizada em todo o sistema.')).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByAltText('Logo da Casa da Sopa de Restinga')[0]?.getAttribute('src')).not.toBe(antes))
    expect(screen.queryByAltText('Prévia da nova logo')).not.toBeInTheDocument()
  })

  it('recusa tipo de arquivo inválido, sem enviar', async () => {
    const api = await abrir()
    const u = userEvent.setup({ applyAccept: false })

    await u.upload(screen.getByLabelText('Escolher arquivo da logo'), png('logo.gif', 'image/gif'))

    expect(await screen.findByText('Use uma imagem PNG, JPG ou WebP.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Salvar nova logo' })).toBeDisabled()
    expect(api.de('POST', '/sistema/logo')).toHaveLength(0)
  })

  it('recusa arquivo grande demais', async () => {
    await abrir()

    await userEvent.upload(screen.getByLabelText('Escolher arquivo da logo'), png('grande.png', 'image/png', LIMITE_DA_LOGO + 10))

    expect(await screen.findByText('A imagem passa de 2 MB. Escolha uma menor.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Salvar nova logo' })).toBeDisabled()
  })

  it('mostra o motivo quando o servidor recusa a imagem', async () => {
    await abrir({ 'POST /sistema/logo': { status: 422, body: { detail: 'O arquivo não é uma imagem válida.' } } })
    await userEvent.upload(screen.getByLabelText('Escolher arquivo da logo'), png())

    await userEvent.click(screen.getByRole('button', { name: 'Salvar nova logo' }))

    expect(await screen.findByText('O arquivo não é uma imagem válida.')).toBeInTheDocument()
  })

  it('com logo personalizada, oferece restaurar a padrão (com confirmação)', async () => {
    const api = await abrir({ 'DELETE /sistema/logo': { body: { personalizada: false } } }, { personalizada: true })

    expect(await screen.findByText('Logo personalizada')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Restaurar logo padrão' }))
    const dialogo = await screen.findByRole('dialog', { name: 'Restaurar a logo padrão?' })
    expect(api.de('DELETE', '/sistema/logo')).toHaveLength(0)
    await userEvent.click(within(dialogo).getByRole('button', { name: 'Restaurar' }))

    await waitFor(() => expect(api.de('DELETE', '/sistema/logo')).toHaveLength(1))
    expect(await screen.findByText('Logo padrão restaurada.')).toBeInTheDocument()
  })
})

describe('Configurações: backup', () => {
  it('mostra a situação, as datas e os arquivos', async () => {
    await abrir()

    const cartao = screen.getByRole('region', { name: 'Backup do banco de dados' })
    expect(within(cartao).getByText('Último backup: sucesso')).toBeInTheDocument()
    expect(within(cartao).getByText('Ligado (semanal)')).toBeInTheDocument()
    expect(within(cartao).getAllByText('25/10 03:00').length).toBeGreaterThan(0)
    expect(within(cartao).getByText('120,6 KB')).toBeInTheDocument()
    expect(within(cartao).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('quando há alerta, destaca o motivo', async () => {
    await abrir({ 'GET /sistema/backup': { body: { ...BACKUP_OK, ultimo_status: 'erro', alerta: true, motivo_alerta: 'O último backup falhou: pg_dump não encontrado.' } } })

    expect(await screen.findByRole('alert')).toHaveTextContent('pg_dump não encontrado')
    expect(screen.getByText('Último backup: falhou')).toBeInTheDocument()
  })

  it('nunca executado e desligado aparecem como tal', async () => {
    await abrir({ 'GET /sistema/backup': { body: { ...BACKUP_OK, habilitado: false, ultimo_status: 'nunca_executado', ultimo_sucesso: null, ultima_tentativa: null, arquivos: [], mensagem: null } } }).catch(() => {})
    expect(await screen.findByText('Nenhum backup ainda')).toBeInTheDocument()
    expect(screen.getByText('Desligado')).toBeInTheDocument()
  })

  it('"Fazer backup agora" chama o servidor e avisa', async () => {
    const api = await abrir({ 'POST /sistema/backup': { status: 201, body: BACKUP_OK } })

    await userEvent.click(screen.getByRole('button', { name: 'Fazer backup agora' }))

    await waitFor(() => expect(api.de('POST', '/sistema/backup')).toHaveLength(1))
    expect(await screen.findByText('Backup concluído.')).toBeInTheDocument()
  })

  it('falha no backup manual mostra o motivo (502)', async () => {
    await abrir({ 'POST /sistema/backup': { status: 502, body: { detail: 'pg_dump não encontrado. Instale o cliente do PostgreSQL ou configure PG_DUMP_PATH.' } } })

    await userEvent.click(screen.getByRole('button', { name: 'Fazer backup agora' }))

    expect(await screen.findByText(/PG_DUMP_PATH/)).toBeInTheDocument()
  })
})
