"""Consulta de CNPJ na Receita Federal (via BrasilAPI), pra qualificar o poder
aquisitivo do lead antes de investir tempo nele - pedido do Eliseu depois do
vídeo "Estou prospectando clientes com Grok Bot e Claude Code": focar em
empresas que pagam sem sentir, não MEI.

Por que isso só funciona com o CNPJ em mãos, não em lote: o Maps não devolve
CNPJ, e não existe hoje uma API gratuita e confiável de busca por nome da
empresa (só por número exato - BrasilAPI, ReceitaWS e Minha Receita são
assim). As opções de busca por nome são pagas (CNPJ.ws Comercial) ou ainda não
lançaram (CNPJ Aberto). Então o fluxo real é: o Eliseu pede o CNPJ no
WhatsApp/na call (comum nessa etapa, é o mesmo dado que vai pro contrato) e
consulta aqui antes de montar a proposta - não é um filtro automático da
busca.
"""

import logging
import re
from datetime import date

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://brasilapi.com.br/api/cnpj/v1"
TIMEOUT_SEGUNDOS = 10
IDADE_MINIMA_MESES_TICKET_ALTO = 24


class ErroConsultaCnpj(Exception):
    """Erro amigável pra mostrar na tela - nunca a exceção crua da rede."""


def cnpj_limpo(cnpj_bruto):
    """Só os 14 dígitos, sem pontuação."""
    return re.sub(r"\D", "", cnpj_bruto or "")


def cnpj_valido(cnpj):
    """Checagem de formato (14 dígitos) - não recalcula os dígitos verificadores,
    isso a própria Receita confere; aqui é só pra não gastar a requisição à toa."""
    return len(cnpj) == 14 and cnpj.isdigit() and len(set(cnpj)) > 1


def _idade_em_meses(data_inicio_atividade):
    if not data_inicio_atividade:
        return None
    try:
        ano, mes, dia = (int(parte) for parte in data_inicio_atividade.split("-"))
        inicio = date(ano, mes, dia)
    except (ValueError, AttributeError):
        return None
    hoje = date.today()
    return (hoje.year - inicio.year) * 12 + (hoje.month - inicio.month)


def consultar_cnpj(cnpj_bruto):
    """Consulta o CNPJ na Receita (via BrasilAPI, gratuita, sem chave) e devolve
    um resumo com o que importa pra qualificar o lead. Levanta ErroConsultaCnpj
    com mensagem pronta pra tela em caso de formato inválido, CNPJ não
    encontrado, limite de requisições ou falha de rede."""
    cnpj = cnpj_limpo(cnpj_bruto)
    if not cnpj_valido(cnpj):
        raise ErroConsultaCnpj("CNPJ inválido. Confira os 14 números, sem letras faltando.")

    try:
        resposta = requests.get(f"{BASE_URL}/{cnpj}", timeout=TIMEOUT_SEGUNDOS)
    except requests.exceptions.RequestException:
        logger.exception("falha de rede consultando CNPJ")
        raise ErroConsultaCnpj(
            "Não consegui falar com a Receita Federal agora. Tente de novo em instantes."
        ) from None

    if resposta.status_code == 404:
        raise ErroConsultaCnpj("CNPJ não encontrado na Receita Federal. Confira o número.")
    if resposta.status_code == 429:
        raise ErroConsultaCnpj("Muitas consultas seguidas. Espere um minuto e tente de novo.")
    if resposta.status_code != 200:
        logger.error("BrasilAPI respondeu %s para %s", resposta.status_code, cnpj)
        raise ErroConsultaCnpj("A consulta de CNPJ falhou. Tente de novo em instantes.")

    try:
        dados = resposta.json()
    except ValueError:
        raise ErroConsultaCnpj("A Receita devolveu uma resposta que não consegui entender.") from None

    mei = bool(dados.get("opcao_pelo_mei"))
    situacao = (dados.get("descricao_situacao_cadastral") or "").upper()
    ativa = situacao == "ATIVA"
    idade_meses = _idade_em_meses(dados.get("data_inicio_atividade"))
    ticket_alto_provavel = (
        not mei and ativa and idade_meses is not None and idade_meses >= IDADE_MINIMA_MESES_TICKET_ALTO
    )

    return {
        "cnpj": cnpj,
        "razao_social": dados.get("razao_social"),
        "nome_fantasia": dados.get("nome_fantasia"),
        "mei": mei,
        "porte": dados.get("porte"),
        "situacao_cadastral": dados.get("descricao_situacao_cadastral"),
        "natureza_juridica": dados.get("natureza_juridica"),
        "capital_social": dados.get("capital_social"),
        "data_inicio_atividade": dados.get("data_inicio_atividade"),
        "idade_meses": idade_meses,
        "ticket_alto_provavel": ticket_alto_provavel,
    }
