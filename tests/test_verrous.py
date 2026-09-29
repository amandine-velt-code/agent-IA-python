"""Les verrous de agent.py, testés sans appeler l'API : seul DuckDB est en jeu."""
import json
import time

import duckdb
import pytest


def sql(agent, requete):
    return agent.executer_sql({"requete": requete})


def test_requete_normale(agent):
    r = json.loads(sql(agent, "SELECT produit, SUM(quantite * prix_unitaire) AS ca FROM ventes "
                              "WHERE date BETWEEN '2026-04-01' AND '2026-06-30' "
                              "GROUP BY produit ORDER BY ca DESC"))
    assert r["lignes"][0] == ["Kit B", 360]


# Verrou 1 : lecture seule
@pytest.mark.parametrize("requete", ["DROP TABLE ventes", "DELETE FROM ventes",
                                     "INSERT INTO ventes VALUES ('2026-01-01', 'X', 1, 1)",
                                     "CREATE TABLE t AS SELECT 1"])
def test_lecture_seule(agent, requete):
    with pytest.raises(duckdb.Error, match="read-only"):
        sql(agent, requete)
    assert agent.con.execute("SELECT count(*) FROM ventes").fetchone()[0] == 5


# Verrou 2 : aucun accès aux fichiers ni au réseau
@pytest.mark.parametrize("requete", ["SELECT * FROM read_csv('/etc/passwd')",
                                     "SELECT * FROM read_text('/etc/hostname')",
                                     "COPY ventes TO '/tmp/fuite.csv'",
                                     "SELECT * FROM read_csv('https://example.com/x.csv')",
                                     "ATTACH '/tmp/autre.duckdb'",
                                     "INSTALL httpfs"])
def test_acces_externe_coupe(agent, requete):
    with pytest.raises(duckdb.Error):
        sql(agent, requete)


# Variables d'environnement : getenv n'existe pas dans le paquet Python de DuckDB (client en ligne de commande
# seulement). Ce n'est pas un verrou de agent.py : le test échoue si une future version l'ajoute.
def test_variables_environnement(agent, monkeypatch):
    monkeypatch.setenv("SECRET_DE_TEST", "ne-doit-pas-sortir")
    with pytest.raises(duckdb.CatalogException, match="getenv does not exist"):
        sql(agent, "SELECT getenv('SECRET_DE_TEST')")
    with pytest.raises(duckdb.CatalogException, match="getenv does not exist"):  # même sans aucun verrou
        duckdb.connect().execute("SELECT getenv('SECRET_DE_TEST')")


# Verrou 3 : configuration verrouillée
@pytest.mark.parametrize("requete", ["SET enable_external_access = true",
                                     "SET memory_limit = '8GB'", "SET threads = 64",
                                     "RESET lock_configuration", "SET lock_configuration = false"])
def test_configuration_verrouillee(agent, requete):
    with pytest.raises(duckdb.Error):
        sql(agent, requete)


# Ressources bornées
def test_requete_trop_longue_interrompue(agent):
    debut = time.monotonic()
    with pytest.raises(duckdb.Error):
        sql(agent, "SELECT sum(hash(a.range * b.range)) FROM range(1000000) a, range(1000000) b")
    assert time.monotonic() - debut < agent.DELAI_MAX_S + 3


def test_requete_trop_gourmande_refusee(agent):
    with pytest.raises(duckdb.Error):
        sql(agent, "SELECT string_agg(repeat('x', 1000), '') FROM range(2000000)")


def test_resultat_plafonne(agent):
    # Trop de caractères : des lignes sont retirées, le JSON reste valide et signale la troncature
    brut = sql(agent, "SELECT range, repeat('x', 500) AS texte FROM range(1000)")
    r = json.loads(brut)
    assert len(brut) <= agent.MAX_CARACTERES and r["tronque"] is True and 0 < len(r["lignes"]) < agent.MAX_LIGNES
    # Trop de lignes : 50 au plus, et le modèle sait qu'il en reste
    r = json.loads(sql(agent, "SELECT range FROM range(1000)"))
    assert len(r["lignes"]) == agent.MAX_LIGNES and r["tronque"] is True
    # Résultat complet : rien n'est signalé à tort
    r = json.loads(sql(agent, "SELECT range FROM range(50)"))
    assert len(r["lignes"]) == 50 and r["tronque"] is False


def test_metadonnees_trop_longues_refusees(agent, monkeypatch):
    monkeypatch.setattr(agent, "MAX_CARACTERES", 80)
    with pytest.raises(ValueError, match="Métadonnées trop longues"):
        sql(agent, 'SELECT 1 AS "' + 'colonne' * 40 + '"')


def test_une_ligne_trop_longue_json_partiel_valide(agent):
    brut = sql(agent, "SELECT repeat('x', 10000) AS texte")
    r = json.loads(brut)
    assert len(brut) <= agent.MAX_CARACTERES
    assert r["tronque"] is True and r["lignes"] == []


def test_description_select_ne_filtre_pas_le_sql(agent):
    # Pas de filtre SELECT dans ce kit : PRAGMA reste possible, sans modifier la base.
    r = json.loads(sql(agent, "PRAGMA table_info('ventes')"))
    assert len(r["lignes"]) == 4
