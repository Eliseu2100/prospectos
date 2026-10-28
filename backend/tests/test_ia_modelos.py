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
