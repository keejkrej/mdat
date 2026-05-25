# mdat (Python)

Python CLI package for standalone ND2/CZI microscopy data utilities.

## Install

```bash
uv sync
```

## Usage

```bash
uv run mdat convert sample.nd2 --output out -y
uv run mdat convert sample.czi --output out -y
uv run mdat convert sample.nd2 --output out --format acdc -y
uv run mdat metadata sample.czi --output sample.metadata.json
uv run mdat metadata sample.czi --raw --output sample.metadata.xml
```

Use `--format mdat` (default) for per-frame TIFF folders (`Pos0/...`), or
`--format acdc` for the Cell-ACDC layout (`Position_1/Images/...` with one
stacked TIFF per channel and a `_metadata.csv`).

The default metadata JSON is a normalized, format-agnostic summary. Use `--raw`
when you need the full vendor/library metadata payload.
