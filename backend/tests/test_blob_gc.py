"""Tests for blob garbage collection helpers."""

from datum.services.blob_gc import find_orphan_blobs, purge_quarantine, quarantine_blobs


def test_find_orphan_blobs():
    referenced = {"ab/cd/keep.txt"}
    on_disk = {"ab/cd/keep.txt", "ef/gh/orphan.txt"}
    assert find_orphan_blobs(referenced, on_disk) == {"ef/gh/orphan.txt"}


def test_quarantine_and_purge(tmp_path):
    blobs = tmp_path / "blobs"
    quarantine = tmp_path / "quarantine"
    blob_path = blobs / "ab" / "cd" / "orphan.txt"
    blob_path.parent.mkdir(parents=True)
    blob_path.write_text("data")

    moved = quarantine_blobs({"ab/cd/orphan.txt"}, blobs, quarantine)
    assert moved == 1
    assert not blob_path.exists()
    quarantined = quarantine / "ab" / "cd" / "orphan.txt"
    assert quarantined.exists()

    assert purge_quarantine(quarantine, min_age_days=0) == 1
    assert not quarantined.exists()
