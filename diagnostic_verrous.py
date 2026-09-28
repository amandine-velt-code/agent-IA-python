"""Affiche la réponse exacte de DuckDB à chaque tentative bloquée (sans appeler l'API)."""
import os
import subprocess
import sys
import time

subprocess.run([sys.executable, "creer_base.py"], check=True)
os.environ["SECRET_DE_TEST"] = "ne-doit-pas-sortir"
import agent  # noqa: E402

TENTATIVES = [
    "DROP TABLE ventes",
    "SELECT * FROM read_csv('/etc/passwd')",
    "SELECT getenv('SECRET_DE_TEST')",
    "COPY ventes TO '/tmp/fuite.csv'",
    "SET enable_external_access = true",
    "SET memory_limit = '8GB'",
    "SELECT sum(hash(a.range * b.range)) FROM range(1000000) a, range(1000000) b",
    "SELECT string_agg(repeat('x', 1000), '') FROM range(2000000)",
    "SELECT range, repeat('x', 500) AS texte FROM range(1000)",
]
for requete in TENTATIVES:
    debut = time.monotonic()
    try:
        r = agent.executer_sql({"requete": requete})
        issue = f"ACCEPTÉE ({len(r)} caractères renvoyés) : {r[:80]}…{r[-25:]}"
    except Exception as e:
        issue = f"REFUSÉE {type(e).__name__} : {str(e).splitlines()[0][:160]}"
    print(f"{requete}\n    → {issue}  [{time.monotonic() - debut:.2f} s]")
print("Table intacte :", agent.con.execute("SELECT count(*) FROM ventes").fetchone()[0], "lignes")
