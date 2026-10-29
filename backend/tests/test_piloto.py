"""Testes do piloto automático: escolha dos leads, primeiro contato, respostas
automáticas, opt-out, passagem pro humano e regras de horário.

Nada toca rede: Evolution (mensageiros) e IA são substituídos por monkeypatch,
o cofre de credenciais por um dict.
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module
import db
import ia
import mensageiros
import piloto
import processar
import rotas_leads
import sincronizacao_whatsapp

# segunda-feira, 10h - dentro da janela padrão
SEGUNDA_10H = datetime(2026, 10, 26, 10, 0, 0)


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
    piloto._estado.update({"proximo_contato_em": None, "ultimo_erro": None, "rodando": False})
    return cofre


@pytest.fixture
def cliente(banco):
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture
def whatsapp(monkeypatch, banco):
    """Evolution falsa: grava os envios, devolve as conversas configuradas."""
    class Falso:
        enviados = []
        conversas = {}
        erro_envio = None

    falso = Falso()
    falso.enviados, falso.conversas = [], {}

    def enviar(telefone, texto):
        if falso.erro_envio:
            raise mensageiros.ErroEnvio(falso.erro_envio)
        falso.enviados.append((telefone, texto))
        return f"ID{len(falso.enviados)}", None

    monkeypatch.setattr(mensageiros, "enviar_whatsapp", enviar)
    monkeypatch.setattr(mensageiros, "estado_whatsapp", lambda: "open")
    monkeypatch.setattr(mensageiros, "buscar_mensagens", lambda jid, limite=100, campo="remoteJid": falso.conversas.get(jid if campo == "remoteJid" else ("alt", jid), []))
    monkeypatch.setattr(mensageiros, "enviar_telegram", lambda texto, chat_id=None: None)
    return falso


@pytest.fixture
def ia_falsa(monkeypatch):
    """Copy fixa e decisão configurável."""
    estado = {"decisao": {"acao": "responder", "motivo": "pergunta simples", "resposta": "Claro! Te mando uma prévia hoje."}}
    def copy(conexao, lead, tipo="contato", mensagens_anteriores=None):
        estado["mensagens_anteriores"] = mensagens_anteriores
        texto = f"Bom dia {lead['nome']}!" if tipo == "contato" else f"Follow-up {lead['nome']}"
        return texto, "gemini", []

    monkeypatch.setattr(rotas_leads, "gerar_copy_para_lead", copy)
    monkeypatch.setattr(ia, "decidir_resposta_piloto",
                        lambda lead, mensagens, info=None: (estado["decisao"], "gemini", []))
    return estado


def criar_lead(place_id, nome="Clínica", telefone="65996757327", nota=4.9, avaliacoes=100,
               nicho="clínica", cidade="Cuiabá", status="novo", site_status="sem_site"):
    conexao = db.conectar()
    try:
        conexao.execute(
            "INSERT INTO leads (place_id, nome, telefone, nota, num_avaliacoes, nicho, cidade, status, "
            "site_status, visto_em, atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-10-01', '2026-10-01')",
            (place_id, nome, telefone, nota, avaliacoes, nicho, cidade, status, site_status),
        )
        conexao.commit()
    finally:
        conexao.close()


def lead(place_id):
    conexao = db.conectar()
    try:
        return dict(conexao.execute("SELECT * FROM leads WHERE place_id = ?", (place_id,)).fetchone())
    finally:
        conexao.close()


def ligar(**extra):
    db.salvar_config("piloto_ativo", "1")
    for chave, valor in extra.items():
        db.salvar_config(chave, str(valor))


class TestHorario:
    def test_dentro_da_janela(self):
        assert piloto.dentro_do_horario(piloto.CONFIG_PADRAO, SEGUNDA_10H)

    def test_fora_da_janela(self):
        assert not piloto.dentro_do_horario(piloto.CONFIG_PADRAO, SEGUNDA_10H.replace(hour=20))

    def test_fim_de_semana_bloqueado_por_padrao(self):
        sabado = SEGUNDA_10H + timedelta(days=5)
        assert not piloto.dentro_do_horario(piloto.CONFIG_PADRAO, sabado)
        assert piloto.dentro_do_horario({**piloto.CONFIG_PADRAO, "piloto_fim_de_semana": "1"}, sabado)


class TestFila:
    def test_ordena_por_score_e_filtra_area(self, banco):
        criar_lead("fraco", nota=4.0, avaliacoes=2)
        criar_lead("forte", nota=5.0, avaliacoes=200)
        criar_lead("outra-cidade", nota=5.0, avaliacoes=200, cidade="Curitiba")
        criar_lead("sem-telefone", telefone="")
        criar_lead("ja-contatado", status="contatado")
        conexao = db.conectar()
        try:
            fila = piloto.proximos_leads(conexao, {**piloto.CONFIG_PADRAO, "piloto_cidade": "cuiab"})
        finally:
            conexao.close()
        assert [l["place_id"] for l in fila] == ["forte", "fraco"]

    def test_so_chama_quem_nao_tem_site(self, banco):
        criar_lead("sem", site_status="sem_site")
        criar_lead("ruim", site_status="site_ruim", nota=5.0, avaliacoes=500)
        conexao = db.conectar()
        try:
            assert [l["place_id"] for l in piloto.proximos_leads(conexao, piloto.CONFIG_PADRAO)] == ["sem"]
        finally:
            conexao.close()

    def test_score_minimo(self, banco):
        criar_lead("fraco", nota=4.0, avaliacoes=2, site_status="site_ok")
        conexao = db.conectar()
        try:
            assert piloto.proximos_leads(conexao, {**piloto.CONFIG_PADRAO, "piloto_score_min": "50"}) == []
        finally:
            conexao.close()


class TestPrimeiroContato:
    def test_envia_para_o_melhor_e_marca_automatico(self, whatsapp, ia_falsa):
        criar_lead("a", nome="Clínica A", nota=4.2)
        criar_lead("b", nome="Clínica B", nota=5.0)
        ligar()
        piloto.rodar_uma_vez(SEGUNDA_10H)

        assert len(whatsapp.enviados) == 1
        assert whatsapp.enviados[0][1].startswith("Bom dia Clínica B") or "Clínica B" in whatsapp.enviados[0][1]
        b = lead("b")
        assert b["piloto_status"] == "automatico"
        assert b["status"] == "contatado"
        assert lead("a")["piloto_status"] is None
        assert piloto._estado["proximo_contato_em"] is not None

    def test_respeita_intervalo(self, whatsapp, ia_falsa):
        criar_lead("a")
        criar_lead("b")
        ligar()
        piloto.rodar_uma_vez(SEGUNDA_10H)
        piloto.rodar_uma_vez(SEGUNDA_10H + timedelta(seconds=30))
        assert len(whatsapp.enviados) == 1
        piloto.rodar_uma_vez(SEGUNDA_10H + timedelta(minutes=10))
        assert len(whatsapp.enviados) == 2

    def test_desligado_nao_envia(self, whatsapp, ia_falsa):
        criar_lead("a")
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert whatsapp.enviados == []

    def test_fora_do_horario_nao_envia(self, whatsapp, ia_falsa):
        criar_lead("a")
        ligar()
        piloto.rodar_uma_vez(SEGUNDA_10H.replace(hour=22))
        assert whatsapp.enviados == []

    def test_respeita_limite_diario(self, whatsapp, ia_falsa):
        criar_lead("a")
        criar_lead("b")
        ligar(whatsapp_limite_diario=1)
        piloto.fazer_primeiro_contato(piloto.config())
        assert piloto.fazer_primeiro_contato(piloto.config()) is None
        assert len(whatsapp.enviados) == 1

    def test_numero_sem_whatsapp_sai_da_fila(self, whatsapp, ia_falsa):
        criar_lead("a")
        whatsapp.erro_envio = "Esse número não tem WhatsApp."
        assert piloto.fazer_primeiro_contato(piloto.config()) is None
        assert lead("a")["piloto_status"] == "sem_whatsapp"

    def test_falha_passageira_devolve_para_fila(self, whatsapp, ia_falsa):
        criar_lead("a")
        whatsapp.erro_envio = "Não consegui falar com a Evolution API."
        with pytest.raises(mensageiros.ErroEnvio):
            piloto.fazer_primeiro_contato(piloto.config())
        assert lead("a")["piloto_status"] is None


def preparar_conversa_respondida(whatsapp, texto_lead, minutos_atras=5):
    """Lead conduzido pelo piloto que acabou de responder."""
    criar_lead("a", nome="Clínica A", status="contatado")
    ts = int((SEGUNDA_10H - timedelta(minutes=minutos_atras)).timestamp())
    conexao = db.conectar()
    try:
        conexao.execute("UPDATE leads SET piloto_status = 'automatico'")
        # o "Oi!" foi o primeiro contato do próprio piloto (mesma chave wa:<id>)
        conexao.execute(
            "INSERT INTO mensagens_conversa (canal, lead_ref, autor, texto, enviada_em, origem, chave_dedup, criada_em) "
            "VALUES ('maps', 'a', 'vendedor', 'Oi!', ?, 'app', 'wa:V1', ?)",
            (datetime.fromtimestamp(ts - 600).isoformat(), datetime.now().isoformat()),
        )
        conexao.commit()
    finally:
        conexao.close()
    whatsapp.conversas["5565996757327@s.whatsapp.net"] = [
        {"key": {"id": "L1", "fromMe": False}, "message": {"conversation": texto_lead}, "messageTimestamp": ts},
        {"key": {"id": "V1", "fromMe": True}, "message": {"conversation": "Oi!"}, "messageTimestamp": ts - 600},
    ]


class TestRespostas:
    def test_responde_pergunta_simples(self, whatsapp, ia_falsa):
        preparar_conversa_respondida(whatsapp, "Como funciona?")
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert whatsapp.enviados == [("65996757327", "Claro! Te mando uma prévia hoje.")]
        a = lead("a")
        assert a["piloto_respostas"] == 1
        assert a["status"] == "respondeu"
        # na próxima volta a última mensagem já é sua: não responde de novo
        piloto.rodar_uma_vez(SEGUNDA_10H + timedelta(seconds=30))
        assert len(whatsapp.enviados) == 1

    def test_espera_antes_de_responder(self, whatsapp, ia_falsa):
        preparar_conversa_respondida(whatsapp, "Como funciona?", minutos_atras=0)
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert whatsapp.enviados == []

    def test_opt_out_despede_e_encerra_sem_ia(self, whatsapp, ia_falsa, monkeypatch):
        monkeypatch.setattr(ia, "decidir_resposta_piloto", lambda *a, **k: pytest.fail("não deve chamar IA"))
        preparar_conversa_respondida(whatsapp, "Não tenho interesse, obrigado")
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert whatsapp.enviados == [("65996757327", piloto.DESPEDIDA_OPT_OUT)]
        a = lead("a")
        assert a["piloto_status"] == "encerrado"
        assert a["status"] == "recusou"

    def test_preco_passa_para_voce(self, whatsapp, ia_falsa):
        ia_falsa["decisao"] = {"acao": "passar_para_humano", "motivo": "Pediu preço", "resposta": ""}
        preparar_conversa_respondida(whatsapp, "Quanto custa?")
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert whatsapp.enviados == []
        assert lead("a")["piloto_status"] == "humano"

    def test_combinar_previa_vira_tarefa_e_passa_para_voce(self, whatsapp, ia_falsa, monkeypatch, cliente):
        from datetime import date
        monkeypatch.setattr(ia, "proximo_dia_util", lambda hoje=None: (date(2026, 10, 27), "amanhã"))
        ia_falsa["decisao"] = {"acao": "combinar_previa", "motivo": "Quer ver",
                               "resposta": "Combinado! Amanhã te mando a prévia. Tem logo?"}
        preparar_conversa_respondida(whatsapp, "Quero ver como ficaria sim")
        piloto.rodar_uma_vez(SEGUNDA_10H)

        assert whatsapp.enviados == [("65996757327", "Combinado! Amanhã te mando a prévia. Tem logo?")]
        a = lead("a")
        assert a["piloto_status"] == "humano"
        assert "prévia" in a["tags"]
        assert a["proximo_followup"] == "2026-10-27"
        painel = cliente.get("/api/piloto").get_json()
        assert [p["nome"] for p in painel["previas"]] == ["Clínica A"]
        assert painel["eventos"][0]["tipo"] == "previa_combinada"

    def test_limite_de_respostas_seguidas(self, whatsapp, ia_falsa):
        preparar_conversa_respondida(whatsapp, "E aí?")
        conexao = db.conectar()
        try:
            conexao.execute("UPDATE leads SET piloto_respostas = 4")
            conexao.commit()
        finally:
            conexao.close()
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert whatsapp.enviados == []
        assert lead("a")["piloto_status"] == "humano"

    def test_lead_com_voce_nao_recebe_resposta_automatica(self, whatsapp, ia_falsa):
        preparar_conversa_respondida(whatsapp, "Como funciona?")
        conexao = db.conectar()
        try:
            conexao.execute("UPDATE leads SET piloto_status = 'humano'")
            conexao.commit()
        finally:
            conexao.close()
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert whatsapp.enviados == []

    def test_mensagem_sua_pelo_celular_tira_o_piloto(self, whatsapp, ia_falsa):
        preparar_conversa_respondida(whatsapp, "Como funciona?")
        ts = int(SEGUNDA_10H.timestamp())
        whatsapp.conversas["5565996757327@s.whatsapp.net"].insert(
            0, {"key": {"id": "CEL", "fromMe": True}, "message": {"conversation": "Te ligo já"},
                "messageTimestamp": ts})
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert whatsapp.enviados == []
        assert lead("a")["piloto_status"] == "humano"


def contatado_pelo_piloto(place_id="a", dias_atras=2, follow_ups=0, nome="Clínica A"):
    """Lead que recebeu o primeiro contato do piloto há `dias_atras` dias e não respondeu."""
    criar_lead(place_id, nome=nome, status="contatado")
    enviada_em = (SEGUNDA_10H - timedelta(days=dias_atras)).isoformat(timespec="seconds")
    conexao = db.conectar()
    try:
        conexao.execute("UPDATE leads SET piloto_status = 'automatico', follow_ups_enviados = ? "
                        "WHERE place_id = ?", (follow_ups, place_id))
        conexao.execute(
            "INSERT INTO mensagens_conversa (canal, lead_ref, autor, texto, enviada_em, origem, chave_dedup, criada_em) "
            "VALUES ('maps', ?, 'vendedor', 'Oi, tudo bem?', ?, 'app', ?, ?)",
            (place_id, enviada_em, f"wa:P-{place_id}", enviada_em),
        )
        conexao.commit()
    finally:
        conexao.close()


def inserir_mensagem_do_lead(place_id, texto, quando, automatica):
    conexao = db.conectar()
    try:
        conexao.execute(
            "INSERT INTO mensagens_conversa (canal, lead_ref, autor, texto, enviada_em, origem, chave_dedup, "
            "criada_em, automatica) VALUES ('maps', ?, 'lead', ?, ?, 'whatsapp', ?, ?, ?)",
            (place_id, texto, quando.isoformat(timespec="seconds"), f"wa:L-{place_id}-{quando.timestamp()}",
             quando.isoformat(), int(automatica)),
        )
        conexao.commit()
    finally:
        conexao.close()


class TestFollowup:
    def test_manda_no_segundo_dia(self, whatsapp, ia_falsa):
        contatado_pelo_piloto(dias_atras=2)
        ligar()
        piloto.rodar_uma_vez(SEGUNDA_10H)

        assert whatsapp.enviados == [("65996757327", "Follow-up Clínica A")]
        assert "Oi, tudo bem?" in ia_falsa["mensagens_anteriores"]
        a = lead("a")
        assert a["follow_ups_enviados"] == 1
        assert a["ultimo_followup_em"] is not None
        conexao = db.conectar()
        try:
            evento = conexao.execute("SELECT tipo, detalhe FROM piloto_eventos ORDER BY id DESC LIMIT 1").fetchone()
        finally:
            conexao.close()
        assert evento["tipo"] == "followup_enviado"
        assert evento["detalhe"].startswith("1º follow-up")

    def test_antes_do_prazo_nao_manda(self, whatsapp, ia_falsa):
        contatado_pelo_piloto(dias_atras=1)
        conexao = db.conectar()
        try:
            assert piloto.leads_para_followup(conexao, SEGUNDA_10H) == []
        finally:
            conexao.close()

    @pytest.mark.parametrize("follow_ups,dias,vence", [(1, 4, False), (1, 5, True), (2, 9, True), (3, 13, False),
                                                       (3, 14, True), (4, 30, False)])
    def test_cadencia(self, banco, follow_ups, dias, vence):
        contatado_pelo_piloto(dias_atras=dias, follow_ups=follow_ups)
        conexao = db.conectar()
        try:
            assert bool(piloto.leads_para_followup(conexao, SEGUNDA_10H)) is vence
        finally:
            conexao.close()

    def test_site_ruim_nao_recebe_followup(self, banco):
        contatado_pelo_piloto(dias_atras=2)
        conexao = db.conectar()
        try:
            conexao.execute("UPDATE leads SET site_status = 'site_ruim'")
            conexao.commit()
            assert piloto.leads_para_followup(conexao, SEGUNDA_10H) == []
        finally:
            conexao.close()

    def test_quem_respondeu_nao_recebe_followup(self, banco):
        contatado_pelo_piloto(dias_atras=5)
        inserir_mensagem_do_lead("a", "Oi, quem é?", SEGUNDA_10H - timedelta(days=4), automatica=False)
        conexao = db.conectar()
        try:
            assert piloto.leads_para_followup(conexao, SEGUNDA_10H) == []
        finally:
            conexao.close()

    def test_resposta_de_robo_nao_conta_como_resposta(self, banco):
        contatado_pelo_piloto(dias_atras=2)
        inserir_mensagem_do_lead("a", "Olá! Digite 1 para...", SEGUNDA_10H - timedelta(days=2), automatica=True)
        conexao = db.conectar()
        try:
            assert [l["place_id"] for l in piloto.leads_para_followup(conexao, SEGUNDA_10H)] == ["a"]
        finally:
            conexao.close()

    def test_tem_prioridade_sobre_lead_novo(self, whatsapp, ia_falsa):
        contatado_pelo_piloto(dias_atras=2)
        criar_lead("novo", nome="Clínica Nova")
        ligar()
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert whatsapp.enviados == [("65996757327", "Follow-up Clínica A")]
        assert lead("novo")["status"] == "novo"

    def test_desligado_segue_para_lead_novo(self, whatsapp, ia_falsa):
        contatado_pelo_piloto(dias_atras=2)
        criar_lead("novo", nome="Clínica Nova")
        ligar(piloto_followup=0)
        piloto.rodar_uma_vez(SEGUNDA_10H)
        assert len(whatsapp.enviados) == 1 and "Clínica Nova" in whatsapp.enviados[0][1]


class TestRecadoRobo:
    def test_robo_recebe_recado_uma_vez(self, whatsapp, ia_falsa):
        contatado_pelo_piloto(dias_atras=0)
        inserir_mensagem_do_lead("a", "Olá! Digite 1 para agendar", SEGUNDA_10H + timedelta(seconds=20), automatica=True)
        piloto.rodar_uma_vez(SEGUNDA_10H + timedelta(minutes=5))

        assert len(whatsapp.enviados) == 1
        assert "não sou cliente" in whatsapp.enviados[0][1]
        assert "Clínica A" in whatsapp.enviados[0][1]
        # o robô responde de novo: não manda outro recado
        inserir_mensagem_do_lead("a", "Olá! Digite 1 para agendar", SEGUNDA_10H + timedelta(minutes=6), automatica=True)
        piloto.rodar_uma_vez(SEGUNDA_10H + timedelta(minutes=10))
        assert len(whatsapp.enviados) == 1

    def test_desligado_nao_manda(self, whatsapp, ia_falsa):
        db.salvar_config("piloto_recado_robo", "0")
        contatado_pelo_piloto(dias_atras=0)
        inserir_mensagem_do_lead("a", "Olá! Digite 1 para agendar", SEGUNDA_10H + timedelta(seconds=20), automatica=True)
        piloto.rodar_uma_vez(SEGUNDA_10H + timedelta(minutes=5))
        assert whatsapp.enviados == []

    def test_resposta_de_pessoa_nao_recebe_recado(self, whatsapp, ia_falsa):
        contatado_pelo_piloto(dias_atras=0)
        inserir_mensagem_do_lead("a", "Olá! Digite 1 para agendar", SEGUNDA_10H + timedelta(seconds=20), automatica=True)
        inserir_mensagem_do_lead("a", "Oi, sou eu o dono", SEGUNDA_10H + timedelta(minutes=2), automatica=False)
        conexao = db.conectar()
        try:
            assert piloto.leads_com_robo(conexao, SEGUNDA_10H + timedelta(minutes=5)) == []
        finally:
            conexao.close()


class TestOptOut:
    @pytest.mark.parametrize("texto", ["Não tenho interesse", "pare de mandar mensagem", "NAO QUERO", "isso é spam"])
    def test_detecta(self, texto):
        assert piloto.e_opt_out(texto)

    @pytest.mark.parametrize("texto", ["Quanto custa?", "Tenho interesse sim", "Pode mandar"])
    def test_nao_detecta(self, texto):
        assert not piloto.e_opt_out(texto)


class TestRotas:
    def test_painel(self, cliente, whatsapp):
        criar_lead("a", nome="Clínica A")
        corpo = cliente.get("/api/piloto").get_json()
        assert corpo["config"]["piloto_ativo"] == "0"
        assert corpo["fila"][0]["nome"] == "Clínica A"
        assert corpo["disponiveis"] == 1
        assert corpo["areas"]["cidades"] == ["Cuiabá"]
        assert corpo["estado"]["whatsapp"] == "open"

    def test_salvar_config_valida(self, cliente, banco):
        assert cliente.post("/api/piloto/config", json={"piloto_hora_inicio": 19, "piloto_hora_fim": 9}).status_code == 400
        assert cliente.post("/api/piloto/config", json={"piloto_intervalo_min": 0}).status_code == 400
        resposta = cliente.post("/api/piloto/config", json={"piloto_nicho": "barbearia", "piloto_auto_resposta": False})
        assert resposta.status_code == 200
        assert piloto.config()["piloto_nicho"] == "barbearia"
        assert piloto.config()["piloto_auto_resposta"] == "0"

    def test_ativar_e_desativar(self, cliente, banco):
        cliente.post("/api/piloto/ativar", json={"ativo": True})
        assert piloto.config()["piloto_ativo"] == "1"
        cliente.post("/api/piloto/ativar", json={"ativo": False})
        assert piloto.config()["piloto_ativo"] == "0"

    def test_assumir_e_devolver(self, cliente, banco):
        criar_lead("a")
        assert cliente.post("/api/piloto/assumir/a").get_json()["piloto_status"] == "humano"
        assert cliente.post("/api/piloto/devolver/a").get_json()["piloto_status"] == "automatico"

    def test_envio_manual_assume_a_conversa(self, cliente, whatsapp, banco):
        criar_lead("a", status="contatado")
        conexao = db.conectar()
        try:
            conexao.execute("UPDATE leads SET piloto_status = 'automatico'")
            conexao.commit()
        finally:
            conexao.close()
        cliente.post("/api/envio/whatsapp/maps/a", json={"texto": "Oi, aqui é o Eliseu"})
        assert lead("a")["piloto_status"] == "humano"


class TestAjustarSaudacao:
    def test_troca_pela_hora_atual(self, monkeypatch):
        monkeypatch.setattr(ia, "saudacao_por_horario", lambda: "Boa tarde")
        assert ia.ajustar_saudacao("Bom dia, Ana! Tudo bem? boa noite") == "Boa tarde, Ana! Tudo bem? boa tarde"
