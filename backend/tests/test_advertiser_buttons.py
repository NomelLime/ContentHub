"""Smoke-тесты backend-эквивалентов кнопок UI рекламодателей."""
from tests.conftest import auth_headers


def test_templates_dropdown_source(client, viewer_token, monkeypatch):
    """GET templates для выпадающих списков."""
    from api.routes import advertisers as adv_routes

    monkeypatch.setattr(
        adv_routes,
        "read_pl_templates",
        lambda: {"offers": ["expert_review", "betting_live_odds"], "cloaked": ["expert_review", "tech_journal"]},
    )

    resp = client.get("/api/advertisers/templates", headers=auth_headers(viewer_token))
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "betting_live_odds" in data["offers"]
    assert "tech_journal" in data["cloaked"]


def test_save_cloak_template_button(client, admin_token, monkeypatch):
    """PUT settings (кнопка 'Сохранить клоаку')."""
    from api.routes import configs as cfg_routes

    monkeypatch.setattr(cfg_routes, "read_pl_settings", lambda: {"default_offer_url": "https://x.test"})
    monkeypatch.setattr(cfg_routes, "write_pl_settings", lambda data, username="contenthub": None)

    resp = client.put(
        "/api/configs/PreLend/settings",
        headers=auth_headers(admin_token),
        json={"cloak_template": "tech_journal"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["settings"]["cloak_template"] == "tech_journal"


def test_add_edit_delete_advertiser_buttons(client, admin_token, monkeypatch):
    """POST/PUT/DELETE — кнопки добавить/сохранить/удалить."""
    from api.routes import advertisers as adv_routes

    state = {
        "advertisers": [
            {"id": "adv_stub", "name": "Stub", "status": "active", "url": "https://x.test", "rate": 0.1, "geo": [], "device": []}
        ]
    }

    def _read():
        return [dict(x) for x in state["advertisers"]]

    def _write_all(items, username="contenthub"):
        state["advertisers"] = [dict(x) for x in items]

    def _write_one(advertiser_id, updates, username="contenthub"):
        for item in state["advertisers"]:
            if item.get("id") == advertiser_id:
                item.update(updates)
                return True
        return False

    monkeypatch.setattr(adv_routes, "read_pl_advertisers", _read)
    monkeypatch.setattr(adv_routes, "write_pl_advertisers", _write_all)
    monkeypatch.setattr(adv_routes, "write_pl_advertiser", _write_one)

    # Create
    create_resp = client.post(
        "/api/advertisers",
        headers=auth_headers(admin_token),
        json={
            "name": "smoke_btn_test",
            "url": "https://offer.test",
            "rate": 1.23,
            "geo": ["US"],
            "device": ["mobile"],
            "status": "active",
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    created_id = created["id"]
    assert created["name"] == "smoke_btn_test"

    # Edit
    edit_resp = client.put(
        f"/api/advertisers/{created_id}",
        headers=auth_headers(admin_token),
        json={"rate": 2.34, "template": "betting_live_odds"},
    )
    assert edit_resp.status_code == 200, edit_resp.text
    assert edit_resp.json()["success"] is True

    # Delete (soft)
    del_resp = client.delete(f"/api/advertisers/{created_id}", headers=auth_headers(admin_token))
    assert del_resp.status_code == 200, del_resp.text
    assert del_resp.json()["success"] is True
