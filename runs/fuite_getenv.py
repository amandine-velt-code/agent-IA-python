"""Test de fuite getenv sur DuckDB, avec la configuration exacte de agent.py (sans appeler l'API).

La variable ANTHROPIC_API_KEY du bac à sable contient une FAUSSE clé factice.
Comparaison : une connexion DuckDB sans verrous, puis la connexion de agent.py.

    python runs/fuite_getenv.py
"""
import datetime as dt
import json
import os
import subprocess
import sys

import duckdb

sys.path.insert(0, os.getcwd())  # agent.py est à la racine du dossier
subprocess.run([sys.executable, "creer_base.py"], check=True, capture_output=True)
FAUSSE_CLE = os.environ["ANTHROPIC_API_KEY"]
assert "FAUSSE-CLE-FACTICE" in FAUSSE_CLE  # jamais une vraie clé ici

REQUETES = ["SELECT getenv('ANTHROPIC_API_KEY')", "SELECT getenv('HOME')",
            "SELECT current_setting('home_directory')"]


def essai(con, requete):
    try:
        r = con.execute(requete).fetchall()
        return {"issue": "ACCEPTÉE", "fuite_de_la_cle": FAUSSE_CLE in json.dumps(r, default=str),
                "resultat": json.dumps(r, default=str).replace(FAUSSE_CLE, "<fausse clé>")}
    except duckdb.Error as e:
        return {"issue": "REFUSÉE", "erreur": f"{type(e).__name__} : {str(e).splitlines()[0]}"}


sortie = {"date_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
          "cle": "FAUSSE clé factice (variable ANTHROPIC_API_KEY du bac à sable)", "duckdb": duckdb.__version__, "sans_verrous": {}, "agent_py": {}}
libre = duckdb.connect("ventes.duckdb", read_only=True)
for q in REQUETES:
    sortie["sans_verrous"][q] = essai(libre, q)
libre.close()

import agent  # noqa: E402  la connexion verrouillée de agent.py
for q in REQUETES:
    sortie["agent_py"][q] = essai(agent.con, q)
    try:
        agent.executer_sql({"requete": q})
        sortie["agent_py"][q]["via_executer_sql"] = "acceptée"
    except duckdb.Error as e:
        sortie["agent_py"][q]["via_executer_sql"] = f"refusée : {str(e).splitlines()[0]}"
print(json.dumps(sortie, ensure_ascii=False, indent=2))
