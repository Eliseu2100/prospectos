"""Testes do score de leads (ordenação da fila de abordagem) e da rota
/api/tarefas-hoje (mesa de trabalho do dia)."""

import sqlite3
from datetime import datetime, timedelta

import pytest

import app as app_module
import db
import processar
from rotas_leads import calcular_score


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    caminho_banco_teste = tmp_path / "leads_teste.db"
    monkeypatch.setattr(db, "CAMINHO_BANCO", caminho_banco_teste)

    conexao = sqlite3.connect(caminho_banco_teste)
    processar.preparar_banco(conexao)
    conexao.close()

    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as cliente_teste:
        yield cliente_teste


def inserir_lead(place_id, **overrides):
    campos = {
        "place_id": place_id,
        "nome": f"Empresa {place_id}",
        "categoria": "Categoria",
        "endereco": "Endereço",
        "nota": 4.5,
        "num_avaliacoes": 20,
        "whatsapp_link": "https://wa.me/5511999999999",
        "telefone": "5511999999999",
        "query_origem": "nicho em cidade",
        "nicho": "nicho",
        "cidade": "cidade",
        "status": "novo",
        "site_status": "sem_site",
        "site_problemas": None,
        "proximo_followup": None,
        "mensagem_gerada": None,
        "visto_em": "2026-01-01",
        "atualizado_em": "2026-01-01T00:00:00",
    }
    campos.update(overrides)

    conexao = sqlite3.connect(db.CAMINHO_BANCO)
    conexao.execute(
        """
        INSERT INTO leads (place_id, nome, categoria, endereco, nota, num_avaliacoes,
                           whatsapp_link, telefone, query_origem, nicho, cidade, status,
                           site_status, site_problemas, proximo_followup, mensagem_gerada,
                           visto_em, atualizado_em)
        VALUES (:place_id, :nome, :categoria, :endereco, :nota, :num_avaliacoes,
                :whatsapp_link, :telefone, :query_origem, :nicho, :cidade, :status,
                :site_status, :site_problemas, :proximo_followup, :mensagem_gerada,
                :visto_em, :atualizado_em)
        """,
        campos,
    )
    conexao.commit()
    conexao.close()


def inserir_lead_instagram(username, **overrides):
    conexao = sqlite3.connect(db.CAMINHO_BANCO)
    cursor = conexao.execute(
        "INSERT INTO instagram_posts (post_url, criado_em, etapa) VALUES ('https://www.instagram.com/p/X/', '2026-01-01', 'concluido')"
    )
    post_id = cursor.lastrowid
    campos = {
        "post_id": post_id,
        "username": username,
        "status": "contatado",
        "proximo_followup": None,
        "sugestao_dm": None,
        "follow_ups_enviados": 0,
        "atualizado_em": "2026-01-01T00:00:00",
    }
    campos.update(overrides)
    conexao.execute(
        """
        INSERT INTO instagram_leads (post_id, username, status, proximo_followup,
                                     sugestao_dm, follow_ups_enviados, atualizado_em)
        VALUES (:post_id, :username, :status, :proximo_followup, :sugestao_dm,
                :follow_ups_enviados, :atualizado_em)
        """,
        campos,
    )
    conexao.commit()
    conexao.close()


class TestCalcularScore:
    def test_lead_perfeito_sem_site(self):
        # nota 5.0 (40) + 100+ avaliações (30) + sem site (30) = 100
        assert calcular_score(5.0, 150, "sem_site") == 100

    def test_lead_site_ruim_pontua_menos_que_sem_site(self):
        assert calcular_score(5.0, 150, "site_ruim") == 92
        assert calcular_score(5.0, 150, "site_ruim") < calcular_score(5.0, 150, "sem_site")

    def test_nota_minima_zera_pontos_de_nota(self):
        assert calcular_score(4.0, 0, "sem_site") == 30

    def test_nota_nula_nao_explode(self):
        assert calcular_score(None, None, None) == 30


class TestOrdenacaoPorScore:
    def test_ordenar_por_score_poe_o_mais_quente_primeiro(self, cliente):
        inserir_lead("morno", nota=4.1, num_avaliacoes=5, visto_em="2026-07-17")
        inserir_lead("quente", nota=5.0, num_avaliacoes=200, visto_em="2026-01-01")

        # ordenação padrão: mais recente primeiro (morno)
        padrao = cliente.get("/api/leads").get_json()["leads"]
        assert [l["place_id"] for l in padrao] == ["morno", "quente"]

        # por score: o quente vem primeiro, mesmo sendo mais antigo
        por_score = cliente.get("/api/leads?ordenar=score").get_json()["leads"]
        assert [l["place_id"] for l in por_score] == ["quente", "morno"]

    def test_resposta_inclui_score_e_campos_de_site(self, cliente):
        inserir_lead("lead-1", site_status="site_ruim", site_problemas="sem HTTPS")

        lead = cliente.get("/api/leads").get_json()["leads"][0]
        assert lead["score"] == calcular_score(4.5, 20, "site_ruim")
        assert lead["site_status"] == "site_ruim"
        assert lead["site_problemas"] == "sem HTTPS"

    def test_ordenar_invalido_retorna_400(self, cliente):
        assert cliente.get("/api/leads?ordenar=alfabetica").status_code == 400

    def test_score_site_ok_e_o_mais_baixo(self):
        assert calcular_score(5.0, 150, "site_ok") == 80
        assert calcular_score(5.0, 150, "site_ok") < calcular_score(5.0, 150, "site_ruim")


class TestFiltroSituacaoDoSite:
    def test_filtra_por_site_ruim(self, cliente):
        inserir_lead("sem", site_status="sem_site")
        inserir_lead("ruim", site_status="site_ruim", site_problemas="sem HTTPS")

        leads = cliente.get("/api/leads?site_status=site_ruim").get_json()["leads"]
        assert [l["place_id"] for l in leads] == ["ruim"]

    def test_site_status_invalido_retorna_400(self, cliente):
        assert cliente.get("/api/leads?site_status=qualquer").status_code == 400


class TestFiltroFollowupVencido:
    def test_traz_so_vencidos_ordenados_pelo_mais_atrasado(self, cliente):
        ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        anteontem = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        inserir_lead("ontem", status="contatado", proximo_followup=ontem)
        inserir_lead("anteontem", status="contatado", proximo_followup=anteontem)
        inserir_lead("futuro", status="contatado", proximo_followup=amanha)
        inserir_lead("sem-followup", status="novo")

        leads = cliente.get("/api/leads?followup=vencido").get_json()["leads"]
        assert [l["place_id"] for l in leads] == ["anteontem", "ontem"]

    def test_followup_invalido_retorna_400(self, cliente):
        assert cliente.get("/api/leads?followup=amanha").status_code == 400


class TestReanalisarSite:
    def test_reanalisa_lead_com_site(self, cliente, monkeypatch):
        import processar
        monkeypatch.setattr(
            processar, "avaliar_site_completo",
            lambda url: ("ruim", ["sem HTTPS"], {"tem": ["fotos do negócio"], "falta": ["botão de WhatsApp"]}),
        )
        inserir_lead("lead-1", site_status="site_ruim")
        conexao = sqlite3.connect(db.CAMINHO_BANCO)
        conexao.execute("UPDATE leads SET site_url = 'https://x.com.br' WHERE place_id = 'lead-1'")
        conexao.commit()
        conexao.close()

        resposta = cliente.post("/api/leads/lead-1/reanalisar-site")
        dados = resposta.get_json()
        assert resposta.status_code == 200
        assert dados["site_status"] == "site_ruim"
        assert dados["site_checklist"]["falta"] == ["botão de WhatsApp"]

        lead = cliente.get("/api/leads?status=novo").get_json()["leads"][0]
        assert lead["site_checklist"]["falta"] == ["botão de WhatsApp"]

    def test_site_que_melhorou_vira_site_ok(self, cliente, monkeypatch):
        import processar
        monkeypatch.setattr(
            processar, "avaliar_site_completo", lambda url: ("ok", [], {"tem": ["botão de WhatsApp"], "falta": []})
        )
        inserir_lead("lead-1", site_status="site_ruim", site_problemas="sem HTTPS")
        conexao = sqlite3.connect(db.CAMINHO_BANCO)
        conexao.execute("UPDATE leads SET site_url = 'https://x.com.br' WHERE place_id = 'lead-1'")
        conexao.commit()
        conexao.close()

        dados = cliente.post("/api/leads/lead-1/reanalisar-site").get_json()
        assert dados["site_status"] == "site_ok"
        assert dados["site_problemas"] is None

    def test_sem_site_tenta_achar_na_web(self, cliente, monkeypatch):
        import processar
        monkeypatch.setattr(processar, "buscar_site_da_empresa", lambda nome, endereco="": None)
        inserir_lead("lead-1", site_status="sem_site")

        dados = cliente.post("/api/leads/lead-1/reanalisar-site").get_json()
        assert dados["site_status"] == "sem_site"

    def test_lead_inexistente_retorna_404(self, cliente):
        assert cliente.post("/api/leads/nao-existe/reanalisar-site").status_code == 404


class TestConsultarCnpjDoLead:
    def test_sem_cnpj_no_corpo_retorna_400(self, cliente):
        inserir_lead("lead-1")
        resposta = cliente.post("/api/leads/lead-1/consultar-cnpj", json={})
        assert resposta.status_code == 400

    def test_lead_inexistente_retorna_404(self, cliente):
        resposta = cliente.post(
            "/api/leads/nao-existe/consultar-cnpj", json={"cnpj": "19131243000197"}
        )
        assert resposta.status_code == 404

    def test_cnpj_invalido_retorna_400_sem_gravar(self, cliente):
        inserir_lead("lead-1")
        resposta = cliente.post("/api/leads/lead-1/consultar-cnpj", json={"cnpj": "123"})
        assert resposta.status_code == 400
        lead = cliente.get("/api/leads?status=novo").get_json()["leads"][0]
        assert lead["cnpj"] is None

    def test_consulta_com_sucesso_grava_no_lead(self, cliente, monkeypatch):
        import cnpj as modulo_cnpj

        resultado_fake = {
            "cnpj": "19131243000197",
            "razao_social": "CONSTRUTORA EXEMPLO LTDA",
            "nome_fantasia": "Construtora Exemplo",
            "mei": False,
            "porte": "DEMAIS",
            "situacao_cadastral": "ATIVA",
            "natureza_juridica": "Sociedade Empresária Limitada",
            "capital_social": 500000,
            "data_inicio_atividade": "2018-01-01",
            "idade_meses": 95,
            "ticket_alto_provavel": True,
        }
        monkeypatch.setattr(modulo_cnpj, "consultar_cnpj", lambda bruto: resultado_fake)
        inserir_lead("lead-1")

        resposta = cliente.post(
            "/api/leads/lead-1/consultar-cnpj", json={"cnpj": "19.131.243/0001-97"}
        )
        assert resposta.status_code == 200
        assert resposta.get_json()["cnpj_dados"]["ticket_alto_provavel"] is True

        lead = cliente.get("/api/leads?status=novo").get_json()["leads"][0]
        assert lead["cnpj"] == "19131243000197"
        assert lead["cnpj_dados"]["razao_social"] == "CONSTRUTORA EXEMPLO LTDA"
        assert lead["cnpj_dados"]["mei"] is False

    def test_erro_da_receita_vira_400_com_mensagem(self, cliente, monkeypatch):
        import cnpj as modulo_cnpj

        def explode(bruto):
            raise modulo_cnpj.ErroConsultaCnpj("CNPJ não encontrado na Receita Federal. Confira o número.")

        monkeypatch.setattr(modulo_cnpj, "consultar_cnpj", explode)
        inserir_lead("lead-1")

        resposta = cliente.post(
            "/api/leads/lead-1/consultar-cnpj", json={"cnpj": "19131243000197"}
        )
        assert resposta.status_code == 400
        assert "não encontrado" in resposta.get_json()["erro"]


class TestHistoricoDeBuscas:
    def test_lista_ultimas_buscas(self, cliente):
        conexao = sqlite3.connect(db.CAMINHO_BANCO)
        for i, status in enumerate(["concluido", "erro", "interrompido"], start=1):
            conexao.execute(
                "INSERT INTO jobs (tipo, status, mensagem, iniciado_em) VALUES ('busca_maps', ?, ?, ?)",
                (status, f"busca {i}", f"2026-07-1{i}T10:00:00"),
            )
        conexao.execute(
            "INSERT INTO jobs (tipo, status, iniciado_em) VALUES ('analise_instagram', 'concluido', '2026-07-14T10:00:00')"
        )
        conexao.commit()
        conexao.close()

        buscas = cliente.get("/api/buscar/historico").get_json()["buscas"]
        assert len(buscas) == 3  # só busca_maps, análise do IG fica de fora
        assert buscas[0]["mensagem"] == "busca 3"  # mais recente primeiro


class TestTarefasHoje:
    def test_estrutura_vazia(self, cliente):
        dados = cliente.get("/api/tarefas-hoje").get_json()
        assert dados == {"followups": [], "novos_quentes": []}

    def test_followups_vencidos_dos_dois_canais_ordenados(self, cliente):
        ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        anteontem = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        amanha = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        inserir_lead("maps-vencido", status="contatado", proximo_followup=ontem,
                     mensagem_gerada="Olá!")
        inserir_lead("maps-futuro", status="contatado", proximo_followup=amanha)
        inserir_lead_instagram("ig_vencido", proximo_followup=anteontem, sugestao_dm="Oi!")

        followups = cliente.get("/api/tarefas-hoje").get_json()["followups"]
        assert [(f["canal"], f["titulo"]) for f in followups] == [
            ("instagram", "@ig_vencido"),  # mais atrasado primeiro
            ("maps", "Empresa maps-vencido"),
        ]
        assert followups[0]["mensagem"] == "Oi!"
        assert followups[1]["whatsapp_link"] == "https://wa.me/5511999999999"

    def test_novos_quentes_ordenados_por_score_max_5(self, cliente):
        for i in range(6):
            inserir_lead(f"novo-{i}", nota=4.0 + i * 0.1, num_avaliacoes=10 * i)
        inserir_lead("contatado", nota=5.0, num_avaliacoes=500, status="contatado")

        quentes = cliente.get("/api/tarefas-hoje").get_json()["novos_quentes"]
        assert len(quentes) == 5  # limite, e só status 'novo'
        assert quentes[0]["id"] == "novo-5"  # maior score primeiro
        assert all(q["score"] >= quentes[-1]["score"] for q in quentes)
        assert "contatado" not in [q["id"] for q in quentes]
