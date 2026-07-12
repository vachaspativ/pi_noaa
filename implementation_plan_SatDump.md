# Migrate from aptdec to SatDump

This plan details the steps to fully replace `aptdec` with `SatDump` for decoding NOAA APT satellite passes, as well as upgrading the web dashboard to support multi-layer image selection (Visible, False Color, Thermal, etc.).

## User Review Required
> [!IMPORTANT]
> **SatDump Installation:** This plan assumes we will change the `install_deps.sh` script to install SatDump. SatDump is a large project. On a Raspberry Pi, it might take a while to compile from source if no pre-built package is available for the OS version.

## Proposed Changes

### Core Configuration
#### [MODIFY] [config.yaml](file:///c:/Users/vacha/code/pi_noaa/config.yaml)
- Change `apt_decoder.backend` from `"aptdec"` to `"satdump"`.
- Replace `aptdec_path` with `satdump_path`.
- Remove `enhancements` array.
- Add `keep_products: ["msa", "mcir", "therm", "1", "2"]` to define which image layers to retain from SatDump's output.

### Decoder Logic
#### [MODIFY] [apt_decoder.py](file:///c:/Users/vacha/code/pi_noaa/sdr/apt_decoder.py)
- Refactor `decode_apt` to handle SatDump's output structure.
- Add `_decode_with_satdump(wav_path, output_dir, apt_cfg)`.
- The function will execute: `satdump noaa_apt wav [wav_path] [temp_dir]`.
- It will then copy the desired products (as defined in `keep_products`) to the final `data/images` directory, appending the product type to the filename (e.g. `NOAA15_1234_msa.png`).
- It will delete the `temp_dir` to purge unneeded logs and raw binary data to save SD card space.
- The function will return a dictionary of product paths (e.g., `{"msa": Path(...), "mcir": Path(...)}`) instead of a single `Path`.

### Image Processing & Storage
#### [MODIFY] [image_processor.py](file:///c:/Users/vacha/code/pi_noaa/sdr/image_processor.py)
- Update `process_image` (if it exists) to handle the new dictionary of layer paths.
- Update the SQLite cache logic (`cache_store.py`) to save the multi-layer JSON payload so that offline users still see the layered structure.

### Backend API
#### [MODIFY] [images.py](file:///c:/Users/vacha/code/pi_noaa/api/routes/images.py)
- Update the `/api/images` endpoint to return the list of available layers for each pass in the JSON response, mapped to their URLs.

### Web Dashboard (UI)
#### [MODIFY] [index.html](file:///c:/Users/vacha/code/pi_noaa/ui/index.html)
- Add a new control panel (toggle buttons or a dropdown) above or below the Satellite Image viewer.
#### [MODIFY] [app.js](file:///c:/Users/vacha/code/pi_noaa/ui/js/app.js)
- Update the logic that renders the image. When a user clicks a pass, load the default layer (e.g., `msa`), and populate the toggle buttons based on available layers in the metadata.
- Wire up the toggle buttons to swap the `<img src="...">` dynamically without reloading the page.

### Dependencies
#### [MODIFY] [install_deps.sh](file:///c:/Users/vacha/code/pi_noaa/scripts/install_deps.sh)
- Remove `aptdec` installation instructions (git clone, make).
- Add `SatDump` installation instructions.

## Verification Plan

### Automated Tests
- Run `python -m pytest tests/` to ensure no existing logic is broken.
- Verify `apt_decoder.py` mock tests work correctly with the new SatDump dict return type.

### Manual Verification
- We will manually trigger a test decode using a mock WAV file to verify the images are parsed, renamed, and moved correctly, and the temporary workspace is cleaned up.
