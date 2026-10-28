"""Ordem da lista de leads: o padrão é atividade recente. Era o bug de 28/10 -
o lead movido para "respondeu" ficava no fim da lista paginada (ordenada pela
data em que foi encontrado) e parecia ter sumido."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module
import db
import processar


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "CAMINHO_BANCO", tmp_path / "leads.db")
    conexao = sqlite3.connect(tmp_path / "leads.db")
    processar.preparar_banco(conexao)
    conexao.close()
    conexao = db.conectar()
    try:
        for i in range(40):  # mais que uma página (30)
            conexao.execute(
                "INSERT INTO leads (place_id, nome, status, visto_em, atualizado_em) "
                "VALUES (?, ?, 'novo', ?, ?)",
                (f"p{i:02d}", f"Lead {i:02d}", f"2026-10-01T10:{i:02d}:00", f"2026-10-01T10:{i:02d}:00"),
            )
        conexao.commit()
    finally:
        conexao.close()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_lead_movido_vai_para_o_topo_da_primeira_pagina(cliente):
    # p00 é o mais antigo: na ordem antiga ficaria fora da 1ª página
    assert cliente.post("/api/leads/p00/status", json={"status": "respondeu"}).status_code == 200
    primeira_pagina = cliente.get("/api/leads").get_json()["leads"]
    assert primeira_pagina[0]["place_id"] == "p00"
    assert primeira_pagina[0]["status"] == "respondeu"


def test_ordem_por_encontrados_continua_disponivel(cliente):
    cliente.post("/api/leads/p00/status", json={"status": "respondeu"})
    leads = cliente.get("/api/leads?ordenar=encontrados").get_json()["leads"]
    assert leads[0]["place_id"] == "p39"


def test_ordenar_invalido(cliente):
    assert cliente.get("/api/leads?ordenar=xyz").status_code == 400
