import { Eye, EyeOff, LogIn } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Logo } from '../components/Logo'
import { Tema } from '../components/Tema'
import { Privacidade } from '../components/Privacidade'
import { Alerta, Botao, Campo } from '../components/ui'
import { ApiError, mensagemDeErro } from '../lib/api'
import { useAuth } from '../lib/auth'
import { emailValido } from '../lib/format'
import { focarErros } from '../lib/acessibilidade'

export default function Login() {
  const { entrar, aviso } = useAuth()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [ver, setVer] = useState(false)
  const [erros, setErros] = useState<{ email?: string; senha?: string }>({})
  const [falha, setFalha] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    focarErros(e.currentTarget as HTMLFormElement)
    const novos: typeof erros = {}
    if (!emailValido(email)) novos.email = 'Informe um e-mail válido.'
    if (!senha) novos.senha = 'Informe a senha.'
    setErros(novos)
    setFalha(null)
    if (Object.keys(novos).length) return
    setEnviando(true)
    try {
      await entrar(email.trim(), senha)
    } catch (err) {
      setFalha(err instanceof ApiError && err.status === 0 ? err.detail : mensagemDeErro(err))
      setSenha('')
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="hidden flex-col items-center justify-center gap-6 bg-gradient-to-br from-brand-900 to-brand-950 p-12 text-center lg:flex">
        <span className="flex h-56 w-56 items-center justify-center rounded-full bg-white p-5 shadow-2xl"><Logo className="h-full w-full" alt="" /></span>
        <div>
          <h1 className="font-display text-3xl font-semibold text-white">Casa da Sopa de Restinga</h1>
          <p className="mt-2 text-brand-200">Sistema de gestão de vendas e estoque</p>
        </div>
      </div>

      <div className="flex items-center justify-center p-6">
        <form onSubmit={enviar} noValidate className="cartao w-full max-w-md space-y-5 p-8">
          <div className="text-center lg:hidden"><Logo className="mx-auto h-24 w-24" alt="Casa da Sopa de Restinga" /></div>
          <div>
            <div className="mb-4 flex justify-end"><Tema /></div>
            <h2 className="font-display text-2xl font-semibold text-brand-900">Entrar</h2>
            <p className="mt-1 text-sm text-slate-500">Use o e-mail e a senha cadastrados pela administradora.</p>
          </div>
          {aviso && <Alerta tipo="info">{aviso}</Alerta>}
          {falha && <Alerta tipo="erro">{falha}</Alerta>}

          <Campo rotulo="E-mail" obrigatorio erro={erros.email}>
            {(p) => <input {...p} className="campo" type="email" autoComplete="username" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} placeholder="voce@exemplo.org" />}
          </Campo>
          <Campo rotulo="Senha" obrigatorio erro={erros.senha}>
            {(p) => (
              <div className="relative">
                <input {...p} className="campo pr-11" type={ver ? 'text' : 'password'} autoComplete="current-password" value={senha} onChange={(e) => setSenha(e.target.value)} />
                <button type="button" aria-label={ver ? 'Ocultar senha' : 'Mostrar senha'} onClick={() => setVer(!ver)} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1.5 text-slate-400 hover:text-slate-600">
                  {ver ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
            )}
          </Campo>
          <Botao type="submit" carregando={enviando} icone={<LogIn className="h-4 w-4" />} className="w-full">Entrar</Botao>
          <Privacidade contexto="login" />
          <p className="text-center text-xs text-slate-400">Esqueceu a senha? Entre em contato com a administradora para redefinir.</p>
        </form>
      </div>
    </div>
  )
}
