from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "orc-trans-app.spec"
APP_NAME = "orc-trans-app"
EXCLUDED_MODULES = [
    "pytest",
    "tkinter",
    "matplotlib",
    "IPython",
    "jupyter",
    "notebook",
    "cupy",
    "tensorrt",
    "torch",
    "torchvision",
    "torchaudio",
    "tensorflow",
    "keras",
    "onnx",
    "onnxruntime",
    "nvidia",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("onedir", "onefile"), default="onedir")
    parser.add_argument("--upx", action="store_true")
    parser.add_argument("--upx-dir")
    return parser


def cleanup_previous_build() -> None:
    for path in (DIST, BUILD, SPEC):
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()


def build_command(mode: str, upx: bool = False, upx_dir: str | None = None) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        f"--{mode}",
        "--add-data",
        f"{ROOT / 'scripts' / 'google_translate.py'};scripts",
        "--add-data",
        f"{ROOT / 'scripts' / 'google_translate_web_tokens.json'};scripts",
    ]

    for module_name in EXCLUDED_MODULES:
        command.extend(["--exclude-module", module_name])

    if upx:
        if upx_dir is not None:
            command.extend(["--upx-dir", upx_dir])
    else:
        command.append("--noupx")

    command.append(str(ROOT / "main.py"))
    return command


def output_path(mode: str) -> Path:
    if mode == "onefile":
        return DIST / f"{APP_NAME}.exe"
    return DIST / APP_NAME / f"{APP_NAME}.exe"


def main() -> None:
    args = build_parser().parse_args()
    cleanup_previous_build()
    command = build_command(mode=args.mode, upx=args.upx, upx_dir=args.upx_dir)
    subprocess.run(command, check=True, cwd=ROOT)
    print(output_path(args.mode))


if __name__ == "__main__":
    main()
