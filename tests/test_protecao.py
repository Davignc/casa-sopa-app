"""Limitador de tentativas e revogador de tokens (unitários, com relógio falso)."""

import pytest

from app.core.errors import TentativasExcedidasError
from app.core.protecao import LimitadorTentativas, RevogadorTokens


class Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


@pytest.fixture
def relogio() -> Relogio:
    return Relogio()


@pytest.fixture
def limitador(relogio) -> LimitadorTentativas:
    return LimitadorTentativas(max_tentativas=3, bloqueio_segundos=600, relogio=relogio)


def _falhar(limitador, chave, vezes):
    for _ in range(vezes):
        limitador.verificar(chave)
        limitador.registrar_falha(chave)


def test_abaixo_do_limite_nao_bloqueia(limitador):
    _falhar(limitador, "a", 2)
    limitador.verificar("a")


def test_ao_atingir_o_limite_bloqueia(limitador):
    _falhar(limitador, "a", 3)
    with pytest.raises(TentativasExcedidasError):
        limitador.verificar("a")


def test_bloqueio_informa_quanto_esperar(limitador):
    _falhar(limitador, "a", 3)
    with pytest.raises(TentativasExcedidasError) as erro:
        limitador.verificar("a")
    assert erro.value.status_code == 429
    assert erro.value.headers == {"Retry-After": "600"}
    assert "10 minuto" in erro.value.detail


def test_bloqueio_expira_com_o_tempo(limitador, relogio):
    _falhar(limitador, "a", 3)
    relogio.avancar(601)
    limitador.verificar("a")


def test_chaves_sao_independentes(limitador):
    _falhar(limitador, "a", 3)
    limitador.verificar("b")


def test_sucesso_zera_a_contagem(limitador):
    _falhar(limitador, "a", 2)
    limitador.registrar_sucesso("a")
    _falhar(limitador, "a", 2)
    limitador.verificar("a")


def test_falhas_antigas_sao_esquecidas(limitador, relogio):
    _falhar(limitador, "a", 2)
    relogio.avancar(601)
    _falhar(limitador, "a", 2)  # contaria 4 se não esquecesse as duas primeiras
    limitador.verificar("a")


def test_depois_de_expirar_precisa_de_novas_falhas_para_bloquear_de_novo(limitador, relogio):
    _falhar(limitador, "a", 3)
    relogio.avancar(601)
    _falhar(limitador, "a", 2)
    limitador.verificar("a")
    limitador.registrar_falha("a")
    with pytest.raises(TentativasExcedidasError):
        limitador.verificar("a")


def test_memoria_nao_cresce_sem_limite(relogio):
    limitador = LimitadorTentativas(3, 600, relogio=relogio)
    for i in range(1500):
        limitador.registrar_falha(f"k{i}")
    relogio.avancar(1200)
    limitador.registrar_falha("nova")  # dispara a limpeza
    assert len(limitador._registros) < 10


# --- RevogadorTokens ---------------------------------------------------------


def test_token_revogado_e_reconhecido(relogio):
    revogador = RevogadorTokens(relogio=relogio)
    revogador.revogar("abc", expira_em=relogio.agora + 3600)
    assert revogador.esta_revogado("abc")
    assert not revogador.esta_revogado("outro")


def test_revogacao_some_quando_o_token_expiraria(relogio):
    revogador = RevogadorTokens(relogio=relogio)
    revogador.revogar("abc", expira_em=relogio.agora + 60)
    relogio.avancar(61)
    assert not revogador.esta_revogado("abc")
