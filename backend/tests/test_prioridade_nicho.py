"""Testes do bônus de nicho prioritário (prioridade_nicho.py) e da sua soma
no score de leads (rotas_leads.calcular_score)."""

import json
import sqlite3

import db
import paths
import prioridade_nicho
import processar
from rotas_leads import calcular_score


def escrever_playbook(tmp_path, monkeypatch, prioritarios):
    monkeypatch.setattr(paths, "DIR_DADOS", tmp_path)
    prioridade_nicho._cache.update({"mtime": None, "prioritarios": []})
    (tmp_path / "nichos_prioritarios.json").write_text(
        json.dumps({"prioritarios": prioritarios}, ensure_ascii=False), encoding="utf-8"
    )


class TestPontosPrioridade:
    def test_sem_arquivo_devolve_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "DIR_DADOS", tmp_path)
        prioridade_nicho._cache.update({"mtime": None, "prioritarios": []})
        assert prioridade_nicho.pontos_prioridade("Clínica de estética", "estetica") == 0

    def test_nicho_prioritario_bate_pela_palavra_chave(self, tmp_path, monkeypatch):
        escrever_playbook(tmp_path, monkeypatch, [
            {"nicho": "Energia solar", "palavras": ["energia solar"], "pontos": 8},
        ])
        assert prioridade_nicho.pontos_prioridade("Energia solar", "instalação de energia solar") == 8

    def test_nicho_fora_da_lista_nao_ganha_bonus(self, tmp_path, monkeypatch):
        escrever_playbook(tmp_path, monkeypatch, [
            {"nicho": "Energia solar", "palavras": ["energia solar"], "pontos": 8},
        ])
        assert prioridade_nicho.pontos_prioridade("Barbearia", "barbearia") == 0

    def test_trava_no_maximo_mesmo_se_arquivo_pedir_mais(self, tmp_path, monkeypatch):
        escrever_playbook(tmp_path, monkeypatch, [
            {"nicho": "Construção", "palavras": ["construtora"], "pontos": 999},
        ])
        assert prioridade_nicho.pontos_prioridade("Construtora", "construtora") == prioridade_nicho.PONTOS_MAXIMOS

    def test_palavra_mais_longa_vence_entre_dois_matches(self, tmp_path, monkeypatch):
        escrever_playbook(tmp_path, monkeypatch, [
            {"nicho": "Clínica", "palavras": ["clinica"], "pontos": 3},
            {"nicho": "Clínica odontológica", "palavras": ["clinica odontologica"], "pontos": 9},
        ])
        assert prioridade_nicho.pontos_prioridade("Clínica odontológica", "") == 9

    def test_arquivo_invalido_nao_quebra(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "DIR_DADOS", tmp_path)
        prioridade_nicho._cache.update({"mtime": None, "prioritarios": []})
        (tmp_path / "nichos_prioritarios.json").write_text("{não é json}", encoding="utf-8")
        assert prioridade_nicho.pontos_prioridade("Qualquer coisa", "qualquer") == 0


class TestCalcularScoreComNicho:
    def test_bonus_de_nicho_soma_ao_score(self):
        base = calcular_score(nota=4.5, num_avaliacoes=20, site_status="sem_site")
        com_bonus = calcular_score(nota=4.5, num_avaliacoes=20, site_status="sem_site", prioridade_nicho_pontos=8)
        assert com_bonus == base + 8

    def test_score_nunca_passa_de_100_mesmo_com_bonus_maximo(self):
        assert calcular_score(nota=5.0, num_avaliacoes=200, site_status="sem_site", prioridade_nicho_pontos=10) == 100

    def test_bonus_negativo_ou_ausente_nao_quebra(self):
        assert calcular_score(nota=4.5, num_avaliacoes=20, site_status="sem_site", prioridade_nicho_pontos=None) == \
            calcular_score(nota=4.5, num_avaliacoes=20, site_status="sem_site")
        assert calcular_score(nota=4.5, num_avaliacoes=20, site_status="sem_site", prioridade_nicho_pontos=-5) == \
            calcular_score(nota=4.5, num_avaliacoes=20, site_status="sem_site")


class TestBackfillRetroativo:
    """A coluna prioridade_nicho_pontos é nova: leads já existentes (de antes dela
    existir) precisam ganhar o bônus na primeira migração, não só os de agora em diante."""

    def test_lead_antigo_ganha_pontos_na_migracao(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "DIR_DADOS", tmp_path)
        monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "leads.db")
        prioridade_nicho._cache.update({"mtime": None, "prioritarios": []})
        (tmp_path / "nichos_prioritarios.json").write_text(
            json.dumps({"prioritarios": [
                {"nicho": "Energia solar", "palavras": ["energia solar"], "pontos": 8},
            ]}),
            encoding="utf-8",
        )

        conexao = sqlite3.connect(tmp_path / "leads.db")
        # cria o schema SEM a coluna nova, como um banco de antes desta mudança
        # (nicho já existia antes de prioridade_nicho_pontos, só adiciono à mão)
        conexao.execute(
            "CREATE TABLE leads (place_id TEXT PRIMARY KEY, nome TEXT, categoria TEXT, "
            "endereco TEXT, nota REAL, num_avaliacoes INTEGER, whatsapp_link TEXT, "
            "telefone TEXT, query_origem TEXT, status TEXT DEFAULT 'novo', observacoes TEXT, "
            "mensagem_gerada TEXT, visto_em TEXT, atualizado_em TEXT)"
        )
        conexao.execute("ALTER TABLE leads ADD COLUMN nicho TEXT")
        conexao.execute(
            "INSERT INTO leads (place_id, nome, categoria, nicho) VALUES "
            "('p1', 'Solar Curitiba', 'Energia solar', 'energia solar')"
        )
        conexao.commit()
        conexao.close()

        # abrir de novo roda migrar_banco, que deve fazer o backfill uma única vez
        conexao = sqlite3.connect(tmp_path / "leads.db")
        processar.preparar_banco(conexao)
        pontos = conexao.execute(
            "SELECT prioridade_nicho_pontos FROM leads WHERE place_id = 'p1'"
        ).fetchone()[0]
        conexao.close()
        assert pontos == 8

    def test_rodar_migracao_de_novo_nao_duplica_nem_zera(self, tmp_path, monkeypatch):
        monkeypatch.setattr(paths, "DIR_DADOS", tmp_path)
        monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "leads.db")
        prioridade_nicho._cache.update({"mtime": None, "prioritarios": []})
        (tmp_path / "nichos_prioritarios.json").write_text(
            json.dumps({"prioritarios": [
                {"nicho": "Energia solar", "palavras": ["energia solar"], "pontos": 8},
            ]}),
            encoding="utf-8",
        )
        conexao = sqlite3.connect(tmp_path / "leads.db")
        processar.preparar_banco(conexao)
        conexao.execute(
            "INSERT INTO leads (place_id, nome, categoria, nicho) VALUES "
            "('p2', 'Solar SP', 'Energia solar', 'energia solar')"
        )
        conexao.commit()
        conexao.close()

        # roda a migração de novo (ex.: reabrir o app) - não deve mexer em quem já tem valor
        conexao = sqlite3.connect(tmp_path / "leads.db")
        processar.migrar_banco(conexao)
        conexao.close()

        conexao = sqlite3.connect(tmp_path / "leads.db")
        pontos = conexao.execute(
            "SELECT prioridade_nicho_pontos FROM leads WHERE place_id = 'p2'"
        ).fetchone()[0]
        conexao.close()
        # inserido depois da coluna existir: fica 0 até a próxima busca recalcular
        # (o backfill é só para o momento em que a coluna é criada)
        assert pontos == 0
