"""Rotas do piloto automático: configuração da campanha (área, horário, ritmo),
painel de status, fila dos próximos leads e as conversas que precisam de você."""

from datetime import datetime

from flask import Blueprint, jsonify, request

import db
import mensageiros
import piloto
from rotas_conversa import _validar_alvo

bp = Blueprint("piloto", __name__)

LIMITES_NUMERICOS = {
    "piloto_score_min": (0, 100),
    "piloto_hora_inicio": (0, 23),
    "piloto_hora_fim": (1, 24),
    "piloto_intervalo_min": (1, 120),
    "piloto_intervalo_max": (1, 240),
    "piloto_max_respostas": (1, 20),
}
MAX_CARACTERES_AREA = 100
MAX_CARACTERES_INFO_OFERTA = 2000


def _resumo_lead(lead):
    return {
        "place_id": lead["place_id"],
        "nome": lead["nome"],
        "nicho": lead.get("nicho"),
        "cidade": lead.get("cidade"),
        "nota": lead.get("nota"),
        "num_avaliacoes": lead.get("num_avaliacoes"),
        "site_status": lead.get("site_status"),
        "score": round(lead.get("score") or 0),
    }


@bp.route("/api/piloto")
def painel_piloto():
    from rotas_envio import _enviados_hoje, _limite_diario

    cfg = piloto.config()
    try:
        estado_whatsapp = mensageiros.estado_whatsapp()
    except mensageiros.ErroEnvio:
        estado_whatsapp = "indisponivel"

    conexao = db.conectar()
    try:
        fila = [_resumo_lead(l) for l in piloto.proximos_leads(conexao, cfg, limite=5)]
        disponiveis = len(piloto.proximos_leads(conexao, cfg, limite=1000))
        contagem = dict(conexao.execute(
            "SELECT piloto_status, COUNT(*) FROM leads WHERE piloto_status IS NOT NULL GROUP BY piloto_status"
        ).fetchall())
        precisa_de_voce = [dict(l) for l in conexao.execute(
            """
            SELECT l.place_id, l.nome, m.texto AS ultimo_texto, m.enviada_em AS ultima_em,
                   (SELECT detalhe FROM piloto_eventos e WHERE e.place_id = l.place_id
                     AND e.tipo = 'passou_para_voce' ORDER BY e.id DESC LIMIT 1) AS motivo
            FROM leads l
            JOIN mensagens_conversa m ON m.id = (
                SELECT id FROM mensagens_conversa WHERE canal = 'maps' AND lead_ref = l.place_id
                ORDER BY enviada_em DESC, id DESC LIMIT 1)
            WHERE l.piloto_status = 'humano' AND m.autor = 'lead'
            ORDER BY m.enviada_em DESC
            """
        ).fetchall()]
        previas = [dict(l) for l in conexao.execute(
            """
            SELECT l.place_id, l.nome, l.proximo_followup AS entregar_em, l.status,
                   (SELECT detalhe FROM piloto_eventos e WHERE e.place_id = l.place_id
                     AND e.tipo = 'previa_combinada' ORDER BY e.id DESC LIMIT 1) AS detalhe
            FROM leads l
            WHERE l.tags LIKE '%prévia%' AND l.status NOT IN ('fechou', 'recusou', 'ignorado')
            ORDER BY COALESCE(l.proximo_followup, '9999')
            """
        ).fetchall()]
        eventos = [dict(l) for l in conexao.execute(
            "SELECT id, em, tipo, place_id, nome, detalhe FROM piloto_eventos ORDER BY id DESC LIMIT 40"
        ).fetchall()]
        nichos = [l[0] for l in conexao.execute(
            "SELECT DISTINCT nicho FROM leads WHERE nicho IS NOT NULL AND nicho != '' ORDER BY nicho")]
        cidades = [l[0] for l in conexao.execute(
            "SELECT DISTINCT cidade FROM leads WHERE cidade IS NOT NULL AND cidade != '' ORDER BY cidade")]
        enviados = _enviados_hoje(conexao)
    finally:
        conexao.close()

    return jsonify({
        "config": cfg,
        "estado": {
            **piloto.estado(),
            "whatsapp": estado_whatsapp,
            "dentro_do_horario": piloto.dentro_do_horario(cfg),
            "enviados_hoje": enviados,
            "limite_diario": _limite_diario(),
        },
        "fila": fila,
        "disponiveis": disponiveis,
        "contagem": {
            "conduzindo": contagem.get("automatico", 0),
            "com_voce": contagem.get("humano", 0),
            "encerrados": contagem.get("encerrado", 0),
            "sem_whatsapp": contagem.get("sem_whatsapp", 0),
        },
        "precisa_de_voce": precisa_de_voce,
        "previas": previas,
        "eventos": eventos,
        "areas": {"nichos": nichos, "cidades": cidades},
    })


@bp.route("/api/piloto/config", methods=["POST"])
def salvar_config_piloto():
    dados = request.json or {}
    valores = {}

    for chave in ("piloto_nicho", "piloto_cidade"):
        if chave in dados:
            valor = str(dados[chave] or "").strip()
            if len(valor) > MAX_CARACTERES_AREA:
                return jsonify({"erro": "área muito longa"}), 400
            valores[chave] = valor

    if "piloto_info_oferta" in dados:
        valor = str(dados["piloto_info_oferta"] or "").strip()
        if len(valor) > MAX_CARACTERES_INFO_OFERTA:
            return jsonify({"erro": f"informações da oferta muito longas (máx. {MAX_CARACTERES_INFO_OFERTA})"}), 400
        valores["piloto_info_oferta"] = valor

    for chave, (minimo, maximo) in LIMITES_NUMERICOS.items():
        if chave in dados:
            try:
                numero = int(dados[chave])
            except (TypeError, ValueError):
                return jsonify({"erro": f"{chave} deve ser um número"}), 400
            if not minimo <= numero <= maximo:
                return jsonify({"erro": f"{chave} deve ficar entre {minimo} e {maximo}"}), 400
            valores[chave] = str(numero)

    for chave in ("piloto_auto_resposta", "piloto_fim_de_semana"):
        if chave in dados:
            valores[chave] = "1" if dados[chave] else "0"

    final = {**piloto.config(), **valores}
    if int(final["piloto_hora_inicio"]) >= int(final["piloto_hora_fim"]):
        return jsonify({"erro": "o horário de início precisa ser antes do fim"}), 400
    if int(final["piloto_intervalo_min"]) > int(final["piloto_intervalo_max"]):
        return jsonify({"erro": "o intervalo mínimo não pode ser maior que o máximo"}), 400

    for chave, valor in valores.items():
        db.salvar_config(chave, valor)
    return jsonify({"ok": True, "config": piloto.config()})


@bp.route("/api/piloto/ativar", methods=["POST"])
def ativar_piloto():
    ativo = bool((request.json or {}).get("ativo"))
    db.salvar_config("piloto_ativo", "1" if ativo else "0")
    conexao = db.conectar()
    try:
        piloto.registrar_evento(conexao, "ligado" if ativo else "desligado")
        conexao.commit()
    finally:
        conexao.close()
    # ao ligar, o primeiro contato sai na próxima volta (não espera um intervalo inteiro)
    piloto._estado["proximo_contato_em"] = None
    return jsonify({"ok": True, "ativo": ativo})


@bp.route("/api/piloto/enviar-proximo", methods=["POST"])
def enviar_proximo_agora():
    """Manda o próximo da fila agora (respeita o limite diário, ignora o intervalo)."""
    try:
        nome = piloto.fazer_primeiro_contato(piloto.config())
    except mensageiros.ErroEnvio as erro:
        return jsonify({"erro": str(erro)}), 502
    except Exception as erro:
        return jsonify({"erro": f"Não consegui gerar a mensagem: {erro}"}), 500
    if not nome:
        return jsonify({"erro": "Nenhum lead disponível na fila, ou o limite diário foi atingido."}), 400
    return jsonify({"ok": True, "nome": nome})


def _mudar_condutor(place_id, novo):
    lead, erro = _validar_alvo("maps", place_id)
    if erro:
        return erro
    conexao = db.conectar()
    try:
        conexao.execute("UPDATE leads SET piloto_status = ?, piloto_respostas = 0, atualizado_em = ? "
                        "WHERE place_id = ?", (novo, datetime.now().isoformat(timespec="seconds"), place_id))
        piloto.registrar_evento(conexao, "voce_assumiu" if novo == "humano" else "devolvido_ao_piloto",
                                place_id, lead["nome"])
        conexao.commit()
    finally:
        conexao.close()
    return jsonify({"ok": True, "piloto_status": novo})


@bp.route("/api/piloto/assumir/<path:place_id>", methods=["POST"])
def assumir_conversa(place_id):
    return _mudar_condutor(place_id, "humano")


@bp.route("/api/piloto/devolver/<path:place_id>", methods=["POST"])
def devolver_ao_piloto(place_id):
    return _mudar_condutor(place_id, "automatico")
