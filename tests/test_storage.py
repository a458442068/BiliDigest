import pytest

from src.utils.storage import ResultStorage


class TestResultStorageSafety:
    def test_save_and_load_metadata_for_valid_bv_id(self, tmp_path):
        storage = ResultStorage(str(tmp_path))
        metadata = {"bv_id": "BV1xx411c7mD", "title": "demo"}

        storage.save_metadata("BV1xx411c7mD", metadata)

        assert storage.load_metadata("BV1xx411c7mD") == metadata
        assert (tmp_path / "BV1xx411c7mD" / "metadata.json").exists()

    def test_save_and_load_metadata_for_hash_id(self, tmp_path):
        storage = ResultStorage(str(tmp_path))
        metadata = {"bv_id": "012345abcdef"}

        storage.save_metadata("012345abcdef", metadata)

        assert storage.load_metadata("012345abcdef") == metadata

    def test_rejects_path_traversal_id(self, tmp_path):
        storage = ResultStorage(str(tmp_path))

        with pytest.raises(ValueError):
            storage.get_dir("../outside")

        assert not (tmp_path.parent / "outside").exists()

    def test_delete_rejects_invalid_id_without_touching_parent(self, tmp_path):
        storage = ResultStorage(str(tmp_path / "results"))
        sentinel = tmp_path / "sentinel"
        sentinel.mkdir()

        with pytest.raises(ValueError):
            storage.delete_video("../sentinel")

        assert sentinel.exists()

    def test_list_videos_skips_invalid_directories(self, tmp_path):
        storage = ResultStorage(str(tmp_path))
        storage.save_metadata("BV1xx411c7mD", {"bv_id": "BV1xx411c7mD"})
        (tmp_path / "not-a-valid-id").mkdir()

        videos = storage.list_videos()

        assert [video["bv_id"] for video in videos] == ["BV1xx411c7mD"]
