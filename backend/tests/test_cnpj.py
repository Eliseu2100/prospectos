"""Testes da consulta de CNPJ (cnpj.py): normalização, erros amigáveis e o
cálculo de ticket_alto_provavel (não MEI, ativa, 2+ anos)."""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import cnpj


class RespostaFake:
    def __init__(self, status_code=200, corpo=None):
        self.status_code = status_code
        self._corpo = corpo or {}

    def json(self):
        return self._corpo


def data_ha_meses(meses):
    aproximado = date.today() - timedelta(days=meses * 30)
    return aproximado.strftime("%Y-%m-%d")


class TestCnpjLimpoEValido:
    def test_remove_pontuacao(self):
        assert cnpj.cnpj_limpo("19.131.243/0001-97") == "19131243000197"

    def test_remove_espacos(self):
        assert cnpj.cnpj_limpo(" 19131243000197 ") == "19131243000197"

    def test_none_vira_vazio(self):
        assert cnpj.cnpj_limpo(None) == ""

    def test_valido_com_14_digitos(self):
        assert cnpj.cnpj_valido("19131243000197") is True

    def test_invalido_com_menos_digitos(self):
        assert cnpj.cnpj_valido("123") is False

    def test_invalido_todos_iguais(self):
        # formato comum de CNPJ de teste/placeholder, nunca é real
        assert cnpj.cnpj_valido("00000000000000") is False


class TestConsultarCnpj:
    def test_formato_invalido_nao_bate_na_rede(self, monkeypatch):
        chamou = []
        monkeypatch.setattr(cnpj.requests, "get", lambda *a, **kw: chamou.append(1))
        with pytest.raises(cnpj.ErroConsultaCnpj, match="inválido"):
            cnpj.consultar_cnpj("123")
        assert chamou == []

    def test_404_vira_mensagem_amigavel(self, monkeypatch):
        monkeypatch.setattr(cnpj.requests, "get", lambda *a, **kw: RespostaFake(404))
        with pytest.raises(cnpj.ErroConsultaCnpj, match="não encontrado"):
            cnpj.consultar_cnpj("19131243000197")

    def test_429_vira_mensagem_de_limite(self, monkeypatch):
        monkeypatch.setattr(cnpj.requests, "get", lambda *a, **kw: RespostaFake(429))
        with pytest.raises(cnpj.ErroConsultaCnpj, match="[Mm]uitas consultas"):
            cnpj.consultar_cnpj("19131243000197")

    def test_falha_de_rede_vira_mensagem_amigavel(self, monkeypatch):
        def explode(*a, **kw):
            raise cnpj.requests.exceptions.ConnectionError("sem rede")

        monkeypatch.setattr(cnpj.requests, "get", explode)
        with pytest.raises(cnpj.ErroConsultaCnpj, match="Receita Federal"):
            cnpj.consultar_cnpj("19131243000197")

    def test_empresa_nao_mei_ativa_antiga_e_ticket_alto(self, monkeypatch):
        corpo = {
            "razao_social": "CONSTRUTORA EXEMPLO LTDA",
            "nome_fantasia": "Construtora Exemplo",
            "opcao_pelo_mei": False,
            "porte": "DEMAIS",
            "descricao_situacao_cadastral": "ATIVA",
            "natureza_juridica": "Sociedade Empresária Limitada",
            "capital_social": 500000,
            "data_inicio_atividade": data_ha_meses(60),
        }
        monkeypatch.setattr(cnpj.requests, "get", lambda *a, **kw: RespostaFake(200, corpo))
        resultado = cnpj.consultar_cnpj("19.131.243/0001-97")
        assert resultado["cnpj"] == "19131243000197"
        assert resultado["mei"] is False
        assert resultado["ticket_alto_provavel"] is True
        assert resultado["idade_meses"] >= 59

    def test_mei_nunca_e_ticket_alto_mesmo_antigo(self, monkeypatch):
        corpo = {
            "opcao_pelo_mei": True,
            "descricao_situacao_cadastral": "ATIVA",
            "data_inicio_atividade": data_ha_meses(60),
        }
        monkeypatch.setattr(cnpj.requests, "get", lambda *a, **kw: RespostaFake(200, corpo))
        resultado = cnpj.consultar_cnpj("19131243000197")
        assert resultado["mei"] is True
        assert resultado["ticket_alto_provavel"] is False

    def test_empresa_nova_nao_e_ticket_alto(self, monkeypatch):
        corpo = {
            "opcao_pelo_mei": False,
            "descricao_situacao_cadastral": "ATIVA",
            "data_inicio_atividade": data_ha_meses(6),
        }
        monkeypatch.setattr(cnpj.requests, "get", lambda *a, **kw: RespostaFake(200, corpo))
        resultado = cnpj.consultar_cnpj("19131243000197")
        assert resultado["ticket_alto_provavel"] is False

    def test_empresa_baixada_nao_e_ticket_alto(self, monkeypatch):
        corpo = {
            "opcao_pelo_mei": False,
            "descricao_situacao_cadastral": "BAIXADA",
            "data_inicio_atividade": data_ha_meses(60),
        }
        monkeypatch.setattr(cnpj.requests, "get", lambda *a, **kw: RespostaFake(200, corpo))
        resultado = cnpj.consultar_cnpj("19131243000197")
        assert resultado["ticket_alto_provavel"] is False

    def test_sem_data_inicio_nao_quebra(self, monkeypatch):
        corpo = {"opcao_pelo_mei": False, "descricao_situacao_cadastral": "ATIVA"}
        monkeypatch.setattr(cnpj.requests, "get", lambda *a, **kw: RespostaFake(200, corpo))
        resultado = cnpj.consultar_cnpj("19131243000197")
        assert resultado["idade_meses"] is None
        assert resultado["ticket_alto_provavel"] is False
