export function Privacidade({ contexto = 'cliente' }: { contexto?: 'cliente' | 'usuario' | 'pedido' | 'login' }) {
  const texto = {
    cliente: 'Nome e telefone identificam o cliente e permitem contato sobre os pedidos. O endereço é usado para a entrega e pode ser cadastrado depois.',
    usuario: 'Nome, e-mail e telefone são usados para identificar a usuária e administrar seu acesso. Cargo e comissão são usados na gestão de vendas.',
    pedido: 'Os dados do cliente são usados para registrar o pedido, organizar a entrega e manter o histórico de atendimento. Nas observações, informe apenas o necessário para o pedido; evite dados sensíveis.',
    login: 'Seu e-mail e sua senha são usados para autenticar o acesso ao sistema.',
  }
  return <aside aria-label="Privacidade e dados pessoais" className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
    <p className="font-semibold">Privacidade e dados pessoais</p>
    <p className="mt-1">{texto[contexto]}</p>
    <details className="mt-2">
      <summary className="cursor-pointer font-medium underline">Como cuidar dos dados e solicitar atendimento</summary>
      <p className="mt-2">Informe à pessoa como seus dados serão usados e preencha somente os campos necessários. Campos marcados com * são obrigatórios; os demais são opcionais. Os registros ficam no sistema da Casa da Sopa e são acessados pela equipe conforme suas permissões.</p>
      <p className="mt-2">Para solicitar acesso, correção ou exclusão de dados, procure a administração da Casa da Sopa pelos canais habituais de atendimento. A solicitação deve ser analisada considerando obrigações de guarda e registros de pedidos. Inativar um cadastro mantém seu histórico e não exclui os dados.</p>
    </details>
  </aside>
}
