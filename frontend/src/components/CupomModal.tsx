import { Download, FileText, Printer } from 'lucide-react'
import { useState } from 'react'
import { abrirBlob, baixar, salvarBlob } from '../lib/api'
import type { Pedido } from '../lib/types'
import { Botao, Modal, useAvisos } from './ui'

const VIAS = [
  { id: 'todas', rotulo: 'Todas as vias', detalhe: 'ONG, entregador e cliente (3 páginas)' },
  { id: 'interna', rotulo: 'Via da ONG', detalhe: 'Uso interno' },
  { id: 'entregador', rotulo: 'Via do entregador', detalhe: 'Para conferir a entrega' },
  { id: 'cliente', rotulo: 'Via do cliente', detalhe: 'Fica com quem comprou' },
] as const

type Via = (typeof VIAS)[number]['id']

/** Cupom não fiscal em PDF (RF15/RF16). Pode ser emitido quantas vezes precisar. */
export function CupomModal({ pedido, onFechar }: { pedido: Pick<Pedido, 'id_pedido'> & { cliente: { nome: string } }; onFechar: () => void }) {
  const avisos = useAvisos()
  const [via, setVia] = useState<Via>('todas')
  const [ocupado, setOcupado] = useState<'abrir' | 'baixar' | null>(null)

  async function executar(modo: 'abrir' | 'baixar') {
    setOcupado(modo)
    try {
      const { blob, nome } = await baixar(`/pedidos/${pedido.id_pedido}/cupom`, { via })
      if (modo === 'baixar') salvarBlob(blob, nome)
      else if (!abrirBlob(blob)) avisos.info('O navegador bloqueou a nova janela. Use “Baixar PDF” ou libere pop-ups para este site.')
    } catch (e) {
      avisos.erro(e)
    } finally {
      setOcupado(null)
    }
  }

  return (
    <Modal aberto onFechar={onFechar} titulo={`Cupom do pedido #${pedido.id_pedido}`} subtitulo={pedido.cliente.nome} largura="max-w-md"
      rodape={<>
        <Botao variante="secundario" onClick={onFechar}>Fechar</Botao>
        <Botao variante="secundario" icone={<Download className="h-4 w-4" />} carregando={ocupado === 'baixar'} disabled={ocupado !== null} onClick={() => void executar('baixar')}>Baixar PDF</Botao>
        <Botao icone={<Printer className="h-4 w-4" />} carregando={ocupado === 'abrir'} disabled={ocupado !== null} onClick={() => void executar('abrir')}>Abrir para imprimir</Botao>
      </>}>
      <fieldset className="space-y-2">
        <legend className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700"><FileText className="h-4 w-4" aria-hidden />Qual via emitir?</legend>
        {VIAS.map((v) => (
          <label key={v.id} className={`flex cursor-pointer items-start gap-3 rounded-xl border p-3 ${via === v.id ? 'border-brand-500 bg-brand-50' : 'border-slate-200 hover:bg-slate-50'}`}>
            <input type="radio" name="via" className="mt-1" checked={via === v.id} onChange={() => setVia(v.id)} />
            <span className="text-sm"><b className="block text-slate-900">{v.rotulo}</b><span className="text-slate-500">{v.detalhe}</span></span>
          </label>
        ))}
      </fieldset>
    </Modal>
  )
}
