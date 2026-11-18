# Podcast audio collection and diarization

Install the dependencies and use the project `.venv` as the notebook kernel:

```bash
uv sync
```

The project uses Python 3.12 or newer. The download and video conversion notebooks also require `ffmpeg` on your PATH.

## Notebooks

- `src/data_preprocessing/data_collection.ipynb`: download audio with yt-dlp using links from `data/podcasts.md`.
- `src/data_preprocessing/pytubefix.ipynb`: alternative downloader using PytubeFix.
- `src/data_preprocessing/video_to_audio.ipynb`: convert videos in `data/videos` to WAV files in `data/raw_audios`.
- `src/data_preprocessing/diarisation.ipynb`: inspect audio and experiment with Silero voice activity detection.
- `src/data_preprocessing/nemo_diarisation.ipynb`: identify who spoke when with NVIDIA NeMo.

For the NeMo notebook, set `audio_path` and optionally `num_speakers`, then run the cells in order. It creates a separate 16 kHz mono copy, prepares a manifest, and runs MarbleNet VAD, multiscale speaker embeddings, clustering, and MSDD refinement. The original audio is preserved. The result is an RTTM file with anonymous speaker labels and timestamps; it is not a transcript.

NeMo's pretrained models are downloaded on first use to `data/models/nemo`. Each run saves its prepared WAV, manifest, intermediate files, and RTTM under a new folder in `outputs/diarization/`. These generated files are ignored by Git. The supplied configuration is NVIDIA's telephonic example, so podcast recordings may need VAD tuning and results should be checked by listening. The notebook defaults to CPU; it can be slow on long recordings.

The yt-dlp downloader may use Node.js and fetch yt-dlp's EJS component from GitHub. If YouTube asks you to sign in, sign in in your browser and set `cookies_from_browser = "chrome"` (or `"firefox"`) in the last cell. YouTube can still reject the request.
