import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Download, FileSpreadsheet, Upload } from 'lucide-react'
import { Alerta, Botao, Pagina_ } from '../components/ui'
import { api, baixar, mensagemDeErro, salvarBlob } from '../lib/api'

type Tipo = 'clientes' | 'produtos' | 'vendas'
interface Resultado {
  tipo: Tipo; total_linhas: number; novos: number; ignorados: number
  erros: { linha: number; mensagem: string }[]; amostra: Record<string, string>[]
  token: string | null; concluida: boolean
}

export default function Importacoes() {
  const cache = useQueryClient()
  const [tipo, setTipo] = useState<Tipo>('clientes')
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)

  async function modelo() {
    setOcupado(true); setErro(null)
    try { const a = await baixar('/importacoes/modelo', { tipo }); salvarBlob(a.blob, a.nome) }
    catch (e) { setErro(mensagemDeErro(e)) }
    finally { setOcupado(false) }
  }

  async function processar(confirmar = false) {
    if (!arquivo) return
    setErro(null); setOcupado(true)
    const form = new FormData()
    form.append('arquivo', arquivo); form.append('tipo', tipo)
    if (confirmar && resultado?.token) form.append('token', resultado.token)
    try {
      const resposta = await api<Resultado>(confirmar ? '/importacoes/confirmar' : '/importacoes/analisar', { method: 'POST', form })
      setResultado(resposta)
      if (resposta.concluida) await cache.invalidateQueries()
    } catch (e) { setErro(mensagemDeErro(e)); setResultado(null) }
    finally { setOcupado(false) }
  }

  function escolher(f: File | undefined) {
    setResultado(null); setErro(null); setArquivo(null)
    if (!f) return
    if (!/\.(xlsx|csv)$/i.test(f.name)) return setErro('Use uma planilha Excel (.xlsx) ou CSV (.csv).')
    if (f.size === 0 || f.size > 5 * 1024 * 1024) return setErro('O arquivo deve ter conteúdo e no máximo 5 MB.')
    setArquivo(f)
  }

  return <Pagina_ titulo="Importar dados">
    <section className="cartao space-y-5 p-6">
      <div className="flex items-start gap-3"><FileSpreadsheet className="h-8 w-8 shrink-0 text-brand-700" aria-hidden /><div>
        <h2 className="font-display text-lg font-semibold text-brand-900">Traga suas planilhas antigas</h2>
        <p className="text-sm text-slate-500">Importe na ordem: clientes, produtos e vendas. Baixe o modelo e adapte as colunas da sua planilha.</p>
      </div></div>
      <ol className="list-inside list-decimal space-y-2 text-sm text-slate-600">
        <li>Escolha o tipo e baixe o modelo. A aba “Instruções” explica cada campo.</li>
        <li>Copie os registros antigos para a primeira aba, sem fórmulas ou totais.</li>
        <li>Envie o arquivo, confira a prévia e confirme para salvar.</li>
      </ol>
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-medium">Tipo de dados<select disabled={ocupado} className="campo mt-1 w-52" value={tipo} onChange={e => { setTipo(e.target.value as Tipo); setArquivo(null); setResultado(null); setErro(null) }}><option value="clientes">1. Clientes</option><option value="produtos">2. Produtos e estoque</option><option value="vendas">3. Vendas antigas</option></select></label>
        <Botao variante="secundario" disabled={ocupado} onClick={() => void modelo()} icone={<Download className="h-4 w-4" />}>Baixar modelo Excel</Botao>
      </div>
      {tipo === 'clientes' && <Alerta tipo="info">Telefone com DDD identifica cada cliente. Cadastros existentes são ignorados. Para importar vendas, o cliente precisa ter endereço cadastrado.</Alerta>}
      {tipo === 'produtos' && <Alerta tipo="info">O estoque inicial deve ser a quantidade atual disponível. Produtos com nome já existente são ignorados; nenhum saldo existente será sobrescrito.</Alerta>}
      {tipo === 'vendas' && <Alerta tipo="aviso">Vendas antigas entram como entregues ou canceladas, com data e preço originais, sem descontar o estoque atual. Use uma referência única em pedido_origem. Vendas entregues entram nos relatórios e comissões com o percentual atual da responsável. O Excel exportado dos relatórios precisa ser adaptado ao modelo.</Alerta>}
      <label className="block text-sm font-medium">Planilha Excel ou CSV (até 5 MB e 2.000 linhas)
        <input key={tipo} type="file" accept=".xlsx,.csv" disabled={ocupado} onChange={e => escolher(e.target.files?.[0])} className="mt-2 block w-full text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-4 file:py-2 file:text-brand-700" />
      </label>
      {erro && <Alerta tipo="erro">{erro}</Alerta>}
      <Botao disabled={!arquivo || ocupado} carregando={ocupado} onClick={() => void processar()} icone={<Upload className="h-4 w-4" />}>Analisar planilha</Botao>
    </section>
    {resultado && <section className="cartao space-y-4 p-6" aria-label="Resultado da análise">
      <h2 className="font-display text-lg font-semibold text-brand-900">{resultado.concluida ? 'Importação concluída' : 'Confira antes de importar'}</h2>
      <div className="flex flex-wrap gap-3 text-sm"><span>{resultado.total_linhas} linhas lidas</span><span>· {resultado.novos} {tipo === 'vendas' ? 'pedidos' : 'registros'} {resultado.concluida ? 'importados' : 'novos'}</span><span>· {resultado.ignorados} já existentes / ignorados</span></div>
      {resultado.erros.length > 0 ? <>
        <Alerta tipo="erro">Nada foi salvo. Corrija os erros na planilha e analise novamente.</Alerta>
        <ul className="max-h-72 space-y-2 overflow-y-auto text-sm">{resultado.erros.map((e, i) => <li key={i}><strong>Linha {e.linha}:</strong> {e.mensagem}</li>)}</ul>
      </> : resultado.concluida ? <Alerta tipo="info">Os dados foram salvos e já estão disponíveis no sistema.</Alerta> : <>
        <Alerta tipo="info">A análise ainda não salvou dados. Confira as primeiras cinco linhas abaixo. Cadastros existentes serão preservados.</Alerta>
        <div className="overflow-x-auto"><table className="w-full"><thead><tr>{Object.keys(resultado.amostra[0] ?? {}).map(c => <th className="th" key={c}>{c}</th>)}</tr></thead><tbody>{resultado.amostra.map((linha, i) => <tr key={i}>{Object.entries(linha).map(([c, v]) => <td className="td" key={c}>{v || '—'}</td>)}</tr>)}</tbody></table></div>
        <Botao disabled={ocupado || !resultado.token || resultado.novos === 0} carregando={ocupado} onClick={() => void processar(true)}>Confirmar importação de {resultado.novos} {tipo === 'vendas' ? 'pedidos' : 'registros'}</Botao>
      </>}
    </section>}
  </Pagina_>
}
