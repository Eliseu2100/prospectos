"""Método de abordagem usado pela IA: como abrir conversa no primeiro contato,
a cadência de follow-up de quem não respondeu, como responder às objeções
comuns e o recado para quando quem responde é um robô de atendimento.

As regras aqui são genéricas e escritas para o fluxo deste app (sem preço por
texto além do que estiver na oferta, prévia combinada para o dia seguinte,
fechamento com o vendedor).

A dor típica de cada nicho vem de um arquivo LOCAL opcional,
`playbook_nichos.json` na pasta de dados (%LOCALAPPDATA%\\SeriaxOS). Ele não
fica no repositório porque pode conter material de uso pessoal do vendedor.
Formato:
    {"nichos": [{"nicho": "Barbearia", "palavras": ["barbearia", "barber"],
                 "dor": "frase da dor na língua do dono",
                 "venda_primeiro": "o que oferecer primeiro"}]}
Sem o arquivo, tudo funciona; a IA só não recebe a dor do nicho.
"""

import json
import logging
import random
import unicodedata

import paths

logger = logging.getLogger(__name__)

ARQUIVO_PLAYBOOK_NICHOS = "playbook_nichos.json"
TAMANHO_MINIMO_PALAVRA_CHAVE = 5

# ---------------------------------------------------------------------------
# Primeiro contato
# ---------------------------------------------------------------------------

REGRAS_PRIMEIRO_CONTATO = """Método do primeiro contato (vale acima de qualquer outra orientação de estilo):
- A primeira mensagem NÃO vende: ela só abre a conversa. Nada de listar serviços, falar de prévia, preço ou marcar horário. Só uma coisa de apresentação é obrigatória: dizer em meia frase quem você é e o que faz (ex.: "aqui é o Eliseu, crio sites para negócios locais"). Quem recebe mensagem de desconhecido precisa saber com quem fala antes de responder.
- Cabe numa tela de celular sem rolar: 2 ou 3 frases curtas, idealmente menos de 280 caracteres.
- Termina com UMA pergunta só, que o dono consegue responder de cabeça. Mensagem que pede duas coisas não recebe resposta.
- Fale do negócio DELE (clientes, agenda, pedidos), nunca da sua ferramenta ou de como você trabalha.
- Personalize com um fato REAL e verificável dos dados fornecidos (a nota, o número de avaliações, o site fora do ar, não ter site). Elogio genérico ("adorei o perfil") denuncia disparo em massa.
- Zero emoji, zero travessão (— ou –), zero lista. Escreva como alguém falaria com um conhecido; se soaria robô lido em voz alta, reescreva."""

# Estruturas de abertura. A escolha é feita em Python (variedade e coerência
# com os dados do lead); o modelo só escreve dentro da estrutura sorteada.
ESTRUTURAS_ABERTURA = {
    "observacao": (
        "Observação cuidadosa: só use esta abertura se o problema informado for algo que o dono "
        "confirma em 5 segundos abrindo o link (ex.: o endereço do perfil dá erro ao abrir). Diga o "
        "fato em tom de aviso útil, sem julgar o trabalho dele e sem concluir nada sobre vendas, e "
        "pergunte se ele já sabia. Se o problema for lentidão, 'não seguro', celular ou qualquer "
        "coisa que depende de aparelho ou navegador, NÃO use: troque por uma pergunta sobre como o "
        "cliente novo chega hoje. Falha apontada que o dono desmente na hora queima a conversa."
    ),
    "elogio_e_lacuna": (
        "Elogio verdadeiro + lacuna: reconheça algo específico e real (a nota alta com muitas "
        "avaliações), mostre a lacuna (quem pesquisa no Google fora do Maps não encontra um site "
        "deles) e pergunte, sem acusar, se é falta de tempo ou se ainda não tinham pensado nisso."
    ),
    "como_chega_cliente": (
        "Pergunta de diagnóstico: pergunte, de forma direta e curiosa, se hoje o cliente novo chega "
        "mais por indicação ou pela internet. Pode citar um fato real deles numa frase antes."
    ),
    "teste_do_google": (
        "Teste do Google: pergunte se, quando alguém da cidade procura pelo tipo de serviço deles no "
        "Google, encontra eles fácil ou acha o concorrente primeiro. Sem aula de internet."
    ),
}

NOTA_ELOGIAVEL = 4.5
AVALIACOES_ELOGIAVEIS = 30


def escolher_estrutura_abertura(site_status, site_problemas, nota, num_avaliacoes):
    """Escolhe a estrutura da primeira mensagem a partir do que dá pra afirmar
    com verdade sobre o lead. Retorna a chave de ESTRUTURAS_ABERTURA."""
    opcoes = ["como_chega_cliente", "teste_do_google"]
    if site_status == "site_ruim" and site_problemas:
        opcoes += ["observacao", "observacao"]  # problema concreto é a melhor abertura
    try:
        reputacao_forte = float(nota or 0) >= NOTA_ELOGIAVEL and int(num_avaliacoes or 0) >= AVALIACOES_ELOGIAVEIS
    except (TypeError, ValueError):
        reputacao_forte = False
    if reputacao_forte and site_status != "site_ruim":
        opcoes.append("elogio_e_lacuna")
    return random.choice(opcoes)


# ---------------------------------------------------------------------------
# Follow-up de quem não respondeu
# ---------------------------------------------------------------------------

# dias depois do primeiro contato em que sai cada follow-up (1º, 2º, 3º, 4º).
# O 4º é a despedida: depois dele o piloto não manda mais nada.
CADENCIA_FOLLOWUP_DIAS = [2, 5, 9, 14]

ANGULOS_FOLLOWUP = {
    1: (
        "Novo motivo para responder (o link do site de exemplo é anexado depois, por Python): em uma "
        "frase, diga o que o exemplo mostra de útil para o negócio DELE (ex.: as instalações já feitas "
        "num lugar só, o pedido de orçamento a um toque) e termine com uma pergunta concreta que se "
        "responde em uma palavra (ex.: 'Posso montar um parecido com as fotos de vocês?'). Proibido: "
        "'subir a conversa', 'não se perder na correria', 'é só me avisar que não insisto' e qualquer "
        "variação, porque virou assinatura de disparo em massa e convida o 'não'. Sem culpa, sem 'vi que "
        "você visualizou'."
    ),
    2: (
        "Novo ângulo: troque a pergunta original por um problema típico desse tipo de negócio "
        "(use a dor do nicho, se informada, na língua do dono, sem estatística inventada), diga que "
        "olhou o deles de novo e acha que dá pra resolver rápido, e pergunte se ele quer que você "
        "diga o que viu."
    ),
    3: (
        "Resumo em uma linha: imagine que ele não leu nada antes. Em uma frase, diga o que você "
        "notou de concreto no negócio dele (dados reais) e o que isso custa em cliente; feche dizendo "
        "que, se quiser ver, você está por aqui. Sem cobrar resposta."
    ),
    4: (
        "Despedida digna: avise com leveza que é a sua última mensagem, que entendeu que agora não é "
        "o momento, que não vai mais escrever para não incomodar e que o contato fica aqui se um dia "
        "fizer sentido. Deseje sucesso. Nenhuma pergunta e nenhuma oferta."
    ),
}


def angulo_followup(numero):
    """Orientação do follow-up número `numero` (1 em diante). Do 4º em diante
    é sempre a despedida."""
    return ANGULOS_FOLLOWUP[min(max(int(numero), 1), max(ANGULOS_FOLLOWUP))]


# ---------------------------------------------------------------------------
# Objeções (usado nas respostas do piloto)
# ---------------------------------------------------------------------------

GUIA_OBJECOES = """Como responder às objeções mais comuns (curto, sem textão, sempre devolvendo UMA pergunta e puxando para o próximo passo, que é mostrar uma prévia do site DELE):
- "O que exatamente você faz?": resuma o resultado numa frase (fazer quem já procura esse serviço na cidade achar e escolher o negócio dele em vez do concorrente), diga que o formato depende do caso e devolva a pergunta: hoje o cliente novo chega por onde? Nunca despeje lista de serviços.
- "Tá caro" dito ANTES de qualquer valor ter sido conversado: concorde sem discutir com o bolso dele e convide a comparar com quanto custa por mês continuar sem aparecer para quem procura. Se o "caro" vier depois de um valor passado, é negociação: passe para o humano.
- "Já tenho quem faça": valide a decisão e pergunte só se essa pessoa consegue entregar na velocidade que ele precisa. Nunca critique o trabalho de outro profissional.
- "Isso é feito com IA?": seja honesto, sem pedir desculpa: você usa tecnologia no processo como qualquer profissional usa boas ferramentas, mas o que ele recebe é o resultado. Ofereça mostrar uma prévia do site dele para ele julgar pelo resultado.
- "Vou fazer eu mesmo" / "tem ferramenta grátis": concorde que dá para fazer; o que você entrega é o resto (o texto certo para virar cliente, o que o Google exige, o acabamento que passa confiança e as horas dele de volta). Diga que, se travar, pode te chamar.
- "O Instagram já me serve": não discuta nem diminua o Instagram; diga que o site atende quem pesquisa no Google e quer entender a empresa sem abrir post por post, e pergunte se hoje chega pedido de quem não conhecia a empresa.
- "Vivo de indicação": concorde; o site entra depois da indicação, porque quem recebe o nome costuma pesquisar antes de ligar. Pergunte se hoje essa pessoa encontra o trabalho deles.
- "Vou pensar": aceite e pergunte com sinceridade se ficou alguma dúvida que você possa esclarecer ou se é o momento que não é bom.
- "Me chama depois" / "mês que vem": aceite sem insistir e pergunte o que muda até lá, para você voltar com algo útil. Quando ele disser QUANDO retomar, passe para o humano com o motivo "retomar em <quando>".
- "Já temos site" / "o site está no ar" / "nosso site ranqueia bem": nunca defenda a observação feita antes nem rebata com dado técnico (SEO, velocidade, nota de ferramenta). Reconheça que errou na leitura em uma frase, sem pedir desculpa longa, e faça UMA pergunta de curiosidade sobre o resultado dele (de onde vêm os pedidos de orçamento hoje, o que ele gostaria que o site fizesse a mais). Se ele disser que está satisfeito, encerre com educação.
- "Recebo isso o tempo todo" / "todo dia aparece alguém vendendo site": concorde sem se defender, diga em uma frase o que é diferente (você fala direto com quem cria, sem agência no meio, e o primeiro passo é só ver um exemplo, sem compromisso) e, se ele não mostrar abertura, encerre agradecendo a franqueza. Nunca insista depois de uma queixa de excesso de abordagem.
- "Você trabalha para agência ou por conta própria?": responda a verdade em uma frase (por conta própria, falando direto com o dono) e devolva uma pergunta curta. Passe para o humano se ele quiser parceria ou revenda.
- "Já fechamos com outra empresa" / "já estamos criando o site": parabenize em uma frase, não compare nem critique, peça para guardar o contato caso o projeto não saia como esperado e encerre.
- Elogio com crítica de posicionamento ("sua abordagem foi genérica", "faltou pesquisar o modelo da empresa"): agradeça o feedback sem bajular, não rebata nenhum ponto, e passe para o humano com o motivo "feedback sobre a abordagem" para o Eliseu decidir se responde.
- Atendente virtual de IA ("Já conectei você com nossa equipe", "vou encaminhar para o Rodrigo", pergunta qual o foco da proposta): é um robô que parece pessoa e abre a porta para você mandar proposta e dados a quem não decide. Não mande proposta, preço, e-mail nem portfólio para ele. Peça só uma coisa: o nome e o contato do responsável pelo marketing ou o dono, e passe para o humano com o motivo "atendente de IA encaminhou à equipe".
- Quem respondeu não é o dono (atendente, recepção, funcionário que diz que vai repassar ou que passa outro contato): passe para o humano com o motivo "falar com o dono", incluindo o contato se ele mandou."""


# ---------------------------------------------------------------------------
# Robô de atendimento
# ---------------------------------------------------------------------------

# Escrito em Python (sem IA): é curto, sempre igual em essência, e precisa sair
# mesmo com todos os provedores fora. Sorteado pra não repetir palavra por palavra.
RECADOS_PARA_ROBO = [
    "Oi! Vi que aqui cai no atendimento automático, então vou ser direto: não sou cliente, é um "
    "assunto rápido com quem é responsável pela {nome}. Qual o melhor jeito de falar com essa "
    "pessoa? Pode ser outro número ou e-mail.",
    "Oi, tudo bem? Sei que este é o canal de atendimento, então já adianto: "
    "não sou cliente, é um assunto comercial rápido com o dono ou dona da {nome}. Como consigo falar "
    "com ele(a)? Pode ser outro número ou e-mail.",
    "Olá! Como aqui é o atendimento automático, vou direto ao ponto: não sou cliente, queria falar "
    "rapidinho com quem cuida da {nome}. Qual o melhor caminho até essa pessoa: outro número "
    "ou e-mail?",
]


def recado_para_robo(nome_empresa):
    return random.choice(RECADOS_PARA_ROBO).format(nome=nome_empresa or "empresa")


# ---------------------------------------------------------------------------
# Dor do nicho (arquivo local opcional)
# ---------------------------------------------------------------------------

_cache_nichos = {"mtime": None, "nichos": []}


def _normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def _carregar_nichos():
    """Lê o playbook local (relido só quando o arquivo muda). Arquivo ausente
    ou inválido = lista vazia."""
    caminho = paths.caminho_dados(ARQUIVO_PLAYBOOK_NICHOS)
    try:
        mtime = caminho.stat().st_mtime
    except OSError:
        return []
    if _cache_nichos["mtime"] != mtime:
        try:
            dados = json.loads(caminho.read_text(encoding="utf-8"))
            nichos = [n for n in dados.get("nichos", []) if n.get("dor") and n.get("palavras")]
        except (OSError, ValueError, AttributeError) as erro:
            logger.warning("playbook de nichos inválido (%s): %s", caminho, erro)
            nichos = []
        _cache_nichos.update({"mtime": mtime, "nichos": nichos})
    return _cache_nichos["nichos"]


def ficha_do_nicho(categoria=None, nicho=None):
    """A ficha do playbook que melhor casa com a categoria/nicho do lead (a
    palavra-chave mais longa encontrada vence), ou None."""
    alvo = _normalizar(f"{categoria or ''} {nicho or ''}")
    if not alvo.strip():
        return None
    melhor, tamanho_melhor = None, 0
    for ficha in _carregar_nichos():
        for palavra in ficha["palavras"]:
            palavra = _normalizar(palavra)
            if len(palavra) >= TAMANHO_MINIMO_PALAVRA_CHAVE and palavra in alvo and len(palavra) > tamanho_melhor:
                melhor, tamanho_melhor = ficha, len(palavra)
    return melhor


def bloco_dor_do_nicho(categoria=None, nicho=None):
    """Linhas prontas pro prompt com a dor típica do nicho, ou "" se não houver."""
    ficha = ficha_do_nicho(categoria, nicho)
    if not ficha:
        return ""
    linhas = [
        "",
        f"Dor típica desse tipo de negócio ({ficha['nicho']}), na língua do dono. Use só como pano de "
        "fundo para soar como quem entende do ramo: se citar, fale como algo comum no ramo (\"muito negócio "
        "assim...\"), nunca como fato sobre ESTE negócio, e sem inventar números:",
        f'"{ficha["dor"]}"',
    ]
    if ficha.get("venda_primeiro"):
        linhas.append(f"O que costuma resolver essa dor: {ficha['venda_primeiro']}")
    if ficha.get("regras_nicho"):
        linhas.append(f"Regras desse ramo (obrigatórias): {ficha['regras_nicho']}")
    return "\n".join(linhas) + "\n"
