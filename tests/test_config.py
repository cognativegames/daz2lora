from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from daz2lora.utils import config as config_module
from daz2lora.utils.config import AppConfig


class TestAppConfig:
    def test_defaults(self) -> None:
        cfg = AppConfig()
        assert cfg.daz_studio_path == ""
        assert cfg.workspace_root == ""
        assert cfg.kohya_ss_path == ""
        assert cfg.sdxl_checkpoint_path == ""
        assert cfg.comfyui_loras_path == ""
        assert cfg.renders_per_session == 50
        assert cfg.render_width == 1536
        assert cfg.render_height == 1536
        assert cfg.render_samples == 32

    def test_custom_values(self) -> None:
        cfg = AppConfig(
            daz_studio_path="/daz/studio.exe",
            workspace_root="/workspace",
            kohya_ss_path="/kohya",
            sdxl_checkpoint_path="/model.safetensors",
            comfyui_loras_path="/comfy/loras",
            renders_per_session=100,
            render_width=1024,
            render_height=1024,
            render_samples=64,
        )
        assert cfg.daz_studio_path == "/daz/studio.exe"
        assert cfg.renders_per_session == 100

    def test_content_library_roots_default(self) -> None:
        cfg = AppConfig()
        assert isinstance(cfg.content_library_roots, list)
        assert len(cfg.content_library_roots) == 1
        assert "DAZ 3D" in cfg.content_library_roots[0]

    def test_save_creates_file(self, tmp_path: Path) -> None:
        cfg = AppConfig(daz_studio_path="/daz.exe")
        test_file = tmp_path / "config.json"
        test_file.write_text(json.dumps(asdict(cfg), indent=2))
        assert test_file.exists()
        data = json.loads(test_file.read_text())
        assert data["daz_studio_path"] == "/daz.exe"

    def test_load_and_save_roundtrip(self, tmp_path: Path) -> None:
        """Test that saving then loading via module-level CONFIG_FILE works."""
        test_cfg = AppConfig(
            daz_studio_path="/test/daz.exe",
            workspace_root="/test/ws",
            kohya_ss_path="/test/kohya",
            sdxl_checkpoint_path="/test/model.safetensors",
            comfyui_loras_path="/test/comfy",
            renders_per_session=75,
            render_width=1920,
            render_height=1080,
            render_samples=48,
            content_library_roots=["/test/lib"],
        )

        # Write the JSON directly and load via module-level CONFIG_FILE
        test_file = tmp_path / "test_config.json"
        test_file.write_text(json.dumps(asdict(test_cfg), indent=2))

        # Monkey-patch the module-level CONFIG_FILE
        orig = config_module.CONFIG_FILE
        try:
            config_module.CONFIG_FILE = str(test_file)
            loaded = AppConfig.load()
            assert loaded.daz_studio_path == "/test/daz.exe"
            assert loaded.renders_per_session == 75
            assert loaded.content_library_roots == ["/test/lib"]
        finally:
            config_module.CONFIG_FILE = orig

    def test_load_uses_correct_file(self, tmp_path: Path) -> None:
        orig = config_module.CONFIG_FILE
        test_file = tmp_path / "cfg.json"
        test_file.write_text(json.dumps({
            "daz_studio_path": "/daz2.exe",
            "content_library_roots": ["/lib"],
            "workspace_root": "/ws",
            "kohya_ss_path": "",
            "sdxl_checkpoint_path": "",
            "comfyui_loras_path": "",
            "renders_per_session": 10,
            "render_width": 512,
            "render_height": 512,
            "render_samples": 16,
        }))
        try:
            config_module.CONFIG_FILE = str(test_file)
            cfg = AppConfig.load()
            assert cfg.daz_studio_path == "/daz2.exe"
            assert cfg.renders_per_session == 10
            assert cfg.content_library_roots == ["/lib"]
        finally:
            config_module.CONFIG_FILE = orig

    def test_load_defaults_when_file_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.json"
        orig = config_module.CONFIG_FILE
        try:
            config_module.CONFIG_FILE = str(missing)
            cfg = AppConfig.load()
            assert cfg.daz_studio_path == ""
            assert cfg.renders_per_session == 50
        finally:
            config_module.CONFIG_FILE = orig
