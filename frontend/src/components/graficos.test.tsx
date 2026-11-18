import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { GraficoMovimentacoes, GraficoRanking, GraficoRosca, GraficoSerie } from './graficos'

describe('GraficoSerie', () => {
  it('sem vendas mostra uma mensagem em vez de um gráfico vazio', () => {
    render(<GraficoSerie agrupamento="dia" dados={[{ inicio: '2026-10-28', pedidos: 0, faturamento: '0.00' }]} />)

    expect(screen.getByText('Sem vendas neste período')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })

  it('com vendas, descreve o gráfico para leitores de tela', () => {
    render(<GraficoSerie agrupamento="semana" dados={[{ inicio: '2026-10-26', pedidos: 2, faturamento: '50.00' }, { inicio: '2026-11-02', pedidos: 3, faturamento: '75.00' }]} />)

    expect(screen.getByRole('img', { name: 'Vendas por semana: 5 pedidos' })).toBeInTheDocument()
  })
})

describe('GraficoRosca', () => {
  it('sem dados mostra mensagem', () => {
    render(<GraficoRosca dados={[{ nome: 'A', valor: 0 }]} />)

    expect(screen.getByText('Sem dados neste período')).toBeInTheDocument()
  })

  it('mostra a legenda só dos itens com valor, formatada', () => {
    render(<GraficoRosca formato={(v) => `R$ ${v}`} dados={[{ nome: 'PIX', valor: 120 }, { nome: 'Dinheiro', valor: 55 }, { nome: 'Boleto', valor: 0 }]} />)

    expect(screen.getByText('PIX')).toBeInTheDocument()
    expect(screen.getByText('R$ 120')).toBeInTheDocument()
    expect(screen.getByText('Dinheiro')).toBeInTheDocument()
    expect(screen.queryByText('Boleto')).not.toBeInTheDocument()
    expect(screen.getByRole('img').getAttribute('aria-label')).toContain('PIX R$ 120')
  })
})

describe('GraficoRanking', () => {
  it('sem dados mostra mensagem', () => {
    render(<GraficoRanking dados={[]} />)

    expect(screen.getByText('Sem dados neste período')).toBeInTheDocument()
  })

  it('descreve cada item com o valor formatado', () => {
    render(<GraficoRanking dados={[{ nome: 'Centro', valor: 75 }, { nome: 'Jardim', valor: 100 }]} />)

    expect(screen.getByRole('img').getAttribute('aria-label')).toBe('Ranking: Centro R$ 75,00, Jardim R$ 100,00')
  })
})

describe('GraficoMovimentacoes', () => {
  it('sem movimentações mostra mensagem', () => {
    render(<GraficoMovimentacoes agrupamento="dia" serie={[{ inicio: '2026-10-28', entradas: 0, saidas: 0 }]} />)

    expect(screen.getByText('Sem movimentações neste período')).toBeInTheDocument()
  })

  it('com movimentações mostra o gráfico', () => {
    render(<GraficoMovimentacoes agrupamento="dia" serie={[{ inicio: '2026-10-28', entradas: 5, saidas: 0 }]} />)

    expect(screen.getByRole('img', { name: 'Entradas e saídas de estoque' })).toBeInTheDocument()
  })
})
