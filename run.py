import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# (import module name, pip package name)
REQUIRED_PACKAGES = [
    ("streamlit", "streamlit"),
    ("yt_dlp", "yt-dlp"),
    ("static_ffmpeg", "static-ffmpeg"),
]


def is_package_installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def install_package(pip_name: str) -> None:
    print(f"Installing missing dependency: {pip_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])
        print(f"Successfully installed {pip_name}.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing {pip_name}: {e}")
        sys.exit(1)


def main() -> None:
    os.chdir(ROOT)
    print("Checking dependencies...")
    missing = [pip for mod, pip in REQUIRED_PACKAGES if not is_package_installed(mod)]

    if missing:
        print(f"First-time setup detected. Found {len(missing)} missing package(s).")
        for pip_name in missing:
            install_package(pip_name)
        print("All dependencies checked and verified!")
    else:
        print("All dependencies are already satisfied.")

    print("Launching StreamTune...")
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "src/main.py"],
            cwd=ROOT,
        )
    except KeyboardInterrupt:
        print("\nApplication closed by user.")


if __name__ == "__main__":
    main()
