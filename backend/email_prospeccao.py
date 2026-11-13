"""Achar e-mails de empresas para a prospecção por e-mail.

Duas fontes, as duas de dado público:
- `importar_dos_leads`: lê o e-mail publicado no site de cada lead que o CRM já tem
  (link mailto, página de contato). Já vem separado por nicho e cidade.
- `importar_receita`: lê o arquivo aberto de Estabelecimentos da Receita Federal
  (dados abertos do CNPJ) e filtra por atividade (CNAE), UF e município. Acha empresa
  sem site, mas o e-mail cadastral costuma ser o do contador: os que parecem de
  contabilidade são descartados.

Nenhuma das duas envia nada. Quem pediu para sair (lista `email_descadastros`) nunca
entra de novo.
"""

import csv
import html
import ipaddress
import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

TIMEOUT_SITE_SEGUNDOS = 8
MAX_BYTES_PAGINA = 1_500_000
MAX_PAGINAS_CONTATO = 2
CABECALHOS = {"User-Agent": "Mozilla/5.0 (compatible; SeriaxOS/1.0; leitura de e-mail público de contato)"}

REGEX_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
REGEX_LINK_CONTATO = re.compile(r'href=["\']([^"\']*(?:contato|contact|fale-conosco|atendimento|sobre)[^"\']*)["\']', re.I)
SUFIXOS_DE_ARQUIVO = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".css", ".js", ".woff", ".woff2")
DOMINIOS_IGNORADOS = {
    "example.com", "exemplo.com", "email.com", "seudominio.com.br", "dominio.com.br", "domain.com",
    "sentry.io", "wixpress.com", "godaddy.com", "wordpress.com", "sentry-next.wixpress.com",
}
PREFIXOS_IGNORADOS = ("noreply", "no-reply", "naoresponda", "nao-responda", "donotreply", "mailer-daemon", "postmaster")
PREFIXOS_PREFERIDOS = ("contato", "comercial", "vendas", "orcamento", "atendimento", "falecom", "contact", "info")
TERMOS_CONTABILIDADE = ("contab", "contador", "escritorio", "assessoria")


def email_valido(email):
    email = (email or "").strip().lower()
    if len(email) > 120 or not REGEX_EMAIL.fullmatch(email):
        return False
    local, dominio = email.rsplit("@", 1)
    if dominio in DOMINIOS_IGNORADOS or email.endswith(SUFIXOS_DE_ARQUIVO):
        return False
    if local.startswith(PREFIXOS_IGNORADOS) or ".." in email:
        return False
    return True


def parece_contabilidade(email):
    return any(termo in (email or "").lower() for termo in TERMOS_CONTABILIDADE)


def _dominio_do_site(url):
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _host_seguro(url):
    """Só http/https e nunca endereço interno: a leitura de site não pode ser usada para
    alcançar a rede local."""
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.hostname:
        return False
    host = partes.hostname.lower()
    if host in ("localhost",) or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        return True


def extrair_emails_de_html(texto_html, dominio_site=""):
    """E-mails encontrados no HTML (mailto e texto), sem repetição. Os do domínio do próprio
    site vêm primeiro, depois os de nome mais comercial (contato, comercial...)."""
    texto = html.unescape(texto_html or "")
    achados = []
    for email in REGEX_EMAIL.findall(texto):
        email = email.strip(".").lower()
        if email_valido(email) and email not in achados:
            achados.append(email)

    def prioridade(email):
        local, dominio = email.rsplit("@", 1)
        do_site = bool(dominio_site) and (dominio == dominio_site or dominio.endswith("." + dominio_site))
        comercial = local.startswith(PREFIXOS_PREFERIDOS)
        return (0 if do_site else 1, 0 if comercial else 1)

    return sorted(achados, key=prioridade)


def _baixar(url):
    if not _host_seguro(url):
        return ""
    resposta = requests.get(url, headers=CABECALHOS, timeout=TIMEOUT_SITE_SEGUNDOS, stream=True)
    if resposta.status_code >= 400:
        return ""
    conteudo = resposta.raw.read(MAX_BYTES_PAGINA, decode_content=True)
    return conteudo.decode(resposta.encoding or "utf-8", errors="ignore")


def buscar_emails_do_site(url):
    """Lê a página inicial e até duas páginas de contato. Devolve a lista de e-mails (a melhor
    primeiro) ou [] se o site não abrir ou não publicar e-mail."""
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    dominio = _dominio_do_site(url)
    try:
        pagina = _baixar(url)
    except requests.RequestException as erro:
        logger.info("site %s não abriu para ler e-mail: %s", url, erro)
        return []
    emails = extrair_emails_de_html(pagina, dominio)
    if not emails:
        vistos = set()
        for caminho in REGEX_LINK_CONTATO.findall(pagina):
            destino = urljoin(url, caminho)
            if destino in vistos or _dominio_do_site(destino) != dominio:
                continue
            vistos.add(destino)
            try:
                emails += [e for e in extrair_emails_de_html(_baixar(destino), dominio) if e not in emails]
            except requests.RequestException:
                continue
            if len(vistos) >= MAX_PAGINAS_CONTATO or emails:
                break
    return emails


def _agora():
    return datetime.now().isoformat(timespec="seconds")


def _descadastrado(conexao, email):
    return conexao.execute("SELECT 1 FROM email_descadastros WHERE email = ?", (email,)).fetchone() is not None


def inserir_email_lead(conexao, empresa, email, setor=None, cidade=None, site_url=None,
                       fonte="manual", origem_ref=None, cnpj=None):
    """Grava um lead de e-mail. Retorna o id, ou None se o e-mail for inválido, de
    contabilidade, já existir ou estiver na lista de descadastro."""
    email = (email or "").strip().lower()
    if not email_valido(email) or parece_contabilidade(email) or _descadastrado(conexao, email):
        return None
    agora = _agora()
    cursor = conexao.execute(
        "INSERT OR IGNORE INTO email_leads "
        "(empresa, email, setor, cidade, site_url, fonte, origem_ref, cnpj, criado_em, atualizado_em) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ((empresa or email.split("@")[0]).strip()[:150], email, setor, cidade, site_url, fonte,
         origem_ref, cnpj, agora, agora),
    )
    return cursor.lastrowid if cursor.rowcount else None


def importar_dos_leads(conexao, progresso=None, parar=None):
    """Percorre os leads do Maps que têm site e grava o e-mail público de cada um. `progresso`
    é um dict atualizado a cada lead ({processados, total, novos}); `parar` é um Event."""
    import ia  # import tardio: evita ciclo e deixa o módulo testável sem as chaves de IA

    leads = conexao.execute(
        "SELECT place_id, nome, categoria, nicho, endereco, cidade, site_url FROM leads "
        "WHERE site_url IS NOT NULL AND site_url != '' AND status != 'ignorado' "
        "AND place_id NOT IN (SELECT origem_ref FROM email_leads WHERE origem_ref IS NOT NULL)"
    ).fetchall()
    if progresso is not None:
        progresso.update({"processados": 0, "total": len(leads), "novos": 0})
    for lead in leads:
        if parar is not None and parar.is_set():
            break
        emails = buscar_emails_do_site(lead["site_url"])
        for email in emails[:1]:  # um e-mail por empresa: o melhor
            novo = inserir_email_lead(
                conexao, ia.nome_curto_empresa(lead["nome"]), email,
                setor=lead["nicho"] or lead["categoria"],
                cidade=ia.cidade_do_endereco(lead["endereco"], lead["cidade"]),
                site_url=lead["site_url"], fonte="site", origem_ref=lead["place_id"],
            )
            if novo and progresso is not None:
                progresso["novos"] += 1
        conexao.commit()
        if progresso is not None:
            progresso["processados"] += 1
    return progresso


# Colunas do arquivo Estabelecimentos da Receita (sem cabeçalho, separador ";", Latin-1).
COL_CNPJ_BASICO, COL_ORDEM, COL_DV = 0, 1, 2
COL_FANTASIA, COL_SITUACAO, COL_CNAE = 4, 5, 11
COL_UF, COL_MUNICIPIO, COL_EMAIL = 19, 20, 27
SITUACAO_ATIVA = "02"


def carregar_municipios(arquivo):
    """{codigo: nome} do arquivo Municipios da Receita (codigo;NOME)."""
    municipios = {}
    with open(arquivo, encoding="latin-1", newline="") as f:
        for linha in csv.reader(f, delimiter=";"):
            if len(linha) >= 2:
                municipios[linha[0].strip('" ')] = linha[1].strip('" ').title()
    return municipios


def importar_receita(conexao, arquivo, cnaes, uf, municipio=None, municipios_arquivo=None,
                     setor=None, limite=None):
    """Importa empresas ativas da base aberta da Receita. `cnaes` são prefixos (só dígitos,
    ex.: "4321", "7112"); `uf` a sigla; `municipio` o nome (exige `municipios_arquivo`).
    Retorna {"importados", "ignorados"}."""
    prefixos = tuple(re.sub(r"\D", "", c) for c in (cnaes or []) if re.sub(r"\D", "", c))
    uf = (uf or "").strip().upper()
    if not prefixos or len(uf) != 2:
        raise ValueError("Informe ao menos um CNAE e a UF (2 letras).")
    nomes_municipios = {}
    codigos_alvo = None
    if municipios_arquivo:
        nomes_municipios = carregar_municipios(municipios_arquivo)
    if municipio:
        if not nomes_municipios:
            raise ValueError("Para filtrar por município, informe também o arquivo de Municípios da Receita.")
        alvo = municipio.strip().lower()
        codigos_alvo = {c for c, n in nomes_municipios.items() if n.lower() == alvo}
        if not codigos_alvo:
            raise ValueError(f"Município não encontrado no arquivo: {municipio}")

    importados = ignorados = 0
    with open(arquivo, encoding="latin-1", newline="") as f:
        for linha in csv.reader(f, delimiter=";"):
            if len(linha) <= COL_EMAIL:
                continue
            if linha[COL_SITUACAO] != SITUACAO_ATIVA or linha[COL_UF] != uf or not linha[COL_CNAE].startswith(prefixos):
                continue
            if codigos_alvo is not None and linha[COL_MUNICIPIO] not in codigos_alvo:
                continue
            cnpj = f"{linha[COL_CNPJ_BASICO]}{linha[COL_ORDEM]}{linha[COL_DV]}"
            empresa = linha[COL_FANTASIA].strip().title() or f"CNPJ {cnpj}"
            novo = inserir_email_lead(
                conexao, empresa, linha[COL_EMAIL], setor=setor or linha[COL_CNAE][:4],
                cidade=nomes_municipios.get(linha[COL_MUNICIPIO]), fonte="receita", cnpj=cnpj,
            )
            if novo:
                importados += 1
            else:
                ignorados += 1
            if limite and importados >= limite:
                break
    conexao.commit()
    return {"importados": importados, "ignorados": ignorados}
