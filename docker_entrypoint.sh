#!/usr/bin/env bash
set -euo pipefail

cd /app
python generate_parampara_poster.py

out_dir="/out"
if [ -d "$out_dir" ]; then
  shopt -s nullglob
  files=(Sri_Parakala_Matham_Guru_Parampara_*.pdf Sri_Parakala_Matham_Guru_Parampara_*.png)
  if [ ${#files[@]} -gt 0 ]; then
    cp -f "${files[@]}" "$out_dir/"
    echo "Copied output files to $out_dir"
  else
    echo "No output files found to copy."
  fi
fi
