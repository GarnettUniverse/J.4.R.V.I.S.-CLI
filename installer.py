import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path

# --- CONFIGURATION ---
APP_NAME = "jarvis"
INSTALL_DIR = Path.home() / "jarvis_ai"
SCRIPT_NAME = "jarvis.py"
VENV_NAME = "jarvis-venv"

# List of required packages
REQUIREMENTS = [
    "ollama",
    "duckduckgo-search>=6.0.0",
    "psutil",
    "aiohttp",
    "numpy",
    "pyfiglet",
    "beautifulsoup4",
    "opencv-python-headless",  # Headless version is lighter for CLI
    "orjson"  # For speed
]

def print_step(msg):
    print(f"\n[+] {msg}")

def print_error(msg):
    print(f"\n[!] ERROR: {msg}")

def create_directory():
    print_step(f"Creating install directory at: {INSTALL_DIR}")
    try:
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print_error(f"Failed to create directory: {e}")
        sys.exit(1)

def move_script():
    source = Path(SCRIPT_NAME)
    dest = INSTALL_DIR / SCRIPT_NAME
    
    if not source.exists():
        # Check if we are running the installer from the same folder as jarvis.py
        # If not, ask user for path? For now, assume simple setup.
        print_error(f"Could not find '{SCRIPT_NAME}' in the current folder.\nPlease place this installer next to your '{SCRIPT_NAME}' file and run it again.")
        sys.exit(1)
        
    print_step(f"Copying {SCRIPT_NAME} to {INSTALL_DIR}...")
    shutil.copy2(source, dest)

def setup_venv():
    venv_path = INSTALL_DIR / VENV_NAME
    print_step(f"Creating virtual environment: {VENV_NAME}...")
    
    try:
        subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
    except subprocess.CalledProcessError:
        print_error("Failed to create virtual environment.")
        sys.exit(1)
        
    # Determine pip path based on OS
    if platform.system() == "Windows":
        pip_cmd = venv_path / "Scripts" / "pip"
    else:
        pip_cmd = venv_path / "bin" / "pip"
        
    print_step("Installing dependencies (this may take a minute)...")
    try:
        # Upgrade pip first
        subprocess.check_call([str(pip_cmd), "install", "--upgrade", "pip"])
        # Install requirements
        subprocess.check_call([str(pip_cmd), "install"] + REQUIREMENTS)
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install dependencies: {e}")
        sys.exit(1)

def create_launcher():
    print_step(f"Creating '{APP_NAME}' command...")
    
    os_name = platform.system()
    venv_path = INSTALL_DIR / VENV_NAME
    script_path = INSTALL_DIR / SCRIPT_NAME
    
    if os_name == "Windows":
        # Windows: Create a .bat file and add to PATH
        python_exe = venv_path / "Scripts" / "python.exe"
        bat_content = f'@echo off\n"{python_exe}" "{script_path}" %*'
        bat_file = INSTALL_DIR / f"{APP_NAME}.bat"
        
        with open(bat_file, "w") as f:
            f.write(bat_content)
            
        print(f"    Created batch file: {bat_file}")
        
        # Add to User PATH using PowerShell (non-destructive)
        print_step("Adding installation folder to User PATH...")
        try:
            cmd = f'[Environment]::SetEnvironmentVariable("Path", [Environment]::GetEnvironmentVariable("Path", "User") + ";{str(INSTALL_DIR)}", "User")'
            subprocess.run(["powershell", "-Command", cmd], check=True)
            print("    Success! You may need to restart your terminal.")
        except Exception as e:
            print_error(f"Could not automatically add to PATH: {e}")
            print(f"    MANUAL STEP: Add '{INSTALL_DIR}' to your User PATH environment variable.")

    else:
        # Linux/Mac: Create a shell script and alias
        python_exe = venv_path / "bin" / "python"
        
        # Create a robust shell wrapper
        wrapper_path = INSTALL_DIR / APP_NAME
        wrapper_content = f"""#!/bin/bash
cd "{INSTALL_DIR}"
"{python_exe}" "{script_path}" "$@"
"""
        with open(wrapper_path, "w") as f:
            f.write(wrapper_content)
        
        # Make executable
        wrapper_path.chmod(0o755)
        
        # Detect shell config
        shell = os.environ.get("SHELL", "/bin/bash")
        rc_file = None
        if "zsh" in shell:
            rc_file = Path.home() / ".zshrc"
        elif "bash" in shell:
            rc_file = Path.home() / ".bashrc"
        
        if rc_file and rc_file.exists():
            print_step(f"Adding alias to {rc_file}...")
            alias_line = f'\n# Jarvis AI Alias\nexport PATH="$PATH:{INSTALL_DIR}"\n'
            
            # Check if already exists to avoid duplicates
            if str(INSTALL_DIR) not in rc_file.read_text():
                with open(rc_file, "a") as f:
                    f.write(alias_line)
                print(f"    Added {INSTALL_DIR} to PATH.")
                print(f"    run 'source {rc_file}' to apply changes immediately.")
            else:
                print("    Path already exists in shell config.")
        else:
            print_step(f"Could not detect shell config file. Please add '{INSTALL_DIR}' to your PATH manually.")

def main():
    print("="*50)
    print(f"   {APP_NAME.upper()} INSTALLER")
    print("="*50)
    
    create_directory()
    move_script()
    setup_venv()
    create_launcher()
    
    print("\n" + "="*50)
    print("   INSTALLATION COMPLETE!")
    print("="*50)
    print(f"\n1. Your AI is located at: {INSTALL_DIR}")
    print(f"2. To run it, restart your terminal and type: {APP_NAME}")
    if platform.system() != "Windows":
        print("   (Or run 'source ~/.bashrc' or 'source ~/.zshrc' first)")
    print("\nEnjoy your new assistant!")

if __name__ == "__main__":
    main()
