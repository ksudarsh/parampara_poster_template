# Paramparā Poster Template (Docker-first)

Generate high-resolution A1/A2 posters for the Sri Parakala Matham guru paramparā using the provided Excel captions and portrait images.

**Recommended for everyone:** use the **prebuilt Docker image on GHCR** (GitHub Container Registry).  
That way you don’t need to install Python/Conda, and you don’t need to build the image locally.

---

## Quick start (no git clone required)

### 1) Install Docker
- **Windows/macOS:** install **Docker Desktop** and start it.
- **Ubuntu/Linux:** install **Docker Engine** and ensure the daemon is running.

Verify:
```sh
docker --version
docker run --rm hello-world
```

### 2) Pull the prebuilt image from GHCR (no rebuild)
```sh
docker pull ghcr.io/ksudarsh/parampara_poster_template:latest
```

### 3) Run it (outputs go into a local `output/` folder)

The container will prompt you for:
- **Language(s):** English/Kannada/Telugu/Sanskrit (default: English)
- **Output format:** PDF or PNG (default: PDF)

#### Windows (PowerShell)
```powershell
New-Item -ItemType Directory -Force -Path .\output | Out-Null
docker run --rm -it -v "${PWD}\output:/out" ghcr.io/ksudarsh/parampara_poster_template:latest
```

#### Windows (CMD)
```bat
mkdir output 2>nul
docker run --rm -it -v "%cd%\output:/out" ghcr.io/ksudarsh/parampara_poster_template:latest
```

#### macOS / Linux
```sh
mkdir -p output
docker run --rm -it -v "$(pwd)/output:/out" ghcr.io/ksudarsh/parampara_poster_template:latest
```

✅ After it finishes, your PDFs/PNGs will be in `output/`.

---

## Override defaults (XLSX / assets / images) — without cloning

The GHCR image already includes **default data**:
- the 4 language-specific caption workbooks:
  - `acharyan_captions_english.xlsx`
  - `acharyan_captions_kannada.xlsx`
  - `acharyan_captions_telugu.xlsx`
  - `acharyan_captions_sanskrit.xlsx`
- `assets/` (backgrounds, tiles, signature, fonts)
- `images/` (default portraits, if present in the image)

To override, create a local folder named `overrides/` and mount it to **`/overrides`**.
Anything inside `/overrides` is copied over the built-in defaults before generation.

### Override ONLY captions (XLSX)

**Example:** Replace English captions while using the default images/assets from the container.

Folder:
```
overrides/
  acharyan_captions_english.xlsx
```

Run:

#### Windows (PowerShell)
```powershell
New-Item -ItemType Directory -Force -Path .\overrides | Out-Null
# Put your XLSX into .\overrides (example copies a file you already have)
# Copy-Item .\my_english.xlsx .\overrides\acharyan_captions_english.xlsx

New-Item -ItemType Directory -Force -Path .\output | Out-Null
docker run --rm -it `
  -v "${PWD}\output:/out" `
  -v "${PWD}\overrides:/overrides" `
  ghcr.io/ksudarsh/parampara_poster_template:latest
```

#### macOS / Linux
```sh
mkdir -p overrides output
# cp ./my_english.xlsx ./overrides/acharyan_captions_english.xlsx

docker run --rm -it \
  -v "$(pwd)/output:/out" \
  -v "$(pwd)/overrides:/overrides" \
  ghcr.io/ksudarsh/parampara_poster_template:latest
```

### Override individual images (most common customizations)

You can override **just one thing** (e.g., background) or many things.

#### A) Choose a different background texture
Put your replacement file here (same path/name):
```
overrides/assets/parchment_bg.jpg
```

#### B) Use a different mandala/tile overlay
```
overrides/assets/mandala_tile.png
```

#### C) Use a different signature/footer image
```
overrides/assets/signature.png
```

#### D) Change fonts (English / Kannada / Telugu / Sanskrit)
Drop fonts into:
```
overrides/assets/fonts/
```

If you want to force specific fonts for your language, include the appropriate `.ttf` files in that folder.
(If you don’t override fonts, the image uses the bundled/default fonts.)

#### E) Replace a specific Acharyan portrait image
Use the same filename conventions as the defaults:

- **Founders / early acharyas:** filenames containing `F00`, `F01`, `F02`, ...
- **Parakāla acharyas:** filenames containing four digits like `0100`, `0200`, ... `3600`
- Extensions: `.png`, `.jpg`, `.jpeg`

Example:
```
overrides/images/F03_newphoto.jpg
overrides/images/0120_better_crop.png
```

Run with overrides (same command as above):
```sh
docker run --rm -it \
  -v "$(pwd)/output:/out" \
  -v "$(pwd)/overrides:/overrides" \
  ghcr.io/ksudarsh/parampara_poster_template:latest
```

---

## If you want to clone the repo (developer / advanced)

### Clone
```sh
git clone https://github.com/ksudarsh/parampara_poster_template.git
cd parampara_poster_template
```

### Run with Python (optional)
> Docker is strongly recommended on Windows for correct complex-script shaping.

```sh
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python generate_parampara_poster.py
```

#### Ensure Pillow has RAQM shaping (Kannada/Telugu/Devanagari etc.)
```sh
python -c "from PIL import features; print('RAQM available:', features.check('raqm'))"
```
- If it prints `True`, you are set.
- If it prints `False`:
  - Ubuntu/macOS: try `python -m pip install --upgrade pillow` and recheck.
  - Windows: pip wheels often lack RAQM; prefer Docker/WSL or conda-forge.

### Docker (local build/run from source)
Windows (PowerShell):
```powershell
.\run_docker.ps1
```

macOS/Linux:
```sh
./run_docker.sh
```

---

## Publishing to GHCR (maintainers)

### Manual build & push
From the repo folder:
```sh
docker build -t ghcr.io/ksudarsh/parampara_poster_template:latest .
docker push ghcr.io/ksudarsh/parampara_poster_template:latest
```

### Auto-publish with GitHub Actions
This repo includes a workflow that builds and publishes the Docker image to GHCR on pushes to `main` (and can be run manually).

End users should only need:
```sh
docker pull ghcr.io/ksudarsh/parampara_poster_template:latest
```

---

## Troubleshooting

### PowerShell: “The ampersand (&) character is not allowed”
That happens if you paste CMD-style chaining like:
```bat
mkdir output 2>nul & docker run ...
```
In PowerShell, run commands on separate lines, or use `;`.

### Output folder is empty
Make sure you mounted `/out` correctly:
- PowerShell: `-v "${PWD}\\output:/out"`
- CMD: `-v "%cd%\\output:/out"`
- macOS/Linux: `-v "$(pwd)/output:/out"`

### Line ending issues (`bash\r` / `exec format error`)
If you edit shell scripts on Windows, CRLF can break execution inside Linux containers.
Prefer editing `.sh` files with LF line endings, and keep `.gitattributes` rules in place.

---

## Notes
- Fonts are chosen per language. If you have language-specific Noto fonts, place them under `assets/fonts/` for best rendering.
- Variable fonts are supported; the script requests weight axes when available.
- The script auto-adjusts image scale to fit content above the footer.
- `pyproject.toml` remains for reference; installation uses `requirements.txt`.
