from __future__ import annotations

from daz2lora.models.datamodels import CharacterProject, PoseGroup


def compute_render_counts(project: CharacterProject) -> dict:
    per_look: dict[str, int] = {}
    per_pose_group: dict[str, int] = {}
    total = 0

    for look in project.looks:
        look_total = 0
        for pg_id in (look.pose_group_ids or []):
            pose_group = _find_pose_group(project.pose_groups, pg_id)
            if pose_group is None:
                continue

            cameras = _resolve_cameras(pose_group, project)
            lighting = _resolve_lighting(pose_group, project)
            poses = pose_group.pose_asset_paths

            pg_total = len(poses) * len(cameras) * len(lighting)
            look_total += pg_total
            per_pose_group[pg_id] = per_pose_group.get(pg_id, 0) + pg_total

        per_look[look.trigger_phrase] = look_total
        total += look_total

    return {"per_look": per_look, "total": total, "per_pose_group": per_pose_group}


def estimate_render_time(total_count: int, completed_count: int, elapsed_seconds: float) -> float:
    if completed_count <= 0:
        return 0.0
    avg = elapsed_seconds / completed_count
    return avg * (total_count - completed_count)


def validate_render_counts(project: CharacterProject) -> list[str]:
    counts = compute_render_counts(project)
    warnings: list[str] = []
    for trigger, count in counts["per_look"].items():
        if count < 20:
            warnings.append(
                f"Look '{trigger}' only gets {count} images (< 20 recommended minimum)"
            )
        elif count > 80:
            warnings.append(
                f"Look '{trigger}' gets {count} images (> 80 may be excessive)"
            )
    return warnings


def _find_pose_group(pose_groups: list[PoseGroup], group_id: str) -> PoseGroup | None:
    for pg in pose_groups:
        if pg.pose_group_id == group_id:
            return pg
    return None


def _resolve_cameras(pose_group: PoseGroup, project: CharacterProject) -> list[str]:
    if pose_group.camera_overrides:
        return pose_group.camera_overrides
    for cp in project.camera_profiles:
        if cp.camera_profile_id == pose_group.assigned_camera_profile:
            return cp.cameras
    return []


def _resolve_lighting(pose_group: PoseGroup, project: CharacterProject) -> list[str]:
    if pose_group.lighting_overrides:
        return pose_group.lighting_overrides
    for cp in project.camera_profiles:
        if cp.camera_profile_id == pose_group.assigned_camera_profile:
            return cp.lighting
    return []
