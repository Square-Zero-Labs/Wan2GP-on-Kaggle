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

* Step 5 writes a constraints file pinning Kaggle's detected `torch`, `torchvision`, and `torchaudio` versions before installing Wan2GP requirements.
* Dependency installs use `--no-cache-dir`, and model/runtime caches are pointed at `/kaggle/temp` to reduce disk pressure.
* If GPU options are grayed out, check Kaggle phone verification and GPU quota.
* If Kaggle changes its base image or GPU availability, restart the session and rerun the notebook from the top.

## Contributing

Issues and pull requests are welcome.
