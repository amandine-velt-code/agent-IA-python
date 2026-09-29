"""La boucle de agent.py avec le vrai SDK anthropic : seul le serveur de l'API est simulé (aucun appel réseau)."""
import json

import anthropic
import httpx2
import pytest

REQUETE = ("SELECT produit, SUM(quantite * prix_unitaire) AS ca FROM ventes "
           "WHERE date BETWEEN '2026-04-01' AND '2026-06-30' GROUP BY produit ORDER BY ca DESC")


def serveur_simule(appels):
    def msg(content, stop):
        return {"id": f"msg_{len(appels)}", "type": "message", "role": "assistant",
                "model": "claude-opus-5-5", "content": content, "stop_reason": stop,
                "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 10}}

    def handler(request):
        appels.append(json.loads(request.content))
        n = len(appels)
        if n == 1:
            return httpx2.Response(200, json=msg([{"type": "tool_use", "id": "t1", "name": "decrire_tables",
                                                   "input": {}}], "tool_use"))
        if n == 2:
            return httpx2.Response(200, json=msg([
                {"type": "tool_use", "id": "t2", "name": "executer_sql", "input": {"requete": REQUETE}},
                {"type": "tool_use", "id": "t3", "name": "executer_sql", "input": {"requete": "DROP TABLE ventes"}},
            ], "tool_use"))
        return httpx2.Response(200, json=msg([{"type": "text", "text": "Kit B : 360 €."}], "end_turn"))
    return handler


def test_boucle_complete(agent, monkeypatch):
    appels = []
    vrai = anthropic.Anthropic
    transport = httpx2.MockTransport(serveur_simule(appels))
    monkeypatch.setattr(agent.anthropic, "Anthropic",
                        lambda: vrai(api_key="test", http_client=anthropic.DefaultHttpxClient(transport=transport)))

    assert agent.agent("Quel produit a le plus rapporté au deuxième trimestre ?") == "Kit B : 360 €."
    assert len(appels) == 3 and appels[0]["model"] == agent.MODELE
    resultats = appels[2]["messages"][-1]["content"]      # un seul message pour les deux outils du tour 2
    assert [r["is_error"] for r in resultats] == [False, True]
    assert "Kit B" in resultats[0]["content"] and "read-only" in resultats[1]["content"]
    assert [m["role"] for m in appels[2]["messages"]] == ["user", "assistant", "user", "assistant", "user"]


def test_limite_de_tours(agent, monkeypatch):
    vrai = anthropic.Anthropic

    def toujours_un_outil(request):
        return httpx2.Response(200, json={"id": "m", "type": "message", "role": "assistant", "model": "x",
                                          "content": [{"type": "tool_use", "id": "t", "name": "decrire_tables",
                                                       "input": {}}],
                                          "stop_reason": "tool_use", "stop_sequence": None,
                                          "usage": {"input_tokens": 1, "output_tokens": 1}})
    transport = httpx2.MockTransport(toujours_un_outil)
    monkeypatch.setattr(agent.anthropic, "Anthropic",
                        lambda: vrai(api_key="test", http_client=anthropic.DefaultHttpxClient(transport=transport)))
    assert agent.agent("boucle") == "Arrêt : nombre maximal de tours atteint."


def reponse_fixe(stop_reason, texte):
    def handler(request):
        return httpx2.Response(200, json={"id": "m", "type": "message", "role": "assistant", "model": "x",
                                          "content": [{"type": "text", "text": texte}],
                                          "stop_reason": stop_reason, "stop_sequence": None,
                                          "usage": {"input_tokens": 1, "output_tokens": 1}})
    return handler


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal", "model_context_window_exceeded", "pause_turn"])
def test_arret_anormal_signale(agent, monkeypatch, stop_reason):
    """Un arrêt autre qu'une réponse terminée n'est jamais présenté comme une réponse normale."""
    vrai = anthropic.Anthropic
    transport = httpx2.MockTransport(reponse_fixe(stop_reason, "Réponse coupée"))
    monkeypatch.setattr(agent.anthropic, "Anthropic",
                        lambda: vrai(api_key="test", http_client=anthropic.DefaultHttpxClient(transport=transport)))
    assert agent.agent("question") == f"Arrêt anormal ({stop_reason}) : Réponse coupée"



@pytest.mark.parametrize("stop", ["end_turn", "stop_sequence"])
def test_reponse_terminee(agent, monkeypatch, stop):
    vrai = anthropic.Anthropic
    transport = httpx2.MockTransport(reponse_fixe(stop, "Réponse complète"))
    monkeypatch.setattr(agent.anthropic, "Anthropic",
        lambda: vrai(api_key="test", http_client=anthropic.DefaultHttpxClient(transport=transport)))
    assert agent.agent("question") == "Réponse complète"


def test_reponse_vide_signalee(agent, monkeypatch):
    vrai = anthropic.Anthropic
    transport = httpx2.MockTransport(reponse_fixe("end_turn", ""))
    monkeypatch.setattr(agent.anthropic, "Anthropic",
        lambda: vrai(api_key="test", http_client=anthropic.DefaultHttpxClient(transport=transport)))
    assert agent.agent("question") == "Arrêt : réponse vide du modèle."
