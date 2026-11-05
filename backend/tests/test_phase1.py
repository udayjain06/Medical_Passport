from app.main import app
from fastapi.testclient import TestClient

ORIGIN = {"Origin": "http://localhost:3000"}
PASSWORD = "Safe-demo-passphrase-42"


def register(client: TestClient, email: str, name: str = "Test Patient"):
    return client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={"full_name": name, "email": email, "password": PASSWORD},
    )


def test_health_and_readiness(client: TestClient):
    assert client.get("/api/health/live").json() == {"status": "ok"}
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_registration_profile_persistence_login_and_logout(client: TestClient):
    response = register(client, "first@example.com", "Asha Rao")
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "first@example.com"
    cookie = response.headers["set-cookie"].lower()
    assert "mp_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert response.headers["cache-control"] == "no-store, private"

    profile = client.get("/api/profile")
    assert profile.status_code == 200
    assert profile.json()["full_name"] == "Asha Rao"
    assert profile.json()["known_allergies"] is None
    assert profile.json()["verification_status"] == "patient_reported"

    update = client.put(
        "/api/profile",
        headers=ORIGIN,
        json={
            "full_name": "Asha Rao",
            "date_of_birth": "1994-05-17",
            "blood_group": "O+",
            "phone_number": "+91 98765 43210",
            "known_allergies": "Penicillin (patient reported)",
            "major_conditions": None,
            "current_medications": "Not recorded",
            "emergency_contacts": [
                {
                    "full_name": "Kiran Rao",
                    "phone_number": "+91 90000 12345",
                    "relationship_label": "Sibling",
                }
            ],
        },
    )
    assert update.status_code == 200, update.text
    assert update.json()["blood_group"] == "O+"
    assert update.json()["emergency_contacts"][0]["full_name"] == "Kiran Rao"

    persisted = client.get("/api/profile")
    assert persisted.status_code == 200
    assert persisted.json()["known_allergies"] == "Penicillin (patient reported)"
    assert persisted.json()["emergency_contacts"][0]["phone_number"] == "+91 90000 12345"

    logout = client.post("/api/auth/logout", headers=ORIGIN)
    assert logout.status_code == 200
    assert logout.json() == {"status": "logged_out"}
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/profile").status_code == 401

    login = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"email": "FIRST@example.com", "password": PASSWORD},
    )
    assert login.status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "first@example.com"

    wrong_password = client.post(
        "/api/auth/login",
        headers=ORIGIN,
        json={"email": "first@example.com", "password": "wrong-password"},
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["detail"] == "Email or password is incorrect"


def test_unauthenticated_access_and_untrusted_write_origin(client: TestClient):
    assert client.get("/api/profile").status_code == 401
    response = client.post(
        "/api/auth/register",
        headers={"Origin": "https://attacker.invalid"},
        json={"full_name": "Nope", "email": "nope@example.com", "password": PASSWORD},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Untrusted request origin"


def test_cross_user_profile_isolation(client: TestClient):
    first = register(client, "one@example.com", "Patient One")
    assert first.status_code == 201
    first_cookie = client.cookies.get("mp_session")

    with TestClient(app, headers=ORIGIN) as second_client:
        second = register(second_client, "two@example.com", "Patient Two")
        assert second.status_code == 201
        assert second_client.get("/api/profile").json()["full_name"] == "Patient Two"

    client.cookies.set("mp_session", first_cookie)
    first_profile = client.get("/api/profile")
    assert first_profile.status_code == 200
    assert first_profile.json()["full_name"] == "Patient One"
    assert first_profile.json()["full_name"] != "Patient Two"


def test_validation_errors_do_not_echo_submitted_values(client: TestClient):
    secret = "short-pass"
    response = client.post(
        "/api/auth/register",
        headers=ORIGIN,
        json={"full_name": "Test", "email": "validation@example.com", "password": secret},
    )
    assert response.status_code == 422
    assert secret not in response.text

    assert register(client, "valid@example.com").status_code == 201
    bad_profile = client.put(
        "/api/profile",
        headers=ORIGIN,
        json={
            "full_name": "Test Patient",
            "blood_group": "X+",
            "known_allergies": "private detail",
        },
    )
    assert bad_profile.status_code == 422
    assert "private detail" not in bad_profile.text


def test_profile_update_requires_same_origin(client: TestClient):
    assert register(client, "csrf@example.com").status_code == 201
    response = client.put(
        "/api/profile",
        headers={"Origin": "null"},
        json={"full_name": "Changed Name"},
    )
    assert response.status_code == 403
    assert client.get("/api/profile").json()["full_name"] == "Test Patient"
