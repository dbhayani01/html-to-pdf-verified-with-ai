#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd -- "$script_dir/../.." && pwd -P)"
input_arg="${1:-$repo_root/sample.html}"
output_arg="${2:-$repo_root/sample_ecs_local.pdf}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Engine or Docker Desktop, then retry." >&2
  exit 127
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed, but its daemon is not available. Start Docker and retry." >&2
  exit 1
fi
if [[ ! -f "$input_arg" ]]; then
  echo "Input HTML file not found: $input_arg" >&2
  exit 2
fi

input_path="$(cd -- "$(dirname -- "$input_arg")" && pwd -P)/$(basename -- "$input_arg")"
input_dir="$(dirname -- "$input_path")"
input_name="$(basename -- "$input_path")"
output_dir_arg="$(dirname -- "$output_arg")"
output_name="$(basename -- "$output_arg")"
mkdir -p "$output_dir_arg"
output_dir="$(cd -- "$output_dir_arg" && pwd -P)"
output_path="$output_dir/$output_name"
temp_output_dir="$(mktemp -d "${TMPDIR:-/tmp}/html-to-pdf-local.XXXXXX")"
trap 'rm -rf -- "$temp_output_dir"' EXIT

image="html-to-pdf-ecs-local:latest"
echo "Building the ECS task image..."
docker build -f "$script_dir/Dockerfile" -t "$image" "$repo_root"

echo "Running the full render pipeline with container networking disabled..."
docker run --rm --network none \
  --mount "type=bind,src=$input_dir,dst=/work/input,readonly" \
  --mount "type=bind,src=$temp_output_dir,dst=/work/output" \
  --env "INPUT_HTML_PATH=/work/input/$input_name" \
  --env OUTPUT_DIR=/work/output \
  "$image"

input_stem="${input_name%.*}"
container_pdf="$temp_output_dir/$input_stem.pdf"
if [[ ! -s "$container_pdf" ]]; then
  echo "The local renderer did not produce a PDF at $container_pdf." >&2
  exit 1
fi
pdf_header="$(head -c 5 "$container_pdf")"
if [[ "$pdf_header" != "%PDF-" ]]; then
  echo "The local renderer output does not have a valid PDF header." >&2
  exit 1
fi
pages_dir="$temp_output_dir/${input_stem}_pages"
shopt -s nullglob
page_images=("$pages_dir"/page_*.png)
if (( ${#page_images[@]} < 1 )); then
  echo "The local renderer did not produce any page images." >&2
  exit 1
fi

cp -- "$container_pdf" "$output_path"
output_stem="${output_name%.*}"
pages_output_path="$output_dir/${output_stem}_pages"
mkdir -p "$pages_output_path"
cp -- "${page_images[@]}" "$pages_output_path/"
echo "PASS: local ECS-style pipeline completed with --network none."
echo "PDF: $output_path"
echo "Pages: $pages_output_path (${#page_images[@]} PNG image(s))"
