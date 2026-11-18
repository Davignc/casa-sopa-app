"""Proteções em memória: bloqueio de tentativas de login e revogação de tokens.

Limites desta abordagem (o modelo de dados não tem colunas para isso):
* o estado vale **por processo** — com vários workers cada um tem o seu;
* o estado se perde se o servidor reiniciar.
Para uma ONG com um único servidor isso atende; se o sistema crescer, o caminho é
mover estes dois contadores para Redis (ou para tabelas).
"""

import math
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import settings
from app.core.errors import TentativasExcedidasError

_LIMPEZA_A_CADA = 1000  # entradas; evita crescimento ilimitado da memória


@dataclass
class _Registro:
    falhas: int = 0
    ultima_falha: float = 0.0
    bloqueado_ate: float = 0.0


class LimitadorTentativas:
    """Conta falhas por chave e bloqueia ao atingir o limite (RF01, critério 4).

    * ``max_tentativas`` falhas seguidas bloqueiam a chave por ``bloqueio_segundos``;
    * falhas esquecidas após ``bloqueio_segundos`` sem novas tentativas;
    * um sucesso zera a contagem da chave.
    """

    def __init__(
        self,
        max_tentativas: int,
        bloqueio_segundos: int,
        relogio: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max = max_tentativas
        self._bloqueio = bloqueio_segundos
        self._relogio = relogio
        self._registros: dict[str, _Registro] = {}
        self._trava = threading.Lock()

    def verificar(self, chave: str) -> None:
        """Lança ``TentativasExcedidasError`` se a chave estiver bloqueada."""
        agora = self._relogio()
        with self._trava:
            registro = self._registros.get(chave)
            if registro and registro.bloqueado_ate > agora:
                restante = math.ceil(registro.bloqueado_ate - agora)
                raise TentativasExcedidasError(restante)

    def registrar_falha(self, chave: str) -> None:
        agora = self._relogio()
        with self._trava:
            if len(self._registros) >= _LIMPEZA_A_CADA:
                self._limpar_expirados(agora)
            registro = self._registros.setdefault(chave, _Registro())
            if agora - registro.ultima_falha > self._bloqueio:
                registro.falhas = 0  # a janela anterior já passou
            registro.falhas += 1
            registro.ultima_falha = agora
            if registro.falhas >= self._max:
                registro.bloqueado_ate = agora + self._bloqueio
                registro.falhas = 0

    def registrar_sucesso(self, chave: str) -> None:
        with self._trava:
            self._registros.pop(chave, None)

    def limpar(self) -> None:
        with self._trava:
            self._registros.clear()

    def _limpar_expirados(self, agora: float) -> None:
        self._registros = {
            k: r
            for k, r in self._registros.items()
            if r.bloqueado_ate > agora or agora - r.ultima_falha <= self._bloqueio
        }


class RevogadorTokens:
    """Lista de tokens encerrados no logout (RF02), guardados até expirarem."""

    def __init__(self, relogio: Callable[[], float] = time.time) -> None:
        self._relogio = relogio
        self._revogados: dict[str, float] = {}
        self._trava = threading.Lock()

    def revogar(self, jti: str, expira_em: float) -> None:
        agora = self._relogio()
        with self._trava:
            if len(self._revogados) >= _LIMPEZA_A_CADA:
                self._revogados = {j: e for j, e in self._revogados.items() if e > agora}
            self._revogados[jti] = expira_em

    def esta_revogado(self, jti: str) -> bool:
        agora = self._relogio()
        with self._trava:
            expira_em = self._revogados.get(jti)
            if expira_em is None:
                return False
            if expira_em <= agora:  # o token já expiraria sozinho
                del self._revogados[jti]
                return False
            return True

    def limpar(self) -> None:
        with self._trava:
            self._revogados.clear()


_BLOQUEIO_SEGUNDOS = settings.LOGIN_BLOQUEIO_MINUTOS * 60

# Por par (IP + e-mail): barra quem tenta adivinhar a senha de UMA conta, sem deixar
# um atacante trancar a conta da vítima a partir de outro IP.
limitador_login_conta = LimitadorTentativas(settings.LOGIN_MAX_TENTATIVAS, _BLOQUEIO_SEGUNDOS)
# Por IP: barra quem testa muitas contas diferentes (limite maior).
limitador_login_ip = LimitadorTentativas(settings.LOGIN_MAX_TENTATIVAS * 4, _BLOQUEIO_SEGUNDOS)
revogador_tokens = RevogadorTokens()


def limpar_tudo() -> None:
    """Zera o estado (usado nos testes)."""
    limitador_login_conta.limpar()
    limitador_login_ip.limpar()
    revogador_tokens.limpar()
