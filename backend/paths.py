"""Caminhos centrais do app: onde ficam os recursos (read-only) e os dados (graváveis).

Dois modos de execução:

- **Fonte** (clone do repo, `py app.py`): tudo fica na pasta do projeto, como sempre
  foi — nada muda para quem desenvolve ou roda os testes.
- **Empacotado** (PyInstaller, `sys.frozen`): o código e os recursos viram um bundle
  read-only (possivelmente em Program Files), então os dados do usuário (banco,
  backups, saídas, sessão do Instagram) PRECISAM ir para uma pasta gravável —
  `%APPDATA%\\ProspectOS`. Sem essa separação, o app instalado não consegue gravar
  nada e um update apagaria os leads.

Regra prática para os outros módulos:
- arquivo que o app só LÊ e vem junto do código (scraper .exe, os .py do instagram,
  o build do frontend) → `caminho_recurso(...)`
- arquivo que o app ESCREVE (leads.db, backups/, saidas/, queries.txt, logs/,
  instagram/sessao/, instagram/comentarios/) → `caminho_dados(...)`
"""

import os
import sys
from pathlib import Path

# PyInstaller define sys.frozen no executável gerado
EMPACOTADO = bool(getattr(sys, "frozen", False))

_DIR_FONTE = Path(__file__).parent

if EMPACOTADO:
    # --onedir: recursos adicionados via --add-data ficam em sys._MEIPASS
    # (na prática a pasta _internal ao lado do .exe)
    DIR_RECURSOS = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    DIR_DADOS = Path(os.environ.get("APPDATA", str(Path.home()))) / "ProspectOS"
else:
    DIR_RECURSOS = _DIR_FONTE
    DIR_DADOS = _DIR_FONTE

# Pasta de dados explícita (o iniciar.bat aponta para %LOCALAPPDATA%\SeriaxOS).
# Motivo: quando o projeto mora no OneDrive/Dropbox, o sincronizador trava o
# leads.db enquanto envia para a nuvem e o SQLite responde "database is locked"
# ao acaso - travando buscas, piloto e sincronização do WhatsApp.
if os.environ.get("PROSPECCAO_DIR_DADOS"):
    DIR_DADOS = Path(os.environ["PROSPECCAO_DIR_DADOS"])

# o que é dado do usuário e vai junto quando a pasta de dados muda de lugar
ITENS_DE_DADOS = ("leads.db", "backups", "saidas", "logs", "instagram", "queries.txt")


def caminho_recurso(*partes):
    """Caminho de um recurso read-only distribuído junto com o app."""
    return DIR_RECURSOS.joinpath(*partes)


def caminho_dados(*partes, criar_pai=False):
    """Caminho de um arquivo/pasta de dados do usuário (sempre gravável).

    Com criar_pai=True, garante que o diretório pai exista antes de devolver —
    útil pra quem vai abrir o arquivo pra escrita logo em seguida.
    """
    caminho = DIR_DADOS.joinpath(*partes)
    if criar_pai:
        caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


def migrar_dados_da_pasta_antiga(origem=None, destino=None):
    """Na primeira vez com uma pasta de dados nova, COPIA os dados da pasta antiga
    (a do projeto) para lá - nada é apagado. O banco antigo é renomeado para
    leads.db-antigo para ninguém editar o arquivo errado sem querer.
    Retorna True se migrou."""
    origem = Path(origem or _DIR_FONTE)
    destino = Path(destino or DIR_DADOS)
    if origem.resolve() == destino.resolve():
        return False
    if (destino / "leads.db").exists() or not (origem / "leads.db").exists():
        return False

    import shutil
    import sqlite3

    destino.mkdir(parents=True, exist_ok=True)
    # o banco vai pela API de backup do SQLite: inclui o que ainda está no -wal.
    # Fecha explicitamente: o "with" do sqlite3 só faz commit, e no Windows um
    # arquivo aberto não pode ser renomeado logo abaixo.
    banco_antigo = sqlite3.connect(origem / "leads.db")
    banco_novo = sqlite3.connect(destino / "leads.db")
    try:
        banco_antigo.backup(banco_novo)
    finally:
        banco_novo.close()
        banco_antigo.close()
    for item in ITENS_DE_DADOS:
        if item == "leads.db" or not (origem / item).exists():
            continue
        if (origem / item).is_dir():
            shutil.copytree(origem / item, destino / item, dirs_exist_ok=True)
        else:
            shutil.copy2(origem / item, destino / item)
    for sufixo in ("", "-wal", "-shm"):
        antigo = origem / f"leads.db{sufixo}"
        if antigo.exists():
            antigo.rename(origem / f"leads.db-antigo{sufixo}")
    return True


def garantir_pastas_de_dados():
    """Cria a estrutura de pastas graváveis (chamado no startup do app)."""
    # só migra quando a pasta nova foi pedida explicitamente - nunca em testes
    if os.environ.get("PROSPECCAO_DIR_DADOS"):
        migrar_dados_da_pasta_antiga()
    DIR_DADOS.mkdir(parents=True, exist_ok=True)
    for sub in ("backups", "saidas", "logs", Path("instagram") / "sessao", Path("instagram") / "comentarios"):
        (DIR_DADOS / sub).mkdir(parents=True, exist_ok=True)
