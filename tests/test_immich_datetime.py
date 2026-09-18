"""
Tests for the datetime serialization that goes on the wire to Immich.

Immich >= 3.2 rejects a naive timestamp such as "2023-01-01T00:00:00" with
400 Validation failed / invalid_format, so every datetime in a request body has to
carry a "Z" or a numeric offset.
"""
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from immich.immich_api import apply_date_filters, to_immich_datetime
from immich.selectors import (
    RandomAssetSelector,
    RandomSmartSearchAssetSelector,
    SmartSearchAssetSelector,
)

# The shape Immich accepts: an ISO-8601 timestamp with a timezone designator.
IMMICH_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}(Z|[+-]\d{2}:\d{2})$"
)

BASE_URL = "http://immich.test"


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    """Records request bodies instead of talking to a server."""

    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def post(self, url, json):
        self.calls.append((url, json))
        return FakeResponse(self._payload)

    def get(self, url):
        raise AssertionError("no GET expected in these tests")


# --- to_immich_datetime -------------------------------------------------------


def test_naive_datetime_is_qualified_as_utc():
    assert to_immich_datetime(datetime(2023, 1, 1)) == "2023-01-01T00:00:00.000Z"


def test_naive_datetime_with_time_is_qualified_as_utc():
    assert (
        to_immich_datetime(datetime(2025, 10, 20, 13, 45, 30))
        == "2025-10-20T13:45:30.000Z"
    )


def test_aware_datetime_keeps_its_offset():
    value = datetime(2023, 1, 1, tzinfo=timezone(timedelta(hours=-5)))
    assert to_immich_datetime(value) == "2023-01-01T00:00:00.000-05:00"


def test_aware_utc_datetime_renders_as_z():
    value = datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert to_immich_datetime(value) == "2023-01-01T12:00:00.000Z"


def test_plain_date_becomes_midnight_utc():
    assert to_immich_datetime(date(2023, 1, 1)) == "2023-01-01T00:00:00.000Z"


@pytest.mark.parametrize(
    "value",
    [
        "2023-01-01",
        "2023-01-01T00:00:00",
        "2023-01-01T00:00:00+00:00",
        "2023-01-01T00:00:00Z",
        "2023-01-01T00:00:00.000Z",
    ],
)
def test_string_values_are_normalized(value):
    serialized = to_immich_datetime(value)
    assert IMMICH_DATETIME_RE.match(serialized), serialized
    assert serialized == "2023-01-01T00:00:00.000Z"


@pytest.mark.parametrize(
    "value",
    [
        datetime(2023, 1, 1),
        datetime(2023, 1, 1, tzinfo=timezone.utc),
        datetime(2023, 1, 1, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        date(2023, 1, 1),
        "2023-01-01",
    ],
)
def test_every_supported_input_matches_the_accepted_shape(value):
    assert IMMICH_DATETIME_RE.match(to_immich_datetime(value))


def test_invalid_string_raises_value_error():
    with pytest.raises(ValueError):
        to_immich_datetime("not-a-date")


def test_unsupported_type_raises_type_error():
    with pytest.raises(TypeError):
        to_immich_datetime(1672531200)


# --- apply_date_filters ------------------------------------------------------


def test_apply_date_filters_sets_both_bounds():
    body = {}
    apply_date_filters(body, datetime(2023, 1, 1), datetime(2024, 1, 1))
    assert body == {
        "takenAfter": "2023-01-01T00:00:00.000Z",
        "takenBefore": "2024-01-01T00:00:00.000Z",
    }


def test_apply_date_filters_omits_missing_bounds():
    body = {"size": 5}
    apply_date_filters(body, None, None)
    assert body == {"size": 5}


# --- selectors put a qualified datetime on the wire --------------------------


def _random_selector(session, **kwargs):
    return RandomAssetSelector(session=session, base_url=BASE_URL, **kwargs)


def _smart_selector(session, **kwargs):
    return SmartSearchAssetSelector(
        session=session, base_url=BASE_URL, search_query="dogs", **kwargs
    )


def _smart_rng_selector(session, **kwargs):
    return RandomSmartSearchAssetSelector(
        session=session, base_url=BASE_URL, search_query="dogs", **kwargs
    )


SELECTOR_CASES = [
    (_random_selector, [{"id": "asset-1"}], "/api/search/random"),
    (_smart_selector, {"assets": {"items": [{"id": "asset-1"}]}}, "/api/search/smart"),
    (
        _smart_rng_selector,
        {"assets": {"items": [{"id": "asset-1"}]}},
        "/api/search/smart",
    ),
]


@pytest.mark.parametrize("factory,payload,path", SELECTOR_CASES)
def test_selector_sends_qualified_naive_dates(factory, payload, path):
    session = FakeSession(payload)
    selector = factory(
        session,
        taken_after=datetime(2023, 1, 1),
        taken_before=datetime(2024, 6, 30, 23, 59, 59),
    )

    assert selector.get_assets(count=1) == ["asset-1"]

    url, body = session.calls[0]
    assert url == f"{BASE_URL}{path}"
    assert body["takenAfter"] == "2023-01-01T00:00:00.000Z"
    assert body["takenBefore"] == "2024-06-30T23:59:59.000Z"
    assert IMMICH_DATETIME_RE.match(body["takenAfter"])
    assert IMMICH_DATETIME_RE.match(body["takenBefore"])


@pytest.mark.parametrize("factory,payload,path", SELECTOR_CASES)
def test_selector_preserves_aware_dates(factory, payload, path):
    session = FakeSession(payload)
    selector = factory(
        session, taken_after=datetime(2023, 1, 1, tzinfo=timezone(timedelta(hours=-5)))
    )

    selector.get_assets(count=1)

    body = session.calls[0][1]
    assert body["takenAfter"] == "2023-01-01T00:00:00.000-05:00"
    assert "takenBefore" not in body


@pytest.mark.parametrize("factory,payload,path", SELECTOR_CASES)
def test_selector_omits_dates_when_unset(factory, payload, path):
    session = FakeSession(payload)
    selector = factory(session)

    selector.get_assets(count=1)

    body = session.calls[0][1]
    assert "takenAfter" not in body
    assert "takenBefore" not in body
