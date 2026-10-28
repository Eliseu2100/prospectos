"""Testes do envio direto (WhatsApp via Evolution API, Telegram via bot) e da
escolha do modelo do Gemini.

Nada aqui toca rede: `requests` é substituído por monkeypatch e o cofre de
credenciais por um dict em memória.
"""

import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module
import db
import ia
import mensageiros
import processar


@pytest.fixture
def banco(tmp_path, monkeypatch):
    caminho = tmp_path / "leads_teste.db"
    monkeypatch.setattr(db, "CAMINHO_BANCO", caminho)
    cofre = {}
    monkeypatch.setattr(db, "_keyring_obter", cofre.get)
    monkeypatch.setattr(db, "_keyring_salvar", lambda c, v: cofre.update({c: v}) or True)
    monkeypatch.setattr(db, "_keyring_apagar", lambda c: cofre.pop(c, None))
    for variavel in db.CHAVES_ENV_ENVIO.values():
        monkeypatch.delenv(variavel, raising=False)
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
def evolution_configurada(banco):
    db.salvar_config("evolution_url", "http://localhost:8080")
    db.salvar_config("evolution_api_key", "chave-secreta")
    db.salvar_config("evolution_instancia", "prospectos")


class RespostaFalsa:
    def __init__(self, status_code=200, dados=None):
        self.status_code = status_code
        self._dados = dados if dados is not None else {}

    def json(self):
        return self._dados


@pytest.fixture
def http(monkeypatch):
    """Grava as chamadas HTTP e devolve a resposta configurada em `http.resposta`."""
    class Gravador:
        chamadas = []
        resposta = RespostaFalsa(201, {"key": {"id": "MSG123"}})

        def __call__(self, metodo, url, json=None, headers=None, timeout=None):
            self.chamadas.append({"metodo": metodo, "url": url, "json": json, "headers": headers})
            return self.resposta

    gravador = Gravador()
    gravador.chamadas = []
    monkeypatch.setattr(mensageiros.requests, "request", gravador)
    monkeypatch.setattr(mensageiros.requests, "post",
                        lambda url, json=None, timeout=None: gravador("POST", url, json))
    return gravador


def criar_lead(place_id="place-1", telefone="65996757327", status="novo"):
    conexao = db.conectar()
    try:
        conexao.execute(
            "INSERT INTO leads (place_id, nome, telefone, whatsapp_link, status, visto_em, atualizado_em) "
            "VALUES (?, 'Estética Vitá', ?, ?, ?, '2026-07-01', '2026-07-01')",
            (place_id, telefone, f"https://wa.me/55{telefone}", status),
        )
        conexao.commit()
    finally:
        conexao.close()
    return place_id


class TestNumeroInternacional:
    def test_adiciona_ddi(self):
        assert mensageiros.numero_internacional("(65) 99675-7327") == "5565996757327"

    def test_mantem_ddi_existente(self):
        assert mensageiros.numero_internacional("5565996757327") == "5565996757327"

    def test_ddd_55_nao_e_confundido_com_ddi(self):
        assert mensageiros.numero_internacional("55999998888") == "5555999998888"

    def test_link_wa_me(self):
        assert mensageiros.numero_internacional("https://wa.me/5565996757327") == "5565996757327"

    def test_vazio(self):
        assert mensageiros.numero_internacional("") is None


class TestEnvioWhatsapp:
    def test_sem_configuracao_avisa(self, cliente, http):
        criar_lead()
        resposta = cliente.post("/api/envio/whatsapp/maps/place-1", json={"texto": "Oi"})
        assert resposta.status_code == 502
        assert "não configurado" in resposta.get_json()["erro"]
        assert http.chamadas == []

    def test_envia_registra_historico_e_marca_contatado(self, cliente, http, evolution_configurada):
        criar_lead()
        resposta = cliente.post("/api/envio/whatsapp/maps/place-1", json={"texto": "Oi, tudo bem?"})
        assert resposta.status_code == 200
        corpo = resposta.get_json()
        assert corpo["status_novo"] == "contatado"
        assert corpo["enviados_hoje"] == 1

        chamada = http.chamadas[0]
        assert chamada["url"] == "http://localhost:8080/message/sendText/prospectos"
        assert chamada["json"] == {"number": "5565996757327", "text": "Oi, tudo bem?"}
        assert chamada["headers"] == {"apikey": "chave-secreta"}

        conexao = db.conectar()
        try:
            lead = conexao.execute("SELECT status FROM leads WHERE place_id = 'place-1'").fetchone()
            msg = conexao.execute("SELECT autor, origem, chave_dedup FROM mensagens_conversa").fetchone()
            historico = conexao.execute("SELECT status_novo FROM historico_status").fetchone()
        finally:
            conexao.close()
        assert lead["status"] == "contatado"
        assert dict(msg) == {"autor": "vendedor", "origem": "app", "chave_dedup": "wa:MSG123"}
        assert historico["status_novo"] == "contatado"

    def test_nao_rebaixa_status_avancado(self, cliente, http, evolution_configurada):
        criar_lead(status="respondeu")
        resposta = cliente.post("/api/envio/whatsapp/maps/place-1", json={"texto": "Oi"})
        assert resposta.get_json()["status_novo"] is None

    def test_respeita_limite_diario(self, cliente, http, evolution_configurada):
        criar_lead()
        db.salvar_config("whatsapp_limite_diario", "1")
        assert cliente.post("/api/envio/whatsapp/maps/place-1", json={"texto": "1"}).status_code == 200
        resposta = cliente.post("/api/envio/whatsapp/maps/place-1", json={"texto": "2"})
        assert resposta.status_code == 429
        assert len(http.chamadas) == 1

    def test_texto_vazio(self, cliente, http, evolution_configurada):
        criar_lead()
        assert cliente.post("/api/envio/whatsapp/maps/place-1", json={"texto": "  "}).status_code == 400

    def test_lead_inexistente(self, cliente, http, evolution_configurada):
        assert cliente.post("/api/envio/whatsapp/maps/nao-existe", json={"texto": "Oi"}).status_code == 404

    def test_erro_da_evolution_nao_grava_historico(self, cliente, http, evolution_configurada):
        criar_lead()
        http.resposta = RespostaFalsa(400, {"response": {"message": [{"exists": False}]}})
        resposta = cliente.post("/api/envio/whatsapp/maps/place-1", json={"texto": "Oi"})
        assert resposta.status_code == 502
        assert "não tem WhatsApp" in resposta.get_json()["erro"]
        conexao = db.conectar()
        try:
            assert conexao.execute("SELECT COUNT(*) FROM mensagens_conversa").fetchone()[0] == 0
        finally:
            conexao.close()


class TestConexaoWhatsapp:
    def test_estado_indisponivel_sem_config(self, cliente):
        assert cliente.get("/api/envio/whatsapp/estado").get_json()["estado"] == "indisponivel"

    def test_estado_conectado(self, cliente, http, evolution_configurada):
        http.resposta = RespostaFalsa(200, {"instance": {"instanceName": "prospectos", "state": "open"}})
        assert cliente.get("/api/envio/whatsapp/estado").get_json()["estado"] == "open"

    def test_conectar_devolve_qrcode(self, cliente, http, evolution_configurada):
        http.resposta = RespostaFalsa(200, {"instance": {"state": "close"}, "base64": "data:image/png;base64,AAA"})
        corpo = cliente.post("/api/envio/whatsapp/conectar").get_json()
        assert corpo == {"conectado": False, "qrcode": "data:image/png;base64,AAA"}


class TestConfigEnvio:
    def test_chave_evolution_vai_pro_cofre(self, cliente, banco):
        resposta = cliente.post("/api/envio/config/whatsapp", json={
            "url": "http://localhost:8080/", "instancia": "minha-loja", "chave": "abc12345",
            "limite_diario": 20,
        })
        assert resposta.status_code == 200
        assert banco["evolution_api_key"] == "abc12345"
        config = cliente.get("/api/envio/config").get_json()["whatsapp"]
        assert config["url"] == "http://localhost:8080"
        assert config["instancia"] == "minha-loja"
        assert config["limite_diario"] == 20
        assert config["chave_mascarada"].endswith("2345")

    def test_url_invalida(self, cliente):
        resposta = cliente.post("/api/envio/config/whatsapp", json={"url": "localhost", "instancia": "x"})
        assert resposta.status_code == 400

    def test_limite_fora_da_faixa(self, cliente):
        resposta = cliente.post("/api/envio/config/whatsapp", json={
            "url": "http://localhost:8080", "instancia": "x", "limite_diario": 999})
        assert resposta.status_code == 400

    def test_modelo_gemini(self, cliente):
        assert ia.modelo_gemini() == ia.MODELO_GEMINI_PADRAO
        assert cliente.post("/api/envio/config/gemini-modelo", json={"modelo": "gemini-pro-latest"}).status_code == 200
        assert ia.modelo_gemini() == "gemini-pro-latest"
        assert cliente.post("/api/envio/config/gemini-modelo", json={"modelo": "gpt-4"}).status_code == 400


class TestTelegram:
    def test_detectar_chat(self, cliente, http, banco):
        db.salvar_config("telegram_bot_token", "123:abc")
        http.resposta = RespostaFalsa(200, {"ok": True, "result": [
            {"message": {"chat": {"id": 111, "first_name": "Antigo"}}},
            {"message": {"chat": {"id": 222, "first_name": "Eliseu"}}},
        ]})
        corpo = cliente.post("/api/envio/telegram/detectar-chat").get_json()
        assert corpo == {"ok": True, "chat_id": "222", "nome": "Eliseu"}
        assert db.obter_config("telegram_chat_id") == "222"

    def test_detectar_sem_mensagens(self, cliente, http, banco):
        db.salvar_config("telegram_bot_token", "123:abc")
        http.resposta = RespostaFalsa(200, {"ok": True, "result": []})
        assert cliente.post("/api/envio/telegram/detectar-chat").status_code == 400

    def test_resumo_envia_para_o_chat(self, cliente, http, banco):
        db.salvar_config("telegram_bot_token", "123:abc")
        db.salvar_config("telegram_chat_id", "222")
        criar_lead()
        conexao = db.conectar()
        try:
            conexao.execute("UPDATE leads SET proximo_followup = ?", (date.today().isoformat(),))
            conexao.commit()
        finally:
            conexao.close()
        http.resposta = RespostaFalsa(200, {"ok": True, "result": {}})

        assert cliente.post("/api/envio/telegram/resumo").status_code == 200
        chamada = http.chamadas[0]
        assert chamada["url"] == "https://api.telegram.org/bot123:abc/sendMessage"
        assert chamada["json"]["chat_id"] == "222"
        assert "Estética Vitá" in chamada["json"]["text"]

    def test_sem_token(self, cliente, http):
        resposta = cliente.post("/api/envio/telegram/teste")
        assert resposta.status_code == 400
        assert "@BotFather" in resposta.get_json()["erro"]


# ---------------------------------------------------------------------------
# Sincronização das conversas do WhatsApp e caixa de entrada
# ---------------------------------------------------------------------------

import sincronizacao_whatsapp


def registro_wa(id_msg, texto, from_me=False, ts=1793150000, jid="5565996757327@s.whatsapp.net"):
    return {"key": {"id": id_msg, "fromMe": from_me, "remoteJid": jid},
            "messageType": "conversation", "message": {"conversation": texto},
            "messageTimestamp": ts}


@pytest.fixture
def evolution_com_mensagens(monkeypatch, evolution_configurada):
    """Substitui a busca da Evolution por um dict jid -> registros."""
    conversas = {}
    consultados = []

    def buscar(jid, limite=100):
        consultados.append(jid)
        return conversas.get(jid, [])

    monkeypatch.setattr(sincronizacao_whatsapp.mensageiros, "buscar_mensagens", buscar)
    return conversas, consultados


class TestTextoDaMensagem:
    def test_texto_simples(self):
        assert sincronizacao_whatsapp.texto_da_mensagem(registro_wa("1", "Oi")) == "Oi"

    def test_texto_estendido(self):
        reg = {"message": {"extendedTextMessage": {"text": "Com link"}}}
        assert sincronizacao_whatsapp.texto_da_mensagem(reg) == "Com link"

    def test_imagem_com_legenda(self):
        reg = {"message": {"imageMessage": {"caption": "cardápio"}}}
        assert sincronizacao_whatsapp.texto_da_mensagem(reg) == "[📷 Imagem] cardápio"

    def test_audio(self):
        assert sincronizacao_whatsapp.texto_da_mensagem({"message": {"audioMessage": {}}}) == "[🎤 Áudio]"

    def test_evento_tecnico_e_ignorado(self):
        reg = {"messageType": "reactionMessage", "message": {"reactionMessage": {}}}
        assert sincronizacao_whatsapp.texto_da_mensagem(reg) is None


class TestSincronizacao:
    def test_resposta_do_lead_entra_no_historico_e_marca_respondeu(self, cliente, evolution_com_mensagens):
        conversas, consultados = evolution_com_mensagens
        criar_lead(status="contatado")
        conversas["5565996757327@s.whatsapp.net"] = [
            registro_wa("B", "Tenho interesse sim!", ts=1793150100),
            registro_wa("A", "Oi, tudo bem?", from_me=True, ts=1793150000),
        ]

        corpo = cliente.post("/api/envio/whatsapp/sincronizar").get_json()
        assert corpo["novas"] == 2
        # consulta com e sem o 9º dígito
        assert "556596757327@s.whatsapp.net" in consultados

        conexao = db.conectar()
        try:
            status = conexao.execute("SELECT status FROM leads").fetchone()["status"]
            msgs = conexao.execute(
                "SELECT autor, texto, origem FROM mensagens_conversa ORDER BY enviada_em").fetchall()
        finally:
            conexao.close()
        assert status == "respondeu"
        assert [tuple(m) for m in msgs] == [
            ("vendedor", "Oi, tudo bem?", "whatsapp"),
            ("lead", "Tenho interesse sim!", "whatsapp"),
        ]

    def test_rodar_duas_vezes_nao_duplica(self, cliente, evolution_com_mensagens):
        conversas, _ = evolution_com_mensagens
        criar_lead(status="contatado")
        conversas["5565996757327@s.whatsapp.net"] = [registro_wa("A", "Oi")]
        assert cliente.post("/api/envio/whatsapp/sincronizar").get_json()["novas"] == 1
        assert cliente.post("/api/envio/whatsapp/sincronizar").get_json()["novas"] == 0

    def test_mensagem_enviada_pelo_app_nao_duplica(self, cliente, http, evolution_com_mensagens):
        conversas, _ = evolution_com_mensagens
        criar_lead()
        cliente.post("/api/envio/whatsapp/maps/place-1", json={"texto": "Oi"})  # id MSG123
        conversas["5565996757327@s.whatsapp.net"] = [registro_wa("MSG123", "Oi", from_me=True)]
        assert cliente.post("/api/envio/whatsapp/sincronizar").get_json()["novas"] == 0

    def test_usa_jid_lid_salvo_no_envio(self, cliente, http, evolution_com_mensagens):
        conversas, consultados = evolution_com_mensagens
        criar_lead()
        http.resposta = RespostaFalsa(201, {"key": {"id": "X1", "remoteJid": "999@lid"}})
        cliente.post("/api/envio/whatsapp/maps/place-1", json={"texto": "Oi"})
        conversas["999@lid"] = [registro_wa("R1", "Opa, pode falar", jid="999@lid")]

        assert cliente.post("/api/envio/whatsapp/sincronizar/maps/place-1").get_json()["novas"] == 1
        assert "999@lid" in consultados

    def test_lead_novo_sem_mensagens_nao_e_consultado(self, cliente, evolution_com_mensagens):
        _, consultados = evolution_com_mensagens
        criar_lead(status="novo")
        cliente.post("/api/envio/whatsapp/sincronizar")
        assert consultados == []

    def test_status_avancado_nao_volta_para_respondeu(self, cliente, evolution_com_mensagens):
        conversas, _ = evolution_com_mensagens
        criar_lead(status="fechou")
        conversas["5565996757327@s.whatsapp.net"] = [registro_wa("A", "Obrigado!")]
        cliente.post("/api/envio/whatsapp/sincronizar")
        conexao = db.conectar()
        try:
            assert conexao.execute("SELECT status FROM leads").fetchone()["status"] == "fechou"
        finally:
            conexao.close()


class TestCaixaDeEntrada:
    def test_separa_quem_aguarda_resposta(self, cliente, evolution_com_mensagens):
        conversas, _ = evolution_com_mensagens
        criar_lead("p1", "65996757327", status="contatado")
        criar_lead("p2", "11988887777", status="contatado")
        conversas["5565996757327@s.whatsapp.net"] = [
            registro_wa("2", "Quanto custa?", ts=1793150100),
            registro_wa("1", "Oi", from_me=True, ts=1793150000),
        ]
        conversas["5511988887777@s.whatsapp.net"] = [
            registro_wa("3", "Oi", from_me=True, ts=1793150200, jid="5511988887777@s.whatsapp.net"),
        ]
        cliente.post("/api/envio/whatsapp/sincronizar")

        conversas_caixa = cliente.get("/api/envio/whatsapp/caixa").get_json()["conversas"]
        por_lead = {c["place_id"]: c for c in conversas_caixa}
        assert por_lead["p1"]["aguardando_voce"] is True
        assert por_lead["p1"]["ultimo_texto"] == "Quanto custa?"
        assert por_lead["p1"]["status"] == "respondeu"
        assert por_lead["p2"]["aguardando_voce"] is False
        assert por_lead["p2"]["ja_respondeu"] is False
        # mais recente primeiro
        assert [c["place_id"] for c in conversas_caixa] == ["p2", "p1"]
