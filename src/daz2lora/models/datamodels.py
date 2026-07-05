from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class CharacterMode(str, Enum):
    FIXED = "fixed"
    MODULAR = "modular"


@dataclass
class CameraDef:
    id: str
    description: str
    typical_use: str


@dataclass
class LightingDef:
    id: str
    description: str


HARDCODED_CAMERAS: list[CameraDef] = [
    CameraDef("portrait_close", "bust/face close-up", "identity/face training weight"),
    CameraDef("half_body", "cowboy shot", "general"),
    CameraDef("full_body_front", "full body, front-facing", "general"),
    CameraDef("full_body_3q", "full body, 3/4 turn", "general"),
    CameraDef("full_body_profile", "full body, side profile", "general"),
    CameraDef("full_body_low_angle", "low angle hero shot", "action poses"),
    CameraDef("full_body_high_angle", "high angle, downward", "seated/candid poses"),
]

HARDCODED_LIGHTING: list[LightingDef] = [
    LightingDef("studio_3point", "neutral, consistent, default for most shots"),
    LightingDef("soft_outdoor_hdri", "soft diffuse outdoor"),
    LightingDef("dramatic_rim", "side/rim lighting"),
]

CAMERA_ID_TO_PROFILE_SUGGESTION: dict[str, list[str]] = {
    "action_full_body": ["full_body_front", "full_body_3q", "full_body_low_angle", "full_body_profile"],
    "portrait_and_half_body": ["portrait_close", "half_body", "full_body_front"],
    "full_coverage": ["portrait_close", "half_body", "full_body_front", "full_body_3q", "full_body_profile", "full_body_low_angle", "full_body_high_angle"],
    "face_focus": ["portrait_close"],
}

LIGHTING_ID_TO_PROFILE_SUGGESTION: dict[str, list[str]] = {
    "action_full_body": ["studio_3point", "dramatic_rim"],
    "portrait_and_half_body": ["studio_3point", "soft_outdoor_hdri"],
    "full_coverage": ["studio_3point", "soft_outdoor_hdri", "dramatic_rim"],
    "face_focus": ["studio_3point"],
}

DEFAULT_CAMERA_PROFILES: list[CameraProfile] = []


@dataclass
class CameraProfile:
    camera_profile_id: str
    cameras: list[str] = field(default_factory=list)
    lighting: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"camera_profile_id": self.camera_profile_id, "cameras": self.cameras, "lighting": self.lighting}


def _init_default_profiles() -> None:
    global DEFAULT_CAMERA_PROFILES
    if DEFAULT_CAMERA_PROFILES:
        return
    for pid in ["full_coverage", "action_full_body", "portrait_and_half_body", "face_focus"]:
        cams = CAMERA_ID_TO_PROFILE_SUGGESTION.get(pid, [])
        lights = LIGHTING_ID_TO_PROFILE_SUGGESTION.get(pid, [])
        DEFAULT_CAMERA_PROFILES.append(CameraProfile(pid, list(cams), list(lights)))


_init_default_profiles()


@dataclass
class PoseGroup:
    pose_group_id: str
    display_name: str
    pose_asset_paths: list[str] = field(default_factory=list)
    default_camera_profile: str = "full_coverage"
    assigned_camera_profile: str = "full_coverage"
    camera_overrides: Optional[list[str]] = None
    lighting_overrides: Optional[list[str]] = None

    def to_dict(self) -> dict:
        return {
            "pose_group_id": self.pose_group_id,
            "display_name": self.display_name,
            "pose_asset_paths": list(self.pose_asset_paths),
            "default_camera_profile": self.default_camera_profile,
            "assigned_camera_profile": self.assigned_camera_profile,
            "camera_overrides": self.camera_overrides,
            "lighting_overrides": self.lighting_overrides,
        }


@dataclass
class Look:
    trigger_phrase: str
    wardrobe_asset_paths: list[str] = field(default_factory=list)
    hair_override_path: Optional[str] = None
    pose_group_ids: list[str] = field(default_factory=list)
    include_in_dataset: bool = True

    def to_dict(self) -> dict:
        return {
            "trigger_phrase": self.trigger_phrase,
            "wardrobe_asset_paths": list(self.wardrobe_asset_paths),
            "hair_override_path": self.hair_override_path,
            "pose_group_ids": list(self.pose_group_ids),
            "include_in_dataset": self.include_in_dataset,
        }


@dataclass
class Character:
    character_id: str
    base_trigger_word: str
    figure_asset_path: str
    shape_preset_path: str
    skin_material_path: str
    default_hair_asset_path: str
    mode: CharacterMode = CharacterMode.MODULAR
    static_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "character_id": self.character_id,
            "base_trigger_word": self.base_trigger_word,
            "figure_asset_path": self.figure_asset_path,
            "shape_preset_path": self.shape_preset_path,
            "skin_material_path": self.skin_material_path,
            "default_hair_asset_path": self.default_hair_asset_path,
            "mode": self.mode.value,
            "static_tags": list(self.static_tags),
        }


@dataclass
class TrainingHistoryEntry:
    version: int
    looks_included: list[str]
    path: str

    def to_dict(self) -> dict:
        return {"version": self.version, "looks_included": list(self.looks_included), "path": self.path}


@dataclass
class CharacterProject:
    project_id: str
    character: Character
    looks: list[Look] = field(default_factory=list)
    pose_groups: list[PoseGroup] = field(default_factory=list)
    camera_profiles: list[CameraProfile] = field(default_factory=list)
    dataset_root: str = ""
    trained_lora_path: Optional[str] = None
    training_history: list[TrainingHistoryEntry] = field(default_factory=list)

    @property
    def dataset_root_path(self) -> Path:
        return Path(self.dataset_root) if self.dataset_root else Path(f"projects/{self.project_id}/dataset")

    @property
    def next_version(self) -> int:
        if not self.training_history:
            return 1
        return max(e.version for e in self.training_history) + 1

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "character": self.character.to_dict(),
            "looks": [l.to_dict() for l in self.looks],
            "pose_groups": [p.to_dict() for p in self.pose_groups],
            "camera_profiles": [c.to_dict() for c in self.camera_profiles],
            "dataset_root": self.dataset_root,
            "trained_lora_path": self.trained_lora_path,
            "training_history": [t.to_dict() for t in self.training_history],
        }

    def save(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path | str) -> CharacterProject:
        data = json.loads(Path(path).read_text())
        character = Character(**data["character"])
        character.mode = CharacterMode(character.mode)
        looks = [Look(**l) for l in data.get("looks", [])]
        pose_groups = [PoseGroup(**pg) for pg in data.get("pose_groups", [])]
        camera_profiles = [CameraProfile(**cp) for cp in data.get("camera_profiles", [])]
        training_history = [TrainingHistoryEntry(**th) for th in data.get("training_history", [])]
        return cls(
            project_id=data["project_id"],
            character=character,
            looks=looks,
            pose_groups=pose_groups,
            camera_profiles=camera_profiles,
            dataset_root=data.get("dataset_root", ""),
            trained_lora_path=data.get("trained_lora_path"),
            training_history=training_history,
        )
