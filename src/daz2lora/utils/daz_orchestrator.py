from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from daz2lora.utils.config import AppConfig


def _build_daz_command(daz_path: str, script_path: str, arg_path: str) -> list[str]:
    system = platform.system()
    exe = daz_path
    if system == "Darwin" and daz_path.endswith(".app"):
        exe = os.path.join(daz_path, "Contents", "MacOS", "DAZStudio")
    return [exe, "-scriptArg", arg_path, script_path, "-noPrompt", "-headless"]


def tail_progress(
    log_path: str,
    callback: Callable[[dict], None],
    cancel_event: threading.Event,
    poll_interval: float = 0.5,
) -> None:
    path = Path(log_path)
    last_pos = 0

    while not cancel_event.is_set():
        if not path.exists():
            time.sleep(poll_interval)
            continue

        try:
            with open(path, "r") as f:
                f.seek(last_pos)
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split("\t")
                    if not parts:
                        continue
                    status = parts[0]

                    if status == "RENDERED":
                        callback({
                            "type": "rendered",
                            "index": int(parts[1]) if len(parts) > 1 else 0,
                            "total": int(parts[2]) if len(parts) > 2 else 0,
                            "trigger": parts[3] if len(parts) > 3 else "",
                            "pose": parts[4] if len(parts) > 4 else "",
                            "camera": parts[5] if len(parts) > 5 else "",
                            "lighting": parts[6] if len(parts) > 6 else "",
                        })
                    elif status == "FAILED":
                        callback({
                            "type": "failed",
                            "index": int(parts[1]) if len(parts) > 1 else 0,
                            "total": int(parts[2]) if len(parts) > 2 else 0,
                            "trigger": parts[3] if len(parts) > 3 else "",
                            "pose": parts[4] if len(parts) > 4 else "",
                            "camera": parts[5] if len(parts) > 5 else "",
                            "lighting": parts[6] if len(parts) > 6 else "",
                            "error": parts[7] if len(parts) > 7 else "",
                        })
                    elif status == "COMPLETE":
                        callback({
                            "type": "complete",
                            "session_id": parts[1] if len(parts) > 1 else "",
                            "total": int(parts[2]) if len(parts) > 2 else 0,
                            "successful": int(parts[3]) if len(parts) > 3 else 0,
                            "failed": int(parts[4]) if len(parts) > 4 else 0,
                        })
                        return
                    elif status == "FATAL":
                        callback({
                            "type": "fatal",
                            "session_id": parts[1] if len(parts) > 1 else "",
                            "total": int(parts[2]) if len(parts) > 2 else 0,
                            "successful": int(parts[3]) if len(parts) > 3 else 0,
                            "failed": int(parts[4]) if len(parts) > 4 else 0,
                            "error": parts[5] if len(parts) > 5 else "",
                        })
                        return

                last_pos = f.tell()
        except (IOError, OSError, ValueError):
            pass

        time.sleep(poll_interval)


def run_catalog_export(config: AppConfig) -> dict:
    script_path = _get_script_path("catalog_export.dsa")
    args_dir = _get_args_dir(config)
    args_path = args_dir / "catalog_args.json"
    output_path = args_dir / "catalog_output.json"

    content_roots = config.content_library_roots or []
    args_payload = {
        "output_path": str(output_path),
        "content_dirs": content_roots,
    }
    args_path.write_text(json.dumps(args_payload, indent=2))

    cmd = _build_daz_command(config.daz_studio_path, str(script_path), str(args_path))
    subprocess.run(cmd, check=True)

    if not output_path.exists():
        raise FileNotFoundError(f"Catalog export did not produce output at {output_path}")

    return json.loads(output_path.read_text())


def run_render_job(
    job_config: dict,
    config: AppConfig,
    progress_callback: Callable[[dict], None],
) -> int:
    total = _count_renders(job_config)
    if total > config.renders_per_session:
        return _run_split_sessions(job_config, config, progress_callback)
    return _run_single_session(job_config, config, progress_callback)


def _run_single_session(
    job_config: dict,
    config: AppConfig,
    progress_callback: Callable[[dict], None],
) -> int:
    script_path = _get_script_path("master_render.dsa")
    args_dir = _get_args_dir(config)
    session_id = str(int(time.time()))

    job_config["session_id"] = session_id
    job_config["progress_log"] = str(args_dir / f"progress_{session_id}.log")

    job_path = args_dir / f"job_{session_id}.json"
    job_path.write_text(json.dumps(job_config, indent=2))

    cmd = _build_daz_command(config.daz_studio_path, str(script_path), str(job_path))

    cancel_event = threading.Event()
    tail_thread = threading.Thread(
        target=tail_progress,
        args=(job_config["progress_log"], progress_callback, cancel_event),
        daemon=True,
    )
    tail_thread.start()

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode
    finally:
        cancel_event.set()
        tail_thread.join(timeout=2)


def _run_split_sessions(
    job_config: dict,
    config: AppConfig,
    progress_callback: Callable[[dict], None],
) -> int:
    looks = job_config.get("looks", [])
    per_session = config.renders_per_session
    current_look_list: list[dict] = []
    current_count = 0
    session_num = 0
    overall_exit = 0

    for look in looks:
        look_count = _count_renders_for_look(look, job_config)
        if current_count + look_count > per_session and current_look_list:
            session_num += 1
            session_job = dict(job_config)
            session_job["looks"] = current_look_list
            session_job["session_num"] = session_num
            ec = _run_single_session(session_job, config, progress_callback)
            if ec != 0:
                overall_exit = ec
            current_look_list = []
            current_count = 0

        current_look_list.append(look)
        current_count += look_count

    if current_look_list:
        session_num += 1
        session_job = dict(job_config)
        session_job["looks"] = current_look_list
        session_job["session_num"] = session_num
        ec = _run_single_session(session_job, config, progress_callback)
        if ec != 0:
            overall_exit = ec

    return overall_exit


def _count_renders(job_config: dict) -> int:
    total = 0
    for look in job_config.get("looks", []):
        total += _count_renders_for_look(look, job_config)
    return total


def _count_renders_for_look(look: dict, job_config: dict) -> int:
    pose_groups = {pg["pose_group_id"]: pg for pg in job_config.get("pose_groups", [])}
    camera_profiles = {cp["camera_profile_id"]: cp for cp in job_config.get("camera_profiles", [])}
    total = 0

    for pg_id in look.get("pose_group_ids", []):
        pg = pose_groups.get(pg_id)
        if pg is None:
            continue

        cameras = pg.get("camera_overrides")
        if not cameras:
            profile = camera_profiles.get(pg.get("assigned_camera_profile", "full_coverage"), {})
            cameras = profile.get("cameras", [])

        lighting = pg.get("lighting_overrides")
        if not lighting:
            profile = camera_profiles.get(pg.get("assigned_camera_profile", "full_coverage"), {})
            lighting = profile.get("lighting", [])

        total += len(pg.get("pose_asset_paths", [])) * len(cameras) * len(lighting)

    return total


def _get_script_path(script_name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "daz_scripts" / script_name


def _get_args_dir(config: AppConfig) -> Path:
    args_dir = Path(config.workspace_root) / ".daz2lora" / "args"
    args_dir.mkdir(parents=True, exist_ok=True)
    return args_dir
