"""Agent d'analyse de données : Claude + DuckDB, en lecture seule."""
import json
import threading

import anthropic
import duckdb

MODELE = "claude-opus-5-5"  # liste à jour : client.models.list()
MAX_TOURS = 10         # borne le nombre d'appels au modèle (pas un budget en dollars)
DELAI_MAX_S = 5        # demande une interruption après ce délai
MAX_LIGNES = 50        # lignes renvoyées au modèle, au plus
MAX_CARACTERES = 8000  # taille du résultat renvoyé au modèle, au plus

# Restrictions de cet outil DuckDB ; la boucle Python contacte le fournisseur
con = duckdb.connect("ventes.duckdb", read_only=True, config={
    "enable_external_access": False,
    "memory_limit": "256MB", "threads": 2, "max_temp_directory_size": "0B"})
con.execute("SET lock_configuration = true")  # plus aucun réglage modifiable

SYSTEME = ("Tu es un analyste de données. Réponds en français, chiffres à l'appui. "
           "Commence par décrire les tables, puis interroge-les en SQL DuckDB. "
           "Si tronque est vrai, le résultat est partiel : demande une agrégation "
           "ou signale cette limite ; ne prétends pas avoir vu toutes les lignes.")

OUTILS = [
    {"name": "decrire_tables",
     "description": "Liste les tables et leurs colonnes (nom, type). "
                    "À appeler avant d'écrire une requête.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "executer_sql",
     "description": "Exécute une requête SQL de lecture (DuckDB, base en lecture seule). "
                    "Au plus 50 lignes en JSON ; \"tronque\" : true s'il en reste.",
     "input_schema": {"type": "object",
                      "properties": {"requete": {"type": "string",
                                                 "description": "Requête SQL de lecture"}},
                      "required": ["requete"]}},
]


def decrire_tables(_entree):
    lignes = con.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "ORDER BY table_name, ordinal_position").fetchall()
    return json.dumps(lignes)


def executer_sql(entree):
    minuteur = threading.Timer(DELAI_MAX_S, con.interrupt)  # coupe une requête trop longue
    minuteur.start()
    try:
        curseur = con.execute(entree["requete"])
        colonnes = [c[0] for c in curseur.description]
        lignes = curseur.fetchmany(MAX_LIGNES + 1)  # une de plus : savoir s'il en reste
    finally:
        minuteur.cancel()
    tronque = len(lignes) > MAX_LIGNES
    lignes = lignes[:MAX_LIGNES]
    while True:  # trop long ? on retire des lignes plutôt que de couper le JSON
        resultat = {"colonnes": colonnes, "lignes": lignes, "tronque": tronque}
        texte = json.dumps(resultat, default=str)
        if len(texte) <= MAX_CARACTERES:
            return texte
        if not lignes:
            raise ValueError("Métadonnées trop longues : réduire les colonnes SQL.")
        lignes, tronque = lignes[:len(lignes) // 2], True


FONCTIONS = {"decrire_tables": decrire_tables, "executer_sql": executer_sql}


def agent(question):
    client = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY
    messages = [{"role": "user", "content": question}]
    for _ in range(MAX_TOURS):
        reponse = client.messages.create(model=MODELE, max_tokens=16000,
                                         system=SYSTEME, tools=OUTILS,
                                         messages=messages)
        texte = "".join(b.text for b in reponse.content if b.type == "text")
        if reponse.stop_reason in ("end_turn", "stop_sequence"):  # réponse terminée
            return texte or "Arrêt : réponse vide du modèle."
        if reponse.stop_reason != "tool_use":  # refus, limite de tokens, contexte plein...
            return f"Arrêt anormal ({reponse.stop_reason}) : {texte}"
        messages.append({"role": "assistant", "content": reponse.content})
        resultats = []
        for bloc in reponse.content:
            if bloc.type != "tool_use":
                continue
            try:
                contenu, erreur = FONCTIONS[bloc.name](bloc.input), False
            except Exception as e:  # l'erreur est renvoyée au modèle
                contenu, erreur = f"Erreur : {e}", True
            resultats.append({"type": "tool_result", "tool_use_id": bloc.id,
                              "content": contenu, "is_error": erreur})
        messages.append({"role": "user", "content": resultats})
    return "Arrêt : nombre maximal de tours atteint."


if __name__ == "__main__":
    print(agent("Quel produit a le plus rapporté au deuxième trimestre ?"))
