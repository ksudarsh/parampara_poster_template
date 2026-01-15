#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
default_out="$script_dir/output"

read -r -p "Output folder (default: $default_out): " out_dir
out_dir=${out_dir:-$default_out}
mkdir -p "$out_dir"

docker build -t parampara-poster "$script_dir"
docker run -it --rm -v "$script_dir:/app" -v "$out_dir:/out" parampara-poster
