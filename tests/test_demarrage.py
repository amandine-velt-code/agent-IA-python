"""Démarrage et conservation de la base si le CSV fourni est introuvable."""
import subprocess
import sys
from conftest import RACINE


def test_csv_introuvable_preserve_base(agent, tmp_path):
    r = subprocess.run([sys.executable, str(RACINE / "creer_base.py"), "absent.csv"],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode != 0 and "CSV introuvable" in r.stderr
    assert agent.con.execute("SELECT count(*) FROM ventes").fetchone()[0] == 5
