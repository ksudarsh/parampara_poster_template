# Parampara Poster Template

Generate high-resolution A1/A2 posters for the Sri Parakala Matham guru parampara using the provided Excel captions and portrait images.

## What you need
- Python 3.9–3.12 installed on this computer
- Git (to clone the repo)
- [Poetry](https://python-poetry.org/) 1.8+ (for dependency and venv management)
- Repo assets present locally: `acharyan_captions.xlsx`, `assets/` (backgrounds, fonts, signature), and your `images/` directory with portraits

## Clone and install on this computer
1) Open PowerShell and move to the folder where you want the project (for example `E:\CODING\POSTER`):
   ```sh
   cd E:\CODING\POSTER
   ```
2) Clone the repository (replace `<repo-url>` with the actual URL):
   ```sh
   git clone <repo-url>
   cd parampara_poster_template
   ```
3) Install Poetry if you do not already have it:
   ```sh
   pip install poetry
   ```
4) Install project dependencies inside the Poetry environment:
   ```sh
   poetry install
   ```
   This creates an isolated venv with Pillow, pandas, openpyxl, and numpy.

## Prepare your data
- Ensure `acharyan_captions.xlsx` is present and up to date (sheets: `Founders_Early_Acharyas` and `acharyan_captions`).
- Place portrait files in `images/`.
- File name expectations:
  - Founders/early acharyas: filenames containing `F00`, `F01`, `F02`, ... (case-insensitive) map to IDs in the Excel sheet.
  - Parakala acharyas: filenames containing four digits like `0100`, `0200`, ... `3600` map to the corresponding IDs.
  - Accepted extensions: `.png`, `.jpg`, `.jpeg`.

## Run the generator
Execute the script through Poetry so it uses the venv:
```sh
poetry run python generate_parampara_poster.py
```
You will be prompted for:
- Poster size: `A1` (7016x9921 @ 300 DPI) or `A2` (4961x7016 @ 300 DPI)
- Output format: `PDF` or `PNG`

Outputs are written beside the script as `Sri_Parakala_Matham_Guru_Parampara_GRID_<SIZE>.<ext>`.

## Notes
- Fonts are loaded from `assets/fonts/` when present; otherwise common system serif fonts are used.
- The script auto-adjusts image scale to fit content above the footer.
- If you want pinned versions, run `poetry lock` to generate `poetry.lock` and commit it.
