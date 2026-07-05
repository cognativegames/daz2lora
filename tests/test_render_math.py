from __future__ import annotations

import pytest

from daz2lora.models.datamodels import (
    CameraProfile,
    Character,
    CharacterProject,
    PoseGroup,
)
from daz2lora.utils.render_math import (
    compute_render_counts,
    estimate_render_time,
    validate_render_counts,
)


def _make_project(pose_groups: list, looks: list, profiles: list | None = None) -> CharacterProject:
    c = Character("test", "test", "f.duf", "s.duf", "sk.duf", "h.duf")
    p = CharacterProject("test", c)
    p.pose_groups = pose_groups
    p.looks = looks
    if profiles:
        p.camera_profiles = profiles
    else:
        p.camera_profiles = [
            CameraProfile("default", ["cam1", "cam2"], ["light1"]),
        ]
    return p


class TestComputeRenderCounts:
    def test_single_pose_group_single_look(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", ["pose1.duf", "pose2.duf"],
                      assigned_camera_profile="default"),
        ]
        looks = [
            _make_look("look1", ["pg1"]),
        ]
        p = _make_project(pose_groups, looks)
        result = compute_render_counts(p)
        assert result["total"] == 4  # 2 poses × 2 cameras × 1 light
        assert result["per_look"]["look1"] == 4
        assert result["per_pose_group"]["pg1"] == 4

    def test_multiple_looks(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", ["p1.duf"],
                      assigned_camera_profile="default"),
        ]
        looks = [
            _make_look("look_a", ["pg1"]),
            _make_look("look_b", ["pg1"]),
        ]
        p = _make_project(pose_groups, looks)
        result = compute_render_counts(p)
        assert result["total"] == 4  # 2 looks × (1 pose × 2 cameras × 1 light)
        assert result["per_look"]["look_a"] == 2
        assert result["per_look"]["look_b"] == 2

    def test_camera_overrides(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", ["p1.duf"],
                      assigned_camera_profile="default",
                      camera_overrides=["cam_custom"]),
        ]
        looks = [_make_look("look1", ["pg1"])]
        p = _make_project(pose_groups, looks)
        result = compute_render_counts(p)
        assert result["total"] == 1  # 1 pose × 1 camera (override) × 1 light

    def test_lighting_overrides(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", ["p1.duf"],
                      assigned_camera_profile="default",
                      lighting_overrides=["light_custom"]),
        ]
        looks = [_make_look("look1", ["pg1"])]
        p = _make_project(pose_groups, looks)
        result = compute_render_counts(p)
        assert result["total"] == 2  # 1 pose × 2 cameras × 1 light (override)

    def test_no_poses_in_group(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", [], assigned_camera_profile="default"),
        ]
        looks = [_make_look("look1", ["pg1"])]
        p = _make_project(pose_groups, looks)
        result = compute_render_counts(p)
        assert result["total"] == 0
        assert result["per_look"]["look1"] == 0

    def test_pose_group_not_found(self) -> None:
        pose_groups: list = []
        looks = [_make_look("look1", ["nonexistent"])]
        p = _make_project(pose_groups, looks)
        result = compute_render_counts(p)
        assert result["total"] == 0

    def test_profile_not_found(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", ["p.duf"],
                      assigned_camera_profile="missing_profile"),
        ]
        looks = [_make_look("look1", ["pg1"])]
        p = _make_project(pose_groups, looks)
        result = compute_render_counts(p)
        assert result["total"] == 0

    def test_empty_project(self) -> None:
        c = Character("t", "t", "f.duf", "s.duf", "sk.duf", "h.duf")
        p = CharacterProject("t", c)
        result = compute_render_counts(p)
        assert result["total"] == 0
        assert result["per_look"] == {}
        assert result["per_pose_group"] == {}


class TestEstimateRenderTime:
    def test_no_completions(self) -> None:
        assert estimate_render_time(100, 0, 0.0) == 0.0

    def test_basic_estimate(self) -> None:
        # 10 renders in 100 seconds = 10 sec/render, 90 remaining = 900 sec
        est = estimate_render_time(100, 10, 100.0)
        assert abs(est - 900.0) < 0.001

    def test_exact_estimate(self) -> None:
        est = estimate_render_time(20, 5, 25.0)  # 5 sec/render, 15 remaining
        assert abs(est - 75.0) < 0.001

    def test_all_done(self) -> None:
        est = estimate_render_time(10, 10, 100.0)
        assert abs(est - 0.0) < 0.001

    def test_fast_render(self) -> None:
        est = estimate_render_time(100, 50, 25.0)  # 0.5 sec/render, 50 remaining
        assert abs(est - 25.0) < 0.001


class TestValidateRenderCounts:
    def test_valid_range(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", ["p1.duf"] * 20,
                      assigned_camera_profile="default"),
        ]
        looks = [_make_look("look1", ["pg1"])]
        p = _make_project(pose_groups, looks)
        # 2 cameras × 1 light × 20 poses = 40 images
        p.camera_profiles[0].cameras = ["cam1", "cam2"]
        p.camera_profiles[0].lighting = ["light1"]
        warnings = validate_render_counts(p)
        assert len(warnings) == 0

    def test_too_few(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", ["p1.duf"],
                      assigned_camera_profile="default"),
        ]
        looks = [_make_look("look1", ["pg1"])]
        p = _make_project(pose_groups, looks)
        p.camera_profiles[0].cameras = ["cam1"]
        p.camera_profiles[0].lighting = ["light1"]
        warnings = validate_render_counts(p)
        assert len(warnings) == 1
        assert "only gets" in warnings[0]

    def test_too_many(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", ["p1.duf"] * 30,
                      assigned_camera_profile="default"),
        ]
        looks = [_make_look("look1", ["pg1"])]
        p = _make_project(pose_groups, looks)
        p.camera_profiles[0].cameras = ["cam1", "cam2", "cam3"]
        p.camera_profiles[0].lighting = ["light1"]
        warnings = validate_render_counts(p)
        assert len(warnings) == 1
        assert "excessive" in warnings[0]

    def test_mixed_warnings(self) -> None:
        pose_groups = [
            PoseGroup("pg1", "PG1", ["p1.duf"] * 5,
                      assigned_camera_profile="default"),
            PoseGroup("pg2", "PG2", ["p2.duf"] * 30,
                      assigned_camera_profile="default"),
        ]
        looks = [_make_look("look_a", ["pg1"]), _make_look("look_b", ["pg2"])]
        p = _make_project(pose_groups, looks)
        p.camera_profiles[0].cameras = ["cam1", "cam2"]
        p.camera_profiles[0].lighting = ["light1"]
        warnings = validate_render_counts(p)
        # look_a: 5 poses x 2 cams x 1 light = 10 images (< 20)
        # look_b: 30 poses x 2 cams x 1 light = 60 images (in range)
        assert len(warnings) == 1
        assert "look_a" in warnings[0]


def _make_look(trigger: str, pose_group_ids: list[str]) -> "Look":
    from daz2lora.models.datamodels import Look
    return Look(trigger_phrase=trigger, pose_group_ids=pose_group_ids)
