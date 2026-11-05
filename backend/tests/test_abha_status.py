from test_phase1 import ORIGIN, register


def test_abha_status_does_not_fake_a_connection(client):
    assert register(client, "abha-status@example.com").status_code == 201
    status = client.get("/api/integrations/abha")
    assert status.status_code == 200
    assert status.json()["connection_status"] == "externally_blocked"
    assert status.json()["live_calls_enabled"] is False
    assert client.post("/api/integrations/abha/connect", headers=ORIGIN).status_code == 503
