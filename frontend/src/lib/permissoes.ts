import type { Pedido, Usuario } from './types'
export function podeAlterarPedido(usuario: Usuario | null, pedido: Pedido | null | undefined) {
  return !!usuario && !!pedido && (usuario.cargo === 'administradora' || (usuario.cargo === 'vendedora' && usuario.id_usuario === pedido.vendedora.id_usuario))
}
