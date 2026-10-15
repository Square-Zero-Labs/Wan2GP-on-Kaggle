# Wan2GP on Kaggle

[![Open in Kaggle](https://kaggle.com/static/images/open-in-kaggle.svg)](https://kaggle.com/kernels/welcome?src=https://github.com/Square-Zero-Labs/Wan2GP-on-Kaggle/blob/main/wan2gp-kaggle.ipynb)

Kaggle notebook for running [Wan2GP](https://github.com/deepbeepmeep/Wan2GP) with a GPU-backed session.

## Tutorial

[![Watch the Wan2GP on Kaggle tutorial](https://img.youtube.com/vi/7jboiN00aRk/hqdefault.jpg)](https://youtu.be/7jboiN00aRk)

[Watch the notebook tutorial on YouTube](https://youtu.be/7jboiN00aRk)

## Before You Run

* Complete Kaggle phone verification.
* In notebook settings, enable **Internet** and select **GPU T4** if available. Use **GPU P100** only as a fallback.
* Run the notebook cells from top to bottom.

Kaggle's 16 GB GPUs are tight for Wan2GP. Start with `Wan 2.2 TextImage2Video 5B FastWan` at 480p before trying larger models or higher resolutions.

## What The Notebook Does

* Clones or updates Wan2GP in `/kaggle/working/Wan2GP`.
* Stores large checkpoints, LoRAs, and model caches in `/kaggle/temp/Wan2GP-data` to avoid filling Kaggle's smaller output quota.
* Stores generated files in `/kaggle/working/Wan2GP-outputs` so they can be saved with the notebook output.
* Uses Kaggle's preinstalled CUDA-enabled PyTorch and installs only Wan2GP's missing Python requirements.
* Launches Wan2GP through a public Gradio link.

Keep the final launch cell running while using the UI. Stopping that cell stops Wan2GP.

## Notes

* Step 6 probes the FFmpeg binary selected by Wan2GP (`FFMPEG_BINARY`, bundled binary, then `PATH`). Builds without `-fps_mode` use the equivalent `-vsync 0` only in the rawvideo decoder commands; builds with `-fps_mode` keep the upstream source. Rerun Step 6 after updating Wan2GP. No FFmpeg upgrade is required.
* Step 5 writes a constraints file pinning Kaggle's detected `torch`, `torchvision`, and `torchaudio` versions before installing Wan2GP requirements.
* Dependency installs use `--no-cache-dir`, and model/runtime caches are pointed at `/kaggle/temp` to reduce disk pressure.
* If GPU options are grayed out, check Kaggle phone verification and GPU quota.
* If Kaggle changes its base image or GPU availability, restart the session and rerun the notebook from the top.

## Contributing

Issues and pull requests are welcome.

### Compatibility tests

Run the notebook setup regression tests with the Python standard library:

```bash
python -m unittest discover -s tests -v
```

For real media coverage, install NumPy and CPU PyTorch in a test environment and
point `WAN2GP_SOURCE` at an upstream Wan2GP checkout. The CI workflow pins upstream
revision `af2ed29a83dbccc7f1c0571a73005648436b392e` and runs on Ubuntu 22.04 and
24.04 with their system FFmpeg packages. The notebook itself continues to use the
Wan2GP revision downloaded in Step 3.

```bash
WAN2GP_SOURCE=/path/to/Wan2GP \
FFMPEG_TEST_BINARIES=/path/to/older/ffmpeg:/usr/bin/ffmpeg \
python -m unittest discover -s tests -v
```

The media tests execute the notebook compatibility cell and actual upstream decoder
functions against generated lossless MP4s. They cover contiguous decoding, seeking,
frame limits, sparse ordering and duplicates, resampling, variable timestamps,
virtual clips, and pixel aspect correction. They also compare passthrough timestamps
and frame hashes. Without `WAN2GP_SOURCE`, media tests are explicitly skipped.
A local run reproduced the original error on FFmpeg 4.2.2 and passed the compatibility
suite on 4.2.2 and 7.1.5. Kaggle images change; the runtime capability probe, rather
than a hardcoded version threshold, chooses the compatibility path.
