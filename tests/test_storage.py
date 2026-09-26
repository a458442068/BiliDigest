import os
import time
from pathlib import Path

import pytest

from src.models.domain import ArtifactKind
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

    def test_artifact_api_lists_and_loads_part_outputs(self, tmp_path):
        storage = ResultStorage(str(tmp_path))
        bv_id = "BV1xx411c7mD"

        storage.save_artifact(
            bv_id, 1, 2, ArtifactKind.TRANSCRIPT, "hello world"
        )
        storage.save_artifact(
            bv_id, 1, 2, ArtifactKind.SEGMENTS, [{"start": 0, "end": 1}]
        )

        artifacts = storage.list_part_artifacts(bv_id, 1, 2)

        assert artifacts["transcript"] is True
        assert artifacts["segments"] is True
        assert artifacts["translation"] is False
        assert storage.load_artifact(bv_id, 1, 2, "transcript") == "hello world"

    def test_summary_insights_are_stored_as_json(self, tmp_path):
        storage = ResultStorage(str(tmp_path))
        bv_id = "BV1xx411c7mD"
        storage.save_summary(
            bv_id,
            1,
            1,
            {
                "transcript_clean": "clean",
                "summary": "summary",
                "key_points": ["point"],
                "chapters": [{"title": "开场", "summary": "介绍"}],
                "action_items": ["复习"],
                "entities": [{"name": "BiliDigest", "type": "项目"}],
            },
        )

        insights = storage.load_insights(bv_id, 1, 1)

        assert insights["key_points"] == ["point"]
        assert insights["chapters"][0]["title"] == "开场"

    def test_audio_download_transaction_moves_audio_to_final_path(self, tmp_path):
        storage = ResultStorage(str(tmp_path))
        bv_id = "BV1xx411c7mD"

        with storage.audio_download_transaction(bv_id, 1, 1) as tx:
            source = tx.work_dir / "audio.wav"
            source.write_bytes(b"audio")

            final_path = Path(tx.commit_audio(str(source)))
            work_dir = tx.work_dir

            assert final_path.read_bytes() == b"audio"
            assert not source.exists()

        assert not work_dir.exists()
        assert not (tmp_path / bv_id / ".staging").exists()

    def test_audio_download_transaction_rolls_back_without_replacing_final(
        self, tmp_path
    ):
        storage = ResultStorage(str(tmp_path))
        bv_id = "BV1xx411c7mD"
        existing = tmp_path / "existing.wav"
        existing.write_bytes(b"old")
        final_path = Path(storage.save_audio(bv_id, 1, 1, str(existing)))

        with pytest.raises(RuntimeError):
            with storage.audio_download_transaction(bv_id, 1, 1) as tx:
                staged = tx.work_dir / "audio.wav"
                staged.write_bytes(b"new")
                work_dir = tx.work_dir
                raise RuntimeError("boom")

        assert final_path.read_bytes() == b"old"
        assert not work_dir.exists()

    def test_cleanup_staging_removes_old_orphan_download_dirs(self, tmp_path):
        storage = ResultStorage(str(tmp_path))
        bv_id = "BV1xx411c7mD"
        staging_dir = storage.get_dir(bv_id) / ".staging"
        old_dir = staging_dir / "download-old"
        fresh_dir = staging_dir / "download-fresh"
        old_dir.mkdir(parents=True)
        fresh_dir.mkdir()
        old_time = time.time() - 7200
        os.utime(old_dir, (old_time, old_time))

        deleted = storage.cleanup_staging(max_age_hours=1)

        assert old_dir in deleted
        assert not old_dir.exists()
        assert fresh_dir.exists()

    def test_delete_artifacts_respects_from_step(self, tmp_path):
        storage = ResultStorage(str(tmp_path))
        bv_id = "BV1xx411c7mD"
        storage.save_transcript(bv_id, 1, 1, "hello")
        storage.save_translation(bv_id, 1, 1, "你好")
        storage.save_summary(
            bv_id,
            1,
            1,
            {"transcript_clean": "clean", "summary": "summary"},
        )

        deleted = storage.delete_artifacts(bv_id, 1, 1, "translation")

        assert {path.name for path in deleted} == {
            "translation.txt",
            "summary.txt",
            "transcript_clean.txt",
        }
        assert storage.has_transcript(bv_id, 1, 1) is True
        assert storage.has_translation(bv_id, 1, 1) is False
        assert storage.has_summary(bv_id, 1, 1) is False
