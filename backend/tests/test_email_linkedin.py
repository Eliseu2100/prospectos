"""Testes da prospecção por e-mail (achar e-mails, escrever, enviar, descadastrar) e do LinkedIn
assistido. Nada toca rede: SMTP, IA e leitura de sites são substituídos."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module
import db
import email_modelo
import email_prospeccao
import ia
import mensageiros
import processar
import rotas_email


@pytest.fixture
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "leads_teste.db"
    monkeypatch.setattr(db, "CAMINHO_BANCO", caminho)
    cofre = {}
    monkeypatch.setattr(db, "_keyring_obter", cofre.get)
    monkeypatch.setattr(db, "_keyring_salvar", lambda c, v: cofre.update({c: v}) or True)
    monkeypatch.setattr(db, "_keyring_apagar", lambda c: cofre.pop(c, None))
    conexao = sqlite3.connect(caminho)
    processar.preparar_banco(conexao)
    conexao.close()
    return cofre


@pytest.fixture
def cliente(banco):
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture
def enviados(monkeypatch):
    """Substitui o envio SMTP e guarda o que seria enviado."""
    registro = []

    def falso(para, assunto, corpo, html=None, imagens=None, anexos=None):
        registro.append({"para": para, "assunto": assunto, "corpo": corpo, "html": html, "anexos": anexos or []})
        return f"<id-{len(registro)}@teste>"

    monkeypatch.setattr(mensageiros, "enviar_email", falso)
    monkeypatch.setattr(mensageiros, "config_smtp", lambda: {
        "host": "smtp.teste", "porta": 587, "usuario": "eu@teste.com", "senha": "x",
        "remetente_nome": "Eliseu", "remetente_email": "eu@teste.com"})
    return registro


def _novo_lead(cliente, email="contato@empresa.com.br", empresa="Empresa X"):
    resposta = cliente.post("/api/email/leads", json={"empresa": empresa, "email": email, "setor": "energia solar",
                                                        "cidade": "Campinas"})
    assert resposta.status_code == 200, resposta.get_json()
    return resposta.get_json()["id"]


class TestExtracaoDeEmail:
    def test_pega_mailto_e_texto_e_descarta_lixo(self):
        pagina = ('<a href="mailto:contato@loja.com.br">fale</a> vendas@loja.com.br '
                  'logo@2x.png noreply@loja.com.br x@sentry.io')
        achados = email_prospeccao.extrair_emails_de_html(pagina, "loja.com.br")
        assert "contato@loja.com.br" in achados and "vendas@loja.com.br" in achados
        assert not any(e.endswith(".png") or "noreply" in e or "sentry" in e for e in achados)

    def test_prefere_o_dominio_do_proprio_site(self):
        achados = email_prospeccao.extrair_emails_de_html("fulano@gmail.com contato@loja.com.br", "loja.com.br")
        assert achados[0] == "contato@loja.com.br"

    def test_email_de_contabilidade_nao_entra(self, banco):
        conexao = db.conectar()
        try:
            assert email_prospeccao.inserir_email_lead(conexao, "X", "contato@contabilidadeabc.com.br") is None
            assert email_prospeccao.inserir_email_lead(conexao, "X", "dono@loja.com.br") is not None
        finally:
            conexao.close()

    def test_nao_le_site_interno(self):
        assert not email_prospeccao._host_seguro("http://127.0.0.1:5000/admin")
        assert not email_prospeccao._host_seguro("http://192.168.0.10")
        assert email_prospeccao._host_seguro("https://empresa.com.br")

    def test_importar_dos_leads_usa_o_site(self, banco, monkeypatch):
        conexao = db.conectar()
        conexao.execute("INSERT INTO leads (place_id, nome, categoria, endereco, site_url, status, visto_em, atualizado_em) "
                        "VALUES ('p1', 'Solar Tech - Energia', 'energia solar', 'Rua A, Campinas - SP, 1', "
                        "'https://solartech.com.br', 'contatado', '2026-11-01', '2026-11-01')")
        conexao.commit()
        monkeypatch.setattr(email_prospeccao, "buscar_emails_do_site", lambda url: ["contato@solartech.com.br"])
        progresso = {}
        email_prospeccao.importar_dos_leads(conexao, progresso)
        linha = conexao.execute("SELECT empresa, email, fonte, origem_ref FROM email_leads").fetchone()
        conexao.close()
        assert tuple(linha) == ("Solar Tech", "contato@solartech.com.br", "site", "p1")
        assert progresso["novos"] == 1 and progresso["processados"] == 1


class TestReceita:
    def _linha(self, basico, fantasia, situacao, cnae, uf, municipio, email):
        campos = [""] * 30
        campos[0], campos[1], campos[2] = basico, "0001", "55"
        campos[4], campos[5], campos[11], campos[19], campos[20], campos[27] = fantasia, situacao, cnae, uf, municipio, email
        return ";".join(f'"{c}"' for c in campos)

    def test_filtra_por_cnae_uf_situacao_e_municipio(self, banco, tmp_path):
        arquivo = tmp_path / "estab.csv"
        arquivo.write_text("\n".join([
            self._linha("11111111", "SOLAR BOA", "02", "4321500", "SP", "6291", "dono@solarboa.com.br"),
            self._linha("22222222", "SOLAR BAIXADA", "08", "4321500", "SP", "6291", "x@baixada.com.br"),
            self._linha("33333333", "PADARIA", "02", "1091101", "SP", "6291", "p@padaria.com.br"),
            self._linha("44444444", "SOLAR RJ", "02", "4321500", "RJ", "6291", "r@solarrj.com.br"),
            self._linha("55555555", "SOLAR OUTRA CIDADE", "02", "4321500", "SP", "7107", "o@outra.com.br"),
            self._linha("66666666", "SOLAR CONTAB", "02", "4321500", "SP", "6291", "c@contabilsolar.com.br"),
        ]), encoding="latin-1")
        municipios = tmp_path / "mun.csv"
        municipios.write_text('"6291";"CAMPINAS"\n"7107";"SAO PAULO"\n', encoding="latin-1")
        conexao = db.conectar()
        try:
            resultado = email_prospeccao.importar_receita(
                conexao, str(arquivo), ["4321"], "SP", municipio="Campinas", municipios_arquivo=str(municipios),
                setor="energia solar")
            linhas = conexao.execute("SELECT empresa, email, cidade, setor, fonte FROM email_leads").fetchall()
        finally:
            conexao.close()
        assert resultado["importados"] == 1
        assert tuple(linhas[0]) == ("Solar Boa", "dono@solarboa.com.br", "Campinas", "energia solar", "receita")

    def test_municipio_exige_arquivo(self, banco, tmp_path):
        arquivo = tmp_path / "e.csv"
        arquivo.write_text("", encoding="latin-1")
        conexao = db.conectar()
        try:
            with pytest.raises(ValueError):
                email_prospeccao.importar_receita(conexao, str(arquivo), ["4321"], "SP", municipio="Campinas")
        finally:
            conexao.close()


class TestEnvioDeEmail:
    def test_primeiro_simples_depois_marca_com_pdf(self, cliente, enviados, tmp_path, monkeypatch):
        pdf = tmp_path / "proposta.pdf"
        pdf.write_bytes(b"%PDF-1.4 teste")
        monkeypatch.setattr(rotas_email, "_arquivo_anexo", lambda: str(pdf))
        lead_id = _novo_lead(cliente)
        r1 = cliente.post(f"/api/email/leads/{lead_id}/enviar", json={"assunto": "uma pergunta", "corpo": "Oi, tudo bem?"})
        assert r1.get_json() == {"ok": True, "status": "contatado"}
        assert enviados[0]["html"] is None and enviados[0]["anexos"] == []
        assert "descadastrar" in enviados[0]["corpo"] and "Criação de Sites Premium" in enviados[0]["corpo"]
        cliente.post(f"/api/email/leads/{lead_id}/enviar", json={"assunto": "outra", "corpo": "Segundo e-mail."})
        assert enviados[1]["html"] and "descadastrar" in enviados[1]["html"]
        assert enviados[1]["anexos"] == [str(pdf)]
        cliente.post(f"/api/email/leads/{lead_id}/enviar", json={"assunto": "terceira", "corpo": "Terceiro."})
        assert enviados[2]["anexos"] == [str(pdf)]  # o anexo vai em todo e-mail de marca; desligue o interruptor se não quiser
        lead = cliente.get("/api/email/leads").get_json()["leads"][0]
        assert lead["follow_ups_enviados"] == 2
        historico = cliente.get(f"/api/email/leads/{lead_id}/historico").get_json()["mensagens"]
        assert len(historico) == 3 and historico[0]["autor"] == "vendedor"

    def test_com_o_interruptor_desligado_o_primeiro_sai_com_marca_e_pdf(self, cliente, enviados, tmp_path, monkeypatch):
        pdf = tmp_path / "proposta.pdf"
        pdf.write_bytes(b"%PDF-1.4 teste")
        monkeypatch.setattr(rotas_email, "_arquivo_anexo", lambda: str(pdf))
        db.salvar_config("email_primeiro_simples", "0")
        lead_id = _novo_lead(cliente)
        cliente.post(f"/api/email/leads/{lead_id}/enviar", json={"assunto": "x", "corpo": "y"})
        assert enviados[0]["html"] and enviados[0]["anexos"] == [str(pdf)]

    def test_respeita_o_limite_diario(self, cliente, enviados):
        db.salvar_config("email_limite_diario", "1")
        a, b = _novo_lead(cliente, "a@empresa.com.br"), _novo_lead(cliente, "b@empresa.com.br")
        assert cliente.post(f"/api/email/leads/{a}/enviar", json={"assunto": "x", "corpo": "y"}).status_code == 200
        r = cliente.post(f"/api/email/leads/{b}/enviar", json={"assunto": "x", "corpo": "y"})
        assert r.status_code == 429 and len(enviados) == 1

    def test_descadastrado_nunca_recebe_e_nao_volta(self, cliente, enviados):
        lead_id = _novo_lead(cliente)
        cliente.post(f"/api/email/leads/{lead_id}/status", json={"status": "descadastrado"})
        r = cliente.post(f"/api/email/leads/{lead_id}/enviar", json={"assunto": "x", "corpo": "y"})
        assert r.status_code == 400 and not enviados
        assert "contato@empresa.com.br" in cliente.get("/api/email/descadastros").get_json()["emails"]
        r2 = cliente.post("/api/email/leads", json={"empresa": "Outra", "email": "contato@empresa.com.br"})
        assert r2.status_code == 400

    def test_sem_texto_nao_envia(self, cliente, enviados):
        lead_id = _novo_lead(cliente)
        assert cliente.post(f"/api/email/leads/{lead_id}/enviar", json={"assunto": "", "corpo": "x"}).status_code == 400

    def test_gerar_usa_a_ia(self, cliente, monkeypatch):
        monkeypatch.setattr(ia, "gerar_email_com_fallback", lambda lead, n, anterior: (
            {"assunto": "uma pergunta", "corpo": "Oi"}, "claude", []))
        lead_id = _novo_lead(cliente)
        corpo = cliente.post(f"/api/email/leads/{lead_id}/gerar").get_json()
        assert corpo == {"assunto": "uma pergunta", "corpo": "Oi", "provedor": "claude"}

    def test_senha_smtp_vai_para_o_cofre(self, cliente, banco):
        r = cliente.post("/api/email/config", json={"host": "smtp.x.com", "porta": 587, "usuario": "eu@x.com",
                                                      "senha": "segredo123", "limite_diario": 15})
        assert r.status_code == 200 and banco["smtp_senha"] == "segredo123"
        config = cliente.get("/api/email/config").get_json()["smtp"]
        assert config["senha_configurada"] and "segredo123" not in str(config)


class TestModeloVisual:
    def test_html_tem_marca_assinatura_e_descadastro(self, banco):
        html = email_modelo.montar_html("Primeiro parágrafo.\n\nSegundo https://exemplo.com", "eu@teste.com")
        assert "cid:logo-es" in html and "Criação de Sites Premium" in html
        assert "descadastrar" in html and 'href="https://exemplo.com"' in html

    def test_texto_do_usuario_e_escapado(self, banco):
        html = email_modelo.montar_html("<script>alert(1)</script>", "eu@teste.com")
        assert "<script>" not in html


class TestPromptsDeIA:
    def test_email_proibe_defeito_de_site_e_estatistica_inventada(self):
        prompt = ia.montar_prompt_email({"empresa": "X", "setor": "energia solar", "fonte": "receita"})
        assert "NUNCA afirme defeito do site" in prompt and "NUNCA invente estatística" in prompt
        assert "não se sabe se tem site" in prompt

    def test_link_do_exemplo_so_a_partir_do_segundo(self, banco):
        db.salvar_config("site_modelo_atual", '{"link": "https://exemplo.netlify.app"}')
        lead = {"empresa": "X", "setor": "obras", "fonte": "site"}
        assert "exemplo.netlify.app" not in ia.montar_prompt_email(lead, 0)
        assert "exemplo.netlify.app" in ia.montar_prompt_email(lead, 1)

    def test_nota_de_conexao_nao_passa_de_300(self, monkeypatch):
        monkeypatch.setattr(ia, "executar_com_fallback", lambda *a, **k: ("palavra " * 80, "gemini", []))
        texto, _, _ = ia.gerar_texto_linkedin_com_fallback({"nome": "Ana"}, "conexao")
        assert len(texto) <= 300


class TestLinkedin:
    CSV = ("First Name,Last Name,Company,Position,URL,Location\n"
           "Ana,Souza,Solar Tech,Diretora,https://www.linkedin.com/in/ana-souza/?trk=x,Campinas\n"
           "Bruno,Lima,Obras SA,Sócio,linkedin.com/in/bruno-lima,Santos\n"
           "Carlos,,Sem Perfil,CEO,https://site-qualquer.com/c,SP\n")

    def test_importa_csv_do_linkedin_em_ingles(self, cliente):
        r = cliente.post("/api/linkedin/importar", json={"csv": self.CSV}).get_json()
        assert r == {"importados": 3, "ignorados": 0}
        leads = cliente.get("/api/linkedin/leads").get_json()["leads"]
        ana = next(l for l in leads if l["nome"] == "Ana Souza")
        assert ana["perfil_url"] == "https://www.linkedin.com/in/ana-souza" and ana["cargo"] == "Diretora"
        assert next(l for l in leads if l["nome"] == "Carlos")["perfil_url"] is None
        assert cliente.post("/api/linkedin/importar", json={"csv": self.CSV}).get_json()["importados"] == 1  # só o sem URL repete

    def test_csv_com_ponto_e_virgula_e_colunas_em_portugues(self, cliente):
        csv_br = "Nome;Cargo;Empresa;Link do perfil\nDaniela;Gerente;Loja Y;https://linkedin.com/in/dani\n"
        assert cliente.post("/api/linkedin/importar", json={"csv": csv_br}).get_json()["importados"] == 1

    def test_arquivo_sem_coluna_de_nome_e_recusado(self, cliente):
        assert cliente.post("/api/linkedin/importar", json={"csv": "foo,bar\n1,2\n"}).status_code == 400

    def test_funil_e_proximo_followup(self, cliente):
        lead_id = cliente.post("/api/linkedin/leads", json={"nome": "Ana", "perfil_url": "linkedin.com/in/ana"}).get_json()["id"]
        cliente.post(f"/api/linkedin/leads/{lead_id}/status", json={"status": "conexao_enviada", "texto": "Oi Ana"})
        cliente.post(f"/api/linkedin/leads/{lead_id}/status", json={"status": "mensagem_enviada", "texto": "Mensagem 1"})
        cliente.post(f"/api/linkedin/leads/{lead_id}/status", json={"status": "mensagem_enviada", "texto": "Mensagem 2"})
        lead = cliente.get("/api/linkedin/leads").get_json()["leads"][0]
        assert lead["status"] == "mensagem_enviada" and lead["follow_ups_enviados"] == 1
        assert lead["ultimo_texto"] == "Mensagem 2" and lead["proximo_followup"]
        assert len(cliente.get(f"/api/linkedin/leads/{lead_id}/historico").get_json()["mensagens"]) == 3

    def test_status_sem_texto_aceito_e_invalido_recusado(self, cliente):
        lead_id = cliente.post("/api/linkedin/leads", json={"nome": "Ana"}).get_json()["id"]
        assert cliente.post(f"/api/linkedin/leads/{lead_id}/status", json={"status": "respondeu"}).status_code == 200
        assert cliente.post(f"/api/linkedin/leads/{lead_id}/status", json={"status": "voando"}).status_code == 400

    def test_gerar_texto(self, cliente, monkeypatch):
        monkeypatch.setattr(ia, "gerar_texto_linkedin_com_fallback", lambda lead, tipo, anterior: ("Oi Ana", "claude", []))
        lead_id = cliente.post("/api/linkedin/leads", json={"nome": "Ana"}).get_json()["id"]
        r = cliente.post(f"/api/linkedin/leads/{lead_id}/gerar", json={"tipo": "conexao"}).get_json()
        assert r == {"texto": "Oi Ana", "provedor": "claude", "limite_caracteres": 300}
        assert cliente.post(f"/api/linkedin/leads/{lead_id}/gerar", json={"tipo": "x"}).status_code == 400


class TestMontagemMime:
    def test_monta_texto_html_imagem_embutida_e_anexo(self, banco, monkeypatch, tmp_path):
        import smtplib
        capturado = {}

        class SmtpFalso:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def starttls(self, **k): pass
            def login(self, u, s): capturado["login"] = (u, s)
            def send_message(self, mensagem): capturado["mensagem"] = mensagem

        monkeypatch.setattr(smtplib, "SMTP", SmtpFalso)
        db.salvar_config("smtp_host", "smtp.teste")
        db.salvar_config("smtp_usuario", "eu@teste.com")
        db.salvar_config("smtp_senha", "segredo")
        pdf = tmp_path / "proposta.pdf"
        pdf.write_bytes(b"%PDF-1.4 teste")
        imagens = email_modelo.imagens_inline()
        assert imagens, "logos de assets/email precisam existir"
        mensageiros.enviar_email("cliente@empresa.com.br", "assunto", "texto simples",
                                 html=email_modelo.montar_html("Olá", "eu@teste.com"),
                                 imagens=imagens, anexos=[str(pdf)])
        msg = capturado["mensagem"]
        tipos = [p.get_content_type() for p in msg.walk()]
        assert "text/plain" in tipos and "text/html" in tipos and "image/png" in tipos and "application/pdf" in tipos
        assert msg["List-Unsubscribe"].startswith("<mailto:eu@teste.com") and msg["To"] == "cliente@empresa.com.br"
        assert capturado["login"] == ("eu@teste.com", "segredo")


class TestSenhaGmail:
    def test_recusa_senha_que_nao_e_de_app(self, cliente, banco):
        r = cliente.post("/api/email/config", json={"host": "smtp.gmail.com", "porta": 465, "usuario": "eu@gmail.com",
                                                      "senha": "x" * 64})
        assert r.status_code == 400 and "16 letras" in r.get_json()["erro"] and "smtp_senha" not in banco

    def test_aceita_senha_de_app_com_espacos_e_guarda_sem_eles(self, cliente, banco):
        r = cliente.post("/api/email/config", json={"host": "smtp.gmail.com", "porta": 465, "usuario": "eu@gmail.com",
                                                      "senha": "abcd efgh ijkl mnop"})
        assert r.status_code == 200 and banco["smtp_senha"] == "abcdefghijklmnop"

    def test_servidor_que_fecha_a_conexao_vira_mensagem_clara(self, banco, monkeypatch):
        import smtplib

        class SmtpQueCai:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def login(self, u, s): raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")

        monkeypatch.setattr(smtplib, "SMTP_SSL", SmtpQueCai)
        db.salvar_config("smtp_host", "smtp.gmail.com")
        db.salvar_config("smtp_porta", "465")
        db.salvar_config("smtp_usuario", "eu@gmail.com")
        db.salvar_config("smtp_senha", "errada")
        with pytest.raises(mensageiros.ErroEnvio, match="senha de app de 16 letras"):
            mensageiros.enviar_email("a@b.com", "x", "y")
