#!/usr/bin/env bash
# Wait until an ASR server transcribes again. Every INTERVAL seconds (default 300) it sends one short wav to each
# server in APIS and returns as soon as a job completes on one of them; prints a line per failed round. For example,
# inside tmux:
#
#   scripts/wait_for_asr.sh runs/test/outputs/chunks/<audio>/short/0003_speaker_0.wav && scripts/run_pipeline.sh 02 03 04 05 06
set -u
APIS=${APIS:-"http://192.168.1.71:8201 http://192.168.1.71:8199"}   # the same servers as API in 02
wav=$1
every=${2:-300}
json() { python3 -c "import sys, json; d = json.load(sys.stdin); print($1)" 2>/dev/null; }
works() {  # $1 = server; 0 if it transcribes the wav
  local id st
  id=$(curl -s -m 60 -F language=uz -F word_probs=false -F min_probability=0.0 -F "file=@$wav;filename=audio.wav" \
       "$1/jobs" | json 'd.get("job_id") or d.get("id") or ""')
  [ -n "$id" ] || { why="$1: no answer"; return 1; }
  for _ in $(seq 1 40); do
    sleep 3
    st=$(curl -s -m 10 "$1/jobs/$id" | json 'd.get("status", "")')
    case "$st" in
      completed|done|complete|succeeded|success|finished) return 0 ;;
      failed|error|errored|cancelled|canceled) break ;;
    esac
  done
  why="$1: ${st:-no answer}"
  return 1
}
while true; do
  whys=""
  for api in $APIS; do
    if works "$api"; then echo "[$(date '+%F %T')] the ASR server $api works"; exit 0; fi
    whys="$whys; $why"
  done
  echo "[$(date '+%F %T')] the ASR servers still fail (${whys#; }); next try in ${every} s"
  sleep "$every"
done
