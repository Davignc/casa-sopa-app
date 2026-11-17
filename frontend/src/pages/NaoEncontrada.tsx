import { Link } from 'react-router-dom'
import { Vazio } from '../components/ui'

export default function NaoEncontrada({ restrita }: { restrita?: boolean }) {
  return (
    <div className="cartao mx-auto mt-10 max-w-lg">
      <Vazio titulo={restrita ? 'Área restrita à administradora' : 'Página não encontrada'}>
        {restrita ? 'Você não tem permissão para ver esta tela.' : 'O endereço não existe.'}{' '}
        <Link to="/" className="font-medium text-brand-700 underline">Voltar ao início</Link>
      </Vazio>
    </div>
  )
}
