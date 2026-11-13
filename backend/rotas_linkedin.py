"""Prospecção no LinkedIn, em modo ASSISTIDO.

O app NÃO acessa o LinkedIn, não busca perfil e não envia nada: automatizar isso viola os termos do
LinkedIn e costuma levar a restrição ou banimento da conta. O fluxo é:
1. você importa uma lista de perfis (CSV do Sales Navigator, do seu LinkedIn ou montado à mão);
2. a IA escreve a nota de conexão, a primeira mensagem e os follow-ups;
3. você copia, envia no LinkedIn e marca aqui o passo dado. O app guarda o funil e o prazo do próximo follow-up.
"""

import csv
import io
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

import db
import ia
from rotas_conversa import _inserir_mensagem

logger = logging.getLogger(__name__)

bp = Blueprint("linkedin", __name__)

STATUS_LINKEDIN = ("novo", "conexao_enviada", "conectado", "mensagem_enviada", "respondeu", "recusou", "ignorado")
# dias até o próximo passo, por status que acabou de ser registrado
PRAZO_PROXIMO_PASSO_DIAS = {"conexao_enviada": 5, "mensagem_enviada": 3}
PRAZO_DEPOIS_DO_FOLLOWUP_DIAS = 7

SINONIMOS_COLUNAS = {
    "nome": ("nome", "name", "full name", "nome completo"),
    "primeiro_nome": ("first name", "primeiro nome"),
    "sobrenome": ("last name", "sobrenome"),
    "cargo": ("cargo", "position", "title", "job title", "headline", "titulo", "ocupacao"),
    "empresa": ("empresa", "company", "organization", "organizacao", "current company"),
    "perfil_url": ("link do perfil", "perfil", "profile url", "linkedin url", "url", "profile link", "link", "profile"),
    "setor": ("setor", "industry", "segmento"),
    "cidade": ("cidade", "location", "localizacao", "local", "geography"),
}


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _erro(excecao, status=400):
    return jsonify({"erro": str(excecao)}), status


def _normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().replace("_", " ").split())


def _mapear_colunas(cabecalho):
    mapa = {}
    for indice, rotulo in enumerate(cabecalho):
        normal = _normalizar(rotulo)
        for campo, sinonimos in SINONIMOS_COLUNAS.items():
            if normal in sinonimos and campo not in mapa:
                mapa[campo] = indice
    return mapa


def _url_perfil_limpa(url):
    url = (url or "").strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if "linkedin.com" not in url.lower():
        return None
    return url.split("?")[0].rstrip("/")


def _linhas_do_csv(texto):
    texto = texto.lstrip("﻿")
    try:
        delimitador = csv.Sniffer().sniff(texto[:2000], delimiters=",;\t").delimiter
    except csv.Error:
        delimitador = ","
    return list(csv.reader(io.StringIO(texto), delimiter=delimitador))


@bp.route("/api/linkedin/importar", methods=["POST"])
def importar_csv():
    texto = str((request.json or {}).get("csv", ""))
    if not texto.strip():
        return _erro("O arquivo está vazio.")
    linhas = _linhas_do_csv(texto)
    if len(linhas) < 2:
        return _erro("Não achei linhas de dados no arquivo.")
    mapa = _mapear_colunas(linhas[0])
    if "nome" not in mapa and not ("primeiro_nome" in mapa or "sobrenome" in mapa):
        return _erro("Não encontrei a coluna de nome (aceito: nome, name, first name + last name).")

    def valor(linha, campo):
        indice = mapa.get(campo)
        return linha[indice].strip() if indice is not None and indice < len(linha) else ""

    importados = ignorados = 0
    conexao = db.conectar()
    try:
        for linha in linhas[1:]:
            nome = valor(linha, "nome") or f"{valor(linha, 'primeiro_nome')} {valor(linha, 'sobrenome')}".strip()
            if not nome:
                ignorados += 1
                continue
            novo = _inserir(conexao, nome, valor(linha, "cargo"), valor(linha, "empresa"),
                            valor(linha, "perfil_url"), valor(linha, "setor"), valor(linha, "cidade"))
            importados, ignorados = (importados + 1, ignorados) if novo else (importados, ignorados + 1)
        conexao.commit()
    finally:
        conexao.close()
    return jsonify({"importados": importados, "ignorados": ignorados})


def _inserir(conexao, nome, cargo, empresa, perfil_url, setor, cidade):
    agora = _agora()
    cursor = conexao.execute(
        "INSERT OR IGNORE INTO linkedin_leads (nome, cargo, empresa, perfil_url, setor, cidade, criado_em, atualizado_em) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (nome[:120], cargo or None, empresa or None, _url_perfil_limpa(perfil_url), setor or None, cidade or None,
         agora, agora))
    return cursor.lastrowid if cursor.rowcount else None


@bp.route("/api/linkedin/leads", methods=["POST"])
def adicionar_lead():
    dados = request.json or {}
    nome = str(dados.get("nome", "")).strip()
    if not nome:
        return _erro("Informe o nome.")
    conexao = db.conectar()
    try:
        novo = _inserir(conexao, nome, str(dados.get("cargo") or "").strip(), str(dados.get("empresa") or "").strip(),
                        str(dados.get("perfil_url") or "").strip(), str(dados.get("setor") or "").strip(),
                        str(dados.get("cidade") or "").strip())
        if not novo:
            return _erro("Esse perfil já está na lista.")
        conexao.commit()
    finally:
        conexao.close()
    return jsonify({"id": novo})


def _filtros(args, incluir_status=True):
    condicoes, valores = [], []
    if incluir_status and args.get("status"):
        condicoes.append("status = ?")
        valores.append(args["status"])
    if args.get("setor"):
        condicoes.append("setor = ?")
        valores.append(args["setor"])
    if args.get("busca"):
        condicoes.append("(nome LIKE ? OR empresa LIKE ? OR cargo LIKE ?)")
        valores += [f"%{args['busca']}%"] * 3
    return (" WHERE " + " AND ".join(condicoes)) if condicoes else "", valores


@bp.route("/api/linkedin/leads")
def listar_leads():
    pagina = max(1, request.args.get("pagina", 1, type=int))
    por_pagina = min(200, max(1, request.args.get("por_pagina", 50, type=int)))
    conexao = db.conectar()
    try:
        onde, valores = _filtros(request.args)
        total = conexao.execute(f"SELECT COUNT(*) FROM linkedin_leads{onde}", valores).fetchone()[0]
        linhas = conexao.execute(
            "SELECT id, nome, cargo, empresa, perfil_url, setor, cidade, status, ultimo_texto, "
            f"follow_ups_enviados, proximo_followup, criado_em FROM linkedin_leads{onde} "
            "ORDER BY COALESCE(atualizado_em, criado_em) DESC, id DESC LIMIT ? OFFSET ?",
            valores + [por_pagina, (pagina - 1) * por_pagina]).fetchall()
        onde2, valores2 = _filtros(request.args, incluir_status=False)
        contagem = {l[0]: l[1] for l in conexao.execute(
            f"SELECT status, COUNT(*) FROM linkedin_leads{onde2} GROUP BY status", valores2)}
        setores = [r[0] for r in conexao.execute(
            "SELECT DISTINCT setor FROM linkedin_leads WHERE setor IS NOT NULL AND setor != '' ORDER BY setor")]
    finally:
        conexao.close()
    return jsonify({"leads": [dict(l) for l in linhas], "total": total, "setores": setores,
                    "contagem_por_status": contagem})


def _obter(conexao, lead_id):
    linha = conexao.execute("SELECT * FROM linkedin_leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(linha) if linha else None


@bp.route("/api/linkedin/leads/<int:lead_id>/gerar", methods=["POST"])
def gerar_texto(lead_id):
    tipo = str((request.json or {}).get("tipo", "")).strip()
    if tipo not in ia.TIPOS_LINKEDIN:
        return _erro("Tipo inválido. Use conexao, mensagem ou followup.")
    conexao = db.conectar()
    try:
        lead = _obter(conexao, lead_id)
    finally:
        conexao.close()
    if not lead:
        return _erro("Lead não encontrado.", 404)
    try:
        texto, provedor, _ = ia.gerar_texto_linkedin_com_fallback(lead, tipo, lead.get("ultimo_texto"))
    except RuntimeError as excecao:
        return _erro(excecao, 503)
    limite = ia.LIMITE_NOTA_CONEXAO_LINKEDIN if tipo == "conexao" else ia.LIMITE_MENSAGEM_LINKEDIN
    return jsonify({"texto": texto, "provedor": provedor, "limite_caracteres": limite})


@bp.route("/api/linkedin/leads/<int:lead_id>/status", methods=["POST"])
def mudar_status(lead_id):
    dados = request.json or {}
    status = str(dados.get("status", "")).strip()
    texto = str(dados.get("texto") or "").strip()
    if status not in STATUS_LINKEDIN:
        return _erro(f"Status inválido. Use um de: {', '.join(STATUS_LINKEDIN)}")
    conexao = db.conectar()
    try:
        lead = _obter(conexao, lead_id)
        if not lead:
            return _erro("Lead não encontrado.", 404)
        agora = _agora()
        if texto:
            _inserir_mensagem(conexao, "linkedin", lead_id, "vendedor", texto, agora, "linkedin", None)
        follow_ups = lead["follow_ups_enviados"]
        dias = PRAZO_PROXIMO_PASSO_DIAS.get(status)
        if status == "mensagem_enviada" and lead["status"] == "mensagem_enviada":
            follow_ups += 1  # segunda mensagem em diante é follow-up
            dias = PRAZO_DEPOIS_DO_FOLLOWUP_DIAS
        proximo = (date.today() + timedelta(days=dias)).isoformat() if dias else None
        conexao.execute(
            "UPDATE linkedin_leads SET status = ?, ultimo_texto = COALESCE(?, ultimo_texto), follow_ups_enviados = ?, "
            "proximo_followup = ?, atualizado_em = ? WHERE id = ?",
            (status, texto or None, follow_ups, proximo, agora, lead_id))
        conexao.commit()
    finally:
        conexao.close()
    return jsonify({"ok": True})


@bp.route("/api/linkedin/leads/<int:lead_id>/historico")
def historico(lead_id):
    conexao = db.conectar()
    try:
        linhas = conexao.execute(
            "SELECT autor, texto, enviada_em FROM mensagens_conversa WHERE canal = 'linkedin' AND lead_ref = ? "
            "ORDER BY enviada_em", (str(lead_id),)).fetchall()
    finally:
        conexao.close()
    return jsonify({"mensagens": [dict(l) for l in linhas]})
