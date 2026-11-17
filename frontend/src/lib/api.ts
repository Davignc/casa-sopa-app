type Query = Record<string, string | number | boolean | null | undefined>
interface Opcoes { method?: string; body?: unknown; form?: FormData; query?: Query; signal?: AbortSignal }
const TOKEN = 'casa-sopa-token'
export const getToken = () => sessionStorage.getItem(TOKEN)
export function setToken(token: string | null) { if (token) sessionStorage.setItem(TOKEN, token); else sessionStorage.removeItem(TOKEN) }
export class ApiError extends Error {
  constructor(public status: number, public detail: string) { super(detail); this.name = 'ApiError' }
}
export const mensagemDeErro = (erro: unknown) => erro instanceof Error ? erro.message : 'Não foi possível concluir a operação.'
function url(caminho: string, query?: Query) {
  const params = new URLSearchParams()
  for (const [k, v] of Object.entries(query ?? {})) if (v !== undefined && v !== null && v !== '') params.set(k, String(v))
  return caminho + (params.size ? `?${params}` : '')
}
async function requisitar(caminho: string, { method, body, form: formulario, query, signal }: Opcoes = {}) {
  body = formulario ?? body
  const headers = new Headers()
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const form = body instanceof FormData
  if (body !== undefined && !form) headers.set('Content-Type', 'application/json')
  let resposta: Response
  try { resposta = await fetch(url(caminho, query), { method: method ?? (body !== undefined ? 'POST' : 'GET'), headers, body: body === undefined ? undefined : form ? body as FormData : JSON.stringify(body), signal }) }
  catch (erro) { if (signal?.aborted) throw erro; throw new ApiError(0, 'Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.') }
  if (!resposta.ok) {
    const dados = await resposta.json().catch(() => null)
    const detail = typeof dados?.detail === 'string' ? dados.detail : Array.isArray(dados?.detail) ? dados.detail.map((e: { msg: string }) => e.msg).join(' ') : 'Não foi possível concluir a operação.'
    if (resposta.status === 401 && token) { setToken(null); window.dispatchEvent(new Event('sessao-expirada')) }
    throw new ApiError(resposta.status, detail)
  }
  return resposta
}
export async function api<T = void>(caminho: string, opcoes?: Opcoes): Promise<T> {
  const resposta = await requisitar(caminho, opcoes)
  return resposta.status === 204 ? undefined as T : resposta.json()
}
export async function baixar(caminho: string, query?: Query) {
  const resposta = await requisitar(caminho, { query })
  const nome = resposta.headers.get('content-disposition')?.match(/filename="?([^";]+)"?/)?.[1] ?? 'arquivo'
  return { blob: await resposta.blob(), nome }
}
export function salvarBlob(blob: Blob, nome: string) {
  const href = URL.createObjectURL(blob)
  const link = document.createElement('a'); link.href = href; link.download = nome
  document.body.appendChild(link); link.click(); link.remove()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}
export function abrirBlob(blob: Blob) {
  const href = URL.createObjectURL(blob)
  const janela = window.open(href, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(href), 60_000)
  return janela
}
