"""Importa para o CRM (tela E-mail) as empresas da base aberta da Receita, em lote, para vários CNAEs e
todos os estados numa passada só pelos arquivos.

Uso (da pasta backend, com PROSPECCAO_DIR_DADOS apontando para a pasta de dados):
    .venv/Scripts/python importar_receita_lote.py C:\\receita --cnaes 4322302,4930202,... [--uf TODOS] [--sem-empresas]

A pasta precisa ter Estabelecimentos0..9.zip e Municipios.zip (os .zip são lidos direto, sem extrair). Se
tiver Empresas0..9.zip, uma segunda passada preenche razão social, porte e natureza jurídica.
Pode rodar de novo: e-mail repetido e quem está na lista de descadastro são ignorados.
"""

import argparse
import time

import db
import email_prospeccao

# Nome legível do setor, com o código ao lado para conferir (descrições do IBGE/CNAE, resumidas).
ROTULOS_CNAE = {
    "4322302": "Ar-condicionado, ventilação e refrigeração (4322302)",
    "4322303": "Prevenção contra incêndio (4322303)",
    "3314710": "Manutenção de máquinas e equipamentos (3314710)",
    "4313400": "Terraplenagem (4313400)",
    "8122200": "Controle de pragas urbanas (8122200)",
    "4930202": "Transporte rodoviário de carga (4930202)",
    "5211799": "Depósitos de mercadorias (5211799)",
    "5250804": "Organização logística de carga (5250804)",
    "2222600": "Embalagens plásticas (2222600)",
    "1731100": "Embalagens de papel (1731100)",
    "2599399": "Produtos de metal (2599399)",
    "2063100": "Cosméticos e higiene pessoal (2063100)",
    "7120100": "Testes e análises técnicas (7120100)",
    "3811400": "Coleta de resíduos (3811400)",
    "7732201": "Aluguel de máquinas para construção (7732201)",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta")
    ap.add_argument("--cnaes", required=True, help="códigos separados por vírgula")
    ap.add_argument("--uf", default="TODOS", help="sigla do estado, lista separada por vírgula ou TODOS")
    ap.add_argument("--sem-empresas", action="store_true", help="não faz a segunda passada (razão social e porte)")
    args = ap.parse_args()

    cnaes = [c.strip() for c in args.cnaes.split(",") if c.strip()]
    ufs = args.uf if args.uf.upper() == "TODOS" else [u for u in args.uf.split(",") if u.strip()]
    setores = {c: ROTULOS_CNAE.get(c, c) for c in cnaes}

    conexao = db.conectar()
    try:
        inicio = time.time()
        resultado = email_prospeccao.importar_receita(conexao, args.pasta, cnaes, ufs, setor=setores)
        print(f"Estabelecimentos: {resultado} em {time.time() - inicio:.0f}s", flush=True)
        if not args.sem_empresas:
            inicio = time.time()
            try:
                print(f"Empresas: {email_prospeccao.completar_com_empresas(conexao, args.pasta)} "
                      f"em {time.time() - inicio:.0f}s", flush=True)
            except ValueError as erro:
                print("Segunda passada ignorada:", erro, flush=True)
        total = conexao.execute("SELECT COUNT(*) FROM email_leads").fetchone()[0]
        por_setor = conexao.execute(
            "SELECT setor, COUNT(*) FROM email_leads WHERE fonte = 'receita' GROUP BY setor ORDER BY 2 DESC").fetchall()
        print(f"Total de leads de e-mail: {total}", flush=True)
        for setor, n in por_setor:
            print(f"  {n:>8}  {setor}", flush=True)
    finally:
        conexao.close()


if __name__ == "__main__":
    main()
