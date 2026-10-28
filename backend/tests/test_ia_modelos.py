"""Reservas dentro de cada provedor: Gemini sobrecarregado cai pro Flash-Lite,
modelo aposentado da Groq cai pro próximo da lista. Sem rede (SDKs falsos)."""

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import ia


class ErroApi(Exception):
    def __init__(self, status, texto):
        super().__init__(texto)
        self.status_code = status


@pytest.fixture(autouse=True)
def chaves(monkeypatch):
    monkeypatch.setattr(db, "obter_config", lambda chave, default=None: {"gemini": "g", "groq": "q"}.get(chave))


def test_gemini_sobrecarregado_usa_flash_lite(monkeypatch):
    usados = []

    class Modelos:
        def generate_content(self, model, contents, config):
            usados.append(model)
            if model == "gemini-flash-latest":
                raise ErroApi(503, "This model is currently experiencing high demand")
            return types.SimpleNamespace(text=" ok ")

    cliente = types.SimpleNamespace(models=Modelos())
    genai = types.SimpleNamespace(Client=lambda **kw: cliente)
    monkeypatch.setitem(sys.modules, "google", types.SimpleNamespace(genai=genai))
    monkeypatch.setitem(sys.modules, "google.genai", genai)

    assert ia.gemini_gerar_mensagem("s", "u") == "ok"
    assert usados == ["gemini-flash-latest", "gemini-flash-lite-latest"]


def test_gemini_erro_de_chave_nao_tenta_reserva(monkeypatch):
    usados = []

    class Modelos:
        def generate_content(self, model, contents, config):
            usados.append(model)
            raise ErroApi(400, "API key not valid")

    genai = types.SimpleNamespace(Client=lambda **kw: types.SimpleNamespace(models=Modelos()))
    monkeypatch.setitem(sys.modules, "google", types.SimpleNamespace(genai=genai))
    monkeypatch.setitem(sys.modules, "google.genai", genai)

    with pytest.raises(ErroApi):
        ia.gemini_gerar_mensagem("s", "u")
    assert usados == ["gemini-flash-latest"]


def test_groq_modelo_aposentado_tenta_o_proximo(monkeypatch):
    usados = []

    class Completions:
        def create(self, model, **kw):
            usados.append(model)
            if model == ia.MODELOS_GROQ[0]:
                raise ErroApi(404, "model_not_found")
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="oi"))])

    cliente = types.SimpleNamespace(chat=types.SimpleNamespace(completions=Completions()))
    monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(OpenAI=lambda **kw: cliente))

    assert ia.groq_gerar_mensagem("s", "u") == "oi"
    assert usados == ia.MODELOS_GROQ[:2]


# ---------------------------------------------------------------------------
# Claude (reserva paga): só entra depois de Gemini e Groq
# ---------------------------------------------------------------------------

def _anthropic_falso(monkeypatch, capturado, resposta):
    class Mensagens:
        def create(self, **kw):
            capturado.update(kw)
            return resposta

    cliente = types.SimpleNamespace(messages=Mensagens())
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=lambda **kw: cliente))


def _resposta(texto, stop="end_turn"):
    return types.SimpleNamespace(
        stop_reason=stop,
        content=[types.SimpleNamespace(type="thinking", thinking=""), types.SimpleNamespace(type="text", text=texto)],
    )


def test_claude_usa_haiku_sem_temperature(monkeypatch):
    capturado = {}
    _anthropic_falso(monkeypatch, capturado, _resposta(" Oi! "))
    assert ia.claude_gerar_mensagem("sys", "user", temperatura=0.9) == "Oi!"
    assert capturado["model"] == "claude-haiku-5-5"
    assert "temperature" not in capturado  # o Haiku 5.5 devolve 400 com temperature
    assert capturado["output_config"] == {"effort": "medium"}


def test_claude_json_usa_effort_baixo_e_reforca_formato(monkeypatch):
    capturado = {}
    _anthropic_falso(monkeypatch, capturado, _resposta('{"a": 1}'))
    ia.claude_gerar_mensagem("sys", "user", formato_json=True)
    assert capturado["output_config"] == {"effort": "low"}
    assert "JSON" in capturado["system"]


def test_claude_recusa_vira_erro_para_o_fallback(monkeypatch):
    _anthropic_falso(monkeypatch, {}, _resposta("", stop="refusal"))
    with pytest.raises(RuntimeError):
        ia.claude_gerar_mensagem("sys", "user")


def test_claude_so_entra_depois_dos_gratuitos(monkeypatch):
    chamados = []

    def falha(nome):
        def gerar(*a, **k):
            chamados.append(nome)
            raise ErroApi(429, "quota exceeded")
        return gerar

    def claude(*a, **k):
        chamados.append("claude")
        return "resposta do claude"

    monkeypatch.setattr(db, "obter_config", lambda chave, default=None: "chave")
    monkeypatch.setattr(ia, "_provedores_em_cooldown", {})
    monkeypatch.setitem(ia.GERADORES, "gemini", falha("gemini"))
    monkeypatch.setitem(ia.GERADORES, "groq", falha("groq"))
    monkeypatch.setitem(ia.GERADORES, "claude", claude)

    resultado, provedor, _avisos = ia.executar_com_fallback("s", "u")
    assert (resultado, provedor) == ("resposta do claude", "claude")
    assert chamados == ["gemini", "groq", "claude"]
