from __future__ import annotations

from pathlib import Path

import uuid
import pytest

from daz2lora.models.datamodels import (
    CameraProfile,
    Character,
    CharacterMode,
    CharacterProject,
    Look,
    PoseGroup,
)
from daz2lora.utils.config import AppConfig
from daz2lora.utils.dataset_assembler import (
    assemble_dataset,
    find_replace_captions,
    get_dataset_stats,
    load_captions,
    sanitize_trigger,
)
from daz2lora.utils.render_math import (
    compute_render_counts,
    estimate_render_time,
    validate_render_counts,
)


@pytest.fixture
def full_project() -> CharacterProject:
    """Create a realistic project with multiple looks, pose groups, and camera profiles."""
    character = Character(
        character_id="kelly",
        base_trigger_word="kelly",
        figure_asset_path="/Content/People/Genesis 9/Figures/Genesis 9 Base.duf",
        shape_preset_path="/Content/People/Genesis 9/Shapes/Kelly.duf",
        skin_material_path="/Content/People/Genesis 9/Materials/Kelly Skin.duf",
        default_hair_asset_path="/Content/People/Genesis 9/Hair/Bob Cut.duf",
        mode=CharacterMode.MODULAR,
        static_tags=["female", "human", "realistic", "photorealistic"],
    )

    project = CharacterProject(project_id="kelly", character=character)

    # Camera profiles
    project.camera_profiles = [
        CameraProfile("full_coverage",
                       cameras=["portrait_close", "half_body", "full_body_front",
                                "full_body_3q", "full_body_profile",
                                "full_body_low_angle", "full_body_high_angle"],
                       lighting=["studio_3point", "soft_outdoor_hdri", "dramatic_rim"]),
        CameraProfile("action_full_body",
                       cameras=["full_body_front", "full_body_3q", "full_body_low_angle"],
                       lighting=["studio_3point", "dramatic_rim"]),
        CameraProfile("portrait_and_half_body",
                       cameras=["portrait_close", "half_body", "full_body_front"],
                       lighting=["studio_3point", "soft_outdoor_hdri"]),
        CameraProfile("face_focus",
                       cameras=["portrait_close"],
                       lighting=["studio_3point"]),
    ]

    # Pose groups
    project.pose_groups = [
        PoseGroup(
            pose_group_id="karate_kicks",
            display_name="Karate - Kicks & Strikes",
            pose_asset_paths=[
                "/Poses/front_kick.duf",
                "/Poses/side_kick.duf",
                "/Poses/roundhouse.duf",
                "/Poses/punch_combo.duf",
            ],
            assigned_camera_profile="action_full_body",
        ),
        PoseGroup(
            pose_group_id="karate_stances",
            display_name="Karate - Stances",
            pose_asset_paths=[
                "/Poses/forward_stance.duf",
                "/Poses/back_stance.duf",
                "/Poses/horse_stance.duf",
            ],
            assigned_camera_profile="portrait_and_half_body",
        ),
        PoseGroup(
            pose_group_id="office_seated",
            display_name="Office - Seated",
            pose_asset_paths=[
                "/Poses/desk_sitting.duf",
                "/Poses/chair_crossed.duf",
                "/Poses/leaning_back.duf",
            ],
            assigned_camera_profile="portrait_and_half_body",
        ),
    ]

    # Looks
    project.looks = [
        Look(
            trigger_phrase="kelly karate",
            wardrobe_asset_paths=["/Wardrobe/karate_gi.duf", "/Wardrobe/belt.duf"],
            pose_group_ids=["karate_kicks", "karate_stances"],
            include_in_dataset=True,
        ),
        Look(
            trigger_phrase="kelly office",
            wardrobe_asset_paths=["/Wardrobe/blazer.duf", "/Wardrobe/slacks.duf"],
            hair_override_path="/Hair/updo.duf",
            pose_group_ids=["office_seated"],
            include_in_dataset=True,
        ),
        Look(
            trigger_phrase="kelly casual",
            wardrobe_asset_paths=["/Wardrobe/tshirt.duf", "/Wardrobe/jeans.duf"],
            pose_group_ids=["office_seated"],
            include_in_dataset=True,
        ),
    ]

    return project


class TestEndToEndRenderMath:
    """Test the render math with a realistic project."""

    def test_compute_render_counts_full_project(self, full_project: CharacterProject) -> None:
        result = compute_render_counts(full_project)
        assert result["total"] > 0

        # kelly karate: karate_kicks (4 poses × 3 cameras × 2 lighting = 24)
        #              + karate_stances (3 poses × 3 cameras × 2 lighting = 18)
        #              = 42
        assert result["per_look"]["kelly karate"] == 42

        # kelly office: office_seated (3 poses × 3 cameras × 2 lighting = 18)
        assert result["per_look"]["kelly office"] == 18

        # kelly casual: same as office (shares the pose group)
        assert result["per_look"]["kelly casual"] == 18

        # Total = 42 + 18 + 18 = 78
        assert result["total"] == 78

    def test_validate_render_counts(self, full_project: CharacterProject) -> None:
        warnings = validate_render_counts(full_project)
        # kelly karate has 42 images (in valid 20-80 range)
        # kelly office/casual each have 18 images (below 20)
        assert len(warnings) >= 2  # at least the two < 20 looks
        assert any("office" in w for w in warnings)
        assert any("casual" in w for w in warnings)

    def test_estimate_render_time(self) -> None:
        # 78 renders, 10 done in 300 seconds = 30 sec/render
        est = estimate_render_time(78, 10, 300.0)
        assert abs(est - 2040.0) < 1  # 68 remaining × 30 sec

    def test_estimate_no_completions(self) -> None:
        assert estimate_render_time(78, 0, 0.0) == 0.0


class TestEndToEndDatasetAssembly:
    """Test the full dataset assembly pipeline with rendered files."""

    def _simulate_renders(self, render_dir: Path, project: CharacterProject) -> None:
        render_dir.mkdir(parents=True, exist_ok=True)
        # Simulate renders based on the render math
        # kelly karate: 42 renders
        # kelly office: 18 renders
        # kelly casual: 18 renders
        for _ in range(42):
            f = render_dir / f"kelly_karate__pose_{uuid.uuid4().hex[:8]}__full_body_front__studio_3point.png"
            f.write_text("png")
        for _ in range(18):
            f = render_dir / f"kelly_office__pose_{__import__('uuid').uuid4().hex[:8]}__portrait_close__studio_3point.png"
            f.write_text("png")
        for _ in range(18):
            f = render_dir / f"kelly_casual__pose_{__import__('uuid').uuid4().hex[:8]}__half_body__soft_outdoor_hdri.png"
            f.write_text("png")

    def test_full_assembly_pipeline(self, full_project: CharacterProject, tmp_path: Path) -> None:
        config = AppConfig(workspace_root=str(tmp_path / "ws"))
        render_dir = tmp_path / "renders"
        self._simulate_renders(render_dir, full_project)

        # Run assembly
        dataset_root = assemble_dataset(full_project, config, render_dir)

        # Verify dataset structure
        assert dataset_root.exists()
        assert dataset_root == tmp_path / "ws" / "projects" / "kelly" / "dataset"

        # Check all images present
        images = list(dataset_root.rglob("*.png"))
        assert len(images) == 78  # all renders accounted for

        # Check captions present for all images
        captions = list(dataset_root.rglob("*.txt"))
        assert len(captions) == 78

        # Verify caption content
        for cap_file in captions:
            text = cap_file.read_text()
            assert "kelly" in text
            assert "female" in text
            assert "human" in text
            assert "realistic" in text

        # Verify per-look folder structure
        folders = {d.name for d in dataset_root.iterdir() if d.is_dir()}
        has_karate = any("kelly_karate" in f for f in folders)
        has_office = any("kelly_office" in f for f in folders)
        has_casual = any("kelly_casual" in f for f in folders)
        assert has_karate
        assert has_office
        assert has_casual

        # Verify repeats balancing: casual (18) should have more repeats
        # than karate (42)
        karate_repeats = None
        casual_repeats = None
        for fname in folders:
            parts = fname.split("_", 1)
            if "karate" in fname:
                karate_repeats = int(parts[0])
            if "casual" in fname:
                casual_repeats = int(parts[0])
        assert karate_repeats is not None
        assert casual_repeats is not None
        assert casual_repeats > karate_repeats

    def test_caption_find_replace(self, full_project: CharacterProject,
                                   tmp_path: Path) -> None:
        config = AppConfig(workspace_root=str(tmp_path / "ws"))
        render_dir = tmp_path / "renders"
        self._simulate_renders(render_dir, full_project)
        dataset_root = assemble_dataset(full_project, config, render_dir)

        # Find and replace across all captions (every caption contains "kelly")
        count = find_replace_captions(dataset_root, "kelly", "KELY")
        assert count > 0

        # Verify all captions updated
        captions = list(dataset_root.rglob("*.txt"))
        assert len(captions) == 78
        for cap_file in captions:
            text = cap_file.read_text()
            assert "KELY" in text

    def test_get_dataset_stats(self, full_project: CharacterProject,
                                tmp_path: Path) -> None:
        config = AppConfig(workspace_root=str(tmp_path / "ws"))
        render_dir = tmp_path / "renders"
        self._simulate_renders(render_dir, full_project)
        dataset_root = assemble_dataset(full_project, config, render_dir)

        stats = get_dataset_stats(dataset_root)
        assert stats["total_images"] == 78
        assert stats["total_captions"] == 78
        assert len(stats["per_look_counts"]) == 3

    def test_reassemble_preserves_modified_captions(self, full_project: CharacterProject,
                                                      tmp_path: Path) -> None:
        config = AppConfig(workspace_root=str(tmp_path / "ws"))
        render_dir = tmp_path / "renders"
        self._simulate_renders(render_dir, full_project)
        dataset_root = assemble_dataset(full_project, config, render_dir)

        # Modify all captions
        for cap_file in dataset_root.rglob("*.txt"):
            cap_file.write_text("custom caption")

        # Reassemble without overwrite
        assemble_dataset(full_project, config, render_dir, overwrite=False)

        # Captions should be preserved
        for cap_file in dataset_root.rglob("*.txt"):
            assert cap_file.read_text() == "custom caption"

    def test_save_and_load_captions(self, full_project: CharacterProject,
                                     tmp_path: Path) -> None:
        config = AppConfig(workspace_root=str(tmp_path / "ws"))
        render_dir = tmp_path / "renders"
        self._simulate_renders(render_dir, full_project)
        dataset_root = assemble_dataset(full_project, config, render_dir)

        # Load, modify, save
        captions = load_captions(dataset_root)
        assert len(captions) == 78

        # Modify via dict: replace "kelly" with "KELY" across all captions
        for key in captions:
            captions[key] = captions[key].replace("kelly", "KELY")

        from daz2lora.utils.dataset_assembler import save_captions
        save_captions(dataset_root, captions)

        # Verify modification was persisted
        modified = load_captions(dataset_root)
        for key, val in modified.items():
            assert "KELY" in val
            assert "kelly" not in val.replace("KELY", "")  # only through the replacement


class TestSerializationRoundtrip:
    def test_full_project_roundtrip(self, full_project: CharacterProject,
                                     tmp_path: Path) -> None:
        f = tmp_path / "project.json"
        full_project.save(f)

        loaded = CharacterProject.load(f)
        assert loaded.project_id == full_project.project_id
        assert loaded.character.character_id == full_project.character.character_id
        assert loaded.character.static_tags == full_project.character.static_tags
        assert len(loaded.looks) == len(full_project.looks)
        assert len(loaded.pose_groups) == len(full_project.pose_groups)
        assert len(loaded.camera_profiles) == len(full_project.camera_profiles)

        for orig_look, loaded_look in zip(full_project.looks, loaded.looks):
            assert orig_look.trigger_phrase == loaded_look.trigger_phrase
            assert orig_look.pose_group_ids == loaded_look.pose_group_ids

    def test_character_mode_preserved(self, full_project: CharacterProject,
                                       tmp_path: Path) -> None:
        from daz2lora.models.datamodels import CharacterMode
        full_project.character.mode = CharacterMode.FIXED
        f = tmp_path / "project.json"
        full_project.save(f)
        loaded = CharacterProject.load(f)
        assert loaded.character.mode.value == "fixed"
