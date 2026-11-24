"""Strip the transcription JSONs in data/transcripts/ down to the important fields.

Keeps:  audio, language, language_probability, duration, text
Drops:  job_id, status, error, finished_at, segments / formatted_segments, words
        (i.e. every start/end timestamp)

Rewrites the files in place. Files already in the clean format are left as they are.

    python scripts/edit_transcriptions.py                 # data/transcripts/
    python scripts/edit_transcriptions.py path/to/dir     # another folder
"""
import json
import os
import sys
from pathlib import Path

transcripts_dir = (Path(sys.argv[1]) if len(sys.argv) > 1
                   else Path(__file__).resolve().parent.parent / "data" / "transcripts")


def rounded(x, ndigits):
    return round(x, ndigits) if isinstance(x, (int, float)) else x


cleaned_count = skipped = 0
for json_path in sorted(transcripts_dir.glob("*.json")):
    with json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    response = data.get("response")
    if not isinstance(response, dict):
        skipped += 1  # already clean
        continue

    cleaned = {
        "audio": data.get("audio"),
        "language": response.get("language"),
        "language_probability": rounded(response.get("language_probability"), 3),
        "duration": rounded(response.get("duration"), 2),
        "text": " ".join(data.get("text", "").split()),
    }

    # write to a temp file first so an interrupted run can't leave a half-written JSON
    tmp_path = json_path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=4)
    os.replace(tmp_path, json_path)
    cleaned_count += 1

print(f"{transcripts_dir}: cleaned {cleaned_count}, already clean {skipped}")
