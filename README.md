# Parampara Poster Template

Generate high-resolution A1/A2 posters for the Sri Parakala Matham guru parampara using the provided Excel captions and portrait images.

## What you need
- Python 3.9-3.12 installed (Windows, macOS, Ubuntu)
- Git (to clone the repo)
- Repo assets present locally: `acharyan_captiona_english.xlsx` (or other `acharyan_captiona_<lang>.xlsx` files), `assets/` (backgrounds, fonts, signature), and your `images/` directory with portraits

## Clone the repo
1) Open your terminal/PowerShell and move to the folder where you want the project (for example `E:\CODING\POSTER` or `~/code`):
   ```sh
   cd E:\CODING\POSTER
   ```
2) Clone the repository (replace `<repo-url>` with the actual URL):
   ```sh
   git clone <repo-url>
   cd parampara_poster_template
   ```

## Install dependencies with pip (default)
```sh
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Ensure Pillow has RAQM shaping (Kannada/Telugu/Tamil/Devanagari)
Complex scripts need Pillow built with RAQM (HarfBuzz + FriBidi). Check once:
```sh
python -c "from PIL import features; print('RAQM available:', features.check('raqm'))"
```
- If it prints `True`, you are set.
- If it prints `False`:
  - Ubuntu/macOS (pip): the official Pillow wheels usually include RAQM; try `python -m pip install --upgrade pillow` and recheck.
  - Windows: pip wheels often lack RAQM. Use conda-forge which bundles it:
    ```sh
    conda install -c conda-forge "pillow>=10.2"
    ```
    If RAQM still shows `False`, prefer running the script on Ubuntu/WSL or macOS.

## Install dependencies with conda/Anaconda (optional)
```sh
# create an env (choose Python 3.9-3.12)
conda create -n parampara-poster python=3.11 -y
conda activate parampara-poster
# install deps via pip inside the env
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Prepare your data
- Ensure your captions workbook is present: `acharyan_captiona_english.xlsx` (default) or language-specific files like `acharyan_captiona_kannada.xlsx`, etc. Sheets should include `Banner_Text` (M1-M5), `Founders_Early_Acharyas`, and `acharyan_captions`.
- Place portrait files in `images/`.
- File name expectations:
  - Founders/early acharyas: filenames containing `F00`, `F01`, `F02`, ... (case-insensitive) map to IDs in the Excel sheet.
  - Parakala acharyas: filenames containing four digits like `0100`, `0200`, ... `3600` map to the corresponding IDs.
  - Accepted extensions: `.png`, `.jpg`, `.jpeg`.

## Assets layout (required files)
```
parampara_poster_template/
  assets/
    parchment_bg.jpg
    mandala_tile.png
    signature.png
    fonts/
      NotoSerif-*.ttf (optional but recommended)
  images/
    F00_*.png / F01_*.jpg / ...
    0100_*.png / 0200_*.jpg / ...
```
- `assets/parchment_bg.jpg`: background texture.
- `assets/mandala_tile.png`: subtle tiled overlay.
- `assets/signature.png`: footer signature.
- `assets/fonts/`: drop language fonts here to force consistent rendering across OS.

## Run the generator
From the project folder:
```sh
python generate_parampara_poster.py
```
You will be prompted for:
- Language: English (default), Kannada, Telugu, Tamil, or Sanskrit (picks the corresponding `acharyan_captiona_<lang>.xlsx` if present)
- Poster size: `A1` (7016x9921 @ 300 DPI) or `A2` (4961x7016 @ 300 DPI)
- Output format: `PDF` or `PNG`

Outputs are written beside the script as `Sri_Parakala_Matham_Guru_Parampara_GRID_<SIZE>.<ext>`.

## Docker (local build and run)
This is the easiest way to get Ubuntu+RAQM on Windows/macOS without installing extra packages.

Windows (PowerShell):
```powershell
.\run_docker.ps1
```

macOS/Linux:
```sh
./run_docker.sh
```

Both scripts:
- prompt for an output folder (defaults to `output/`)
- build the image and run interactively (language/size/format prompts)
- copy generated `PDF/PNG` files to the chosen output folder

## Docker (publish to GHCR for end users)
Use GitHub Container Registry so users can pull without building locally.

Build and push (from this repo folder):
```sh
docker build -t ghcr.io/<github-user>/<repo>:latest .
docker push ghcr.io/<github-user>/<repo>:latest
```

End user run:
```sh
docker pull ghcr.io/<github-user>/<repo>:latest
docker run -it --rm -v "$(pwd):/app" -v "$(pwd)/output:/out" ghcr.io/<github-user>/<repo>:latest
```

Windows PowerShell equivalent:
```powershell
docker pull ghcr.io/<github-user>/<repo>:latest
docker run -it --rm -v "${PWD}:/app" -v "${PWD}\output:/out" ghcr.io/<github-user>/<repo>:latest
```

## Docker (auto-publish with GitHub Actions)
This repo includes a workflow that builds and publishes the Docker image to GHCR on every push to `main` (and can be run manually).

1) Ensure your repo is public (or GHCR is allowed for your org).
2) Push to `main` or run the workflow manually in the Actions tab.
3) Pull using:
```sh
docker pull ghcr.io/<github-user>/<repo>:latest
```

## Notes
- Fonts are chosen per language. If you have language-specific Noto fonts, place them under `assets/fonts/` (e.g., NotoSerifKannada, NotoSerifTelugu, NotoSerifTamil, NotoSerifDevanagari) for best rendering; system fallbacks are used if not found.
- Variable fonts (e.g., `...-VariableFont_wght.ttf`) are supported; the script requests weight axes when available.
- The script auto-adjusts image scale to fit content above the footer.
- `pyproject.toml` remains for reference; installation uses `requirements.txt`.
