"""Garde-fou : le client Zoho ne doit jamais émettre autre chose que des GET (hors obtention du token)."""

from unittest import mock

import pytest

pytest.importorskip("django")


def test_only_get_requests(settings):
    settings.ZOHO_BOOKS = {"ORGANIZATION_ID": "x", "CLIENT_ID": "a", "CLIENT_SECRET": "b", "REFRESH_TOKEN": "c"}
    from apps.billing.services.zoho import ZohoReadOnlyClient

    calls = []
    with mock.patch("requests.post") as post, mock.patch("requests.request") as req:
        post.return_value.json.return_value = {"access_token": "t", "expires_in": 3600}
        post.return_value.raise_for_status = lambda: None
        req.return_value.status_code = 200
        req.return_value.json.return_value = {"invoices": [], "page_context": {}}
        req.return_value.raise_for_status = lambda: None
        c = ZohoReadOnlyClient()
        c.list_invoices()
        c.list_contacts()
        c.list_customer_payments()
        calls = [a[0][0] for a in req.call_args_list]
    assert calls and set(calls) == {"GET"}


def test_module_has_no_write_methods():
    from apps.billing.services import zoho

    forbidden = ("create", "update", "delete", "email", "mark_", "void", "write_off")
    names = [n for n in dir(zoho.ZohoReadOnlyClient) if not n.startswith("_")]
    assert not [n for n in names if any(f in n for f in forbidden)]
