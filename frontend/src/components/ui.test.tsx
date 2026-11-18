import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../lib/api'
import { Abas, Alerta, AvisosProvider, Botao, Campo, ChipStatus, Confirmar, Modal, Paginacao, useAvisos } from './ui'

describe('Modal', () => {
  function Exemplo({ onFechar = () => {} }: { onFechar?: () => void }) {
    const [aberto, setAberto] = useState(false)
    return (
      <>
        <button onClick={() => setAberto(true)}>abrir</button>
        <Modal aberto={aberto} onFechar={() => { setAberto(false); onFechar() }} titulo="Título" rodape={<button>ok</button>}>
          <input aria-label="primeiro" />
          <input aria-label="segundo" />
        </Modal>
      </>
    )
  }

  it('é um diálogo acessível, com título, e o foco vai para o primeiro campo', async () => {
    render(<Exemplo />)

    await userEvent.click(screen.getByText('abrir'))

    const dialogo = screen.getByRole('dialog', { name: 'Título' })
    expect(dialogo).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByLabelText('primeiro')).toHaveFocus()
  })

  it('Escape fecha e o foco volta para quem abriu', async () => {
    render(<Exemplo />)
    const abrir = screen.getByText('abrir')
    await userEvent.click(abrir)

    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(abrir).toHaveFocus()
  })

  it('o Tab fica preso dentro do diálogo', async () => {
    render(<Exemplo />)
    await userEvent.click(screen.getByText('abrir'))
    const dialogo = screen.getByRole('dialog')

    for (let i = 0; i < 8; i++) {
      await userEvent.tab()
      expect(dialogo.contains(document.activeElement)).toBe(true)
    }
    await userEvent.tab({ shift: true })
    expect(dialogo.contains(document.activeElement)).toBe(true)
  })

  it('trava a rolagem da página enquanto está aberto e destrava ao fechar', async () => {
    render(<Exemplo />)
    await userEvent.click(screen.getByText('abrir'))
    expect(document.body.style.overflow).toBe('hidden')

    await userEvent.click(screen.getByRole('button', { name: 'Fechar janela' }))

    expect(document.body.style.overflow).not.toBe('hidden')
  })

  it('clicar fora fecha, clicar dentro não', async () => {
    const fechar = vi.fn()
    render(<Exemplo onFechar={fechar} />)
    await userEvent.click(screen.getByText('abrir'))

    await userEvent.click(screen.getByLabelText('primeiro'))
    expect(fechar).not.toHaveBeenCalled()
    await userEvent.pointer({ keys: '[MouseLeft]', target: screen.getByRole('dialog').parentElement as HTMLElement })

    expect(fechar).toHaveBeenCalledOnce()
  })
})

describe('Confirmar', () => {
  it('mostra a mensagem e chama o que o usuário escolher', async () => {
    const ok = vi.fn()
    const voltar = vi.fn()
    render(<Confirmar aberto titulo="Apagar?" mensagem="Isso não tem volta." textoConfirmar="Apagar" perigo onConfirmar={ok} onCancelar={voltar} />)

    expect(screen.getByText('Isso não tem volta.')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Apagar' }))

    expect(voltar).toHaveBeenCalledOnce()
    expect(ok).toHaveBeenCalledOnce()
  })

  it('enquanto salva, trava os dois botões', () => {
    render(<Confirmar aberto titulo="x" mensagem="y" carregando onConfirmar={() => {}} onCancelar={() => {}} />)

    expect(screen.getByRole('button', { name: 'Voltar' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeDisabled()
  })
})

describe('Botao', () => {
  it('carregando desabilita e impede clique duplo', async () => {
    const clique = vi.fn()
    render(<Botao carregando onClick={clique}>Salvar</Botao>)

    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(screen.getByRole('button', { name: 'Salvar' })).toBeDisabled()
    expect(clique).not.toHaveBeenCalled()
  })

  it('é type=button por padrão (não envia formulário sem querer)', () => {
    render(<Botao>x</Botao>)

    expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
  })
})

describe('Campo', () => {
  it('liga o rótulo ao campo e mostra o erro de forma acessível', () => {
    render(<Campo rotulo="Nome" obrigatorio erro="Informe o nome.">{(p) => <input {...p} />}</Campo>)

    const campo = screen.getByLabelText('Nome *')
    expect(campo).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('Informe o nome.')
    expect(campo.getAttribute('aria-describedby')).toBe(screen.getByRole('alert').id)
  })

  it('a dica aparece quando não há erro', () => {
    render(<Campo rotulo="Número" dica="Aceita S/N">{(p) => <input {...p} />}</Campo>)

    expect(screen.getByText('Aceita S/N')).toBeInTheDocument()
    expect(screen.getByLabelText('Número')).not.toHaveAttribute('aria-invalid')
  })
})

describe('Paginacao', () => {
  it('mostra o intervalo e navega', async () => {
    const mudar = vi.fn()
    render(<Paginacao pagina={{ total: 45, limit: 20, offset: 20 }} onMudar={mudar} rotulo="clientes" />)

    expect(screen.getByText('21–40 de 45 clientes')).toBeInTheDocument()
    expect(screen.getByText('Página 2 de 3')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Próxima página' }))
    await userEvent.click(screen.getByRole('button', { name: 'Página anterior' }))

    expect(mudar).toHaveBeenNthCalledWith(1, 40)
    expect(mudar).toHaveBeenNthCalledWith(2, 0)
  })

  it('desabilita os extremos', () => {
    const { rerender } = render(<Paginacao pagina={{ total: 45, limit: 20, offset: 0 }} onMudar={() => {}} />)
    expect(screen.getByRole('button', { name: 'Página anterior' })).toBeDisabled()

    rerender(<Paginacao pagina={{ total: 45, limit: 20, offset: 40 }} onMudar={() => {}} />)
    expect(screen.getByRole('button', { name: 'Próxima página' })).toBeDisabled()
  })

  it('uma página só não mostra botões; vazio diz que não há nada', () => {
    const { rerender } = render(<Paginacao pagina={{ total: 5, limit: 20, offset: 0 }} onMudar={() => {}} />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()

    rerender(<Paginacao pagina={{ total: 0, limit: 20, offset: 0 }} onMudar={() => {}} rotulo="pedido" />)
    expect(screen.getByText('Nenhum pedido')).toBeInTheDocument()
  })
})

describe('Abas', () => {
  it('marca a aba ativa, mostra contagem acessível e avisa a troca', async () => {
    const mudar = vi.fn()
    render(<Abas itens={[{ id: 'a', rotulo: 'Todos', contagem: 4 }, { id: 'b', rotulo: 'Abertos', contagem: 1 }, { id: 'c', rotulo: 'Sem contagem' }]} valor="a" onMudar={mudar} />)

    expect(screen.getByRole('tab', { name: 'Todos: 4' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Abertos: 1' })).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByRole('tab', { name: 'Sem contagem' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Abertos: 1' }))
    expect(mudar).toHaveBeenCalledWith('b')
  })
})

describe('ChipStatus e Alerta', () => {
  it('traduz cada situação', () => {
    render(<>{(['em_aberto', 'confirmado', 'entregue', 'cancelado'] as const).map((s) => <ChipStatus key={s} status={s} />)}</>)

    for (const t of ['Em aberto', 'Confirmado', 'Entregue', 'Cancelado']) expect(screen.getByText(t)).toBeInTheDocument()
  })

  it('erro e aviso são anunciados (role alert); informação não', () => {
    render(<><Alerta tipo="erro">falhou</Alerta><Alerta tipo="aviso">cuidado</Alerta><Alerta tipo="info">fyi</Alerta></>)

    expect(screen.getAllByRole('alert')).toHaveLength(2)
    expect(screen.getByRole('status')).toHaveTextContent('fyi')
  })
})

describe('Avisos (toast)', () => {
  function Disparo() {
    const avisos = useAvisos()
    return (
      <>
        <button onClick={() => avisos.sucesso('Salvo!')}>ok</button>
        <button onClick={() => avisos.erro(new ApiError(409, 'Conflito de dados.'))}>erro</button>
      </>
    )
  }

  it('mostra o aviso, usa a mensagem do erro da API e some sozinho', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    render(<AvisosProvider><Disparo /></AvisosProvider>)

    await userEvent.click(screen.getByText('ok'))
    expect(screen.getByRole('status')).toHaveTextContent('Salvo!')
    await userEvent.click(screen.getByText('erro'))
    expect(screen.getByRole('alert')).toHaveTextContent('Conflito de dados.')

    act(() => { vi.advanceTimersByTime(5000) })
    expect(screen.queryByText('Salvo!')).not.toBeInTheDocument()
    expect(screen.getByText('Conflito de dados.')).toBeInTheDocument() // erros ficam mais tempo
    act(() => { vi.advanceTimersByTime(4000) })
    expect(screen.queryByText('Conflito de dados.')).not.toBeInTheDocument()
  })

  it('pode ser dispensado com o botão', async () => {
    render(<AvisosProvider><Disparo /></AvisosProvider>)
    await userEvent.click(screen.getByText('ok'))

    await userEvent.click(within(screen.getByRole('status')).getByRole('button', { name: 'Dispensar aviso' }))

    expect(screen.queryByText('Salvo!')).not.toBeInTheDocument()
  })
})
