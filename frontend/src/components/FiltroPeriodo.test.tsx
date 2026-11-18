import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { hoje, periodoDoPreset, somarDias } from '../lib/format'
import { FiltroPeriodo, periodoInicial } from './FiltroPeriodo'

const mudarData = (rotulo: string, valor: string) => fireEvent.change(screen.getByLabelText(rotulo), { target: { value: valor } })

describe('FiltroPeriodo', () => {
  it('o período inicial é de 30 dias', () => {
    expect(periodoInicial()).toEqual({ preset: '30', ...periodoDoPreset('30') })
  })

  it('marca o atalho ativo e mostra as datas', () => {
    render(<FiltroPeriodo valor={periodoInicial('30')} onChange={() => {}} />)

    expect(screen.getByRole('button', { name: '30 dias' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '7 dias' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByLabelText('Data final')).toHaveValue(hoje())
  })

  it.each([['7 dias', '7'], ['90 dias', '90'], ['Este ano', 'ano']])('"%s" informa o período do atalho', async (rotulo, id) => {
    const mudar = vi.fn()
    render(<FiltroPeriodo valor={periodoInicial('30')} onChange={mudar} />)

    await userEvent.click(screen.getByRole('button', { name: rotulo }))

    expect(mudar).toHaveBeenCalledWith({ preset: id, ...periodoDoPreset(id) })
  })

  it('datas livres válidas viram um período "personalizado"', () => {
    const mudar = vi.fn()
    render(<FiltroPeriodo valor={periodoInicial('30')} onChange={mudar} />)

    mudarData('Data inicial', '2026-01-10')

    expect(mudar).toHaveBeenCalledWith({ preset: 'custom', inicio: '2026-01-10', fim: hoje() })
  })

  it('data inicial depois da final: avisa e NÃO informa o período', () => {
    const mudar = vi.fn()
    render(<FiltroPeriodo valor={{ preset: 'custom', inicio: '2026-01-01', fim: '2026-01-31' }} onChange={mudar} />)

    mudarData('Data inicial', '2026-02-15')

    expect(screen.getByRole('alert')).toHaveTextContent('A data inicial não pode ser depois da final.')
    expect(mudar).not.toHaveBeenCalled()
  })

  it('data final no futuro é barrada', () => {
    const mudar = vi.fn()
    render(<FiltroPeriodo valor={periodoInicial('30')} onChange={mudar} />)

    mudarData('Data final', somarDias(hoje(), 3))

    expect(screen.getByRole('alert')).toHaveTextContent('não pode estar no futuro')
    expect(mudar).not.toHaveBeenCalled()
  })

  it('mais de um ano é barrado (limite do servidor)', () => {
    const mudar = vi.fn()
    render(<FiltroPeriodo valor={periodoInicial('30')} onChange={mudar} />)

    mudarData('Data inicial', somarDias(hoje(), -400))

    expect(screen.getByRole('alert')).toHaveTextContent('O período máximo é de 1 ano.')
    expect(mudar).not.toHaveBeenCalled()
  })

  it('exatamente um ano (366 dias) ainda vale', () => {
    const mudar = vi.fn()
    render(<FiltroPeriodo valor={periodoInicial('30')} onChange={mudar} />)

    mudarData('Data inicial', somarDias(hoje(), -365))

    expect(mudar).toHaveBeenCalledOnce()
  })

  it('corrigir a data some com o aviso', () => {
    const mudar = vi.fn()
    render(<FiltroPeriodo valor={{ preset: 'custom', inicio: '2026-01-01', fim: '2026-01-31' }} onChange={mudar} />)
    mudarData('Data inicial', '2026-02-15')
    expect(screen.getByRole('alert')).toBeInTheDocument()

    mudarData('Data inicial', '2026-01-05')

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(mudar).toHaveBeenCalledWith({ preset: 'custom', inicio: '2026-01-05', fim: '2026-01-31' })
  })
})
