from types import SimpleNamespace

from ansible_collections.zupersero.elastic.plugins.module_utils.elasticsearch_services.user import (
    UserService,
)


def test_user_path_quotes_usernames():
    assert UserService.path("test user") == "_security/user/test%20user"


def test_user_get_unwraps_named_entry():
    client = SimpleNamespace(
        request=lambda path: SimpleNamespace(
            status=200,
            data={
                "example_user": {
                    "roles": ["superuser"],
                    "full_name": "Example User",
                    "email": "example@example.com",
                    "metadata": {"owner": "qa"},
                    "enabled": True,
                }
            },
        )
    )
    response, user = UserService(client).get("example_user")
    assert response.status == 200
    assert user["username"] == "example_user"
    assert user["roles"] == ["superuser"]


def test_user_payload_preserves_omitted_fields():
    current = {
        "username": "example_user",
        "roles": ["superuser"],
        "full_name": "Example User",
        "email": "example@example.com",
        "metadata": {"owner": "qa"},
        "enabled": True,
    }
    payload = UserService.payload(current, {"email": "updated@example.com"})
    assert payload["email"] == "updated@example.com"
    assert payload["roles"] == ["superuser"]
    assert payload["full_name"] == "Example User"
    assert payload["metadata"] == {"owner": "qa"}
    assert "password" not in payload


def test_user_payload_defaults_omitted_fields_on_creation():
    payload = UserService.payload(None, {"roles": ["superuser"]})
    assert payload["roles"] == ["superuser"]
    assert payload["full_name"] == ""
    assert payload["email"] == ""
    assert payload["metadata"] == {}
    assert payload["enabled"] is True


def test_user_compare_ignores_role_ordering():
    current = {
        "username": "example_user",
        "roles": ["monitoring_user", "superuser"],
        "full_name": "",
        "email": "",
        "metadata": {},
        "enabled": True,
    }
    changed, diff = UserService.compare(current, {"roles": ["superuser", "monitoring_user"]})
    assert changed is False
    assert diff["before"] == diff["after"]


def test_user_compare_detects_real_changes():
    current = {
        "username": "example_user",
        "roles": ["superuser"],
        "full_name": "",
        "email": "",
        "metadata": {},
        "enabled": True,
    }
    changed, diff = UserService.compare(current, {"enabled": False})
    assert changed is True
    assert diff["after"]["enabled"] is False


def test_user_create_or_update_applies_secrets_without_affecting_payload():
    captured = {}

    def fake_request(path, method=None, data=None):
        captured["path"] = path
        captured["method"] = method
        captured["data"] = data
        return SimpleNamespace(status=200, data={})

    client = SimpleNamespace(request=fake_request)
    service = UserService(client)
    service.create_or_update(
        "example_user",
        current=None,
        desired={"roles": ["superuser"]},
        secrets={"password": "s3cret"},
    )
    assert captured["data"]["password"] == "s3cret"
    assert captured["data"]["roles"] == ["superuser"]

    # payload() itself never includes secrets
    assert "password" not in UserService.payload(None, {"roles": ["superuser"]})
