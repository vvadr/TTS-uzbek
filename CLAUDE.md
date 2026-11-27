@AGENTS.md

## For Claude Code
- Read `AGENTS.md` (above) and the matching `docs/` page before changing a notebook. The notebooks in `pipeline/` are the ones that run; `src/data_preprocessing/` holds older copies with the main run's outputs.
- The Spark is `ssh intern@192.168.1.88`. Copy edited notebooks there with `scp`, after backing up the Spark's copy to `~/projects/tts/backups/<date>_<what>/`. Keep the Mac and Spark copies identical, and compare them with `md5sum` / `md5 -q`.
- Before overwriting a notebook on the Spark, check whether the user saved it from VS Code since it was copied (outputs, kernel). If so, back it up and patch that copy, not yours.
- Heavy runs go in tmux (`scripts/run_pipeline.sh`). Say what will run, on how much data, for how long and why, before starting it.
