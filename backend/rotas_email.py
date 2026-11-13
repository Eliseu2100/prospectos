"""Prospecção por e-mail: configuração SMTP, leads (achados nos sites ou na base da Receita),
escrita com IA e envio.

Regras de negócio:
- Um lead por clique, sempre com revisão humana do texto antes de enviar; não existe disparo
  automático nem em massa.
- Limite diário configurável (padrão 20, para caixa nova), contado pelos envios de hoje.
- Todo e-mail sai com identificação e pedido de descadastro (acrescentados aqui, o usuário não
  consegue tirar). Quem pede para sair vai para `email_descadastros` e nunca mais é contatado.
- O PDF da proposta genérica vai anexado só no PRIMEIRO e-mail para cada lead (e-mail com anexo em
  todo follow-up derruba a entrega).
- Histórico em `mensagens_conversa` (canal "email", origem "email", para não contar no limite do WhatsApp).
"""

import logging
import os
import re
import threading
from datetime import date, datetime

from flask import Blueprint, jsonify, request

import db
import email_modelo
import email_prospeccao
import ia
import mensageiros
import paths
from rotas_config import mascarar_chave
from rotas_conversa import _inserir_mensagem

logger = logging.getLogger(__name__)

bp = Blueprint("email_prospeccao", __name__)

LIMITE_DIARIO_PADRAO = 20
STATUS_EMAIL = ("novo", "contatado", "respondeu", "recusou", "descadastrado", "invalido")
STATUS_QUE_NAO_RECEBEM = ("descadastrado", "invalido", "recusou")
ARQUIVO_ANEXO_PADRAO = ("anexos", "proposta-comercial.pdf")

_estado_importacao = {"rodando": False, "processados": 0, "total": 0, "novos": 0, "mensagem": ""}
_trava_importacao = threading.Lock()


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _erro(excecao, status=400):
    return jsonify({"erro": str(excecao)}), status


def _limite_diario():
    try:
        return max(1, int(db.obter_config("email_limite_diario") or LIMITE_DIARIO_PADRAO))
    except ValueError:
        return LIMITE_DIARIO_PADRAO


def _enviados_hoje(conexao):
    return conexao.execute(
        "SELECT COUNT(*) FROM mensagens_conversa WHERE canal = 'email' AND autor = 'vendedor' "
        "AND substr(enviada_em, 1, 10) = ?", (date.today().isoformat(),)
    ).fetchone()[0]


def _arquivo_anexo():
    configurado = (db.obter_config("email_anexo_pdf") or "").strip()
    return configurado or str(paths.caminho_dados(*ARQUIVO_ANEXO_PADRAO))


def _anexar_pdf():
    valor = db.obter_config("email_anexar_pdf")
    return True if valor in (None, "") else str(valor) in ("1", "true", "True")


# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

@bp.route("/api/email/config")
def obter_config():
    conexao = db.conectar()
    try:
        enviados = _enviados_hoje(conexao)
    finally:
        conexao.close()
    senha = db.obter_config("smtp_senha") or ""
    arquivo = _arquivo_anexo()
    return jsonify({"smtp": {
        "host": db.obter_config("smtp_host") or "",
        "porta": int(db.obter_config("smtp_porta") or mensageiros.PORTA_SMTP_PADRAO),
        "usuario": db.obter_config("smtp_usuario") or "",
        "senha_configurada": bool(senha),
        "senha_mascarada": mascarar_chave(senha),
        "remetente_nome": db.obter_config("smtp_remetente_nome") or "",
        "remetente_email": db.obter_config("smtp_remetente_email") or "",
        "limite_diario": _limite_diario(),
        "enviados_hoje": enviados,
        "assinatura": db.obter_config("smtp_assinatura") or "",
        "anexar_pdf": _anexar_pdf(),
        "anexo_pdf": arquivo,
        "anexo_pdf_existe": os.path.isfile(arquivo),
    }})


@bp.route("/api/email/config", methods=["POST"])
def salvar_config():
    dados = request.json or {}
    host = str(dados.get("host", "")).strip()
    usuario = str(dados.get("usuario", "")).strip()
    if not host or not usuario:
        return _erro("Informe o servidor SMTP e o usuário.")
    try:
        porta = int(dados.get("porta") or mensageiros.PORTA_SMTP_PADRAO)
        limite = int(dados.get("limite_diario") or LIMITE_DIARIO_PADRAO)
    except (TypeError, ValueError):
        return _erro("Porta e limite diário precisam ser números.")
    if not (1 <= porta <= 65535) or not (1 <= limite <= 500):
        return _erro("Porta ou limite diário fora do intervalo permitido.")
    senha_nova = str(dados.get("senha", "")).strip()
    if senha_nova and "gmail.com" in host.lower() and len(re.sub(r"\s", "", senha_nova)) != 16:
        return _erro("No Gmail a senha precisa ser uma senha de app de 16 letras (aparece em 4 grupos de 4). "
                     "Crie em myaccount.google.com/apppasswords; precisa da verificação em duas etapas ligada.")
    db.salvar_config("smtp_host", host)
    db.salvar_config("smtp_porta", str(porta))
    db.salvar_config("smtp_usuario", usuario)
    if senha_nova:
        db.salvar_config("smtp_senha", re.sub(r"\s", "", senha_nova) if "gmail.com" in host.lower() else senha_nova)
    db.salvar_config("smtp_remetente_nome", str(dados.get("remetente_nome", "")).strip())
    db.salvar_config("smtp_remetente_email", str(dados.get("remetente_email", "")).strip())
    db.salvar_config("email_limite_diario", str(limite))
    db.salvar_config("smtp_assinatura", str(dados.get("assinatura", "")).strip())
    if "anexar_pdf" in dados:
        db.salvar_config("email_anexar_pdf", "1" if dados["anexar_pdf"] else "0")
    if str(dados.get("anexo_pdf", "")).strip():
        db.salvar_config("email_anexo_pdf", str(dados["anexo_pdf"]).strip())
    return jsonify({"ok": True})


def _montar_e_enviar(para, assunto, corpo, com_anexo):
    cfg = mensageiros.config_smtp()
    anexos = []
    if com_anexo and _anexar_pdf() and os.path.isfile(_arquivo_anexo()):
        anexos.append(_arquivo_anexo())
    imagens = email_modelo.imagens_inline()
    return mensageiros.enviar_email(
        para, assunto, email_modelo.texto_simples(corpo, cfg["remetente_email"]),
        html=email_modelo.montar_html(corpo, cfg["remetente_email"], com_imagens=bool(imagens)),
        imagens=imagens, anexos=anexos,
    )


@bp.route("/api/email/config/testar", methods=["POST"])
def testar_envio():
    para = str((request.json or {}).get("para", "")).strip()
    if not email_prospeccao.email_valido(para):
        return _erro("Informe um e-mail válido para o teste.")
    try:
        _montar_e_enviar(
            para, "teste do envio do Seriax OS",
            "Este é um e-mail de teste do Seriax OS.\n\nSe você está lendo isto com o cabeçalho e a assinatura "
            "da marca, o envio está funcionando.", com_anexo=True)
    except mensageiros.ErroEnvio as excecao:
        return _erro(excecao)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

def _filtros(args, incluir_status=True):
    condicoes, valores = [], []
    if incluir_status and args.get("status"):
        condicoes.append("status = ?")
        valores.append(args["status"])
    if args.get("setor"):
        condicoes.append("setor = ?")
        valores.append(args["setor"])
    if args.get("cidade"):
        condicoes.append("cidade = ?")
        valores.append(args["cidade"])
    if args.get("busca"):
        condicoes.append("(empresa LIKE ? OR email LIKE ?)")
        valores += [f"%{args['busca']}%"] * 2
    return (" WHERE " + " AND ".join(condicoes)) if condicoes else "", valores


@bp.route("/api/email/leads")
def listar_leads():
    pagina = max(1, request.args.get("pagina", 1, type=int))
    por_pagina = min(200, max(1, request.args.get("por_pagina", 50, type=int)))
    conexao = db.conectar()
    try:
        onde, valores = _filtros(request.args)
        total = conexao.execute(f"SELECT COUNT(*) FROM email_leads{onde}", valores).fetchone()[0]
        linhas = conexao.execute(
            "SELECT id, empresa, email, setor, cidade, site_url, fonte, status, follow_ups_enviados, "
            f"ultimo_envio_em, criado_em FROM email_leads{onde} "
            "ORDER BY COALESCE(atualizado_em, criado_em) DESC, id DESC LIMIT ? OFFSET ?",
            valores + [por_pagina, (pagina - 1) * por_pagina]).fetchall()
        onde2, valores2 = _filtros(request.args, incluir_status=False)
        contagem = {linha[0]: linha[1] for linha in conexao.execute(
            f"SELECT status, COUNT(*) FROM email_leads{onde2} GROUP BY status", valores2)}
        setores = [r[0] for r in conexao.execute(
            "SELECT DISTINCT setor FROM email_leads WHERE setor IS NOT NULL AND setor != '' ORDER BY setor")]
        cidades = [r[0] for r in conexao.execute(
            "SELECT DISTINCT cidade FROM email_leads WHERE cidade IS NOT NULL AND cidade != '' ORDER BY cidade")]
    finally:
        conexao.close()
    return jsonify({"leads": [dict(l) for l in linhas], "total": total, "setores": setores,
                    "cidades": cidades, "contagem_por_status": contagem})


@bp.route("/api/email/leads", methods=["POST"])
def adicionar_lead():
    dados = request.json or {}
    email = str(dados.get("email", "")).strip().lower()
    if not email_prospeccao.email_valido(email):
        return _erro("E-mail inválido.")
    conexao = db.conectar()
    try:
        if email_prospeccao._descadastrado(conexao, email):
            return _erro("Este e-mail pediu para não ser contatado e está na lista de descadastros.")
        novo = email_prospeccao.inserir_email_lead(
            conexao, str(dados.get("empresa", "")).strip(), email, setor=(dados.get("setor") or None),
            cidade=(dados.get("cidade") or None), site_url=(dados.get("site_url") or None), fonte="manual")
        if not novo:
            return _erro("Esse e-mail já está na lista (ou parece ser de contabilidade).")
        conexao.commit()
    finally:
        conexao.close()
    return jsonify({"id": novo})


def _obter_lead(conexao, lead_id):
    linha = conexao.execute("SELECT * FROM email_leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(linha) if linha else None


@bp.route("/api/email/leads/<int:lead_id>/gerar", methods=["POST"])
def gerar_email(lead_id):
    conexao = db.conectar()
    try:
        lead = _obter_lead(conexao, lead_id)
        if not lead:
            return _erro("Lead não encontrado.", 404)
        anterior = conexao.execute(
            "SELECT texto FROM mensagens_conversa WHERE canal = 'email' AND lead_ref = ? AND autor = 'vendedor' "
            "ORDER BY enviada_em DESC LIMIT 1", (str(lead_id),)).fetchone()
    finally:
        conexao.close()
    try:
        resultado, provedor, _ = ia.gerar_email_com_fallback(
            lead, lead["follow_ups_enviados"] if anterior else 0, anterior[0] if anterior else None)
    except RuntimeError as excecao:
        return _erro(excecao, 503)
    return jsonify({"assunto": resultado["assunto"], "corpo": resultado["corpo"], "provedor": provedor})


@bp.route("/api/email/leads/<int:lead_id>/enviar", methods=["POST"])
def enviar_email(lead_id):
    dados = request.json or {}
    assunto = str(dados.get("assunto", "")).strip()
    corpo = str(dados.get("corpo", "")).strip()
    if not assunto or not corpo:
        return _erro("Escreva o assunto e o texto antes de enviar.")
    conexao = db.conectar()
    try:
        lead = _obter_lead(conexao, lead_id)
        if not lead:
            return _erro("Lead não encontrado.", 404)
        if lead["status"] in STATUS_QUE_NAO_RECEBEM or email_prospeccao._descadastrado(conexao, lead["email"]):
            return _erro("Este contato não pode receber e-mail (descadastrado, inválido ou recusou).")
        if _enviados_hoje(conexao) >= _limite_diario():
            return _erro(f"Limite diário de {_limite_diario()} e-mails atingido. Continue amanhã.", 429)
        ja_enviou = conexao.execute(
            "SELECT 1 FROM mensagens_conversa WHERE canal = 'email' AND lead_ref = ? AND autor = 'vendedor' LIMIT 1",
            (str(lead_id),)).fetchone() is not None
        try:
            id_mensagem = _montar_e_enviar(lead["email"], assunto, corpo, com_anexo=not ja_enviou)
        except mensageiros.ErroEnvio as excecao:
            return _erro(excecao)
        agora = _agora()
        _inserir_mensagem(conexao, "email", lead_id, "vendedor", f"Assunto: {assunto}\n\n{corpo}", agora,
                          "email", f"email:{id_mensagem}")
        novo_status = "contatado" if lead["status"] == "novo" else lead["status"]
        conexao.execute(
            "UPDATE email_leads SET status = ?, ultimo_envio_em = ?, atualizado_em = ?, "
            "follow_ups_enviados = follow_ups_enviados + ? WHERE id = ?",
            (novo_status, agora, agora, 1 if ja_enviou else 0, lead_id))
        conexao.commit()
    finally:
        conexao.close()
    return jsonify({"ok": True, "status": novo_status})


@bp.route("/api/email/leads/<int:lead_id>/status", methods=["POST"])
def mudar_status(lead_id):
    status = str((request.json or {}).get("status", "")).strip()
    if status not in STATUS_EMAIL:
        return _erro(f"Status inválido. Use um de: {', '.join(STATUS_EMAIL)}")
    conexao = db.conectar()
    try:
        lead = _obter_lead(conexao, lead_id)
        if not lead:
            return _erro("Lead não encontrado.", 404)
        conexao.execute("UPDATE email_leads SET status = ?, atualizado_em = ? WHERE id = ?",
                        (status, _agora(), lead_id))
        if status == "descadastrado":
            conexao.execute("INSERT OR IGNORE INTO email_descadastros (email, motivo, criado_em) VALUES (?, ?, ?)",
                            (lead["email"], "marcado no CRM", _agora()))
        conexao.commit()
    finally:
        conexao.close()
    return jsonify({"ok": True})


@bp.route("/api/email/leads/<int:lead_id>/historico")
def historico(lead_id):
    conexao = db.conectar()
    try:
        linhas = conexao.execute(
            "SELECT autor, texto, enviada_em FROM mensagens_conversa WHERE canal = 'email' AND lead_ref = ? "
            "ORDER BY enviada_em", (str(lead_id),)).fetchall()
    finally:
        conexao.close()
    return jsonify({"mensagens": [dict(l) for l in linhas]})


# ---------------------------------------------------------------------------
# Importação
# ---------------------------------------------------------------------------

def _rodar_importacao_sites():
    conexao = db.conectar()
    try:
        email_prospeccao.importar_dos_leads(conexao, progresso=_estado_importacao)
        _estado_importacao["mensagem"] = f"{_estado_importacao['novos']} e-mail(s) novo(s) encontrado(s)."
    except Exception:
        logger.exception("falha ao buscar e-mails nos sites")
        _estado_importacao["mensagem"] = "A busca parou por um erro. Veja o log do app."
    finally:
        conexao.close()
        _estado_importacao["rodando"] = False
        _trava_importacao.release()


@bp.route("/api/email/importar/sites", methods=["POST"])
def importar_dos_sites():
    if not _trava_importacao.acquire(blocking=False):
        return _erro("Já existe uma busca em andamento.", 409)
    _estado_importacao.update({"rodando": True, "processados": 0, "total": 0, "novos": 0, "mensagem": ""})
    threading.Thread(target=_rodar_importacao_sites, daemon=True).start()
    return jsonify({"iniciado": True})


@bp.route("/api/email/importar/estado")
def estado_importacao():
    return jsonify(dict(_estado_importacao))


@bp.route("/api/email/importar/receita", methods=["POST"])
def importar_da_receita():
    dados = request.json or {}
    arquivo = str(dados.get("arquivo", "")).strip().strip('"')
    if not os.path.isfile(arquivo):
        return _erro("Arquivo não encontrado. Informe o caminho completo do arquivo de Estabelecimentos da Receita.")
    municipios = str(dados.get("municipios_arquivo", "")).strip().strip('"') or None
    if municipios and not os.path.isfile(municipios):
        return _erro("Arquivo de Municípios não encontrado.")
    cnaes = dados.get("cnaes") or []
    if isinstance(cnaes, str):
        cnaes = [c for c in cnaes.replace(";", ",").split(",") if c.strip()]
    conexao = db.conectar()
    try:
        resultado = email_prospeccao.importar_receita(
            conexao, arquivo, cnaes, dados.get("uf"), municipio=(dados.get("municipio") or None),
            municipios_arquivo=municipios, setor=(dados.get("setor") or None),
            limite=int(dados["limite"]) if str(dados.get("limite") or "").isdigit() else None)
    except ValueError as excecao:
        return _erro(excecao)
    finally:
        conexao.close()
    return jsonify(resultado)


# ---------------------------------------------------------------------------
# Descadastros
# ---------------------------------------------------------------------------

@bp.route("/api/email/descadastros")
def listar_descadastros():
    conexao = db.conectar()
    try:
        emails = [r[0] for r in conexao.execute("SELECT email FROM email_descadastros ORDER BY criado_em DESC")]
    finally:
        conexao.close()
    return jsonify({"emails": emails})


@bp.route("/api/email/descadastros", methods=["POST"])
def adicionar_descadastro():
    email = str((request.json or {}).get("email", "")).strip().lower()
    if not email_prospeccao.email_valido(email):
        return _erro("E-mail inválido.")
    conexao = db.conectar()
    try:
        conexao.execute("INSERT OR IGNORE INTO email_descadastros (email, motivo, criado_em) VALUES (?, ?, ?)",
                        (email, "adicionado manualmente", _agora()))
        conexao.execute("UPDATE email_leads SET status = 'descadastrado', atualizado_em = ? WHERE email = ?",
                        (_agora(), email))
        conexao.commit()
    finally:
        conexao.close()
    return jsonify({"ok": True})
