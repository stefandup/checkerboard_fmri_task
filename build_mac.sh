#!/usr/bin/env bash
set -euo pipefail

echo "Building Checkerboard fMRI Task for macOS..."

rm -rf build_output/work/mac
rm -rf "build_output/dist/Checkerboard fMRI Task"
rm -rf "build_output/dist/Checkerboard fMRI Task.app"

python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name "Checkerboard fMRI Task" \
  --osx-bundle-identifier "za.ac.sun.checkerboard_fmri_task" \
  --icon "assets/Radial Checkerboard Optical Target.png" \
  --distpath build_output/dist \
  --workpath build_output/work/mac \
  --copy-metadata checkerboard-fmri-task \
  src/checkerboard_fmri_task/main.py

echo "macOS build complete:"
echo "build_output/dist/Checkerboard fMRI Task.app"
