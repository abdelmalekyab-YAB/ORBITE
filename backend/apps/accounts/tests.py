from rest_framework.test import APIClient


def test_login_me(seeded):
    c = APIClient()
    r = c.post("/api/v1/auth/login", {"email": "julie@wws.fr", "password": "orbit"}, format="json")
    assert r.status_code == 200, r.content
    c.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["access"])
    me = c.get("/api/v1/me")
    assert me.status_code == 200
    assert me.data["organization"] == "WWS" and me.data["job"] == "client"


def test_wrong_password_rejected(seeded):
    r = APIClient().post("/api/v1/auth/login", {"email": "julie@wws.fr", "password": "nope"}, format="json")
    assert r.status_code == 401
