#!/usr/bin/env bash
set -euo pipefail

echo "Building checkerboard_fmri_task for Linux..."

rm -rf build_output/work/linux
rm -rf build_output/dist/checkerboard_fmri_task_linux

python -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name "checkerboard_fmri_task_linux" \
  --distpath build_output/dist \
  --workpath build_output/work/linux \
  --copy-metadata checkerboard-fmri-task \
  src/checkerboard_fmri_task/main.py

echo "Linux build complete:"
echo "build_output/dist/checkerboard_fmri_task_linux"
