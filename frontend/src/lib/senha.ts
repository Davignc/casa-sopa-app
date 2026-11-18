export function requisitosSenha(senha: string) {
  return [
    { rotulo: 'Pelo menos 8 caracteres', atendido: Array.from(senha).length >= 8 },
    { rotulo: 'Uma letra maiúscula', atendido: /\p{Lu}/u.test(senha) },
    { rotulo: 'Uma letra minúscula', atendido: /\p{Ll}/u.test(senha) },
    { rotulo: 'Um número', atendido: /\p{Nd}/u.test(senha) },
    { rotulo: 'Um símbolo (ex.: ! @ # _)', atendido: /[\p{P}\p{S}]/u.test(senha) },
    { rotulo: 'No máximo 72 bytes (acentos e emojis ocupam mais de um byte)', atendido: new TextEncoder().encode(senha).length <= 72 },
  ] as const
}

export function erroSenha(senha: string): string | null {
  const requisitos = requisitosSenha(senha)
  if (!requisitos[5].atendido) return 'Senha longa demais (máx. 72 bytes).'
  if (!requisitos[0].atendido) return 'Mínimo de 8 caracteres.'
  if (requisitos.some((r) => !r.atendido)) return 'Inclua letra maiúscula, minúscula, número e símbolo.'
  return null
}
