"""Agent d'analyse de données : Claude + DuckDB, en lecture seule."""
import json
import threading

import anthropic
import duckdb

MODELE = "claude-opus-5-5"  # liste à jour : client.models.list()
MAX_TOURS = 10         # garde-fou : un agent qui boucle coûte cher
DELAI_MAX_S = 5        # une requête SQL ne tourne jamais plus longtemps
MAX_LIGNES = 50        # lignes renvoyées au modèle, au plus
MAX_CARACTERES = 8000  # taille du résultat renvoyé au modèle, au plus

# Lecture seule, aucun accès aux fichiers ni au réseau, ressources bornées
con = duckdb.connect("ventes.duckdb", read_only=True, config={
    "enable_external_access": False,
    "memory_limit": "256MB", "threads": 2, "max_temp_directory_size": "0B"})
con.execute("SET lock_configuration = true")  # plus aucun réglage modifiable

SYSTEME = ("Tu es un analyste de données. Réponds en français, chiffres à l'appui. "
           "Commence par décrire les tables, puis interroge-les en SQL DuckDB.")

OUTILS = [
    {"name": "decrire_tables",
     "description": "Liste les tables et leurs colonnes (nom, type). "
                    "À appeler avant d'écrire une requête.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "executer_sql",
     "description": "Exécute une seule requête SELECT (dialecte DuckDB) et "
                    "renvoie au plus 50 lignes, en JSON.",
     "input_schema": {"type": "object",
                      "properties": {"requete": {"type": "string",
                                                 "description": "Une requête SELECT."}},
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
        lignes = curseur.fetchmany(MAX_LIGNES)
    finally:
        minuteur.cancel()
    texte = json.dumps({"colonnes": colonnes, "lignes": lignes}, default=str)
    if len(texte) > MAX_CARACTERES:  # ni le contexte ni la facture ne saturent
        texte = texte[:MAX_CARACTERES] + " …[résultat tronqué]"
    return texte


FONCTIONS = {"decrire_tables": decrire_tables, "executer_sql": executer_sql}


def agent(question):
    client = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY
    messages = [{"role": "user", "content": question}]
    for _ in range(MAX_TOURS):
        reponse = client.messages.create(model=MODELE, max_tokens=16000,
                                         system=SYSTEME, tools=OUTILS,
                                         messages=messages)
        if reponse.stop_reason != "tool_use":  # fini (ou refus, ou limite)
            return "".join(b.text for b in reponse.content if b.type == "text")
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
