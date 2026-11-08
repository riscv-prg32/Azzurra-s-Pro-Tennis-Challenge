# Publishing to the Cartridge Store

The build makes a bundle that is ready for submission. **Publishing it is a
separate step, done by a person with Store credentials.** No script in this
repository contacts a Store, and no credential belongs in the repository.

## The bundle

```bash
scripts/build.sh
scripts/pack-store-bundle.sh
```

The second command writes `dist/azzurra-pro-tennis-<version>-store.zip`, in
the layout of the CartridgeStore API (`CartridgeStore/docs/api.md`, "Bundle
Publish"):

| Entry | Source |
|-------|--------|
| `manifest.json` | Generated from `metadata/metadata.json` (minus `runtime`, which the Store derives per variant), plus `colophon`, `assets` and `architectures` |
| `icon.png` | `assets/store/icon.png` (64 × 64, made by `tools/make_store_art.py`) |
| `splash.png` | `assets/store/screenshot.png` (320 × 200, a real QEMU frame) |
| `preview.mp4` | `assets/store/preview.mp4` (60 s, H.264 + stereo AAC, video and audio grabbed from QEMU; see [reproduce.md](reproduce.md)) |
| `azzurra-pro-tennis-esp32c6.prg32` | `dist/`, from `scripts/build.sh` |
| `azzurra-pro-tennis-qemu.prg32` | `dist/`, from `scripts/build.sh` |

The manifest names the preview in `assets.preview`, and it also sits at the
ZIP root as `preview.mp4`. The Store accepts either.

The ZIP is reproducible: every entry's timestamp is pinned to the release date
in `metadata.json` (`updated_at`). `dist/SHA256SUMS` lists the checksums of
both packages and of the bundle.

## Validation

`pack-store-bundle.sh` runs `tools/validate_bundle.py`, which checks the
bundle at the strongest of three levels that it can reach:

1. **`store-ingest`**: the CartridgeStore's own `_prepare_bundle()`, the code
   behind `POST /api/publish/bundle`. It is used when `../CartridgeStore` (or
   `CARTRIDGE_STORE_REPO`) exists and its Python requirements are installed.
   Set `STORE_PYTHON` to such an interpreter.
2. **`store-format`**: each image is rebuilt with the Store's `prg32_format`
   module.
3. **`structural`**: local checks only.

Every level checks:

* `abi` is `prg32-metadata-1.0`;
* `id`, `title`, `version` and `summary` are present;
* the icon and splash are PNG or JPEG;
* the preview is an MP4 (an ISO `ftyp` box);
* exactly the `esp32c6` and `qemu` variants are present;
* each rebuilt image fits the 128 KiB package limit.

It prints `READY for submission` and exits 0 only when every check passes.

## Submitting

A maintainer with an account on the Store submits the ZIP in one of two ways:

* through the Store's web upload page;
* with PRG32's tool, run from the PRG32 checkout. The tool needs the Store's
  URL and the maintainer's token. Type the command yourself, and never save
  the token in a script or commit it:

  ```bash
  python3 -m prg32 store publish-bundle ../Azzurra-s-Pro-Tennis-Challenge/dist/azzurra-pro-tennis-2.2.0-store.zip --store-url <store-url> --token <token>
  ```

The submission waits for an editor to verify it. The editor can watch the
preview before verifying.

## Checklist for a new version

1. Update the version, the summary and the description, and `updated_at`,
   in `metadata/metadata.json`.
2. Update the version and the credits in `metadata/colophon.json`.
3. Add the version to `CHANGELOG.md`.
4. Run the tests: `tests/run_tests.sh`.
5. Rebuild: `scripts/build.sh`.
6. Record the preview again, if the game looks or sounds different
   ([reproduce.md](reproduce.md)), and copy it to `assets/store/preview.mp4`.
7. Pack and validate: `scripts/pack-store-bundle.sh`.
8. Commit `dist/`, including the bundle and `SHA256SUMS`, and tag the release.
