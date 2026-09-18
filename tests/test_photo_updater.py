"""
Tests for the fetch-then-swap update cycle.

The album directory is what the Home Assistant photo frame reads, so a failed fetch
must leave the previous photos in place instead of emptying it.
"""
import asyncio
import io
import os
import zipfile
from pathlib import Path

import pytest

import photo_updater as photo_updater_module
from config.schema import AppConfig, ImmichConfig, PhotoFilters
from photo_updater import STAGING_DIR_NAME, PhotoUpdater

NEW_PHOTOS = {"new-1.jpg": b"new-jpeg-1", "new-2.jpg": b"new-jpeg-2"}


def make_archive(files=None) -> bytes:
    """Build a zip archive the way Immich's /api/download/archive would."""
    files = NEW_PHOTOS if files is None else files
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


class FakeClient:
    """Stands in for ImmichClient: no HTTP, scripted results."""

    def __init__(self, asset_ids=("a1", "a2"), archive=None, get_error=None,
                 download_error=None, on_get_assets=None):
        self.asset_selector = None
        self._asset_ids = list(asset_ids)
        self._archive = make_archive() if archive is None else archive
        self._get_error = get_error
        self._download_error = download_error
        self._on_get_assets = on_get_assets
        self.downloaded = []

    def get_assets(self, count=5):
        if self._on_get_assets:
            self._on_get_assets()
        if self._get_error:
            raise self._get_error
        return self._asset_ids

    def download_assets(self, asset_ids):
        if self._download_error:
            raise self._download_error
        self.downloaded.append(list(asset_ids))
        return self._archive


class FakeImmichAPI:
    """ImmichAPI replacement so constructing PhotoUpdater does not hit the network."""

    def __init__(self, session, base_url):
        self.session = session
        self.base_url = base_url

    def get_people(self):
        return {}


@pytest.fixture
def album_dir(tmp_path):
    directory = tmp_path / "immich-album"
    directory.mkdir()
    (directory / "old-1.jpg").write_bytes(b"old-jpeg-1")
    (directory / "old-2.jpg").write_bytes(b"old-jpeg-2")
    # Not a media file: the updater must never touch it.
    (directory / "keep.txt").write_text("not mine")
    return directory


@pytest.fixture
def make_updater(album_dir, monkeypatch):
    monkeypatch.setattr(photo_updater_module, "ImmichAPI", FakeImmichAPI)

    def _make(client, filters=None):
        config = AppConfig(
            immich=ImmichConfig(url="http://immich.test", api_key="test-key"),
            hass_img_path=Path(album_dir),
            num_photos=2,
            update_interval_minutes=15,
            log_level="DEBUG",
            filters=filters
            or [
                PhotoFilters(name="first", selector_type="random"),
                PhotoFilters(name="second", selector_type="random"),
            ],
        )
        updater = PhotoUpdater(config)
        updater.client = client
        return updater

    return _make


def album_contents(album_dir):
    return {p.name: p.read_bytes() for p in album_dir.iterdir() if p.is_file()}


def staging_path(album_dir):
    return album_dir / STAGING_DIR_NAME


# --- (d) a failing fetch keeps the previous photos ----------------------------


def test_failed_asset_fetch_leaves_existing_photos_untouched(album_dir, make_updater):
    updater = make_updater(FakeClient(get_error=RuntimeError("400 Validation failed")))
    before = album_contents(album_dir)

    asyncio.run(updater.update_photos())

    assert album_contents(album_dir) == before
    assert not staging_path(album_dir).exists()
    assert updater.last_update is None
    # A transient failure retries the same filter set on the next cycle.
    assert updater.current_filter_index == 0


def test_failed_download_leaves_existing_photos_untouched(album_dir, make_updater):
    updater = make_updater(FakeClient(download_error=OSError("connection reset")))
    before = album_contents(album_dir)

    asyncio.run(updater.update_photos())

    assert album_contents(album_dir) == before
    assert not staging_path(album_dir).exists()


def test_corrupt_archive_leaves_existing_photos_untouched(album_dir, make_updater):
    updater = make_updater(FakeClient(archive=b"this is not a zip file"))
    before = album_contents(album_dir)

    asyncio.run(updater.update_photos())

    assert album_contents(album_dir) == before
    assert not staging_path(album_dir).exists()


# --- (e) zero assets keeps the previous photos --------------------------------


def test_zero_assets_leaves_existing_photos_untouched(album_dir, make_updater):
    client = FakeClient(asset_ids=[])
    updater = make_updater(client)
    before = album_contents(album_dir)

    asyncio.run(updater.update_photos())

    assert album_contents(album_dir) == before
    assert not staging_path(album_dir).exists()
    assert client.downloaded == []  # nothing was even downloaded
    assert updater.last_update is None
    # A filter set that matches nothing must not wedge the rotation.
    assert updater.current_filter_index == 1


def test_archive_without_media_leaves_existing_photos_untouched(album_dir, make_updater):
    updater = make_updater(FakeClient(archive=make_archive({"notes.txt": b"no photos"})))
    before = album_contents(album_dir)

    asyncio.run(updater.update_photos())

    assert album_contents(album_dir) == before
    assert not staging_path(album_dir).exists()
    assert updater.last_update is None


# --- (f) a successful cycle swaps the files -----------------------------------


def test_successful_update_replaces_photos(album_dir, make_updater):
    updater = make_updater(FakeClient())

    asyncio.run(updater.update_photos())

    contents = album_contents(album_dir)
    assert "old-1.jpg" not in contents
    assert "old-2.jpg" not in contents
    assert contents["new-1.jpg"] == b"new-jpeg-1"
    assert contents["new-2.jpg"] == b"new-jpeg-2"
    # Non-media files are left alone, and the archive is never published.
    assert contents["keep.txt"] == b"not mine"
    assert not any(name.endswith(".zip") for name in contents)
    assert not staging_path(album_dir).exists()
    assert updater.last_update is not None
    assert updater.current_filter_index == 1


def test_successful_update_flattens_archive_subdirectories(album_dir, make_updater):
    updater = make_updater(
        FakeClient(archive=make_archive({"2023/trip/beach.jpg": b"beach"}))
    )

    asyncio.run(updater.update_photos())

    contents = album_contents(album_dir)
    assert contents["beach.jpg"] == b"beach"
    assert not (album_dir / "2023").exists()


def test_unconverted_heic_is_not_published(album_dir, make_updater, monkeypatch):
    """Only processed, frame-readable formats reach the album directory."""
    updater = make_updater(
        FakeClient(archive=make_archive({"ok.jpg": b"jpeg", "raw.heic": b"heic"}))
    )

    real_process = photo_updater_module.process_media_files

    def leave_heic_unconverted(input_files, output_dir):
        real_process([f for f in input_files if not f.endswith(".heic")], output_dir)
        return list(input_files)

    monkeypatch.setattr(
        photo_updater_module, "process_media_files", leave_heic_unconverted
    )

    asyncio.run(updater.update_photos())

    contents = album_contents(album_dir)
    assert contents["ok.jpg"] == b"jpeg"
    assert "raw.heic" not in contents


def test_colliding_basenames_are_both_published(album_dir, make_updater):
    updater = make_updater(
        FakeClient(
            archive=make_archive({"a/photo.jpg": b"first", "b/photo.jpg": b"second"})
        )
    )

    asyncio.run(updater.update_photos())

    contents = album_contents(album_dir)
    assert sorted(n for n in contents if n.endswith(".jpg")) == [
        "photo.jpg",
        "photo_1.jpg",
    ]


# --- (g) a leftover staging directory is cleaned ------------------------------


def test_leftover_staging_directory_is_cleaned_on_success(album_dir, make_updater):
    stale = staging_path(album_dir)
    stale.mkdir()
    (stale / "stale.jpg").write_bytes(b"stale-jpeg")
    (stale / "photos.zip").write_bytes(b"stale-archive")

    updater = make_updater(FakeClient())
    asyncio.run(updater.update_photos())

    contents = album_contents(album_dir)
    assert "stale.jpg" not in contents  # never served as a photo
    assert sorted(n for n in contents if n.endswith(".jpg")) == [
        "new-1.jpg",
        "new-2.jpg",
    ]
    assert not stale.exists()


def test_staging_starts_empty_even_after_a_crashed_run(album_dir, make_updater):
    """Nothing a crashed run left behind can be mistaken for part of the new batch."""
    stale = staging_path(album_dir)
    stale.mkdir()
    (stale / "stale.jpg").write_bytes(b"stale-jpeg")
    (stale / "photos.zip").write_bytes(b"stale-archive")

    seen = []
    updater = make_updater(
        FakeClient(on_get_assets=lambda: seen.append(sorted(os.listdir(stale))))
    )

    asyncio.run(updater.update_photos())

    assert seen == [[]]


def test_leftover_staging_directory_is_cleaned_on_failure(album_dir, make_updater):
    stale = staging_path(album_dir)
    stale.mkdir()
    (stale / "stale.jpg").write_bytes(b"stale-jpeg")

    updater = make_updater(FakeClient(get_error=RuntimeError("boom")))
    before = album_contents(album_dir)
    asyncio.run(updater.update_photos())

    assert album_contents(album_dir) == before
    assert not stale.exists()


def test_staging_directory_is_hidden_and_ignored_by_cleanup():
    """Home Assistant's folder sensor globs `*`, which never matches a dotfile."""
    assert STAGING_DIR_NAME.startswith(".")


# --- rotation ----------------------------------------------------------------


def test_filter_rotation_wraps(album_dir, make_updater):
    updater = make_updater(FakeClient())

    asyncio.run(updater.update_photos())
    assert updater.current_filter_index == 1
    asyncio.run(updater.update_photos())
    assert updater.current_filter_index == 0
