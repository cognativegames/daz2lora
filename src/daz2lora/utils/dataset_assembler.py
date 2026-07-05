from __future__ import annotations

import re
import shutil
from pathlib import Path

from daz2lora.models.datamodels import CharacterProject, Look
from daz2lora.utils.config import AppConfig

CAMERA_TAG_MAP: dict[str, str] = {
    "portrait_close": "close-up",
    "half_body": "half body shot",
    "full_body_front": "full body",
    "full_body_3q": "three-quarter view",
    "full_body_profile": "side profile",
    "full_body_low_angle": "low angle",
    "full_body_high_angle": "high angle",
}

LIGHTING_TAG_MAP: dict[str, str] = {
    "studio_3point": "studio lighting",
    "soft_outdoor_hdri": "outdoor lighting",
    "dramatic_rim": "dramatic rim lighting",
}

_RENDER_PATTERN = re.compile(r"^(.+?)__(.+?)__(.+?)__(.+?)\.png$")


def sanitize_trigger(trigger: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", trigger).lower()


def _camera_id_to_tag(camera_id: str) -> str:
    return CAMERA_TAG_MAP.get(camera_id, camera_id.replace("_", " "))


def _lighting_id_to_tag(lighting_id: str) -> str:
    return LIGHTING_TAG_MAP.get(lighting_id, lighting_id.replace("_", " "))


def _generate_caption(
    trigger_phrase: str,
    base_trigger_word: str,
    pose_id: str,
    camera_id: str,
    lighting_id: str,
    static_tags: list[str],
) -> str:
    parts = [trigger_phrase, base_trigger_word]
    parts.append(_camera_id_to_tag(camera_id))
    parts.append(_lighting_id_to_tag(lighting_id))
    parts.extend(static_tags)
    return ", ".join(p for p in parts if p)


def _compute_repeats(per_look_counts: dict[str, int]) -> dict[str, int]:
    if not per_look_counts:
        return {}
    max_count = max(per_look_counts.values())
    if max_count == 0:
        return {k: 1 for k in per_look_counts}
    return {
        trigger: max(1, round(max_count / count * 10))
        for trigger, count in per_look_counts.items()
    }


def assemble_dataset(
    project: CharacterProject,
    config: AppConfig,
    render_dir: Path,
    overwrite: bool = False,
) -> Path:
    dataset_root = (
        Path(config.workspace_root)
        / "projects"
        / project.character.character_id
        / "dataset"
    )
    dataset_root.mkdir(parents=True, exist_ok=True)

    active_keys: set[str] = set()
    for look in project.looks:
        if look.include_in_dataset:
            active_keys.add(sanitize_trigger(look.trigger_phrase))

    render_files = list(render_dir.glob("*.png"))
    look_groups: dict[str, list[Path]] = {}

    for f in render_files:
        m = _RENDER_PATTERN.match(f.name)
        if not m:
            continue
        trigger_key = sanitize_trigger(m.group(1))
        if trigger_key not in active_keys:
            continue
        if trigger_key not in look_groups:
            look_groups[trigger_key] = []
        look_groups[trigger_key].append(f)

    counts = {k: len(v) for k, v in look_groups.items()}
    repeats = _compute_repeats(counts)

    for trigger_key, files in look_groups.items():
        look = _find_look_by_key(project, trigger_key)
        if look is None:
            continue
        repeat = repeats.get(trigger_key, 1)
        folder_name = f"{repeat}_{trigger_key}"
        folder = dataset_root / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        for f in files:
            m = _RENDER_PATTERN.match(f.name)
            if not m:
                continue
            pose, camera, lighting = m.group(2), m.group(3), m.group(4)
            dest_stem = f"{pose}__{camera}__{lighting}"
            img_dest = folder / f"{dest_stem}.png"
            if not img_dest.exists() or overwrite:
                shutil.copy2(f, img_dest)

            caption = _generate_caption(
                look.trigger_phrase,
                project.character.base_trigger_word,
                pose,
                camera,
                lighting,
                project.character.static_tags,
            )
            cap_dest = folder / f"{dest_stem}.txt"
            if not cap_dest.exists() or overwrite:
                cap_dest.write_text(caption)

    project.dataset_root = str(dataset_root)
    return dataset_root


def _find_look_by_key(project: CharacterProject, sanitized_key: str) -> Look | None:
    for look in project.looks:
        if look.include_in_dataset and sanitize_trigger(look.trigger_phrase) == sanitized_key:
            return look
    return None


def load_captions(dataset_root: Path) -> dict[str, str]:
    captions: dict[str, str] = {}
    for txt_file in dataset_root.rglob("*.txt"):
        rel = txt_file.relative_to(dataset_root)
        captions[str(rel)] = txt_file.read_text().strip()
    return captions


def save_captions(dataset_root: Path, captions: dict[str, str]) -> None:
    for rel_path, text in captions.items():
        abs_path = dataset_root / rel_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(text.strip())


def find_replace_captions(dataset_root: Path, find: str, replace: str) -> int:
    count = 0
    for txt_file in dataset_root.rglob("*.txt"):
        content = txt_file.read_text()
        if find in content:
            new_content = content.replace(find, replace)
            txt_file.write_text(new_content)
            count += content.count(find)
    return count


def get_dataset_stats(dataset_root: Path) -> dict:
    if not dataset_root.exists():
        return {
            "total_images": 0,
            "total_captions": 0,
            "per_look_counts": {},
            "image_dimensions_sample": None,
        }

    images = list(dataset_root.rglob("*.png"))
    captions = list(dataset_root.rglob("*.txt"))

    per_look_counts: dict[str, int] = {}
    for folder in dataset_root.iterdir():
        if folder.is_dir():
            img_count = len(list(folder.glob("*.png")))
            if img_count > 0:
                per_look_counts[folder.name] = img_count

    dims = None
    if images:
        try:
            from PIL import Image
            with Image.open(images[0]) as img:
                dims = img.size
        except Exception:
            pass

    return {
        "total_images": len(images),
        "total_captions": len(captions),
        "per_look_counts": per_look_counts,
        "image_dimensions_sample": dims,
    }
