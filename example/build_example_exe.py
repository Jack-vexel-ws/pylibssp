#!/usr/bin/env python3
"""
Build script for Z CAM Streaming Example
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(cmd, description):
    """run command and handle errors"""
    print(f"\n{description}...")
    print(f"Running: {cmd}")
    
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print("✓ Success")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Error: {e}")
        print(f"Error output: {e.stderr}")
        return False

def main():
    print("=" * 50)
    print("Z CAM Streaming Example - Build Script")
    print("=" * 50)
    
    # Step 1: Check current directory
    current_dir = Path(__file__).parent
    os.chdir(current_dir)
    print(f"Working directory: {current_dir}")
    
    # Step 2: Check Python environment
    print("\nStep 1: Checking Python environment...")
    if not run_command("python --version", "Checking Python version"):
        return False
    
    # Step 3: Install required packages
    print("\nStep 2: Installing required packages...")
    packages = [
        "pyinstaller",
        "libssp",
        "PySide6", 
        "av",
        "numpy",
        "requests"
    ]
    
    for package in packages:
        if not run_command(f"pip install {package}", f"Installing {package}"):
            print(f"Warning: Failed to install {package}")
    
    # Step 4: Clean previous builds
    print("\nStep 3: Cleaning previous builds...")
    for dir_name in ["build", "dist", "__pycache__"]:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"Cleaned {dir_name}")
    
    # Step 5: Build executable
    print("\nStep 4: Building executable...")
    if not run_command("pyinstaller --clean example.spec", "Building with PyInstaller"):
        return False
    
    # Step 6: Check result
    exe_path = Path("dist/ZCAM Camera Streaming Example.exe")
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n✓ Build completed successfully!")
        print(f"Executable: {exe_path}")
        print(f"Size: {size_mb:.1f} MB")
        print(f"\nYou can now distribute the exe file to users.")
    else:
        print(f"\n✗ Error: Executable not found at {exe_path}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        print("\nBuild failed!")
        sys.exit(1)
    else:
        print("\nBuild completed successfully!") 