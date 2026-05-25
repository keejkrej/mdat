# mdat (microscopy data)

Python CLI package for standalone ND2/CZI microscopy data utilities. **mdat**
stands for **microscopy data**.

## Install

Install the CLI globally with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install git+https://github.com/keejkrej/mdat.git
```

Then run `mdat` directly:

```bash
mdat --help
```

For local development, clone the repo and sync dependencies:

```bash
uv sync
```

## Usage

`mdat` supports **ND2** (Nikon) and **CZI** (Zeiss) microscopy files. Run
commands with `mdat …` after installing, or `uv run mdat …` from a local clone.

```bash
uv run mdat --help
uv run mdat convert --help
uv run mdat metadata --help
```

### `convert`

Export image data to TIFF files under an output directory.

```bash
# Full conversion (mdat layout, default)
uv run mdat convert sample.nd2 --output out -y
uv run mdat convert sample.czi --output out -y

# Cell-ACDC layout
uv run mdat convert sample.nd2 --output out --format acdc -y

# Subset: positions 0–4 and 10, timepoints 0–49 and 100, channels 0 and 2, z 0–9
uv run mdat convert sample.nd2 --output out \
  --position 0:5,10 \
  --time 0:50,100 \
  --channel 0,2 \
  --z 0:10 \
  -y
```

| Option | Description |
| --- | --- |
| `-o`, `--output` | Output directory (required). |
| `--format` | `mdat` (default) or `acdc` (Cell-ACDC). |
| `--position` | Positions to export. Default: `all`. |
| `--time` | Timepoints to export. Default: `all`. |
| `--channel` | Channels to export. Default: `all`. |
| `--z` | Z-slices to export. Default: `all`. |
| `-y`, `--yes` | Skip the confirmation prompt. |

Before writing files, `convert` prints a summary of the input dimensions and the
selected positions, timepoints, and channels. Without `-y`, it asks for
confirmation.

**Selection syntax** (`--position`, `--time`, `--channel`, `--z`):

- `all` — every index along that axis.
- Comma-separated indices — e.g. `0,2,4`.
- Python-style slices — e.g. `0:10` (start:end), `0:10:2` (start:end:step).
- Mix slices and indices — e.g. `0:5,10`.

Indices are **0-based** and refer to the original axis order in the source file.
For timepoints, exported filenames use a **renumbered** index (`t_new`: 0, 1, …)
while `time_map.csv` (mdat layout) records the mapping back to the original
indices.

#### Output layout: `mdat` (default)

One folder per position, one TIFF per `(channel, time, z)` frame:

```
out/
  Pos0/
    time_map.csv
    img_channel000_position000_time000000000_z000.tif
    img_channel000_position000_time000000001_z000.tif
    ...
  Pos1/
    ...
```

`time_map.csv` columns: `t` (exported index), `t_real` (original timepoint index).

#### Output layout: `acdc`

Cell-ACDC-compatible layout: one folder per position, one **stacked** TIFF per
channel (T×Z or Z-only), plus a metadata CSV:

```
out/
  Position_1/
    Images/
      sample_s01_metadata.csv
      sample_s01_GFP.tif
      sample_s01_phase_contrast.tif
  Position_2/
    ...
```

Position folders are **1-based** (`Position_1`, `Position_2`, …). Channel TIFF
names come from normalized channel metadata when available.

### `metadata`

Inspect file metadata without converting image data.

```bash
# Normalized JSON to stdout
uv run mdat metadata sample.czi

# Normalized JSON to file
uv run mdat metadata sample.czi --output sample.metadata.json

# Raw metadata payload (OME-XML for ND2, vendor XML for CZI)
uv run mdat metadata sample.nd2 --raw --output sample.metadata.xml
uv run mdat metadata sample.czi --raw --output sample.metadata.xml
```

| Option | Description |
| --- | --- |
| `-o`, `--output` | Write to this file instead of stdout. |
| `--raw` | Export the native metadata payload instead of normalized JSON (OME-XML for ND2, vendor XML for CZI). |

**Normalized JSON** (default) includes:

- `source`, `format` — input path and reader (`nd2` or `czi`).
- `summary` — axis lengths (`n_pos`, `n_time`, `n_chan`, `n_z`) and image shape.
- `normalized` — format-agnostic fields (channels, pixel sizes, objective, acquisition, …).
- `raw_format` — MIME-like hint for the native payload (when one exists).

Use `--raw` when you need the full native metadata rather than the normalized
summary. Both formats support it:

- **ND2** — OME-XML from the `nd2` library (`raw_format`: `ome_xml`).
- **CZI** — vendor XML from `pylibCZIrw` (`raw_format`: `xml`).
