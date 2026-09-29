"""Serveur MCP minimal : expose les deux outils de agent.py à un autre client (ici, Claude Code).

Rien n'est recopié : mêmes descriptions, mêmes fonctions, même connexion DuckDB, donc mêmes verrous.
Utilisé pour les runs « Opus 5.5 via Claude Code » (runs/run_claude_code.py).

    python creer_base.py && python serveur_mcp.py     # parle MCP sur l'entrée et la sortie standard
"""
import asyncio

import mcp.server.stdio
import mcp.types as types
from mcp.server.lowlevel import Server

import agent  # la connexion verrouillée est ouverte à l'import


async def lister_outils(_ctx, _params):
    return types.ListToolsResult(tools=[types.Tool(name=o["name"], description=o["description"],
                                                   inputSchema=o["input_schema"]) for o in agent.OUTILS])


async def appeler_outil(_ctx, params):
    try:  # même traitement des erreurs que la boucle de agent.py
        contenu, erreur = agent.FONCTIONS[params.name](params.arguments or {}), False
    except Exception as e:
        contenu, erreur = f"Erreur : {e}", True
    return types.CallToolResult(content=[types.TextContent(text=contenu)], isError=erreur)


serveur = Server("duckdb", on_list_tools=lister_outils, on_call_tool=appeler_outil)


async def main():
    async with mcp.server.stdio.stdio_server() as (lecture, ecriture):
        await serveur.run(lecture, ecriture, serveur.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
