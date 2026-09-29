"""Le serveur MCP expose les mêmes outils que agent.py, avec les mêmes verrous (aucune API, aucun modèle)."""
import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from conftest import RACINE


async def dialoguer(dossier):
    params = StdioServerParameters(command=sys.executable, args=[str(RACINE / "serveur_mcp.py")], cwd=dossier)
    async with stdio_client(params) as (lecture, ecriture), ClientSession(lecture, ecriture) as session:
        await session.initialize()
        outils = (await session.list_tools()).tools
        normale = await session.call_tool("executer_sql", {"requete": "SELECT count(*) AS n FROM ventes"})
        drop = await session.call_tool("executer_sql", {"requete": "DROP TABLE ventes"})
        fichier = await session.call_tool("executer_sql", {"requete": "SELECT * FROM read_csv('/etc/passwd')"})
        return outils, normale, drop, fichier


def test_serveur_mcp(agent, tmp_path):  # le fixture a créé ventes.duckdb dans tmp_path
    outils, normale, drop, fichier = asyncio.run(dialoguer(tmp_path))
    assert [(o.name, o.description, o.input_schema) for o in outils] == [
        (o["name"], o["description"], o["input_schema"]) for o in agent.OUTILS]
    assert not normale.is_error and json.loads(normale.content[0].text)["lignes"] == [[5]]
    assert drop.is_error and "read-only" in drop.content[0].text
    assert fichier.is_error and "file system operations are disabled" in fichier.content[0].text
