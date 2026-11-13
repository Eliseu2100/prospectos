"""Importa para o CRM conversas lidas do WhatsApp Web quando a Evolution deixou de
gravar as respostas (ex.: erros "Bad MAC" de descriptografia).

Uso (da pasta backend, com PROSPECCAO_DIR_DADOS apontando para a pasta de dados):
    .venv/Scripts/python importar_historico_whatsapp.py conversas.json          # simula
    .venv/Scripts/python importar_historico_whatsapp.py conversas.json --aplicar # grava

O JSON é {place_id: {"nome", "mensagens": [{"meta", "texto", "id"}]}}, onde "meta" é o
atributo data-pre-plain-text do WhatsApp Web ("[10:49, 12/11/2026] Nome: ").

Regras de segurança:
- só mensagens a partir de --desde (padrão 2026-11-09);
- duplicata é ignorada pela chave "wa:<id>" (a mesma da Evolution) e por texto+horário próximo;
- mensagem do lead que parece resposta automática entra marcada como automática;
- lead que o piloto ainda trata e que tem resposta de pessoa (ou mensagem sua manual)
  passa para "humano": o piloto não responde mensagens antigas;
- sem --aplicar nada é gravado.
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timedelta

import db
import sincronizacao_whatsapp as sinc
from rotas_conversa import _inserir_mensagem

PADRAO_META = re.compile(r"\[(\d\d):(\d\d), (\d\d)/(\d\d)/(\d{4})\] (.*?): ?$")
NOME_VENDEDOR = "eliseu"
JANELA_DUPLICATA_SEGUNDOS = 900


def ler_meta(meta):
    achado = PADRAO_META.match((meta or "").strip())
    if not achado:
        return None, None
    h, mi, d, mo, a, autor = achado.groups()
    return f"{a}-{mo}-{d}T{h}:{mi}:00", autor


def _limpo(texto):
    return " ".join((texto or "").lower().split())


def _mesmo_texto(a, b):
    """Igual, ou um contém o começo do outro (legenda de imagem, link anexado, espaços)."""
    a, b = _limpo(a), _limpo(b)
    if not a or not b:
        return False
    trecho = min(len(a), len(b), 35)
    return a == b or a[:trecho] in b or b[:trecho] in a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arquivo")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--desde", default="2026-11-09")
    args = ap.parse_args()

    dados = json.load(open(args.arquivo, encoding="utf-8"))
    if args.aplicar:
        copia = f"{db.CAMINHO_BANCO}.antes-importacao-{datetime.now():%Y%m%d-%H%M%S}"
        shutil.copy2(db.CAMINHO_BANCO, copia)
        print("backup do banco:", copia)

    conexao = db.conectar()
    resumo = {"novas_lead": 0, "novas_lead_auto": 0, "novas_minhas": 0, "duplicadas": 0, "leads_para_humano": 0}
    try:
        for place_id, conversa in dados.items():
            lead = conexao.execute(
                "SELECT place_id, status, piloto_status FROM leads WHERE place_id = ?", (place_id,)
            ).fetchone()
            if not lead or conversa.get("erro"):
                continue
            existentes = [(r[0], r[1]) for r in conexao.execute(
                "SELECT texto, enviada_em FROM mensagens_conversa WHERE canal='maps' AND lead_ref=?", (place_id,))]
            registros = []
            for m in conversa.get("mensagens", []):
                quando, autor = ler_meta(m.get("meta"))
                texto = (m.get("texto") or "").strip()
                if not quando or not texto or quando[:10] < args.desde:
                    continue
                registros.append((quando, autor or "", texto, m.get("id") or ""))
            registros.sort()
            minhas_em = [q for q, a, _, _ in registros if NOME_VENDEDOR in a.lower()]
            houve_pessoa = houve_manual = False
            for quando, autor, texto, id_msg in registros:
                meu = NOME_VENDEDOR in autor.lower()
                duplicata = any(
                    _mesmo_texto(t, texto) and abs(
                        (datetime.fromisoformat(e) - datetime.fromisoformat(quando)).total_seconds())
                    <= JANELA_DUPLICATA_SEGUNDOS for t, e in existentes if e)
                if duplicata:
                    resumo["duplicadas"] += 1
                    continue
                automatica = False
                if not meu:
                    automatica = sinc.e_resposta_automatica(
                        texto, sinc.segundos_desde_minha_ultima(minhas_em, quando))
                chave = f"wa:{id_msg}" if id_msg else f"web:{place_id}:{quando}:{hash(texto) & 0xffffff:x}"
                gravou = True
                if args.aplicar:
                    gravou = _inserir_mensagem(
                        conexao, "maps", place_id, "vendedor" if meu else "lead",
                        texto[:sinc.MAX_CARACTERES_MENSAGEM_CONVERSA], quando, "whatsapp", chave,
                        automatica=automatica)
                if not gravou:
                    resumo["duplicadas"] += 1
                    continue
                if meu:
                    resumo["novas_minhas"] += 1
                    houve_manual = True
                elif automatica:
                    resumo["novas_lead_auto"] += 1
                else:
                    resumo["novas_lead"] += 1
                    houve_pessoa = True
            if args.aplicar and lead["piloto_status"] == "automatico" and (houve_pessoa or houve_manual):
                conexao.execute("UPDATE leads SET piloto_status='humano' WHERE place_id=?", (place_id,))
                resumo["leads_para_humano"] += 1
            if houve_pessoa and lead["status"] in sinc.STATUS_QUE_VIRAM_RESPONDEU and args.aplicar:
                agora = datetime.now().isoformat(timespec="seconds")
                conexao.execute("UPDATE leads SET status='respondeu', atualizado_em=? WHERE place_id=?", (agora, place_id))
                conexao.execute(
                    "INSERT INTO historico_status (place_id, status_anterior, status_novo, alterado_em) VALUES (?,?,?,?)",
                    (place_id, lead["status"], "respondeu", agora))
        if args.aplicar:
            conexao.commit()
    finally:
        conexao.close()
    print(("APLICADO" if args.aplicar else "SIMULAÇÃO"), json.dumps(resumo, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
