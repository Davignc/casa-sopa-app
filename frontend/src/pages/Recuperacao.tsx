import { useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Logo } from '../components/Logo'
import { Alerta, Botao, Campo } from '../components/ui'
import { api, mensagemDeErro, setToken } from '../lib/api'
import { emailValido } from '../lib/format'

export default function Recuperacao({ onVoltar }: { onVoltar?: () => void }) {
  const local = useLocation()
  const redefinir = local.pathname === '/redefinir-senha'
  const [token] = useState(() => new URLSearchParams(local.search).get('token') ?? '')
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [confirmar, setConfirmar] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [mensagem, setMensagem] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro(null)
    if (!redefinir && !emailValido(email)) return setErro('Informe um e-mail válido.')
    if (redefinir) {
      if (!token) return setErro('Link incompleto. Solicite um novo link de recuperação.')
      if (senha.length < 8 || new TextEncoder().encode(senha).length > 72) return setErro('Use uma senha de ao menos 8 caracteres e no máximo 72 bytes.')
      if (senha !== confirmar) return setErro('As senhas não conferem.')
    }
    setEnviando(true)
    try {
      if (redefinir) {
        await api('/auth/redefinir-senha', { body: { token, senha } })
        setToken(null)
        window.dispatchEvent(new Event('sessao-expirada'))
        window.history.replaceState(null, '', `${window.location.pathname}#/redefinir-senha`)
        setSenha(''); setConfirmar('')
        setMensagem('Senha redefinida. Entre novamente com a nova senha.')
      } else {
        const resposta = await api<{ detail: string }>('/auth/recuperar-senha', { body: { email: email.trim().toLowerCase() } })
        setMensagem(resposta.detail)
      }
    } catch (e) { setErro(mensagemDeErro(e)) }
    finally { setEnviando(false) }
  }

  return <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-900 to-brand-950 p-6">
    <form onSubmit={enviar} noValidate className="cartao w-full max-w-md space-y-5 p-8">
      <Logo className="mx-auto h-24 w-24 rounded-full bg-white p-2" />
      <h1 className="font-display text-2xl font-semibold text-brand-900">{redefinir ? 'Redefinir senha' : 'Recuperar senha'}</h1>
      <p className="text-sm text-slate-500">{redefinir ? 'Escolha uma nova senha para acessar o sistema.' : 'Informe seu e-mail cadastrado. Enviaremos um link temporário para você criar uma nova senha.'}</p>
      {erro && <Alerta tipo="erro">{erro}</Alerta>}
      {mensagem ? <Alerta tipo="info">{mensagem}</Alerta> : <>
        {redefinir ? <>
          <Campo rotulo="Nova senha" obrigatorio dica="Mínimo de 8 caracteres.">{p => <input {...p} className="campo" autoComplete="new-password" type="password" value={senha} onChange={e => setSenha(e.target.value)} />}</Campo>
          <Campo rotulo="Confirmar nova senha" obrigatorio>{p => <input {...p} className="campo" autoComplete="new-password" type="password" value={confirmar} onChange={e => setConfirmar(e.target.value)} />}</Campo>
        </> : <Campo rotulo="E-mail cadastrado" obrigatorio>{p => <input {...p} autoComplete="email" className="campo" type="email" value={email} onChange={e => setEmail(e.target.value)} />}</Campo>}
        <Botao type="submit" className="w-full" carregando={enviando}>{redefinir ? 'Salvar nova senha' : 'Enviar link de recuperação'}</Botao>
      </>}
      {!redefinir && mensagem && <Botao variante="secundario" onClick={() => setMensagem(null)}>Solicitar novamente</Botao>}
      {redefinir && erro && <Link to="/login" className="block text-sm font-semibold text-brand-700 underline">Solicitar outro link pela tela de entrada</Link>}
      {onVoltar ? <button type="button" onClick={onVoltar} className="block text-sm font-semibold text-brand-700 underline">Voltar para entrar</button> : <Link to="/login" className="block text-sm font-semibold text-brand-700 underline">Voltar para entrar</Link>}
    </form>
  </div>
}
