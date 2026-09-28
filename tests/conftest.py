"""Chaque test reçoit un module `agent` neuf, branché sur une base créée depuis ventes.csv."""
import importlib
import pathlib
import shutil
import subprocess
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


@pytest.fixture
def agent(tmp_path, monkeypatch):
    for f in ("ventes.csv", "creer_base.py"):
        shutil.copy(RACINE / f, tmp_path)
    monkeypatch.chdir(tmp_path)
    subprocess.run([sys.executable, "creer_base.py"], check=True, capture_output=True)
    sys.modules.pop("agent", None)
    module = importlib.import_module("agent")
    yield module
    module.con.close()
