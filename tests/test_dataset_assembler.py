from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from daz2lora.models.datamodels import Character, CharacterProject, Look, PoseGroup
from daz2lora.utils.config import AppConfig
from daz2lora.utils.dataset_assembler import (
    _compute_repeats,
    _generate_caption,
    assemble_dataset,
    find_replace_captions,
    get_dataset_stats,
    load_captions,
    sanitize_trigger,
    save_captions,
)


class TestSanitizeTrigger:
    def test_basic(self) -> None:
        assert sanitize_trigger("kelly karate") == "kelly_karate"

    def test_lowercase(self) -> None:
        assert sanitize_trigger("Kelly Karate") == "kelly_karate"

    def test_special_chars(self) -> None:
        assert sanitize_trigger("kelly's look!") == "kelly_s_look_"

    def test_alphanumeric_only(self) -> None:
        assert sanitize_trigger("hello123") == "hello123"

    def test_empty(self) -> None:
        assert sanitize_trigger("") == ""


class TestComputeRepeats:
    def test_balanced(self) -> None:
        counts = {"a": 40, "b": 20}
        repeats = _compute_repeats(counts)
        # max=40: a=40/40*10=10, b=40/20*10=20
        assert repeats["a"] == 10
        assert repeats["b"] == 20

    def test_equal_counts(self) -> None:
        counts = {"a": 30, "b": 30}
        repeats = _compute_repeats(counts)
        assert repeats["a"] == 10
        assert repeats["b"] == 10

    def test_minimum_repeats(self) -> None:
        counts = {"a": 200, "b": 1}
        repeats = _compute_repeats(counts)
        # b: 200/1*10=2000, but that's fine; minimum is 1
        assert repeats["b"] >= 1

    def test_single_look(self) -> None:
        counts = {"a": 50}
        repeats = _compute_repeats(counts)
        assert repeats["a"] == 10

    def test_empty(self) -> None:
        assert _compute_repeats({}) == {}

    def test_rounding(self) -> None:
        counts = {"a": 30, "b": 20}
        repeats = _compute_repeats(counts)
        # max=30: a=30/30*10=10, b=30/20*10=15
        assert repeats["a"] == 10
        assert repeats["b"] == 15


class TestGenerateCaption:
    def test_basic(self) -> None:
        caption = _generate_caption(
            "kelly karate", "kelly",
            "front_kick", "full_body_front", "studio_3point",
            ["female", "human"],
        )
        assert "kelly karate" in caption
        assert "kelly" in caption
        assert "full body" in caption
        assert "studio lighting" in caption
        assert "female" in caption
        assert "human" in caption

    def test_no_static_tags(self) -> None:
        caption = _generate_caption(
            "kelly casual", "kelly",
            "standing", "portrait_close", "dramatic_rim",
            [],
        )
        assert "kelly casual" in caption
        assert "close-up" in caption
        assert "dramatic rim lighting" in caption
        assert "kelly" in caption

    def test_unknown_camera(self) -> None:
        caption = _generate_caption(
            "test", "test", "pose", "unknown_cam", "studio_3point", []
        )
        assert "unknown cam" in caption  # fallback: replace _ with space

    def test_unknown_lighting(self) -> None:
        caption = _generate_caption(
            "test", "test", "pose", "full_body_front", "unknown_light", []
        )
        assert "unknown light" in caption


class TestAssembleDataset:
    @pytest.fixture
    def project(self) -> CharacterProject:
        c = Character("kelly", "kelly", "f.duf", "s.duf", "sk.duf", "h.duf",
                       static_tags=["female"])
        p = CharacterProject("kelly", c)
        p.looks = [
            Look("kelly karate", wardrobe_asset_paths=["gi.duf"],
                 pose_group_ids=["pg1"], include_in_dataset=True),
            Look("kelly casual", wardrobe_asset_paths=["jeans.duf"],
                 pose_group_ids=["pg2"], include_in_dataset=True),
        ]
        p.pose_groups = [
            PoseGroup("pg1", "Karate", ["front_kick.duf", "side_kick.duf"]),
            PoseGroup("pg2", "Casual", ["standing.duf"]),
        ]
        p.camera_profiles = []
        return p

    @pytest.fixture
    def config(self, tmp_path: Path) -> AppConfig:
        cfg = AppConfig()
        cfg.workspace_root = str(tmp_path / "workspace")
        cfg.kohya_ss_path = str(tmp_path / "kohya")
        cfg.sdxl_checkpoint_path = str(tmp_path / "model.safetensors")
        return cfg

    def _create_render_file(self, render_dir: Path, trigger: str, pose: str,
                            camera: str, lighting: str) -> Path:
        fname = f"{sanitize_trigger(trigger)}__{pose}__{camera}__{lighting}.png"
        f = render_dir / fname
        f.write_text("fake_png_content")
        return f

    def _create_render_files(self, render_dir: Path) -> None:
        render_dir.mkdir(parents=True, exist_ok=True)
        # 4 karate renders: 2 poses × 1 camera × 2 lighting
        for pose in ["front_kick", "side_kick"]:
            for cam in ["full_body_front"]:
                for light in ["studio_3point", "dramatic_rim"]:
                    self._create_render_file(render_dir, "kelly karate", pose, cam, light)
        # 2 casual renders: 1 pose × 1 camera × 2 lighting
        for cam in ["half_body"]:
            for light in ["studio_3point", "dramatic_rim"]:
                self._create_render_file(render_dir, "kelly casual", "standing", cam, light)

    def test_assemble_basic(self, project: CharacterProject, config: AppConfig,
                            tmp_path: Path) -> None:
        render_dir = tmp_path / "renders"
        self._create_render_files(render_dir)

        dataset_root = assemble_dataset(project, config, render_dir)

        assert dataset_root.exists()
        assert project.dataset_root == str(dataset_root)

        # Check folder structure
        folders = [d.name for d in dataset_root.iterdir() if d.is_dir()]
        assert any("kelly_karate" in f for f in folders)
        assert any("kelly_casual" in f for f in folders)

        # Check repeats prefix exists
        for folder in folders:
            assert "_" in folder
            repeat_part = folder.split("_")[0]
            assert repeat_part.isdigit()

        # Check images exist
        images = list(dataset_root.rglob("*.png"))
        assert len(images) == 6  # 4 karate + 2 casual

        # Check captions exist
        captions = list(dataset_root.rglob("*.txt"))
        assert len(captions) == 6

        # Verify caption content
        first_cap = captions[0].read_text()
        assert "kelly" in first_cap
        assert "female" in first_cap

    def test_overwrite_flag(self, project: CharacterProject, config: AppConfig,
                            tmp_path: Path) -> None:
        render_dir = tmp_path / "renders"
        self._create_render_files(render_dir)
        dataset_root = assemble_dataset(project, config, render_dir)

        # Modify a caption
        txt_files = list(dataset_root.rglob("*.txt"))
        old_text = txt_files[0].read_text()
        txt_files[0].write_text("modified caption")

        # Reassemble without overwrite
        assemble_dataset(project, config, render_dir, overwrite=False)
        assert txt_files[0].read_text() == "modified caption"  # unchanged

        # Reassemble with overwrite
        assemble_dataset(project, config, render_dir, overwrite=True)
        assert txt_files[0].read_text() == old_text  # restored

    def test_skip_disabled_looks(self, project: CharacterProject, config: AppConfig,
                                  tmp_path: Path) -> None:
        project.looks[1].include_in_dataset = False
        render_dir = tmp_path / "renders"
        self._create_render_files(render_dir)

        dataset_root = assemble_dataset(project, config, render_dir)
        folders = [d.name for d in dataset_root.iterdir() if d.is_dir()]
        casual_folders = [f for f in folders if "casual" in f]
        assert len(casual_folders) == 0  # excluded

    def test_no_render_files(self, project: CharacterProject, config: AppConfig,
                             tmp_path: Path) -> None:
        render_dir = tmp_path / "empty_renders"
        render_dir.mkdir(parents=True, exist_ok=True)
        dataset_root = assemble_dataset(project, config, render_dir)
        assert dataset_root.exists()
        images = list(dataset_root.rglob("*.png"))
        assert len(images) == 0

    def test_repeats_balancing(self, project: CharacterProject, config: AppConfig,
                               tmp_path: Path) -> None:
        render_dir = tmp_path / "renders"
        render_dir.mkdir(parents=True, exist_ok=True)
        # 4 karate renders
        for pose in ["front_kick", "side_kick"]:
            for light in ["studio_3point", "dramatic_rim"]:
                self._create_render_file(render_dir, "kelly karate", pose,
                                         "full_body_front", light)
        # 2 casual renders
        for light in ["studio_3point", "dramatic_rim"]:
            self._create_render_file(render_dir, "kelly casual", "standing",
                                     "half_body", light)

        dataset_root = assemble_dataset(project, config, render_dir)
        folders = {d.name for d in dataset_root.iterdir() if d.is_dir()}
        for fname in folders:
            repeat = int(fname.split("_")[0])
            assert repeat >= 1

        # Casual (2 images) should get more repeats than karate (4 images)
        karate_repeat = None
        casual_repeat = None
        for fname in folders:
            if "karate" in fname:
                karate_repeat = int(fname.split("_")[0])
            if "casual" in fname:
                casual_repeat = int(fname.split("_")[0])
        assert karate_repeat is not None
        assert casual_repeat is not None
        assert casual_repeat > karate_repeat


class TestLoadAndSaveCaptions:
    def test_roundtrip(self, tmp_path: Path) -> None:
        folder = tmp_path / "5_test_look"
        folder.mkdir(parents=True)
        (folder / "image1.png").write_text("img")
        (folder / "image1.txt").write_text("tag1, tag2")
        (folder / "image2.png").write_text("img")
        (folder / "image2.txt").write_text("tag3, tag4")

        captions = load_captions(tmp_path)
        assert len(captions) == 2
        assert "5_test_look/image1.txt" in captions
        assert captions["5_test_look/image1.txt"] == "tag1, tag2"

    def test_save_captions(self, tmp_path: Path) -> None:
        folder = tmp_path / "10_test"
        folder.mkdir(parents=True)
        captions = {"10_test/img.txt": "new caption"}
        save_captions(tmp_path, captions)
        assert (folder / "img.txt").exists()
        assert (folder / "img.txt").read_text() == "new caption"

    def test_empty_dataset(self, tmp_path: Path) -> None:
        captions = load_captions(tmp_path / "nonexistent")
        assert captions == {}


class TestFindReplaceCaptions:
    def test_find_replace(self, tmp_path: Path) -> None:
        folder = tmp_path / "5_test"
        folder.mkdir()
        (folder / "img.txt").write_text("kelly, full body, studio, female")
        (folder / "img2.txt").write_text("kelly, portrait, studio, female")

        count = find_replace_captions(tmp_path, "studio", "studio lighting")
        assert count == 2
        assert "studio lighting" in (folder / "img.txt").read_text()
        assert "studio lighting" in (folder / "img2.txt").read_text()

    def test_no_match(self, tmp_path: Path) -> None:
        folder = tmp_path / "5_test"
        folder.mkdir()
        (folder / "img.txt").write_text("some tags")
        count = find_replace_captions(tmp_path, "nonexistent", "x")
        assert count == 0

    def test_empty_dir(self, tmp_path: Path) -> None:
        count = find_replace_captions(tmp_path / "empty", "a", "b")
        assert count == 0


class TestGetDatasetStats:
    def test_basic_stats(self, tmp_path: Path) -> None:
        for i in range(3):
            folder = tmp_path / f"5_look_{i}"
            folder.mkdir()
            (folder / f"img{i}.png").write_text("img")
            (folder / f"img{i}.txt").write_text("tags")

        stats = get_dataset_stats(tmp_path)
        assert stats["total_images"] == 3
        assert stats["total_captions"] == 3
        assert len(stats["per_look_counts"]) == 3

    def test_no_dataset(self, tmp_path: Path) -> None:
        stats = get_dataset_stats(tmp_path / "nonexistent")
        assert stats["total_images"] == 0
        assert stats["total_captions"] == 0
        assert stats["image_dimensions_sample"] is None

    def test_only_images_no_captions(self, tmp_path: Path) -> None:
        folder = tmp_path / "5_test"
        folder.mkdir()
        (folder / "img.png").write_text("img")
        stats = get_dataset_stats(tmp_path)
        assert stats["total_images"] == 1
        assert stats["total_captions"] == 0
