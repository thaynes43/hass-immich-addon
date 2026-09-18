"""
Tests for loading taken_after/taken_before out of every configuration source.

PyYAML parses an unquoted `taken_after: 2023-01-01` into a datetime.date (and an
unquoted timestamp into a datetime.datetime) before the config code sees it, so the
YAML loader has to cope with all of date, datetime and string.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from config.cli import parse_datetime as cli_parse_datetime
from config.env import parse_datetime as env_parse_datetime
from config.yaml_config import load_yaml_config
from immich.immich_api import to_immich_datetime

YAML_TEMPLATE = """\
immich:
  url: "http://immich.test"
  api_key: "test-key"
hass_img_path: "{img_path}"
filters:
  - name: "quoted date only"
    selector_type: "random"
    taken_after: "2023-01-01"
  - name: "unquoted date"
    selector_type: "random"
    taken_after: 2023-01-01
  - name: "unquoted timestamp"
    selector_type: "random"
    taken_after: 2023-01-01 10:30:00
  - name: "quoted full iso"
    selector_type: "random"
    taken_after: "2023-01-01T10:30:00"
  - name: "quoted iso with offset"
    selector_type: "random"
    taken_after: "2023-01-01T00:00:00-05:00"
  - name: "quoted iso with z"
    selector_type: "random"
    taken_after: "2023-01-01T00:00:00Z"
  - name: "range"
    selector_type: "random"
    taken_after: "2023-01-01"
    taken_before: 2024-01-01
  - name: "no dates"
    selector_type: "random"
"""


@pytest.fixture
def loaded_filters(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(YAML_TEMPLATE.format(img_path=tmp_path / "album"))
    config = load_yaml_config(config_file)
    return {f.name: f for f in config.filters}


def test_all_supported_date_spellings_load(loaded_filters):
    assert len(loaded_filters) == 8
    for name, photo_filter in loaded_filters.items():
        if name == "no dates":
            assert photo_filter.taken_after is None
            continue
        assert isinstance(photo_filter.taken_after, datetime), name


def test_quoted_date_only(loaded_filters):
    taken_after = loaded_filters["quoted date only"].taken_after
    assert taken_after == datetime(2023, 1, 1)
    assert to_immich_datetime(taken_after) == "2023-01-01T00:00:00.000Z"


def test_pyyaml_really_yields_a_bare_date():
    """Premise check for the loader: an unquoted date is a datetime.date, not a str."""
    import yaml

    value = yaml.safe_load("taken_after: 2023-01-01")["taken_after"]
    assert type(value) is date


def test_unquoted_date_parsed_by_pyyaml(loaded_filters):
    """A datetime.date from PyYAML is promoted to midnight, not passed to fromisoformat."""
    taken_after = loaded_filters["unquoted date"].taken_after
    assert type(taken_after) is datetime
    assert taken_after == datetime(2023, 1, 1, 0, 0, 0)
    assert to_immich_datetime(taken_after) == "2023-01-01T00:00:00.000Z"


def test_unquoted_timestamp_parsed_by_pyyaml(loaded_filters):
    taken_after = loaded_filters["unquoted timestamp"].taken_after
    assert taken_after == datetime(2023, 1, 1, 10, 30, 0)
    assert to_immich_datetime(taken_after) == "2023-01-01T10:30:00.000Z"


def test_quoted_full_iso(loaded_filters):
    taken_after = loaded_filters["quoted full iso"].taken_after
    assert taken_after == datetime(2023, 1, 1, 10, 30, 0)
    assert to_immich_datetime(taken_after) == "2023-01-01T10:30:00.000Z"


def test_quoted_iso_with_offset_keeps_offset(loaded_filters):
    taken_after = loaded_filters["quoted iso with offset"].taken_after
    assert taken_after.utcoffset() == timedelta(hours=-5)
    assert to_immich_datetime(taken_after) == "2023-01-01T00:00:00.000-05:00"


def test_quoted_iso_with_z_is_utc(loaded_filters):
    taken_after = loaded_filters["quoted iso with z"].taken_after
    assert taken_after.utcoffset() == timedelta(0)
    assert to_immich_datetime(taken_after) == "2023-01-01T00:00:00.000Z"


def test_range_loads_both_bounds(loaded_filters):
    photo_filter = loaded_filters["range"]
    assert to_immich_datetime(photo_filter.taken_after) == "2023-01-01T00:00:00.000Z"
    assert to_immich_datetime(photo_filter.taken_before) == "2024-01-01T00:00:00.000Z"


def test_filter_str_does_not_blow_up_on_yaml_dates(loaded_filters):
    """PhotoFilters.__str__ calls .isoformat() on the bounds; it is logged every cycle."""
    for photo_filter in loaded_filters.values():
        assert photo_filter.name in str(photo_filter)


def test_invalid_yaml_date_raises_value_error(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text(
        YAML_TEMPLATE.format(img_path=tmp_path / "album")
        + '    taken_before: "not-a-date"\n'
    )
    with pytest.raises(ValueError):
        load_yaml_config(config_file)


@pytest.mark.parametrize(
    "raw,expected_wire",
    [
        ("2023-01-01", "2023-01-01T00:00:00.000Z"),
        ("2023-01-01T10:30:00", "2023-01-01T10:30:00.000Z"),
        ("2023-01-01T00:00:00-05:00", "2023-01-01T00:00:00.000-05:00"),
        ("2023-01-01T00:00:00Z", "2023-01-01T00:00:00.000Z"),
    ],
)
def test_env_and_cli_parsers_accept_the_same_spellings(raw, expected_wire):
    assert to_immich_datetime(env_parse_datetime(raw)) == expected_wire
    assert to_immich_datetime(cli_parse_datetime(raw)) == expected_wire


def test_env_parser_returns_none_for_empty():
    assert env_parse_datetime(None) is None
    assert env_parse_datetime("") is None


def test_env_parser_rejects_garbage():
    with pytest.raises(ValueError):
        env_parse_datetime("yesterday")
