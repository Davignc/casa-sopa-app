import { describe, expect, it } from 'vitest'
import { lerPreco } from './format'

describe('Preço informado no cadastro', () => {
  it.each([
    ['', null], ['12,345', null], ['-1', null], ['100000000', null],
    ['0', 0], ['25,90', 25.9], ['25.90', 25.9], ['1.234', 1234],
    ['12.345', 12345], ['1.234,56', 1234.56],
  ] as const)('interpreta %s como %s sem arredondar casas excedentes', (informado, esperado) => {
    expect(lerPreco(informado)).toBe(esperado)
  })
})
