export type Cargo = 'vendedora' | 'administradora'
export type StatusPedido = 'em_aberto' | 'confirmado' | 'entregue' | 'cancelado'
export type Agrupamento = 'dia' | 'semana' | 'mes'
export interface Pagina<T> { itens: T[]; total: number; limit: number; offset: number }
export interface Responsavel { id_usuario: number; nome: string }
export interface Usuario extends Responsavel { email: string; telefone: string; cargo: Cargo; comissao: string | null; is_ativo: boolean }
export interface Endereco { id_endereco: number; cep: string; cidade: string; bairro: string; tipo_logradouro: string; nome_logradouro: string; numero: string; complemento: string; referencia: string; apelido: string | null; principal: boolean; endereco_formatado: string }
export interface EnderecoBusca { id_endereco: number; cep: string; cidade: string; bairro: string; tipo_logradouro: string; nome_logradouro: string; descricao: string; quantidade_clientes: number }
type Vinculo = Pick<Endereco, 'numero' | 'complemento' | 'referencia' | 'apelido' | 'principal'>
export type EnderecoDoCliente = Vinculo & ({ id_endereco: number } | Pick<Endereco, 'cep' | 'cidade' | 'bairro' | 'tipo_logradouro' | 'nome_logradouro'>)
export interface ClienteResumo { id_cliente: number; nome: string; telefone: string; is_ativo: boolean; endereco_principal: Endereco | null; cadastrado_por: Responsavel }
export interface Cliente extends ClienteResumo { enderecos: Endereco[] }
export interface Produto { id_produto: number; nome: string; descricao: string; preco_unitario: string; estoque_atual: number; estoque_minimo: number; is_ativo: boolean; alerta_estoque_baixo: boolean }
export interface Pedido { id_pedido: number; status: StatusPedido; data_venda: string; forma_pagamento: string; observacao: string | null; data_pagamento: string | null; valor_total: string; total_produtos: number; cliente: Pick<ClienteResumo, 'id_cliente' | 'nome' | 'telefone'>; vendedora: Responsavel; endereco_entrega: Pick<Endereco, 'id_endereco' | 'endereco_formatado' | 'apelido' | 'referencia'>; itens: { id_produto: number; nome_produto: string; quantidade: number; preco_unitario: string; subtotal: string }[] }
export type ContagemPedidos = Record<StatusPedido | 'todos', number>
export interface TotaisVendas { quantidade_pedidos: number; produtos_vendidos: number; valor_total: string; comissao_a_receber: string; comissao_pendente: string }
export interface ResumoVendedora extends TotaisVendas { id_usuario: number; nome: string; cargo?: Cargo; is_ativo: boolean; comissao_percentual: string | null }
export interface Dashboard { periodo: { inicio: string; fim: string }; total_pedidos: number; produtos_vendidos: number; faturamento: string; comissoes: string; comissoes_pendentes: string; pedidos_por_status: Record<StatusPedido, number> }
export interface Analise { periodo: { inicio: string; fim: string }; agrupamento: Agrupamento; totais: TotaisVendas; serie: { inicio: string; pedidos: number; faturamento: string }[]; pedidos_por_status: Record<StatusPedido, number>; por_forma_pagamento: ItemRanking[]; por_vendedora: ResumoVendedora[]; top_produtos: ItemRanking[]; top_clientes: ItemRanking[]; por_bairro: ItemRanking[] }
export interface ItemRanking { id: number | null; nome: string; quantidade: number; valor: string }
export interface Movimentacao { id_movimentacao: number; id_produto: number; nome_produto: string; tipo_movimentacao: string; quantidade: number; tipo_referencia: string; id_venda: number | null; observacao: string | null; data_movimentacao: string }
export interface MovimentacaoResultado { movimentacao: Movimentacao; produto: Produto }
export interface ResumoMovimentacoes { periodo_inicio: string; periodo_fim: string; agrupamento: Agrupamento; total_entradas: number; total_saidas: number; saldo_do_periodo: number; serie: { inicio: string; entradas: number; saidas: number }[] }
export interface StatusBackup { habilitado: boolean; ultimo_status: 'nunca_executado' | 'ok' | 'erro'; ultima_tentativa: string | null; ultimo_sucesso: string | null; mensagem: string | null; proxima_execucao: string | null; alerta: boolean; motivo_alerta: string | null; retencao: number; arquivos: { nome: string; tamanho_bytes: number; criado_em: string }[] }
