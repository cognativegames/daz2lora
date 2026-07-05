from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from daz2lora.utils.config import AppConfig
from daz2lora.utils.daz_orchestrator import (
    _build_daz_command,
    _count_renders,
    _count_renders_for_look,
    _get_args_dir,
    _get_script_path,
    tail_progress,
)


class TestBuildDazCommand:
    def test_windows_command(self) -> None:
        cmd = _build_daz_command(
            "C:/DAZ/DAZStudio.exe",
            "C:/scripts/render.dsa",
            "C:/args/job.json",
        )
        assert cmd[0] == "C:/DAZ/DAZStudio.exe"
        assert "-scriptArg" in cmd
        assert "C:/args/job.json" in cmd
        assert "C:/scripts/render.dsa" in cmd
        assert "-noPrompt" in cmd
        assert "-headless" in cmd

    def test_macos_app_bundle_platform_agnostic(self) -> None:
        cmd = _build_daz_command(
            "/Applications/DAZStudio.app",
            "/scripts/render.dsa",
            "/args/job.json",
        )


class TestTailProgress:
    def test_rendered_line(self, tmp_path: Path) -> None:
        log = tmp_path / "progress.log"
        log.write_text(
            "RENDERED\t1\t10\tlook1\tpose1\tcam1\tlight1\t2024-01-01T00:00:00\n"
            "COMPLETE\ts1\t10\t1\t0\n"
        )

        results = []

        def cb(data: dict) -> None:
            results.append(data)

        tail_progress(str(log), cb, threading.Event(), poll_interval=0.05)
        assert len(results) == 2
        assert results[0]["type"] == "rendered"
        assert results[0]["index"] == 1
        assert results[0]["total"] == 10
        assert results[0]["trigger"] == "look1"

    def test_failed_line(self, tmp_path: Path) -> None:
        log = tmp_path / "progress.log"
        log.write_text(
            "FAILED\t2\t10\tlook1\tpose1\tcam1\tlight1\tOut of memory\n"
            "COMPLETE\ts1\t10\t0\t1\n"
        )

        results = []

        def cb(data: dict) -> None:
            results.append(data)

        tail_progress(str(log), cb, threading.Event(), poll_interval=0.05)
        assert len(results) == 2
        assert results[0]["type"] == "failed"
        assert results[0]["error"] == "Out of memory"

    def test_complete_line_stops(self, tmp_path: Path) -> None:
        log = tmp_path / "progress.log"
        log.write_text(
            "RENDERED\t1\t5\tlook1\tpose1\tcam1\tlight1\t2024-01-01T00:00:00\n"
            "RENDERED\t2\t5\tlook1\tpose1\tcam2\tlight1\t2024-01-01T00:00:01\n"
            "COMPLETE\ts1\t5\t2\t0\n"
        )

        results = []

        def cb(data: dict) -> None:
            results.append(data)

        tail_progress(str(log), cb, threading.Event(), poll_interval=0.05)
        assert len(results) == 3
        assert results[2]["type"] == "complete"
        assert results[2]["successful"] == 2
        assert results[2]["failed"] == 0

    def test_fatal_line_stops(self, tmp_path: Path) -> None:
        log = tmp_path / "progress.log"
        log.write_text("FATAL\ts1\t0\t0\t0\tDAZ crashed\n")

        results = []

        def cb(data: dict) -> None:
            results.append(data)

        tail_progress(str(log), cb, threading.Event(), poll_interval=0.05)
        assert len(results) == 1
        assert results[0]["type"] == "fatal"

    def test_multiple_batches_in_log(self, tmp_path: Path) -> None:
        """Process a log with multiple render lines and a complete."""
        log = tmp_path / "progress.log"
        log.write_text(
            "RENDERED\t1\t4\tl1\tp1\tc1\tlt1\n"
            "RENDERED\t2\t4\tl1\tp1\tc1\tlt2\n"
            "FAILED\t3\t4\tl1\tp1\tc2\tlt1\tError\n"
            "RENDERED\t4\t4\tl1\tp1\tc2\tlt2\n"
            "COMPLETE\ts1\t4\t3\t1\n"
        )

        results = []

        def cb(data: dict) -> None:
            results.append(data)

        tail_progress(str(log), cb, threading.Event(), poll_interval=0.05)
        assert len(results) == 5
        assert sum(1 for r in results if r["type"] == "rendered") == 3
        assert sum(1 for r in results if r["type"] == "failed") == 1

    def test_log_appears_later(self, tmp_path: Path) -> None:
        """Simulate the log file not existing yet when we start tailing."""
        log = tmp_path / "progress.log"
        results = []
        cancel = threading.Event()

        def cb(data: dict) -> None:
            results.append(data)

        def tail_in_thread() -> None:
            tail_progress(str(log), cb, cancel, poll_interval=0.05)

        t = threading.Thread(target=tail_in_thread, daemon=True)
        t.start()

        time.sleep(0.15)

        log.write_text("COMPLETE\ts1\t0\t0\t0\n")
        time.sleep(0.3)
        cancel.set()
        t.join(timeout=1)

        assert len(results) == 1
        assert results[0]["type"] == "complete"


class TestCountRenders:
    def _make_job(self) -> dict:
        return {
            "pose_groups": [
                {
                    "pose_group_id": "pg1",
                    "pose_asset_paths": ["p1.duf", "p2.duf"],
                    "assigned_camera_profile": "profile_a",
                    "camera_overrides": None,
                    "lighting_overrides": None,
                },
                {
                    "pose_group_id": "pg2",
                    "pose_asset_paths": ["p3.duf"],
                    "assigned_camera_profile": "profile_a",
                    "camera_overrides": ["cam_custom"],
                    "lighting_overrides": None,
                },
            ],
            "camera_profiles": [
                {
                    "camera_profile_id": "profile_a",
                    "cameras": ["cam1", "cam2"],
                    "lighting": ["light1", "light2"],
                },
            ],
        }

    def test_count_single_look(self) -> None:
        job = self._make_job()
        look = {"pose_group_ids": ["pg1"]}
        count = _count_renders_for_look(look, job)
        # pg1: 2 poses x 2 cameras x 2 lighting = 8
        assert count == 8

    def test_count_multiple_groups(self) -> None:
        job = self._make_job()
        look = {"pose_group_ids": ["pg1", "pg2"]}
        count = _count_renders_for_look(look, job)
        # pg1: 2 x 2 x 2 = 8, pg2: 1 x 1 (override) x 2 = 2
        assert count == 10

    def test_count_total(self) -> None:
        job = self._make_job()
        job["looks"] = [
            {"pose_group_ids": ["pg1"]},
            {"pose_group_ids": ["pg2"]},
        ]
        total = _count_renders(job)
        assert total == 10

    def test_count_no_poses(self) -> None:
        job = self._make_job()
        job["pose_groups"] = [{
            "pose_group_id": "empty",
            "pose_asset_paths": [],
            "assigned_camera_profile": "profile_a",
            "camera_overrides": None,
            "lighting_overrides": None,
        }]
        look = {"pose_group_ids": ["empty"]}
        assert _count_renders_for_look(look, job) == 0

    def test_camera_overrides(self) -> None:
        job = self._make_job()
        job["pose_groups"][0]["camera_overrides"] = ["cam_only"]
        look = {"pose_group_ids": ["pg1"]}
        count = _count_renders_for_look(look, job)
        assert count == 4  # 2 poses x 1 cam x 2 lighting

    def test_lighting_overrides(self) -> None:
        job = self._make_job()
        job["pose_groups"][0]["lighting_overrides"] = ["light_only"]
        look = {"pose_group_ids": ["pg1"]}
        count = _count_renders_for_look(look, job)
        assert count == 4  # 2 poses x 2 cameras x 1 light

    def test_missing_profile_falls_through(self) -> None:
        job = self._make_job()
        job["pose_groups"][0]["assigned_camera_profile"] = "nonexistent"
        look = {"pose_group_ids": ["pg1"]}
        count = _count_renders_for_look(look, job)
        assert count == 0


class TestGetScriptPath:
    def test_script_path_resolves(self) -> None:
        path = _get_script_path("catalog_export.dsa")
        assert path.exists()
        assert path.name == "catalog_export.dsa"

    def test_default_args_dir(self, tmp_path: Path) -> None:
        cfg = AppConfig(workspace_root=str(tmp_path / "ws"))
        args_dir = _get_args_dir(cfg)
        assert args_dir.exists()
        assert args_dir.name == "args"
        assert ".daz2lora" in str(args_dir)
