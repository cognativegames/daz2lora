# DAZ-to-LoRA

Orchestrates DAZ Studio renders of a custom character into a captioned dataset, then feeds it into a LoRA trainer (kohya_ss / sd-scripts) to produce a `.safetensors` file ready for ComfyUI.

Go from "pick a character in DAZ" to "trained LoRA" without leaving the app.

## Prerequisites

Install these on your Windows PC. The app needs them at runtime.

| Component | Required | Where to Get It |
|-----------|----------|-----------------|
| **Python 3.11+** | Yes | [python.org/downloads](https://www.python.org/downloads/) — Windows installer (64-bit). Check **"Add Python to PATH"**. |
| **DAZ Studio 4.22+** | For renders | [daz3d.com/get_studio](https://www.daz3d.com/get_studio/) — free, requires account. App uses headless CLI (`-scriptArg`, `-headless`). |
| **kohya_ss / sd-scripts** | For training | [github.com/bmaltais/kohya_ss](https://github.com/bmaltais/kohya_ss) — GUI launcher (recommended). Or [github.com/kohya-ss/sd-scripts](https://github.com/kohya-ss/sd-scripts) for the raw scripts. App calls `sdxl_train_network.py`. |
| **SDXL checkpoint** | For training | [civitai.com](https://civitai.com) — search SDXL. Popular: Illustrious, WAI-NSFW-illustrious, NoobAI, Pony Diffusion. Download `.safetensors`. |
| **ComfyUI** | Optional | [comfy.org/download](https://comfy.org/download) — desktop app. Done screen can copy LoRA into Comfy's `models/loras/`. |
| **NVIDIA GPU** | For training | 8+ GB VRAM recommended for SDXL. DAZ Iray uses CUDA. |

## Downloads

Latest automated builds (updated on every push to `master`):

| Artifact | Link |
|----------|------|
| **Windows executable** (`.exe`) | [daz2lora-latest.zip](https://github.com/cognativegames/daz2lora/releases/download/latest/daz2lora-latest.zip) |
| Source code (zip) | [Source code (zip)](https://github.com/cognativegames/daz2lora/archive/refs/tags/latest.zip) |
| Source code (tar.gz) | [Source code (tar.gz)](https://github.com/cognativegames/daz2lora/archive/refs/tags/latest.tar.gz) |
| All releases | [Releases page](https://github.com/cognativegames/daz2lora/releases) |

### About the `.exe` and SmartScreen

The `daz2lora.exe` is built with [PyInstaller](https://pyinstaller.org/), which bundles the Python interpreter and all dependencies into a single Windows executable. It's the same Python code you'd run from source — just packaged for convenience so you don't need to install Python.

Windows SmartScreen will show "Windows protected your PC" / "Unknown publisher" the first time you run it. **This is normal and expected.** The executable isn't code-signed because code signing certificates cost ~$300/year, and this is free open source software. The warning doesn't mean the software is unsafe — it means Microsoft hasn't seen this binary before.

To run it anyway: click **More info** → **Run anyway**.

If you'd prefer to avoid SmartScreen entirely, run from source (see below) — no `.exe` involved.

> **Future:** If there's enough demand, we may apply to [SignPath Foundation](https://signpath.org/) (free code signing for open source projects). That would replace "Unknown publisher" with "SignPath Foundation" and reduce the warning severity. This project would also accept sponsorship for a proper code signing certificate tied to the `cognativegames` publisher name.

## Quick Start (Windows)

**Option A — Pre-built executable (no Python needed):**
1. Download [`daz2lora-latest.zip`](https://github.com/cognativegames/daz2lora/releases/download/latest/daz2lora-latest.zip)
2. Extract and run `daz2lora.exe`

**Option B — From source (no SmartScreen warning):**

```powershell
git clone https://github.com/cognativegames/daz2lora.git
cd daz2lora
python src/daz2lora/main.py   # auto-creates .venv, installs deps, then launches
```

Or double-click `daz2lora.bat` (included in the repo).

**Option C — Manual setup:**

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m daz2lora.main
```

**Option D — Installer (from GitHub Releases):** Download `daz2lora_setup.exe` from the [Releases page](https://github.com/cognativegames/daz2lora/releases) for stable releases (installs with Start Menu shortcut and uninstaller).

## Usage

The app runs linearly through 8 screens. The sidebar tracks your progress.

```
Setup → Project Selector → Character Picker → Looks Editor
    → Pose Groups Editor → Review & Render → Dataset & Training → Done
```

1. **Setup** — DAZ Studio path, workspace dir, kohya_ss path, SDXL checkpoint
2. **Project Selector** — create or open a character project
3. **Character Picker** — define figure/shape/skin/hair assets
4. **Looks Editor** — outfits with trigger phrases + pose group assignments
5. **Pose Groups Editor** — pose collections with camera profile selection
6. **Review & Render** — see the render matrix, launch DAZ Studio renders, watch progress
7. **Dataset & Training** — review captions, set hyperparameters, train LoRA
8. **Done** — copy `.safetensors` to ComfyUI or open the folder

## Development Workflow

This project targets **Windows only** (DAZ Studio doesn't exist on Mac). Development happens on Mac for the fast edit/test loop on unit tests; the full pipeline (render, train) runs on the Windows PC.

```
┌──────────────────────────────┐
│        Your Mac (edit)       │
│  make test    — 118 unit     │
│  make lint    — ruff         │
│  make run     — UI (s1-5)    │
└──────┬───────────────────────┘
       │ rsync via SSH
       ▼
┌──────────────────────────────┐
│   Windows PC (test+build)    │
│  make test-pc    — pytest    │
│  make run-pc     — full app  │
│  make build-pc   — .exe      │
│  make installer-pc — setup   │
│  DAZ Studio renders          │
│  kohya_ss training (GPU)     │
└──────────────────────────────┘
```

### Mac targets (editor, quick checks)

```bash
make setup       # venv + dev deps
make test        # 118 unit tests, ~1 sec
make test-coverage
make lint        # ruff
make typecheck   # mypy
make run         # UI screens 1-5 (render/train fail gracefully on Mac)
make clean
```

### PC targets (rsync + SSH)

Set up `.env`:

```bash
cp .env.example .env
# Edit: PC_HOST, PC_IP, PC_USER, PC_DIR
```

One-time setup on the PC:

```bash
make setup-ssh       # copy SSH key (one password prompt)
make setup-pc        # create venv + install deps
```

Then for the daily loop (edit on Mac, run on PC):

```bash
make test-pc         # rsync code → run tests on PC → results back
make run-pc          # rsync code → launch app on PC
make build-pc        # rsync code → pyinstaller on PC → pull .exe back
make installer-pc    # rsync code → Inno Setup on PC → pull setup.exe back
make pull            # pull latest builds from PC
```

All `make *-pc` commands rsync the source first, so your edits are always included.

### PC prerequisites for remote dev

- Python 3.11+
- [OpenSSH Server](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh_install_firstuse)
- rsync (WSL2 or [cwRsync](https://www.itefix.net/cwrsync))
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (for `installer-pc`)

## Self-Bootstrapping

When you run `python src/daz2lora/main.py` from a fresh clone, `main.py` detects it's outside the project `.venv` and:

1. Creates `.venv` if missing
2. Runs `pip install -e .`
3. Re-executes through the venv's Python

PyInstaller bundles are self-contained — bootstrap is skipped automatically.

## Windows Installer

Build `daz2lora_setup.exe` that installs the app with Start Menu shortcut and uninstaller:

```bash
# On PC directly:
make build       # first time only
make installer   # wraps .exe into setup.exe
# Output: dist\daz2lora_setup.exe

# Or from Mac:
make build-pc
make installer-pc
# Output: dist/daz2lora_setup.exe (pulled back to Mac)
```

## Project Structure

```
src/daz2lora/
├── main.py                     # Entry point (self-bootstrapping)
├── models/
│   └── datamodels.py           # Data classes (Character, Look, PoseGroup, Project)
├── utils/
│   ├── config.py               # AppConfig — paths, render settings
│   ├── render_math.py          # Render count estimator
│   ├── daz_orchestrator.py     # DAZ Studio subprocess + progress tailing
│   ├── dataset_assembler.py    # Captioned dataset builder, repeat-balancing
│   └── training_launcher.py    # kohya_ss subprocess wrapper
├── daz_scripts/
│   ├── catalog_export.dsa      # Content library walker (DAZ Script)
│   └── master_render.dsa       # Unattended render loop (DAZ Script)
├── ui/
│   ├── main_window.py          # QStackedWidget navigation
│   ├── setup_screen.py
│   ├── project_selector.py
│   ├── character_picker.py
│   ├── looks_editor.py
│   ├── pose_groups_editor.py
│   ├── render_screen.py
│   ├── dataset_screen.py
│   └── done_screen.py
└── kohya_config/
tests/
├── test_datamodels.py          # 15 tests
├── test_render_math.py         # 14 tests
├── test_dataset_assembler.py   # 24 tests
├── test_config.py              # 7 tests
├── test_daz_orchestrator.py    # 18 tests
├── test_training_launcher.py   # 11 tests
└── test_integration.py         # 11 tests — full pipeline with temp dirs
```
