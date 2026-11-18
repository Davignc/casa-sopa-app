import type { Cliente, ClienteResumo, Endereco, Pedido, Produto } from '../lib/types'

export const pagina = <T,>(itens: T[], extra: Partial<{ total: number; limit: number; offset: number }> = {}) => ({ itens, total: itens.length, limit: 20, offset: 0, ...extra })

export const endereco = (n: number, extra: Partial<Endereco> = {}): Endereco => ({
  id_endereco: n, cep: '14400000', cidade: 'Franca', bairro: 'Centro', tipo_logradouro: 'Rua', nome_logradouro: `Rua ${n}`, numero: String(n),
  complemento: '', referencia: '', apelido: null, principal: n === 1, endereco_formatado: `Rua ${n}, ${n} - Centro, Franca - CEP 14400-000`, ...extra,
})

export const END1 = endereco(1, { referencia: 'portão azul', apelido: 'Casa' })
export const END2 = endereco(2)

export const CLIENTE_RESUMO: ClienteResumo = {
  id_cliente: 7, nome: 'Ana Souza', telefone: '16999990001', is_ativo: true, endereco_principal: END1, cadastrado_por: { id_usuario: 2, nome: 'Maria Vendedora' },
}
export const CLIENTE: Cliente = { ...CLIENTE_RESUMO, enderecos: [END1, END2] }

export const produto = (id: number, nome: string, preco: string, estoque: number, extra: Partial<Produto> = {}): Produto => ({
  id_produto: id, nome, descricao: `${nome} (pacote)`, preco_unitario: preco, estoque_atual: estoque, estoque_minimo: 5, is_ativo: true,
  alerta_estoque_baixo: estoque <= 5, ...extra,
})
export const PROD_A = produto(1, 'Saco 50L', '10.00', 100)
export const PROD_B = produto(2, 'Saco 100L', '25.90', 20)

export const pedido = (id: number, status: Pedido['status'] = 'em_aberto', extra: Partial<Pedido> = {}): Pedido => ({
  id_pedido: id, status, data_venda: '2026-10-28T12:00:00Z', forma_pagamento: 'pix', observacao: null, data_pagamento: null,
  valor_total: '97.70', total_produtos: 5,
  cliente: { id_cliente: 7, nome: 'Ana Souza', telefone: '16999990001' },
  vendedora: { id_usuario: 2, nome: 'Maria Vendedora' },
  endereco_entrega: { id_endereco: 1, endereco_formatado: END1.endereco_formatado, apelido: 'Casa', referencia: 'portão azul' },
  itens: [
    { id_produto: 1, nome_produto: 'Saco 50L', quantidade: 2, preco_unitario: '10.00', subtotal: '20.00' },
    { id_produto: 2, nome_produto: 'Saco 100L', quantidade: 3, preco_unitario: '25.90', subtotal: '77.70' },
  ],
  ...extra,
})
