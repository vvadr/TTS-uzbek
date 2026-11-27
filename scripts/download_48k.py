"""Download YouTube audio at 48 kHz for this project: the original Opus stream (format 251, 48 kHz), decoded to a
48 kHz mono 16-bit wav without resampling.

The stt_data_collection downloader writes 24 kHz on purpose (its own speech-recognition corpus is 24 kHz), so its wavs
cannot be used here: this pipeline keeps 48 kHz from input to output, and 01/02 stop on any other rate. This script
reuses that project's yt-dlp settings (PO token server, cookies, JS runtime) and its file names (<title slug>_<id>).

Run it on the Mac, from the stt_data_collection folder, with its venv; Docker must be running (`make pot-up`):

    cd ~/Documents/IT/projects/stt_data_collection && make pot-up
    .venv/bin/python ~/Documents/IT/projects/tts/scripts/download_48k.py [--opus-only] <out_dir> <url or video id> ...

Then copy the wavs to the Spark: rsync -av <out_dir>/*.wav intern@192.168.1.88:projects/tts/data/raw_audios/

--opus-only keeps the downloaded stream (<name>.webm, about 1 MB per minute) and writes no wav: copy it to the Spark's
data/source_opus/ and decode it there, so the originals are kept and only ~1/10 of the bytes cross the network:
    ffmpeg -i data/source_opus/<name>.webm -ac 1 -c:a pcm_s16le data/raw_audios/<name>.wav
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))   # the stt_data_collection folder
import soundfile as sf
import yt_dlp
from stt_pipeline.common.config import load_config
from stt_pipeline.download import build_ydl_opts, extract_video_id, get_folder_name_from_title

args = sys.argv[1:]
opus_only = "--opus-only" in args
args = [a for a in args if a != "--opus-only"]
out = Path(args[0]).expanduser()
out.mkdir(parents=True, exist_ok=True)
opts = build_ydl_opts(str(out / "%(id)s.%(ext)s"), str(out / "archive.txt"), load_config("config.yaml"))
for key in ("postprocessors", "postprocessor_args", "download_archive"):
    opts.pop(key, None)                    # no conversion to 24 kHz, no shared archive
opts["format"] = "251"                     # Opus at 48 kHz
opts["cookiefile"] = str(Path(".venv/youtube_cookies.txt").resolve())

failed = []
for arg in args[1:]:
    vid = extract_video_id(arg) or arg
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True)
        assert info.get("asr") == 48000, f"{info.get('asr')} Hz"
    except Exception as e:                 # one bad video must not stop the others
        failed.append(vid)
        print(f"FAILED {vid}: {type(e).__name__}: {e}", flush=True)
        continue
    src = out / f"{vid}.{info['ext']}"
    name = get_folder_name_from_title(info["title"], vid)
    if opus_only:
        src.rename(out / f"{name}.{info['ext']}")
        print(json.dumps({"file": f"{name}.{info['ext']}", "sample_rate": info.get("asr"), "codec": info.get("acodec"),
                          "kbps": info.get("abr"), "minutes": round(info.get("duration", 0) / 60, 1)}, ensure_ascii=False))
        continue
    wav = out / f"{name}.wav"
    # Opus decodes at 48 kHz itself; -ac 1 only mixes the channels to mono, there is no -ar
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-c:a", "pcm_s16le", str(wav)], check=True)
    sr = sf.info(str(wav)).samplerate
    assert sr == 48000, (wav, sr)
    src.unlink()
    print(json.dumps({"wav": wav.name, "sample_rate": sr, "format": info.get("format_id"), "codec": info.get("acodec"),
                      "kbps": info.get("abr"), "minutes": round(info.get("duration", 0) / 60, 1)}, ensure_ascii=False))
print(f"done: {len(args) - 1 - len(failed)} downloaded, {len(failed)} failed" + (f": {' '.join(failed)}" if failed else ""))
