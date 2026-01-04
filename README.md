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

## Install dependencies with conda/Anaconda (optional)
```sh
# create an env (choose Python 3.9–3.12)
conda create -n parampara-poster python=3.11 -y
conda activate parampara-poster
# install deps via pip inside the env
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Prepare your data
- Ensure your captions workbook is present: `acharyan_captiona_english.xlsx` (default) or language-specific files like `acharyan_captiona_kannada.xlsx`, etc. Sheets should include `Banner_Text` (M1–M5), `Founders_Early_Acharyas`, and `acharyan_captions`.
- Place portrait files in `images/`.
- File name expectations:
  - Founders/early acharyas: filenames containing `F00`, `F01`, `F02`, ... (case-insensitive) map to IDs in the Excel sheet.
  - Parakala acharyas: filenames containing four digits like `0100`, `0200`, ... `3600` map to the corresponding IDs.
  - Accepted extensions: `.png`, `.jpg`, `.jpeg`.

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

## Notes
- Fonts are chosen per language. If you have language-specific Noto fonts, place them under `assets/fonts/` (e.g., NotoSerifKannada, NotoSerifTelugu, NotoSerifTamil, NotoSerifDevanagari) for best rendering; system fallbacks are used if not found.
- The script auto-adjusts image scale to fit content above the footer.
- `pyproject.toml` remains for reference; installation uses `requirements.txt`.
