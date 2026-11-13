"""Clientes de envio de mensagens: WhatsApp (Evolution API) e Telegram (Bot API).

Como as peças se encaixam:
- WhatsApp: a Evolution API (open source, roda local via Docker) conecta o SEU
  número por QR code e expõe uma API HTTP de envio. O ProspectOS só fala HTTP
  com ela - nunca automatiza a janela do WhatsApp Web.
- Telegram: bot oficial (BotFather). Bot não pode iniciar conversa com quem
  nunca falou com ele, então o uso aqui é avisar VOCÊ (resumo do dia, teste),
  não abordar lead frio.

Nenhuma função aqui toca o banco de leads: só lê configuração e faz HTTP.
As regras de negócio (limite diário, registro no histórico) ficam em rotas_envio.py.
"""

import logging
import os
import re

import requests

import db

logger = logging.getLogger(__name__)

TIMEOUT_HTTP_SEGUNDOS = 15
URL_API_TELEGRAM = "https://api.telegram.org"


class ErroEnvio(Exception):
    """Falha que já vem com mensagem amigável pro usuário final."""


# ---------------------------------------------------------------------------
# WhatsApp - Evolution API
# ---------------------------------------------------------------------------

def config_evolution():
    """Retorna (url_base, api_key, instancia) ou levanta ErroEnvio se faltar algo."""
    url = (db.obter_config("evolution_url") or "").strip().rstrip("/")
    chave = (db.obter_config("evolution_api_key") or "").strip()
    instancia = (db.obter_config("evolution_instancia") or "").strip()
    if not (url and chave and instancia):
        raise ErroEnvio(
            "WhatsApp não configurado. Preencha URL, chave e instância da Evolution API em Configurações."
        )
    return url, chave, instancia


def _evolution(metodo, caminho, corpo=None):
    url, chave, _ = config_evolution()
    try:
        resposta = requests.request(
            metodo, f"{url}{caminho}", json=corpo,
            headers={"apikey": chave}, timeout=TIMEOUT_HTTP_SEGUNDOS,
        )
    except requests.RequestException as erro:
        logger.warning("evolution inacessível em %s: %s", url, erro)
        raise ErroEnvio(
            "Não consegui falar com a Evolution API. Confira se o Docker está rodando "
            "(docker compose up -d na pasta evolution/) e se a URL está certa."
        ) from erro

    if resposta.status_code == 401:
        raise ErroEnvio("A Evolution API recusou a chave (401). Confira a chave em Configurações.")
    try:
        dados = resposta.json()
    except ValueError:
        dados = {}
    if resposta.status_code >= 400:
        logger.warning("evolution respondeu %s em %s: %s", resposta.status_code, caminho, dados)
        raise ErroEnvio(_mensagem_erro_evolution(resposta.status_code, dados))
    return dados


def _mensagem_erro_evolution(status, dados):
    texto = str(dados).lower()
    if "exists" in texto and "false" in texto:
        return "Esse número não tem WhatsApp."
    if status == 404:
        return "Instância não encontrada na Evolution API. Clique em 'Conectar' em Configurações para criá-la."
    return f"A Evolution API recusou o envio ({status})."


def estado_whatsapp():
    """'open' (conectado), 'connecting', 'close' ou 'inexistente'."""
    _, _, instancia = config_evolution()
    try:
        dados = _evolution("GET", f"/instance/connectionState/{instancia}")
    except ErroEnvio as erro:
        if "não encontrada" in str(erro):
            return "inexistente"
        raise
    return ((dados.get("instance") or {}).get("state")) or dados.get("state") or "close"


def conectar_whatsapp():
    """Cria a instância se ainda não existir e devolve o QR code (data URL base64)
    para escanear com o celular. Retorna None se já estiver conectado."""
    _, _, instancia = config_evolution()
    estado = estado_whatsapp()
    if estado == "open":
        return None
    if estado == "inexistente":
        dados = _evolution("POST", "/instance/create", {
            "instanceName": instancia,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
        })
        qrcode = (dados.get("qrcode") or {}).get("base64")
        if qrcode:
            return qrcode
    dados = _evolution("GET", f"/instance/connect/{instancia}")
    return dados.get("base64")


# ---------------------------------------------------------------------------
# E-mail (SMTP)
# ---------------------------------------------------------------------------

PORTA_SMTP_PADRAO = 587
TIMEOUT_SMTP_SEGUNDOS = 25


def config_smtp():
    """Dicionário com a configuração de envio por e-mail, ou levanta ErroEnvio se faltar algo."""
    host = (db.obter_config("smtp_host") or "").strip()
    usuario = (db.obter_config("smtp_usuario") or "").strip()
    senha = db.obter_config("smtp_senha") or ""
    if not (host and usuario and senha):
        raise ErroEnvio("E-mail não configurado. Preencha servidor, usuário e senha SMTP na página de e-mail.")
    try:
        porta = int(db.obter_config("smtp_porta") or PORTA_SMTP_PADRAO)
    except ValueError:
        porta = PORTA_SMTP_PADRAO
    return {
        "host": host,
        "porta": porta,
        "usuario": usuario,
        "senha": senha,
        "remetente_nome": (db.obter_config("smtp_remetente_nome") or "").strip(),
        "remetente_email": (db.obter_config("smtp_remetente_email") or "").strip() or usuario,
    }


def enviar_email(para, assunto, corpo, html=None, imagens=None, anexos=None):
    """Envia um e-mail: texto simples, com versão HTML opcional (e imagens embutidas por CID) e
    anexos. `imagens` = [(cid, caminho)], `anexos` = [caminho]. Devolve o Message-ID. Levanta
    ErroEnvio com mensagem amigável em qualquer falha - nada de exceção crua da rede na tela."""
    import smtplib
    import ssl
    from email.message import EmailMessage
    from email.utils import formataddr, formatdate, make_msgid

    cfg = config_smtp()
    mensagem = EmailMessage()
    mensagem["From"] = formataddr((cfg["remetente_nome"], cfg["remetente_email"]))
    mensagem["To"] = para
    mensagem["Subject"] = assunto
    mensagem["Date"] = formatdate(localtime=True)
    mensagem["Message-ID"] = make_msgid(domain=cfg["remetente_email"].split("@")[-1])
    # descadastro por resposta: quem escreve "descadastrar" entra na lista de bloqueio
    mensagem["List-Unsubscribe"] = f"<mailto:{cfg['remetente_email']}?subject=descadastrar>"
    mensagem.set_content(corpo)
    if html:
        mensagem.add_alternative(html, subtype="html")
        parte_html = mensagem.get_payload()[-1]
        for cid, caminho in imagens or []:
            with open(caminho, "rb") as f:
                parte_html.add_related(f.read(), maintype="image", subtype="png", cid=f"<{cid}>")
    for caminho in anexos or []:
        with open(caminho, "rb") as f:
            mensagem.add_attachment(f.read(), maintype="application", subtype="pdf",
                                    filename=os.path.basename(caminho))

    try:
        if cfg["porta"] == 465:
            servidor = smtplib.SMTP_SSL(cfg["host"], cfg["porta"], timeout=TIMEOUT_SMTP_SEGUNDOS,
                                        context=ssl.create_default_context())
        else:
            servidor = smtplib.SMTP(cfg["host"], cfg["porta"], timeout=TIMEOUT_SMTP_SEGUNDOS)
            servidor.starttls(context=ssl.create_default_context())
        with servidor:
            servidor.login(cfg["usuario"], cfg["senha"])
            servidor.send_message(mensagem)
    except smtplib.SMTPAuthenticationError as erro:
        raise ErroEnvio("O servidor recusou o usuário ou a senha. No Gmail, use uma senha de app.") from erro
    except smtplib.SMTPServerDisconnected as erro:
        raise ErroEnvio(
            "O servidor fechou a conexão logo depois de conectar. O motivo mais comum é senha errada: no Gmail "
            "precisa ser uma senha de app de 16 letras (myaccount.google.com/apppasswords), não a senha da conta."
        ) from erro
    except smtplib.SMTPRecipientsRefused as erro:
        raise ErroEnvio("O servidor recusou o endereço do destinatário.") from erro
    except (smtplib.SMTPException, OSError) as erro:
        logger.warning("falha ao enviar e-mail: %s", erro)
        raise ErroEnvio("Não consegui enviar o e-mail. Confira servidor, porta e conexão.") from erro
    return mensagem["Message-ID"]


def desconectar_whatsapp():
    """Desconecta o aparelho da Evolution (logout). A instância e o histórico enviado
    continuam; depois é só gerar um QR novo com `conectar_whatsapp`. Serve para refazer as
    chaves de criptografia quando a Evolution deixa de ler as respostas (erros "Bad MAC")."""
    _, _, instancia = config_evolution()
    estado = estado_whatsapp()
    if estado in ("inexistente", "close"):
        return False
    _evolution("DELETE", f"/instance/logout/{instancia}")
    return True


def numero_internacional(telefone):
    """Formato que a Evolution espera: só dígitos, com DDI 55."""
    digitos = re.sub(r"\D", "", telefone or "")
    if not digitos:
        return None
    if not digitos.startswith("55") or len(digitos) <= 11:
        digitos = "55" + digitos
    return digitos


def enviar_whatsapp(telefone, texto):
    """Envia e retorna (id_da_mensagem, jid). O jid é como o WhatsApp endereça
    a conversa - pode vir como @lid em vez do número, e a sincronização precisa
    dele pra achar as respostas."""
    _, _, instancia = config_evolution()
    numero = numero_internacional(telefone)
    if not numero:
        raise ErroEnvio("Este lead não tem telefone.")
    dados = _evolution("POST", f"/message/sendText/{instancia}", {"number": numero, "text": texto})
    chave = dados.get("key") or {}
    return chave.get("id"), chave.get("remoteJid")


def enviar_whatsapp_imagem(telefone, url_imagem, legenda=None):
    """Envia uma imagem (com legenda opcional) via Evolution API. Retorna
    (id_da_mensagem, jid), igual a enviar_whatsapp. `url_imagem` precisa ser uma
    URL pública - a Evolution baixa ela do servidor dela, não do nosso."""
    _, _, instancia = config_evolution()
    numero = numero_internacional(telefone)
    if not numero:
        raise ErroEnvio("Este lead não tem telefone.")
    corpo = {"number": numero, "mediatype": "image", "media": url_imagem}
    if legenda:
        corpo["caption"] = legenda
    dados = _evolution("POST", f"/message/sendMedia/{instancia}", corpo)
    chave = dados.get("key") or {}
    return chave.get("id"), chave.get("remoteJid")


def buscar_mensagens(jid, limite=100, campo="remoteJid"):
    """Mensagens mais recentes de uma conversa (a Evolution devolve da mais nova
    pra mais antiga). `campo="remoteJidAlt"` acha conversas endereçadas por
    @lid: o WhatsApp manda a resposta do contato com remoteJid=<código>@lid e o
    número de telefone só em remoteJidAlt."""
    _, _, instancia = config_evolution()
    dados = _evolution("POST", f"/chat/findMessages/{instancia}", {
        "where": {"key": {campo: jid}},
        "page": 1,
        "offset": limite,
    })
    return ((dados.get("messages") or {}).get("records")) or []


# ---------------------------------------------------------------------------
# Telegram - Bot API oficial
# ---------------------------------------------------------------------------

def _token_telegram():
    token = (db.obter_config("telegram_bot_token") or "").strip()
    if not token:
        raise ErroEnvio("Bot do Telegram não configurado. Cole o token do @BotFather em Configurações.")
    return token


def _telegram(metodo_api, corpo=None):
    token = _token_telegram()
    try:
        resposta = requests.post(f"{URL_API_TELEGRAM}/bot{token}/{metodo_api}", json=corpo or {},
                                 timeout=TIMEOUT_HTTP_SEGUNDOS)
        dados = resposta.json()
    except (requests.ConnectionError, requests.Timeout) as erro:
        # a internet funciona, mas o servidor do bot não responde: na prática é
        # bloqueio de rede (operadora, roteador, antivírus/firewall)
        raise ErroEnvio(
            "Seu computador não consegue alcançar o servidor do Telegram (api.telegram.org). "
            "Costuma ser bloqueio da rede, do roteador ou do antivírus/firewall."
        ) from erro
    except (requests.RequestException, ValueError) as erro:
        raise ErroEnvio("Não consegui falar com o Telegram. Confira sua internet.") from erro
    if not dados.get("ok"):
        descricao = dados.get("description", "erro desconhecido")
        if resposta.status_code == 401:
            raise ErroEnvio("O Telegram recusou o token do bot. Confira em Configurações.")
        raise ErroEnvio(f"O Telegram recusou a mensagem: {descricao}")
    return dados.get("result")


def descobrir_chat_telegram():
    """Pega o chat de quem mandou a mensagem mais recente pro bot. O usuário
    manda /start pro bot e clica em 'Detectar' - sem precisar caçar o chat_id."""
    atualizacoes = _telegram("getUpdates") or []
    for atualizacao in reversed(atualizacoes):
        mensagem = atualizacao.get("message") or atualizacao.get("edited_message") or {}
        chat = mensagem.get("chat") or {}
        if chat.get("id"):
            return str(chat["id"]), chat.get("first_name") or chat.get("title") or ""
    raise ErroEnvio("Nenhuma mensagem encontrada. Mande /start para o seu bot no Telegram e tente de novo.")


def enviar_telegram(texto, chat_id=None):
    _token_telegram()
    chat_id = chat_id or db.obter_config("telegram_chat_id")
    if not chat_id:
        raise ErroEnvio("Chat do Telegram não definido. Mande /start pro bot e clique em 'Detectar chat'.")
    _telegram("sendMessage", {"chat_id": chat_id, "text": texto})


def numero_conectado():
    """Número do WhatsApp conectado na Evolution (só dígitos, com DDI) ou None."""
    _, _, instancia = config_evolution()
    dados = _evolution("GET", f"/instance/fetchInstances?instanceName={instancia}")
    instancia_info = dados[0] if isinstance(dados, list) and dados else dados
    jid = (instancia_info or {}).get("ownerJid") or ""
    return re.sub(r"\D", "", jid.split("@")[0]) or None


# ---------------------------------------------------------------------------
# Avisos para o vendedor (lead respondeu, precisa de você, prévia combinada)
# ---------------------------------------------------------------------------

def avisar_vendedor(texto):
    """Manda o aviso por todos os canais configurados: Telegram e/ou WhatsApp
    num número do vendedor. Nunca levanta exceção - aviso não pode derrubar o
    piloto. Retorna a lista de canais que funcionaram."""
    canais = []
    if db.obter_config("telegram_bot_token") and db.obter_config("telegram_chat_id"):
        try:
            enviar_telegram(texto)
            canais.append("telegram")
        except ErroEnvio as erro:
            logger.warning("aviso pelo Telegram falhou: %s", erro)
    numero = (db.obter_config("aviso_whatsapp_numero") or "").strip()
    if numero:
        try:
            enviar_whatsapp(numero, texto)
            canais.append("whatsapp")
        except ErroEnvio as erro:
            logger.warning("aviso pelo WhatsApp falhou: %s", erro)
    return canais
