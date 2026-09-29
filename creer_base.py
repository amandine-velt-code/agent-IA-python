"""Crée une base d'exemple dans le dossier de travail (la remplace après validation du CSV)."""
from pathlib import Path
import sys
import duckdb

csv = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("ventes.csv")
if not csv.is_file():
    raise SystemExit(f"CSV introuvable : {csv}. Placez-vous dans le dossier du dépôt.")
con = duckdb.connect("ventes.duckdb")
try:
    con.execute("CREATE OR REPLACE TABLE ventes AS SELECT * FROM read_csv(?)", [str(csv)])
    print(csv, "→ ventes.duckdb :", con.execute("SELECT count(*) FROM ventes").fetchone()[0], "lignes")
finally:
    con.close()
