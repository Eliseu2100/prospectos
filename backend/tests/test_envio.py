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
    """Substitui a busca da Evolution por um dict jid -> registros. Conversas
    endereçadas por @lid ficam em conversas[("alt", <jid do telefone>)] e só
    aparecem na consulta por remoteJidAlt - igual à Evolution real."""
    conversas = {}
    consultados = []

    def buscar(jid, limite=100, campo="remoteJid"):
        if campo == "remoteJidAlt":
            return conversas.get(("alt", jid), [])
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

    def test_resposta_por_lid_e_encontrada_e_o_lid_fica_salvo(self, cliente, evolution_com_mensagens):
        """O caso real de 28/10: o cliente responde e o WhatsApp entrega com
        remoteJid=<código>@lid; o telefone só vem em remoteJidAlt."""
        conversas, consultados = evolution_com_mensagens
        criar_lead(status="contatado")
        conversas[("alt", "5565996757327@s.whatsapp.net")] = [
            registro_wa("R1", "Oi, tenho interesse", jid="777@lid"),
        ]
        assert cliente.post("/api/envio/whatsapp/sincronizar").get_json()["novas"] == 1
        conexao = db.conectar()
        try:
            lead = conexao.execute("SELECT status, whatsapp_jid FROM leads").fetchone()
        finally:
            conexao.close()
        assert lead["status"] == "respondeu"
        assert lead["whatsapp_jid"] == "777@lid"
        # próxima rodada consulta o @lid direto
        cliente.post("/api/envio/whatsapp/sincronizar")
        assert "777@lid" in consultados

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


# ---------------------------------------------------------------------------
# Avisos para o vendedor (Telegram e/ou WhatsApp)
# ---------------------------------------------------------------------------

class TestAvisos:
    def test_avisa_por_whatsapp_no_numero_configurado(self, cliente, http, evolution_configurada):
        resposta = cliente.post("/api/envio/config/avisos", json={"whatsapp_numero": "(11) 91234-5678"})
        assert resposta.get_json()["whatsapp_numero"] == "5511912345678"
        assert mensageiros.avisar_vendedor("oi") == ["whatsapp"]
        assert http.chamadas[-1]["json"] == {"number": "5511912345678", "text": "oi"}

    def test_detecta_mesmo_numero_conectado(self, cliente, http, evolution_configurada, monkeypatch):
        monkeypatch.setattr(mensageiros, "numero_conectado", lambda: "5511912345678")
        resposta = cliente.post("/api/envio/config/avisos", json={"whatsapp_numero": "11912345678"})
        assert resposta.get_json()["mesmo_numero_conectado"] is True

    def test_numero_invalido(self, cliente):
        assert cliente.post("/api/envio/config/avisos", json={"whatsapp_numero": "123"}).status_code == 400

    def test_sem_canal_o_teste_avisa(self, cliente):
        assert cliente.post("/api/envio/aviso/teste").status_code == 400

    def test_falha_no_aviso_nao_levanta(self, banco, monkeypatch):
        db.salvar_config("aviso_whatsapp_numero", "5511912345678")
        monkeypatch.setattr(mensageiros, "enviar_whatsapp",
                            lambda *a: (_ for _ in ()).throw(mensageiros.ErroEnvio("fora do ar")))
        assert mensageiros.avisar_vendedor("oi") == []


class TestAvisoDeResposta:
    def _lead_com_resposta(self, conversas, minutos_atras, piloto_status=None):
        from datetime import datetime, timedelta
        criar_lead(status="contatado")
        if piloto_status:
            conexao = db.conectar()
            try:
                conexao.execute("UPDATE leads SET piloto_status = ?", (piloto_status,))
                conexao.commit()
            finally:
                conexao.close()
        ts = int((datetime.now() - timedelta(minutes=minutos_atras)).timestamp())
        conversas["5565996757327@s.whatsapp.net"] = [registro_wa("R", "Quanto custa?", ts=ts)]

    def test_lead_com_voce_respondeu_agora_avisa(self, cliente, evolution_com_mensagens, monkeypatch):
        avisos = []
        monkeypatch.setattr(mensageiros, "avisar_vendedor", avisos.append)
        conversas, _ = evolution_com_mensagens
        self._lead_com_resposta(conversas, minutos_atras=2)
        cliente.post("/api/envio/whatsapp/sincronizar")
        assert len(avisos) == 1 and "Quanto custa?" in avisos[0] and "Estética Vitá" in avisos[0]

    def test_historico_antigo_nao_avisa(self, cliente, evolution_com_mensagens, monkeypatch):
        avisos = []
        monkeypatch.setattr(mensageiros, "avisar_vendedor", avisos.append)
        conversas, _ = evolution_com_mensagens
        self._lead_com_resposta(conversas, minutos_atras=600)
        cliente.post("/api/envio/whatsapp/sincronizar")
        assert avisos == []

    def test_lead_com_o_piloto_nao_avisa_aqui(self, cliente, evolution_com_mensagens, monkeypatch):
        avisos = []
        monkeypatch.setattr(mensageiros, "avisar_vendedor", avisos.append)
        conversas, _ = evolution_com_mensagens
        self._lead_com_resposta(conversas, minutos_atras=2, piloto_status="automatico")
        cliente.post("/api/envio/whatsapp/sincronizar")
        assert avisos == []  # o piloto responde; só avisa se passar pra você


# ---------------------------------------------------------------------------
# "Testar tudo" (diagnostico_sistema.py)
# ---------------------------------------------------------------------------

import diagnostico_sistema


class TestTestarTudo:
    @pytest.fixture
    def evolution_ok(self, monkeypatch, evolution_configurada):
        enviados = []
        monkeypatch.setattr(diagnostico_sistema.time, "sleep", lambda s: None)
        monkeypatch.setattr(mensageiros, "estado_whatsapp", lambda: "open")
        monkeypatch.setattr(mensageiros, "numero_conectado", lambda: "5511912345678")

        def enviar(numero, texto):
            enviados.append((numero, texto))
            return "TESTE1", "5511912345678@s.whatsapp.net"

        monkeypatch.setattr(mensageiros, "enviar_whatsapp", enviar)
        monkeypatch.setattr(mensageiros, "buscar_mensagens",
                            lambda jid, limite=100, campo="remoteJid": [{"key": {"id": "TESTE1", "fromMe": True}}])
        return enviados

    def test_tudo_funcionando(self, cliente, evolution_ok, monkeypatch):
        db.salvar_config("telegram_bot_token", "123:abc")
        db.salvar_config("telegram_chat_id", "999")
        db.salvar_config("gemini", "g")
        monkeypatch.setattr(mensageiros, "enviar_telegram", lambda texto, chat_id=None: None)

        corpo = cliente.post("/api/envio/testar-tudo").get_json()
        assert corpo["ok"] is True
        assert [i["nome"] for i in corpo["itens"]] == [
            "WhatsApp conectado", "Envio pelo CRM", "Leitura das conversas", "Telegram", "Inteligência artificial"]
        # mensagem de teste vai pro PRÓPRIO número, sem lead e sem histórico
        assert evolution_ok[0][0] == "5511912345678"
        conexao = db.conectar()
        try:
            assert conexao.execute("SELECT COUNT(*) FROM mensagens_conversa").fetchone()[0] == 0
        finally:
            conexao.close()

    def test_telegram_bloqueado_aparece_com_o_motivo(self, cliente, evolution_ok, monkeypatch):
        db.salvar_config("telegram_bot_token", "123:abc")
        db.salvar_config("telegram_chat_id", "999")

        def bloqueado(texto, chat_id=None):
            raise mensageiros.ErroEnvio("Seu computador não consegue alcançar o servidor do Telegram")

        monkeypatch.setattr(mensageiros, "enviar_telegram", bloqueado)
        corpo = cliente.post("/api/envio/testar-tudo").get_json()
        telegram = next(i for i in corpo["itens"] if i["nome"] == "Telegram")
        assert corpo["ok"] is False and telegram["ok"] is False
        assert "alcançar" in telegram["detalhe"]

    def test_whatsapp_desconectado_para_cedo(self, cliente, evolution_configurada, monkeypatch):
        monkeypatch.setattr(mensageiros, "estado_whatsapp", lambda: "close")
        corpo = cliente.post("/api/envio/testar-tudo").get_json()
        assert corpo["itens"][0]["ok"] is False
        assert "QR code" in corpo["itens"][0]["detalhe"]

    def test_mensagem_nao_volta_na_leitura(self, cliente, evolution_ok, monkeypatch):
        monkeypatch.setattr(mensageiros, "buscar_mensagens", lambda jid, limite=100, campo="remoteJid": [])
        corpo = cliente.post("/api/envio/testar-tudo").get_json()
        leitura = next(i for i in corpo["itens"] if i["nome"] == "Leitura das conversas")
        assert leitura["ok"] is False


# ---------------------------------------------------------------------------
# Respostas automáticas do WhatsApp Business (casos reais de 28/10)
# ---------------------------------------------------------------------------

class TestRespostaAutomatica:
    @pytest.mark.parametrize("texto", [
        "Olá! Seja bem-vindo(a) 👋 Somos um estúdio profissional...",
        "🌟 Olá! Aqui é a Talita da Clínica. No momento, estamos ausentes, mas não se preocupe!",
        "Obrigado por escolher a *Clínica Needles* Digite *apenas* seu primeiro *NOME*",
        "Para facilitar seu atendimento, responda com o número do atendimento desejado: 1️⃣ – Psicoterapia",
        "Pele Bella Depilação agradece seu contato. Como podemos ajudar? retornarei",
        "Agradeço sua mensagem. Não estou disponível no momento, responderei assim que possível.",
        "Olá! 🐾 Você entrou em contato com o Hospital Veterinário YOUPETZ. Nosso atendimento é 24 horas!",
        "Um atendente já foi notificado e iniciará o atendimento em instantes.",
    ])
    def test_robos_reais(self, texto):
        assert sincronizacao_whatsapp.e_resposta_automatica(texto, segundos_desde_nossa=5)

    def test_frase_fraca_rapida_e_robo(self):
        assert sincronizacao_whatsapp.e_resposta_automatica(
            "Olá. Para agilizar me fala NOME COMPLETO. Dia e horário melhor para agendamento", 3)
        assert sincronizacao_whatsapp.e_resposta_automatica(
            "Bom dia. Tudo bem? Somos da Clínica NEOCOG. Em que podemos ajudar?", 10)

    def test_frase_fraca_lenta_e_pessoa(self):
        assert not sincronizacao_whatsapp.e_resposta_automatica("Oi, em que podemos ajudar?", 3600)

    @pytest.mark.parametrize("texto", [
        "Envia pra mim", "Já estamos com um site em produção, obrigado", "Nao obrigado",
        "Obrigada Eliseu. Agradeço mas no momento não é viável para mim", "Boa tarde",
        "*Rosa:* Olá, boa tarde. No momento não temos interesse, muito obrigada!",
    ])
    def test_pessoas_reais_mesmo_rapidas(self, texto):
        assert not sincronizacao_whatsapp.e_resposta_automatica(texto, segundos_desde_nossa=40)

    def test_robo_nao_marca_respondeu_nem_avisa(self, cliente, evolution_com_mensagens, monkeypatch):
        avisos = []
        monkeypatch.setattr(mensageiros, "avisar_vendedor", avisos.append)
        conversas, _ = evolution_com_mensagens
        criar_lead(status="contatado")
        conexao = db.conectar()
        try:
            conexao.execute("UPDATE leads SET piloto_status = 'humano'")
            conexao.commit()
        finally:
            conexao.close()
        from datetime import datetime
        ts = int(datetime.now().timestamp())
        conversas["5565996757327@s.whatsapp.net"] = [
            registro_wa("BOT", "Olá! Seja bem-vindo(a)! Responderemos em breve.", ts=ts),
            registro_wa("EU", "Oi, tudo bem?", from_me=True, ts=ts - 3),
        ]
        cliente.post("/api/envio/whatsapp/sincronizar")
        conexao = db.conectar()
        try:
            assert conexao.execute("SELECT status FROM leads").fetchone()["status"] == "contatado"
            assert conexao.execute(
                "SELECT automatica FROM mensagens_conversa WHERE autor = 'lead'").fetchone()[0] == 1
        finally:
            conexao.close()
        assert avisos == []

    def test_reclassificar_devolve_para_contatado(self, banco):
        criar_lead(status="respondeu")
        conexao = db.conectar()
        try:
            for autor, texto, quando in [("vendedor", "Oi!", "2026-10-28T10:00:00"),
                                         ("lead", "Seja bem-vindo(a)! Digite 1", "2026-10-28T10:00:04")]:
                conexao.execute(
                    "INSERT INTO mensagens_conversa (canal, lead_ref, autor, texto, enviada_em, origem, criada_em) "
                    "VALUES ('maps', 'place-1', ?, ?, ?, 'whatsapp', ?)", (autor, texto, quando, quando))
            conexao.commit()
        finally:
            conexao.close()
        assert sincronizacao_whatsapp.reclassificar_respostas_automaticas() == 1
        conexao = db.conectar()
        try:
            assert conexao.execute("SELECT status FROM leads").fetchone()["status"] == "contatado"
        finally:
            conexao.close()


def test_texto_longo_instantaneo_e_robo():
    texto = "Olá, aqui é da recepção, recebemos seu contato e logo alguém fala com você aqui."
    assert sincronizacao_whatsapp.e_resposta_automatica(texto, segundos_desde_nossa=4)
    assert not sincronizacao_whatsapp.e_resposta_automatica(texto, segundos_desde_nossa=300)
