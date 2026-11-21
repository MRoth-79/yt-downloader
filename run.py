import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "requirements.txt"
MIN_PYTHON = (3, 10)
REQUIRED_MODULES = ("streamlit", "yt_dlp", "static_ffmpeg")


def check_python() -> None:
    if sys.version_info < MIN_PYTHON:
        required = ".".join(map(str, MIN_PYTHON))
        found = ".".join(map(str, sys.version_info[:3]))
        sys.exit(f"StreamTune needs Python {required}+ (found {found}).")


def is_module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def install_requirements() -> None:
    """Install or upgrade everything in requirements.txt. pip skips packages that are already current."""
    print("Checking dependencies...")
    try:
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "-q",
                "-r",
                str(REQUIREMENTS),
            ]
        )
    except subprocess.CalledProcessError as exc:
        missing = [name for name in REQUIRED_MODULES if not is_module_available(name)]
        if missing:
            sys.exit(
                f"Could not install dependencies (pip exit code {exc.returncode}). "
                f"Missing: {', '.join(missing)}. Check your internet connection and try again."
            )
        print(f"Dependency update failed (pip exit code {exc.returncode}); starting with installed versions.")
        return
    print("All dependencies are up to date.")


def main() -> None:
    check_python()
    install_requirements()

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
