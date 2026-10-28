"""Diagnóstico das integrações ("Testar tudo" em Configurações) - não confundir
com diagnostico.py, que gera o PDF de diagnóstico do site de um lead.

Confere, de verdade, cada peça que o piloto automático usa, sem tocar em lead
nenhum e sem contar no limite diário:
1. Evolution API no ar e WhatsApp conectado;
2. envio pelo mesmo caminho do CRM (mensageiros.enviar_whatsapp) para o PRÓPRIO
   número conectado - aparece no chat "Você" do WhatsApp;
3. ida e volta: a mensagem enviada aparece na Evolution (é o que a
   sincronização lê para trazer as respostas dos clientes);
4. Telegram (envio real de mensagem de teste);
5. chaves de IA cadastradas (sem chamar as IAs, para não gastar cota).
"""

import time
from datetime import datetime

import db
import ia
import mensageiros

ESPERA_IDA_E_VOLTA_SEGUNDOS = (1, 2, 3)


def _item(nome, ok, detalhe):
    return {"nome": nome, "ok": ok, "detalhe": detalhe}


def verificar_whatsapp():
    itens = []
    try:
        estado = mensageiros.estado_whatsapp()
    except mensageiros.ErroEnvio as erro:
        return [_item("WhatsApp conectado", False, str(erro))]
    if estado != "open":
        return [_item("WhatsApp conectado", False,
                      f"A Evolution está no ar, mas o WhatsApp está '{estado}'. Reconecte pelo QR code.")]

    numero = mensageiros.numero_conectado()
    itens.append(_item("WhatsApp conectado", True, f"Número {numero[:4]}…{numero[-4:]} online."))

    texto = f"✅ Teste do Seriax OS ({datetime.now().strftime('%d/%m %H:%M')}): envio pelo CRM funcionando."
    try:
        id_msg, jid = mensageiros.enviar_whatsapp(numero, texto)
    except mensageiros.ErroEnvio as erro:
        itens.append(_item("Envio pelo CRM", False, str(erro)))
        return itens
    itens.append(_item("Envio pelo CRM", bool(id_msg),
                       "Mensagem enviada para o seu próprio número (chat \"Você\" no WhatsApp)."
                       if id_msg else "A Evolution aceitou, mas não devolveu o id da mensagem."))

    # ida e volta: a mensagem precisa aparecer no que a sincronização lê
    encontrada = False
    for espera in ESPERA_IDA_E_VOLTA_SEGUNDOS:
        time.sleep(espera)
        registros = mensageiros.buscar_mensagens(jid or f"{numero}@s.whatsapp.net", limite=20)
        if any((r.get("key") or {}).get("id") == id_msg for r in registros):
            encontrada = True
            break
    itens.append(_item("Leitura das conversas", encontrada,
                       "A mensagem enviada foi encontrada - as respostas dos clientes vão chegar no CRM."
                       if encontrada else
                       "A mensagem foi enviada, mas não apareceu na leitura da Evolution. "
                       "Confira se a Evolution está salvando mensagens."))
    return itens


def verificar_telegram():
    if not db.obter_config("telegram_bot_token"):
        return _item("Telegram", False, "Bot não configurado (cole o token do @BotFather em Configurações).")
    if not db.obter_config("telegram_chat_id"):
        try:
            mensageiros.descobrir_chat_telegram()
        except mensageiros.ErroEnvio as erro:
            return _item("Telegram", False, str(erro))
    try:
        mensageiros.enviar_telegram("✅ Teste do Seriax OS: avisos pelo Telegram funcionando.")
    except mensageiros.ErroEnvio as erro:
        return _item("Telegram", False, str(erro))
    return _item("Telegram", True, "Mensagem de teste enviada para o seu Telegram.")


def verificar_chaves_ia():
    configuradas = [ia.NOMES_AMIGAVEIS_PROVEDOR[p] for p in ia.ORDEM_PROVEDORES_IA if db.obter_config(p)]
    if not configuradas:
        return _item("Inteligência artificial", False, "Nenhuma chave de IA cadastrada.")
    detalhe = "Ordem de uso: " + " → ".join(configuradas)
    if not db.obter_config("claude"):
        detalhe += ". Sem a chave do Claude, quando o Gemini falhar quem responde é a Groq."
    return _item("Inteligência artificial", True, detalhe)


def rodar():
    itens = [*verificar_whatsapp(), verificar_telegram(), verificar_chaves_ia()]
    return {"ok": all(i["ok"] for i in itens), "itens": itens}
