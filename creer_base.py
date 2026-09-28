"""Crée ventes.duckdb à partir d'un CSV. À lancer une seule fois (ou à chaque changement du CSV).

    python creer_base.py                        # ventes.csv
    python creer_base.py ventes_piegees.csv     # la démo d'injection indirecte
"""
import os
import sys

import duckdb

csv = sys.argv[1] if len(sys.argv) > 1 else "ventes.csv"
if os.path.exists("ventes.duckdb"):
    os.remove("ventes.duckdb")
con = duckdb.connect("ventes.duckdb")
con.execute("CREATE TABLE ventes AS SELECT * FROM read_csv(?)", [csv])
print(csv, "→ ventes.duckdb :", con.execute("SELECT count(*) FROM ventes").fetchone()[0], "lignes")
con.close()
