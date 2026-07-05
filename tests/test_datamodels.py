from __future__ import annotations

import json
from pathlib import Path

import pytest

from daz2lora.models.datamodels import (
    HARDCODED_CAMERAS,
    HARDCODED_LIGHTING,
    CameraDef,
    CameraProfile,
    Character,
    CharacterMode,
    CharacterProject,
    LightingDef,
    Look,
    PoseGroup,
    TrainingHistoryEntry,
)


class TestCameraAndLightingDefs:
    def test_hardcoded_cameras_count(self) -> None:
        assert len(HARDCODED_CAMERAS) == 7

    def test_hardcoded_lighting_count(self) -> None:
        assert len(HARDCODED_LIGHTING) == 3

    def test_camera_def_creation(self) -> None:
        c = CameraDef("test_id", "desc", "use")
        assert c.id == "test_id"
        assert c.description == "desc"
        assert c.typical_use == "use"

    def test_lighting_def_creation(self) -> None:
        l = LightingDef("test_id", "desc")
        assert l.id == "test_id"
        assert l.description == "desc"


class TestCameraProfile:
    def test_default_creation(self) -> None:
        cp = CameraProfile("test_profile")
        assert cp.camera_profile_id == "test_profile"
        assert cp.cameras == []
        assert cp.lighting == []

    def test_to_dict(self) -> None:
        cp = CameraProfile("profile_1", ["cam_a"], ["light_b"])
        d = cp.to_dict()
        assert d["camera_profile_id"] == "profile_1"
        assert d["cameras"] == ["cam_a"]
        assert d["lighting"] == ["light_b"]

    def test_default_profiles_loaded(self) -> None:
        from daz2lora.models.datamodels import DEFAULT_CAMERA_PROFILES
        assert len(DEFAULT_CAMERA_PROFILES) == 4
        ids = [p.camera_profile_id for p in DEFAULT_CAMERA_PROFILES]
        assert "full_coverage" in ids
        assert "action_full_body" in ids
        assert "portrait_and_half_body" in ids
        assert "face_focus" in ids


class TestPoseGroup:
    def test_default_creation(self) -> None:
        pg = PoseGroup("pg_1", "Pose Group 1")
        assert pg.pose_group_id == "pg_1"
        assert pg.display_name == "Pose Group 1"
        assert pg.pose_asset_paths == []
        assert pg.default_camera_profile == "full_coverage"
        assert pg.assigned_camera_profile == "full_coverage"

    def test_to_dict(self) -> None:
        pg = PoseGroup("kick", "Kicks", ["kick.duf"])
        pg.assigned_camera_profile = "action_full_body"
        pg.camera_overrides = ["full_body_front"]
        d = pg.to_dict()
        assert d["pose_group_id"] == "kick"
        assert d["camera_overrides"] == ["full_body_front"]
        assert d["assigned_camera_profile"] == "action_full_body"

    def test_to_dict_no_overrides(self) -> None:
        pg = PoseGroup("kick", "Kicks")
        d = pg.to_dict()
        assert d["camera_overrides"] is None
        assert d["lighting_overrides"] is None


class TestLook:
    def test_default_creation(self) -> None:
        look = Look("kelly karate")
        assert look.trigger_phrase == "kelly karate"
        assert look.wardrobe_asset_paths == []
        assert look.hair_override_path is None
        assert look.pose_group_ids == []
        assert look.include_in_dataset is True

    def test_to_dict(self) -> None:
        look = Look("test", ["a.duf"], hair_override_path="h.duf", pose_group_ids=["pg1"])
        d = look.to_dict()
        assert d["trigger_phrase"] == "test"
        assert d["wardrobe_asset_paths"] == ["a.duf"]
        assert d["hair_override_path"] == "h.duf"
        assert d["pose_group_ids"] == ["pg1"]
        assert d["include_in_dataset"] is True

    def test_to_dict_exclude(self) -> None:
        look = Look("skip", include_in_dataset=False)
        d = look.to_dict()
        assert d["include_in_dataset"] is False


class TestCharacter:
    def test_default_creation(self) -> None:
        c = Character("kelly", "kelly", "fig.duf", "shape.duf", "skin.duf", "hair.duf")
        assert c.character_id == "kelly"
        assert c.base_trigger_word == "kelly"
        assert c.mode == CharacterMode.MODULAR
        assert c.static_tags == []

    def test_fixed_mode(self) -> None:
        c = Character("kelly", "kelly", "fig.duf", "shape.duf", "skin.duf", "hair.duf",
                       mode=CharacterMode.FIXED)
        assert c.mode == CharacterMode.FIXED

    def test_to_dict(self) -> None:
        c = Character("kelly", "kelly", "fig.duf", "shape.duf", "skin.duf", "hair.duf",
                       static_tags=["female", "human"])
        d = c.to_dict()
        assert d["character_id"] == "kelly"
        assert d["mode"] == "modular"
        assert d["static_tags"] == ["female", "human"]

    def test_to_dict_fixed(self) -> None:
        c = Character("kelly", "kelly", "fig.duf", "shape.duf", "skin.duf", "hair.duf",
                       mode=CharacterMode.FIXED)
        d = c.to_dict()
        assert d["mode"] == "fixed"


class TestTrainingHistoryEntry:
    def test_creation(self) -> None:
        e = TrainingHistoryEntry(1, ["look_a"], "/path/to/lora.safetensors")
        assert e.version == 1
        assert e.looks_included == ["look_a"]
        assert e.path == "/path/to/lora.safetensors"

    def test_to_dict(self) -> None:
        e = TrainingHistoryEntry(2, ["a", "b"], "/p.safetensors")
        d = e.to_dict()
        assert d["version"] == 2
        assert d["looks_included"] == ["a", "b"]


class TestCharacterProject:
    def test_minimal_creation(self) -> None:
        c = Character("kelly", "kelly", "f.duf", "s.duf", "sk.duf", "h.duf")
        p = CharacterProject("kelly", c)
        assert p.project_id == "kelly"
        assert p.looks == []
        assert p.pose_groups == []
        assert p.trained_lora_path is None
        assert p.training_history == []

    def test_next_version_empty(self) -> None:
        c = Character("kelly", "kelly", "f.duf", "s.duf", "sk.duf", "h.duf")
        p = CharacterProject("kelly", c)
        assert p.next_version == 1

    def test_next_version_increments(self) -> None:
        c = Character("kelly", "kelly", "f.duf", "s.duf", "sk.duf", "h.duf")
        p = CharacterProject("kelly", c)
        p.training_history.append(TrainingHistoryEntry(1, ["a"], "/p1.safetensors"))
        assert p.next_version == 2
        p.training_history.append(TrainingHistoryEntry(2, ["b"], "/p2.safetensors"))
        assert p.next_version == 3

    def test_roundtrip_serialization(self, tmp_path: Path) -> None:
        c = Character("kelly", "kelly", "f.duf", "s.duf", "sk.duf", "h.duf",
                       static_tags=["female"], mode=CharacterMode.MODULAR)
        p = CharacterProject("kelly", c)
        p.looks.append(Look("look1", ["w.duf"], pose_group_ids=["pg1"]))
        p.pose_groups.append(PoseGroup("pg1", "PG1"))
        p.camera_profiles.append(CameraProfile("custom", ["cam1"], ["light1"]))
        p.training_history.append(TrainingHistoryEntry(1, ["look1"], "/lora_v1.safetensors"))
        p.trained_lora_path = "/lora_v1.safetensors"

        f = tmp_path / "project.json"
        p.save(f)
        assert f.exists()

        loaded = CharacterProject.load(f)
        assert loaded.project_id == "kelly"
        assert loaded.character.base_trigger_word == "kelly"
        assert loaded.character.mode == CharacterMode.MODULAR
        assert loaded.character.static_tags == ["female"]
        assert len(loaded.looks) == 1
        assert loaded.looks[0].trigger_phrase == "look1"
        assert loaded.looks[0].wardrobe_asset_paths == ["w.duf"]
        assert len(loaded.pose_groups) == 1
        assert loaded.pose_groups[0].pose_group_id == "pg1"
        assert len(loaded.camera_profiles) == 1
        assert loaded.camera_profiles[0].camera_profile_id == "custom"
        assert len(loaded.training_history) == 1
        assert loaded.training_history[0].version == 1
        assert loaded.trained_lora_path == "/lora_v1.safetensors"

    def test_roundtrip_handles_empty_looks(self, tmp_path: Path) -> None:
        c = Character("kelly", "kelly", "f.duf", "s.duf", "sk.duf", "h.duf")
        p = CharacterProject("kelly", c)
        f = tmp_path / "project.json"
        p.save(f)
        loaded = CharacterProject.load(f)
        assert loaded.looks == []

    def test_dataset_root_path_default(self) -> None:
        c = Character("kelly", "kelly", "f.duf", "s.duf", "sk.duf", "h.duf")
        p = CharacterProject("kelly", c)
        assert "projects/kelly/dataset" in str(p.dataset_root_path)

    def test_dataset_root_path_configured(self) -> None:
        c = Character("kelly", "kelly", "f.duf", "s.duf", "sk.duf", "h.duf")
        p = CharacterProject("kelly", c, dataset_root="/custom/dataset")
        assert str(p.dataset_root_path) == "/custom/dataset"
