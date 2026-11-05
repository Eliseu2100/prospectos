"""Pontos de prioridade de nicho, somados ao score do lead (rotas_leads.calcular_score).

Vem de um arquivo LOCAL opcional, `nichos_prioritarios.json` na pasta de dados
(%LOCALAPPDATA%\\SeriaxOS), no mesmo espírito do `playbook_nichos.json` do
`abordagem.py`: fica fora do repositório porque é uma decisão comercial do
Eliseu (`_memoria/estrategia.md` / `templates/cofre-abordagens/nichos-prioritarios.md`),
não um dado técnico do produto. Sem o arquivo, todo lead recebe 0 ponto extra -
o score cai de volta no comportamento de antes desta mudança.

Formato:
    {"prioritarios": [{"nicho": "Energia solar", "palavras": ["energia solar", ...],
                        "pontos": 8}, ...]}

Este módulo só soma pontos. Nunca decide excluir um lead da lista - os nichos
"fora_da_prospeccao" e "em_pausa" do mesmo arquivo continuam sendo critério
manual do Eliseu, não um filtro automático.
"""

import json
import logging
import unicodedata

import paths

logger = logging.getLogger(__name__)

ARQUIVO_NICHOS_PRIORITARIOS = "nichos_prioritarios.json"
TAMANHO_MINIMO_PALAVRA_CHAVE = 5
PONTOS_MAXIMOS = 10  # trava o bônus mesmo se o arquivo local declarar mais

_cache = {"mtime": None, "prioritarios": []}


def _normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def _carregar():
    """Lê o arquivo local (relido só quando ele muda). Ausente ou inválido = lista vazia,
    e nesse caso todo lead recebe 0 ponto de prioridade de nicho."""
    caminho = paths.caminho_dados(ARQUIVO_NICHOS_PRIORITARIOS)
    try:
        mtime = caminho.stat().st_mtime
    except OSError:
        return []
    if _cache["mtime"] != mtime:
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            prioritarios = [
                item for item in dados.get("prioritarios", [])
                if item.get("palavras") and isinstance(item.get("pontos"), (int, float))
            ]
        except (OSError, ValueError, AttributeError) as erro:
            logger.warning("nichos_prioritarios.json inválido (%s): %s", caminho, erro)
            prioritarios = []
        _cache.update({"mtime": mtime, "prioritarios": prioritarios})
    return _cache["prioritarios"]


def pontos_prioridade(categoria=None, nicho=None):
    """0 a PONTOS_MAXIMOS: quanto o nicho deste lead (categoria do Maps + nicho
    extraído da busca) coincide com um nicho prioritário do Eliseu. A palavra-chave
    mais longa encontrada vence quando mais de um item bate."""
    alvo = _normalizar(f"{categoria or ''} {nicho or ''}")
    if not alvo.strip():
        return 0
    melhor_pontos, tamanho_melhor = 0, 0
    for item in _carregar():
        for palavra in item["palavras"]:
            palavra = _normalizar(palavra)
            if len(palavra) >= TAMANHO_MINIMO_PALAVRA_CHAVE and palavra in alvo and len(palavra) > tamanho_melhor:
                melhor_pontos, tamanho_melhor = item["pontos"], len(palavra)
    return max(0, min(round(melhor_pontos), PONTOS_MAXIMOS))
