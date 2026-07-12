import sys
import subprocess
import importlib.util

# List of required Python packages to check and install
REQUIRED_PACKAGES = ["streamlit", "yt-dlp"]

def is_package_installed(package_name):
    """Check if a specific Python package is available in the current environment."""
    return importlib.util.find_spec(package_name) is not None

def install_package(package_name):
    """Install a package using pip quietly."""
    print(f"Installing missing dependency: {package_name}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"Successfully installed {package_name}.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing {package_name}: {e}")
        sys.exit(1)

def main():
    print("Checking dependencies...")
    missing_packages = [pkg for pkg in REQUIRED_PACKAGES if not is_package_installed(pkg)]
    
    # Install any missing packages automatically on the first run
    if missing_packages:
        print(f"First-time setup detected. Found {len(missing_packages)} missing packages.")
        for pkg in missing_packages:
            install_package(pkg)
        print("All dependencies checked and verified!")
    else:
        print("All dependencies are already satisfied.")

    # Boot up the Streamlit interface using the current python executable
    print("Launching YouTube Media Downloader...")
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/main.py"])
    except KeyboardInterrupt:
        print("\nApplication closed by user.")

if __name__ == "__main__":
    main()