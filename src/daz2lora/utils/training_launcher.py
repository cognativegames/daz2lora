from __future__ import annotations

import re
import subprocess
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from daz2lora.models.datamodels import CharacterProject, TrainingHistoryEntry
from daz2lora.utils.config import AppConfig
from daz2lora.utils.kohya_setup import find_venv_python


class TrainingWorker(threading.Thread):
    def __init__(
        self,
        cmd: list[str],
        log_callback,
        progress_callback,
        done_callback,
    ) -> None:
        super().__init__(daemon=True)
        self.cmd = cmd
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.done_callback = done_callback
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            progress_pattern = re.compile(
                r"(?:Step\s+)?(\d+)\s*/\s*(\d+)"
            )

            for line in iter(proc.stdout.readline, ""):
                if self._cancel:
                    proc.terminate()
                    proc.wait()
                    self.done_callback(False, "Training cancelled by user.")
                    return
                line = line.rstrip("\n")
                self.log_callback(line)

                m = progress_pattern.search(line)
                if m:
                    current, total = int(m.group(1)), int(m.group(2))
                    self.progress_callback(current, total)

            proc.wait()
            if proc.returncode == 0:
                self.done_callback(True, None)
            else:
                self.done_callback(False, f"Process exited with code {proc.returncode}")

        except Exception as e:
            self.done_callback(False, str(e))


class TrainingLauncher(QObject):
    log_line = Signal(str)
    progress = Signal(int, int)
    completed = Signal(bool, str)
    sample_available = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._worker: Optional[TrainingWorker] = None

    def launch(
        self,
        project: CharacterProject,
        config: AppConfig,
        params: dict,
        dataset_root: Path,
    ) -> None:
        if self._worker is not None:
            self.completed.emit(False, "Training already in progress.")
            return

        kohya_path = Path(config.kohya_ss_path)
        trainer = kohya_path / "sdxl_train_network.py"

        if not trainer.exists():
            self.completed.emit(False, f"Trainer not found: {trainer}")
            return

        python = find_venv_python(kohya_path)
        if python is None:
            self.completed.emit(
                False,
                "Python venv not found in kohya_ss install.\n"
                "Run: uv sync  (inside kohya_ss directory)",
            )
            return

        output_dir = (
            Path(config.workspace_root)
            / "projects"
            / project.character.character_id
            / "lora"
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        output_name = f"{project.character.character_id}_v{project.next_version}"

        cmd = [
            str(python),
            str(trainer),
            f"--pretrained_model_name_or_path={config.sdxl_checkpoint_path}",
            f"--train_data_dir={dataset_root}",
            f"--output_dir={output_dir}",
            f"--output_name={output_name}",
            "--network_module=networks.lora",
            f"--network_dim={params['dim']}",
            f"--network_alpha={params['alpha']}",
            f"--learning_rate={params['lr']}",
            f"--train_batch_size={params['batch_size']}",
            f"--max_train_steps={params['steps']}",
            f"--save_every_n_epochs={params['save_every']}",
            f"--mixed_precision={params['mixed_precision']}",
            f"--optimizer_type={params['optimizer']}",
            f"--resolution={params['resolution']}",
            "--enable_bucket",
            "--min_bucket_reso=512",
            "--max_bucket_reso=2048",
        ]

        sample_interval = params.get("sample_every_n_steps", 0)
        if sample_interval > 0:
            sample_dir = output_dir / "samples"
            sample_dir.mkdir(parents=True, exist_ok=True)
            cmd.append(f"--sample_every_n_steps={sample_interval}")
            cmd.append(f"--sample_output_dir={sample_dir}")
            prompts = params.get("sample_prompts", "").strip()
            if prompts:
                prompts_path = sample_dir / "prompts.txt"
                prompts_path.write_text(prompts)
                cmd.append(f"--sample_prompts={prompts_path}")

        if params.get("retrain_from_scratch"):
            pass
        elif params.get("continue_from_prior") and project.trained_lora_path:
            prior = Path(project.trained_lora_path)
            if prior.exists():
                cmd.append(f"--network_weights={prior}")

        def on_log(line: str) -> None:
            self.log_line.emit(line)

        def on_progress(current: int, total: int) -> None:
            self.progress.emit(current, total)

        def on_done(success: bool, message: Optional[str]) -> None:
            self._worker = None
            if success:
                safetensors = output_dir / f"{output_name}.safetensors"
                if safetensors.exists():
                    entry = TrainingHistoryEntry(
                        version=project.next_version,
                        looks_included=[l.trigger_phrase for l in project.looks if l.include_in_dataset],
                        path=str(safetensors),
                    )
                    project.training_history.append(entry)
                    project.trained_lora_path = str(safetensors)

                    proj_file = (
                        Path(config.workspace_root)
                        / "projects"
                        / project.character.character_id
                        / "project.json"
                    )
                    proj_file.parent.mkdir(parents=True, exist_ok=True)
                    project.save(proj_file)

                    self.completed.emit(True, str(safetensors))
                else:
                    self.completed.emit(
                        True, "Training completed but output file not found."
                    )
            else:
                self.completed.emit(False, message or "Unknown error.")

        self._worker = TrainingWorker(cmd, on_log, on_progress, on_done)
        self._worker.start()

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
