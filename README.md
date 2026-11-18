# Podcast audio collection and diarization

```bash
uv sync
```

Python 3.12+, `ffmpeg` on PATH.

## Notebooks

In `src/data_preprocessing/`, run in order. All audio goes to `data/raw_audios/`.

1. `01_download_ytdlp.ipynb` - download links from `data/podcasts.md` (`01_download_pytubefix.ipynb` if yt-dlp fails)
2. `02_video_to_wav.ipynb` - videos in `data/videos/` to wav (optional)
3. `03_vad.ipynb` - Silero VAD
4. `04_diarization.ipynb` - NeMo diarization (nvidia/Nemotron-3-Diarization), results in `outputs/diarization/`

If YouTube asks to sign in, set `cookies_from_browser` in the download notebook.
