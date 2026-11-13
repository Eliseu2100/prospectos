"""Modelo visual dos e-mails de prospecção: cabeçalho com o logo, texto, assinatura e
rodapé de identificação e descadastro, nas cores da marca (identidade/design-guide.md).

HTML de e-mail usa tabela e estilo em linha (os clientes de e-mail ignoram CSS moderno)
e fontes seguras (Arial). As imagens vão embutidas no próprio e-mail (CID), sem depender
de endereço externo. A versão em texto simples sai junto, para quem não renderiza HTML.
"""

import html
import re

import db
import paths

AZUL = "#2563EB"
NAVY = "#0E1A2F"
CINZA = "#94A3B8"
TEXTO = "#1E293B"
TEXTO_2 = "#475569"

CID_LOGO = "logo-es"
CID_SIMBOLO = "simbolo-es"
LINHA_DESCADASTRO = 'Se não quiser receber mais mensagens minhas, é só responder com "descadastrar".'


def _arquivo(nome):
    caminho = paths.caminho_recurso("assets", "email", nome)
    return caminho if caminho.exists() else None


def imagens_inline():
    """[(cid, caminho)] das imagens que o HTML referencia e que existem no disco."""
    achadas = []
    for cid, nome in ((CID_LOGO, "logo.png"), (CID_SIMBOLO, "simbolo.png")):
        caminho = _arquivo(nome)
        if caminho:
            achadas.append((cid, caminho))
    return achadas


def _dados_assinatura(remetente_email):
    nome = (db.obter_config("vendedor_nome") or "Eliseu Souza").strip()
    numero = re.sub(r"\D", "", db.obter_config("aviso_whatsapp_numero") or "")
    return {
        "nome": nome,
        "cargo": (db.obter_config("smtp_assinatura") or "").strip() or "Criação de Sites Premium",
        "whatsapp_texto": f"({numero[:2]}) {numero[2:7]}-{numero[7:]}" if len(numero) == 11 else numero,
        "whatsapp_link": f"https://wa.me/55{numero}" if numero else "",
        "email": remetente_email,
    }


def texto_simples(corpo, remetente_email):
    a = _dados_assinatura(remetente_email)
    return (
        f"{corpo.strip()}\n\n--\n{a['nome']}\n{a['cargo']}\n"
        f"{('WhatsApp ' + a['whatsapp_texto'] + ' · ') if a['whatsapp_link'] else ''}{a['email']}\n\n"
        f"{LINHA_DESCADASTRO}\n"
    )


def _paragrafos_html(corpo):
    blocos = [b.strip() for b in re.split(r"\n\s*\n", corpo.strip()) if b.strip()]
    saida = []
    for bloco in blocos:
        seguro = html.escape(bloco).replace("\n", "<br>")
        seguro = re.sub(r"(https?://[^\s<]+)", rf'<a href="\1" style="color:{AZUL};text-decoration:none;">\1</a>', seguro)
        saida.append(
            f'<p style="margin:0 0 16px;font-size:15px;line-height:1.65;color:{TEXTO};">{seguro}</p>'
        )
    return "\n".join(saida)


def montar_html(corpo, remetente_email, com_imagens=True):
    a = _dados_assinatura(remetente_email)
    logo = (f'<img src="cid:{CID_LOGO}" width="170" alt="{html.escape(a["nome"])} · {a["cargo"]}" '
            f'style="display:block;height:auto;border:0;">') if com_imagens else \
        f'<span style="font-size:18px;font-weight:700;color:#FFFFFF;">{html.escape(a["nome"])}</span>'
    simbolo = (f'<td style="padding-right:14px;vertical-align:top;">'
               f'<img src="cid:{CID_SIMBOLO}" width="56" height="56" alt="" '
               f'style="display:block;border:0;border-radius:10px;"></td>') if com_imagens else ""
    whatsapp = (f'<a href="{a["whatsapp_link"]}" style="color:{AZUL};text-decoration:none;">'
                f'WhatsApp {a["whatsapp_texto"]}</a><br>') if a["whatsapp_link"] else ""
    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"></head>
<body style="margin:0;padding:0;background:#F4F6FA;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#F4F6FA;">
  <tr><td align="center" style="padding:24px 12px;">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:600px;background:#FFFFFF;border-radius:14px;overflow:hidden;font-family:Arial,Helvetica,sans-serif;">
      <tr><td style="background:{NAVY};padding:20px 28px;border-bottom:3px solid {AZUL};">{logo}</td></tr>
      <tr><td style="padding:28px 28px 8px;">
{_paragrafos_html(corpo)}
      </td></tr>
      <tr><td style="padding:8px 28px 26px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse;">
          <tr>
            {simbolo}
            <td style="vertical-align:top;border-left:2px solid {AZUL};padding-left:14px;">
              <div style="font-size:16px;font-weight:700;color:{NAVY};line-height:1.3;">{html.escape(a["nome"])}</div>
              <div style="font-size:13px;color:{TEXTO_2};letter-spacing:0.3px;margin-bottom:6px;">{a["cargo"]}</div>
              <div style="font-size:13px;line-height:1.7;">
                {whatsapp}
                <a href="mailto:{html.escape(a["email"])}" style="color:{AZUL};text-decoration:none;">{html.escape(a["email"])}</a>
              </div>
            </td>
          </tr>
        </table>
      </td></tr>
      <tr><td style="background:#F8FAFC;padding:16px 28px;border-top:1px solid #E2E8F0;font-size:12px;line-height:1.6;color:{TEXTO_2};">
        {html.escape(LINHA_DESCADASTRO)}
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>
"""
