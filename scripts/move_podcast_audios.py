"""Move podcast audio folders into data/raw_audios using podcast titles."""

import argparse
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "podcasts"
DESTINATION = ROOT / "data" / "raw_audios"
PODCAST_LIST = ROOT / "data" / "podcasts.md"
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".webm"}


def podcast_titles(path: Path) -> dict[str, str]:
    """Read YouTube ID -> title from podcasts.md."""
    titles = {}
    title = None
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"\s*\d+\.\s+\*\*(.+?)\*\*", line)
        if heading:
            title = heading.group(1)
        video = re.search(r"youtu\.be/([A-Za-z0-9_-]{11})", line)
        if title and video:
            titles[video.group(1)] = title
            title = None
    return titles


def safe_name(name: str) -> str:
    name = re.sub(r"[/\\|]", " - ", name)
    name = re.sub(r'[<>:"?*\x00-\x1f]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" .-")
    return name[:180].rstrip(" .-")


def target_name(audio: Path, source: Path, titles: dict[str, str]) -> str:
    parts = audio.relative_to(source).parts
    folder_or_stem = parts[0] if len(parts) > 1 else audio.stem
    video_id = next(
        (video_id for video_id in titles if folder_or_stem == video_id or folder_or_stem.endswith("_" + video_id)),
        None,
    )
    return safe_name(titles.get(video_id, folder_or_stem))


def move_podcasts(source: Path, destination: Path, titles: dict[str, str], dry_run: bool = False) -> tuple[int, int]:
    if not source.is_dir():
        raise FileNotFoundError(f"Podcast folder not found: {source}")

    audios = sorted(
        path for path in source.rglob("*")
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    if not audios:
        print(f"No audio files found in {source}")
        return 0, 0

    plans = []
    skipped = 0
    for audio in audios:
        if audio.parent == source and audio.stem == "audio":
            print(f"Skipped, no podcast name for: {audio}")
            skipped += 1
            continue
        name = target_name(audio, source, titles)
        if not name:
            print(f"Skipped invalid name: {audio}")
            skipped += 1
            continue
        plans.append((audio, destination / f"{name}.wav"))

    targets = [target for _, target in plans]
    if len(targets) != len(set(targets)):
        raise ValueError("Multiple source files would get the same destination name")

    moved = 0
    for audio, target in plans:
        if target.exists():
            print(f"Skipped, destination exists: {target.name}")
            skipped += 1
            continue
        if dry_run:
            print(f"Would move: {audio.relative_to(source)} -> {target.name}")
            moved += 1
            continue

        destination.mkdir(parents=True, exist_ok=True)
        if audio.suffix.lower() == ".wav":
            shutil.move(str(audio), str(target))
        else:
            with tempfile.TemporaryDirectory(dir=destination) as temp_dir:
                converted = Path(temp_dir) / "audio.wav"
                subprocess.run(
                    ["ffmpeg", "-loglevel", "error", "-i", str(audio), "-vn", "-c:a", "pcm_s16le", str(converted)],
                    check=True,
                )
                if converted.stat().st_size <= 44:
                    raise ValueError(f"Converted audio is empty: {audio}")
                converted.replace(target)
            audio.unlink()

        print(f"Moved: {audio.relative_to(source)} -> {target.name}")
        moved += 1

    return moved, skipped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show filenames without moving audio")
    args = parser.parse_args()
    moved, skipped = move_podcasts(SOURCE, DESTINATION, podcast_titles(PODCAST_LIST), dry_run=args.dry_run)
    print(f"Done: {moved} {'planned' if args.dry_run else 'moved'}, {skipped} skipped")
