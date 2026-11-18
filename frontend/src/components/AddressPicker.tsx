import { useQuery } from '@tanstack/react-query'
import { MapPin, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import { cepValido, mascaraCep, soDigitos, TIPOS_LOGRADOURO } from '../lib/format'
import { useDebounce } from '../lib/hooks'
import type { EnderecoBusca, EnderecoDoCliente } from '../lib/types'
import { Abas, Alerta, Campo, Chip, cn, Interruptor } from './ui'

type Modo = 'buscar' | 'novo'

interface Props {
  /** Recebe o endereço pronto para enviar à API, ou null enquanto estiver incompleto. */
  onChange: (valor: EnderecoDoCliente | null) => void
  /** Mostra a opção "endereço principal". */
  comPrincipal?: boolean
  /** Endereços que o cliente já tem: aparecem na busca, mas não podem ser escolhidos de novo. */
  jaVinculados?: number[]
  /** Mostra os erros de todos os campos (depois de uma tentativa de salvar). */
  mostrarErros?: boolean
  modoInicial?: Modo
}

const VAZIO_NOVO = { cep: '', cidade: '', bairro: '', tipo_logradouro: 'Rua', nome_logradouro: '' }
const VAZIO_VINCULO = { numero: '', complemento: '', referencia: '', apelido: '' }

/**
 * Escolha do endereço: BUSCAR um que já está registrado (de outro cliente) ou CADASTRAR um novo.
 * Ao escolher um registrado, aparece uma seção extra com os dados que são só deste cliente
 * (número, complemento, ponto de referência e apelido): é a "relação" entre cliente e endereço.
 */
export function AddressPicker({ onChange, comPrincipal, jaVinculados = [], mostrarErros, modoInicial = 'buscar' }: Props) {
  const [modo, setModo] = useState<Modo>(modoInicial)
  const [busca, setBusca] = useState('')
  const [escolhido, setEscolhido] = useState<EnderecoBusca | null>(null)
  const [novo, setNovo] = useState(VAZIO_NOVO)
  const [vinculo, setVinculo] = useState(VAZIO_VINCULO)
  const [principal, setPrincipal] = useState(false)
  const [tocados, setTocados] = useState<Record<string, boolean>>({})

  const termo = useDebounce(busca.trim(), 300)
  const consulta = useQuery({
    queryKey: ['enderecos', termo],
    queryFn: () => api<EnderecoBusca[]>('/enderecos', { query: { busca: termo, limit: 8 } }),
    enabled: modo === 'buscar' && termo.length >= 2 && !escolhido,
  })

  const erros = useMemo(() => {
    const e: Record<string, string> = {}
    if (!vinculo.numero.trim()) e.numero = 'Informe o número (ou S/N).'
    if (modo === 'novo') {
      if (!cepValido(novo.cep)) e.cep = 'CEP deve ter 8 dígitos.'
      if (!novo.cidade.trim()) e.cidade = 'Informe a cidade.'
      if (!novo.bairro.trim()) e.bairro = 'Informe o bairro.'
      if (!novo.nome_logradouro.trim()) e.nome_logradouro = 'Informe o nome da rua.'
    }
    return e
  }, [modo, novo, vinculo.numero])

  const valido = modo === 'novo' || escolhido !== null ? Object.keys(erros).length === 0 : false

  useEffect(() => {
    if (!valido) return onChange(null)
    const comuns = {
      numero: vinculo.numero.trim(),
      complemento: vinculo.complemento.trim(),
      referencia: vinculo.referencia.trim(),
      apelido: vinculo.apelido.trim() || null,
      principal: comPrincipal ? principal : false,
    }
    if (modo === 'buscar' && escolhido) onChange({ id_endereco: escolhido.id_endereco, ...comuns })
    else
      onChange({
        cep: soDigitos(novo.cep),
        cidade: novo.cidade.trim(),
        bairro: novo.bairro.trim(),
        tipo_logradouro: novo.tipo_logradouro,
        nome_logradouro: novo.nome_logradouro.trim(),
        ...comuns,
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valido, modo, escolhido, novo, vinculo, principal, comPrincipal])

  const ver = (campo: string) => (mostrarErros || tocados[campo] ? erros[campo] : undefined)
  const tocar = (campo: string) => () => setTocados((t) => ({ ...t, [campo]: true }))

  function trocarModo(m: Modo) {
    setModo(m)
    setTocados({})
  }

  const camposDoVinculo = (
    <div className="grid gap-4 sm:grid-cols-2">
      <Campo rotulo="Número" obrigatorio erro={ver('numero')} dica='Aceita "123A" e "S/N"'>
        {(p) => <input {...p} className={cn('campo', ver('numero') && 'campo-erro')} maxLength={10} value={vinculo.numero} onBlur={tocar('numero')} onChange={(e) => setVinculo({ ...vinculo, numero: e.target.value })} />}
      </Campo>
      <Campo rotulo="Complemento">
        {(p) => <input {...p} className="campo" maxLength={50} placeholder="Apto, bloco, fundos…" value={vinculo.complemento} onChange={(e) => setVinculo({ ...vinculo, complemento: e.target.value })} />}
      </Campo>
      <Campo rotulo="Ponto de referência">
        {(p) => <input {...p} className="campo" maxLength={50} placeholder="Ex.: casa amarela na esquina" value={vinculo.referencia} onChange={(e) => setVinculo({ ...vinculo, referencia: e.target.value })} />}
      </Campo>
      <Campo rotulo="Apelido do endereço">
        {(p) => <input {...p} className="campo" maxLength={50} placeholder="Casa, Trabalho…" value={vinculo.apelido} onChange={(e) => setVinculo({ ...vinculo, apelido: e.target.value })} />}
      </Campo>
    </div>
  )

  return (
    <div className="space-y-4">
      <Abas<Modo> rotulo="Como informar o endereço" itens={[{ id: 'buscar', rotulo: 'Buscar endereço já registrado' }, { id: 'novo', rotulo: 'Cadastrar novo endereço' }]} valor={modo} onMudar={trocarModo} />

      {modo === 'buscar' && (
        <div className="space-y-3">
          {!escolhido ? (
            <>
              <Campo rotulo="Buscar por rua, bairro, cidade ou CEP">
                {(p) => (
                  <div className="relative">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" aria-hidden />
                    <input {...p} className="campo pl-9" autoComplete="off" placeholder="Ex.: Presidente Vargas, Centro, 14400…" value={busca} onChange={(e) => setBusca(e.target.value)} />
                  </div>
                )}
              </Campo>
              {termo.length >= 2 && consulta.isFetching && <p className="text-sm text-slate-500">Buscando…</p>}
              {consulta.isError && <Alerta tipo="erro">Não foi possível buscar os endereços.</Alerta>}
              {consulta.data && consulta.data.length === 0 && (
                <Alerta tipo="info">
                  Nenhum endereço registrado combina com «{termo}».{' '}
                  <button type="button" className="font-semibold underline" onClick={() => trocarModo('novo')}>Cadastrar um novo</button>
                </Alerta>
              )}
              {!!consulta.data?.length && (
                <ul className="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200" aria-label="Endereços encontrados">
                  {consulta.data.map((e) => {
                    const ja = jaVinculados.includes(e.id_endereco)
                    return (
                      <li key={e.id_endereco}>
                        <button type="button" disabled={ja} onClick={() => setEscolhido(e)}
                          className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-brand-50 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400">
                          <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" aria-hidden />
                          <span className="flex-1 text-sm">{e.descricao}</span>
                          <Chip cor={ja ? 'ambar' : 'slate'}>{ja ? 'Já é deste cliente' : e.quantidade_clientes === 1 ? '1 cliente' : `${e.quantidade_clientes} clientes`}</Chip>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </>
          ) : (
            <div className="space-y-4">
              <div className="flex items-start gap-3 rounded-xl border border-brand-200 bg-brand-50 px-4 py-3">
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden />
                <div className="flex-1 text-sm">
                  <p className="font-medium text-brand-900">{escolhido.descricao}</p>
                  <p className="text-xs text-brand-700">Endereço já registrado no sistema</p>
                </div>
                <button type="button" className="text-sm font-medium text-brand-700 underline" onClick={() => { setEscolhido(null); setTocados({}) }}>Trocar</button>
              </div>
              {/* Só aparece depois de escolher um endereço existente: os dados deste vínculo. */}
              <section aria-label="Dados deste endereço para este cliente" className="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Dados deste endereço para este cliente</h3>
                  <p className="text-xs text-slate-500">A rua é compartilhada, mas número, complemento e referência são só deste cliente.</p>
                </div>
                {camposDoVinculo}
              </section>
            </div>
          )}
        </div>
      )}

      {modo === 'novo' && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <Campo rotulo="CEP" obrigatorio erro={ver('cep')}>
              {(p) => <input {...p} className={cn('campo', ver('cep') && 'campo-erro')} inputMode="numeric" placeholder="00000-000" value={novo.cep} onBlur={tocar('cep')} onChange={(e) => setNovo({ ...novo, cep: mascaraCep(e.target.value) })} />}
            </Campo>
            <Campo rotulo="Cidade" obrigatorio erro={ver('cidade')} className="sm:col-span-2">
              {(p) => <input {...p} className={cn('campo', ver('cidade') && 'campo-erro')} maxLength={50} value={novo.cidade} onBlur={tocar('cidade')} onChange={(e) => setNovo({ ...novo, cidade: e.target.value })} />}
            </Campo>
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Campo rotulo="Tipo" obrigatorio>
              {(p) => (
                <select {...p} className="campo" value={novo.tipo_logradouro} onChange={(e) => setNovo({ ...novo, tipo_logradouro: e.target.value })}>
                  {TIPOS_LOGRADOURO.map((t) => <option key={t}>{t}</option>)}
                </select>
              )}
            </Campo>
            <Campo rotulo="Rua" obrigatorio erro={ver('nome_logradouro')} className="sm:col-span-2">
              {(p) => <input {...p} className={cn('campo', ver('nome_logradouro') && 'campo-erro')} maxLength={100} placeholder="Nome da rua" value={novo.nome_logradouro} onBlur={tocar('nome_logradouro')} onChange={(e) => setNovo({ ...novo, nome_logradouro: e.target.value })} />}
            </Campo>
          </div>
          <Campo rotulo="Bairro" obrigatorio erro={ver('bairro')}>
            {(p) => <input {...p} className={cn('campo', ver('bairro') && 'campo-erro')} maxLength={50} value={novo.bairro} onBlur={tocar('bairro')} onChange={(e) => setNovo({ ...novo, bairro: e.target.value })} />}
          </Campo>
          {camposDoVinculo}
        </div>
      )}

      {comPrincipal && (modo === 'novo' || escolhido) && (
        <Interruptor marcado={principal} onChange={setPrincipal} rotulo="Usar como endereço principal do cliente" />
      )}
    </div>
  )
}
