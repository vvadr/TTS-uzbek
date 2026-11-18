# Podcast audio collection and diarization

Install the dependencies and use the project `.venv` as the notebook kernel:

```bash
uv sync
```

The project uses Python 3.12 or newer. Steps 1, 2 and 4 also need `ffmpeg` on your PATH.

## Notebooks (run in this order)

All notebooks are in `src/data_preprocessing/`. Every step reads and writes audio in `data/raw_audios/`, so the output of one step is the input of the next.

| Step | Notebook | What it does |
|---|---|---|
| 1a | `01a_download_audio_ytdlp.ipynb` | Download the audio of every link in `data/podcasts.md` as WAV. |
| 1b | `01b_download_audio_pytubefix.ipynb` | Alternative downloader. Use it only if 1a fails. |
| 2 | `02_video_to_audio.ipynb` | Optional: convert videos in `data/videos/` to WAV. |
| 3 | `03_voice_activity_silero.ipynb` | Listen to one file, plot it and mark where there is speech (Silero VAD). |
| 4 | `04_speaker_diarization_nemo.ipynb` | Find who spoke when (NVIDIA Nemotron-3-Diarization). |

To get audio, use step 1 (download), step 2 (local videos), or put WAV files into `data/raw_audios/` yourself. Steps 3 and 4 list the files in that folder; change the number in `wavs[0]` to pick one.

### Downloading (steps 1a and 1b)

Steps 1a and 1b skip links that were already downloaded, so you can run them again after failures. yt-dlp may use Node.js and fetch yt-dlp's EJS component from GitHub. If YouTube asks you to sign in, sign in to YouTube in your browser and set `cookies_from_browser` to `"chrome"`, `"firefox"` or `"safari"`. YouTube can still reject the request, and PytubeFix may be blocked as a bot.

### Speaker diarization (step 4)

The notebook makes a 16 kHz mono copy (the original is not changed) and runs one model, Nemotron-3-Diarization, which finds up to 8 speakers. The result is an RTTM file with anonymous speaker labels and timestamps, plus talk time per speaker and a timeline plot. It is not a transcript. Set `TEST_MINUTES` to try only the start of a long recording.

The model (about 190 MB) is downloaded from Hugging Face on first use into the shared Hugging Face cache, `~/.cache/huggingface/hub`. Results go to `outputs/diarization/<file name>/nemotron/`; running the same file again overwrites them. It runs on CPU and is fast: about a second for a one-minute clip on an M-series Mac. Check the labels by listening, because a few very short turns can show up as an extra speaker. If you upgrade NeMo, restart the notebook kernel before running it again.

Downloaded audio, videos and results are ignored by Git.
