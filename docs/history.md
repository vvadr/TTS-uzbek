# History: what was built, tried and decided

Newest first. Each entry says *why*, so the decision isn't reopened without a reason.

## 2026-11-27: 48 kHz from input to output
- **The user's request:** keep 48 kHz at all times, because features get lost by resampling, and report any input that is not 48 kHz.
- **Found:**
  - All input was below 48 kHz: the test run's 2 audios and 32 of the main dataset's at 24 kHz, 3 at 44.1 kHz.
  - The `stt_data_collection` downloader fetches YouTube's Opus at 48 kHz but converts it to 24 kHz on purpose, for its own corpus, and deletes the original.
  - Inside the pipeline:
    - 02 upsampled to 48 kHz;
    - 03 sent music chunks 48 → 16 → 48 kHz through MossFormerGAN;
    - 06 downsampled to 24 kHz.
- **Changed:**
  - `pipeline_paths.SAMPLE_RATE = 48000` and `check_sample_rate` (01 and 02 stop on another rate).
  - 00 keeps the video's rate and makes the audio mono.
  - 02 and 06 never resample.
  - 03 uses **MossFormer2_SE_48K** (ClearerVoice) for music instead of MossFormerGAN_SE_16K:
    - it works at 48 kHz itself;
    - it is about 6 times faster on the Spark's GPU;
    - it removed about as much as DeepFilterNet3 on 6 music chunks.
  - `scripts/download_48k.py` downloads format 251 and decodes it to 48 kHz mono, with no resampling.
- **Result:**
  - The test run's audios were downloaded again: 48 kHz, with content up to 20 kHz (the 24 kHz files stopped at 12 kHz).
  - The whole test run was redone from 01. The 24 kHz run is in `backups/2026-11-27_test_v2_24k/`.
- **Not used:** MossFormer2_SR_48K (super-resolution). It would invent the 12–24 kHz band of 24 kHz files instead of recovering it.

## 2026-11-27: several diarization systems, consensus chunking, fix instead of drop
- **01** runs four diarization systems:
  - Nemotron-3-Diarization;
  - streaming Sortformer 4spk v2;
  - streaming Sortformer 4spk v2.1;
  - NeMo's clustering diarizer (MarbleNet VAD + TitaNet + spectral clustering).

  **DOVER-Lap** combines them into a `consensus`. pyannote was not available: its models need a Hugging Face login.
- **Reference:** the plan was to cut by the consensus. On the test series (a drama, 8+ actors, music) that failed:
  - the 4-speaker models merged actors;
  - the unguided clustering called everything one speaker, because its VAD took the music for speech (39 min instead of 23);
  - the consensus came out with 4 speakers.

  So **02 keeps cutting by Nemotron** (`DIARIZATION = "nemotron"`), the only system built for 8 speakers.
- **Clustering is guided:** it takes Nemotron's speech regions and speaker count, and TitaNet clustering decides who is who.
- **Agreement:** measured many-to-one, so merging isn't punished. 1.0 on the podcast, 0.42–0.84 on the series, so the series' speaker labels are genuinely uncertain.
- **06** checks every final chunk against the other three systems:
  - **Mixed speakers:** a majority hears another speaker alone inside the chunk, and it is dropped.
  - **Doubted label:** a majority doubts the label. Then the voice decides: TitaNet on the *denoised* chunk, against speaker voices averaged over confirmed chunks only. The chunk is kept, relabeled, or dropped only when the voice is too close to call.
  - **Small speakers** are kept (`MIN_SPEAKER_MIN = 0`).
- Why: the user found the dataset shrank too aggressively (test run: 110.8 → 68.4 min). Most of that was music and silence, but about 8 min of speech was dropped, and part of it could be fixed instead.
- `scripts/run_pipeline.sh` runs 01–06 headless, each notebook with its kernel; `run_notebook.py --save` writes the printed output into the notebooks.

## 2026-11-26: the `pipeline/` folder, 05 step 5, 06
- **Folder:** the notebooks to run were copied into `pipeline/`, numbered 00–06 in run order. `src/data_preprocessing/` keeps the older copies with the main run's outputs.
- **Paths and repeats:**
  - `pipeline_paths.py` (`RUN`, `AUDIOS`) keeps test runs apart from the main dataset. Before it, running 08 on new audio would have deleted the main `dataset_clean` (same chunk names).
  - Repeated work removed:
    - 02 reuses the step-2 text of short turns instead of sending them to the ASR server again (179 chunks; 178 came back identical);
    - 05 no longer runs Silero, which it never used;
    - dropped chunks are hard links, not copies.
- **`.venv-nemo`:** Python 3.12 for NeMo (01, later 06). NeMo needs ≥ 3.12, and `.venv-denoise` must stay on numpy < 2.
- **05 step 5, sentence chunks:** 02 cut turns longer than 29.5 s at a pause, often mid-sentence, and about 30% of chunks ended mid-sentence. Step 5 joins a speaker's consecutive chunks and cuts only at sentence ends with a pause ≥ 0.5 s. Long speech without such a pause keeps its old cuts. On the test run, chunks ending a sentence went from 70% to 90%.
- **06 finalize:**
  - numbers and symbols written as Uzbek words, with MMS picking the reading the audio matches;
  - the text–audio match (`align_prob`);
  - TitaNet speaker merge and check;
  - −23 LUFS, 24 kHz, and `train.txt` / `val.txt`.
- **Vocal Burst Locator v2** (LAION) was added to 05 to find laughs, coughs, sneezes and sighs, including quiet ones; AST names them. Breaths are kept.
- **GigaAM** (v3 and Multilingual) was tried as an ASR that keeps fillers. It dropped most of them, wrote "mhm" in Cyrillic, and v3 is Russian-only. It was rejected and deleted.
- **Kaggle** was considered: its limits (T4/P100, ~30 GPU h a week, 20 GB output) fit 05, but moving 12 GB each way costs more than it saves. Not used.

## 2026-11-26: 09 non-speech, fillers
- **09** (now 04) scores chunks with Silero VAD and moves out those with < 0.3 s speech, or speech on < 20% of the chunk.
- **Fillers** ("hm", "a-a", "ee", "mhm"), written or not, should not be learned by the TTS:
  - `scripts/flag_fillers.py` listed the written ones (67 filler-only, 530 with fillers);
  - 10 (now 05) does it properly: MMS forced alignment, then each unwritten sound between words is typed by what MMS hears in it, pitch steadiness (pYIN), AST and the burst locator;
  - fillers are cut from audio *and* text, and filler-only chunks are dropped.

## 2026-11-25: denoising (08, now 03)
- Measured per chunk: AST "Music" probability, and the steady background in the pauses (DeepFilterNet3 finds the pauses). DNSMOS was rejected by the user (download).
- Before/after samples of DeepFilterNet3 and MossFormerGAN. The user chose **MossFormerGAN for music** (below 7 kHz, DFN3 above) and **DeepFilterNet3 for noisy** chunks.
- Main dataset: 9,736 chunks, 38.4 h. 8,040 kept their original audio, 1,290 went through DFN3 and 406 through MossFormerGAN. It ran on the Spark (~2.6 h), and `dataset/` there was deleted afterwards.
- Lessons:
  - MossFormerGAN's `torch.angle` fails on MPS, so its forward pass was rewritten without complex numbers;
  - the MPS cache grows unless emptied after each chunk;
  - DFN3 removes a lone "hm", so chunks where a model removed more than it kept are left out.

## 2026-11-20 to 24: chunking and transcription
- **Diarization:** NeMo Nemotron-3-Diarization (streaming Sortformer).
- **First chunking** (`05_chunks` + `06_dataset`) cut by diarization plus old word alignments. It was replaced by `07_chunk_transcribe_dataset` (now 02), which:
  - transcribes every chunk on its own, so its text is exactly what is in its wav;
  - merges a speaker's turn across short interruptions;
  - drops Whisper loops and empty transcripts.
- **Mel-Band RoFormer** vocal separation + dereverb (`chunk_clean.ipynb`) was tried and **dropped**: 32 of 36 suspicious chunks came out practically unchanged, at ~1.7 h of compute. Don't propose source separation again without a new reason.

## Still open
- The main dataset hasn't been through 05 (finished) and 06. Its 02 outputs (`outputs/chunks/`) and RTTMs are on the Mac, and 06's diarization check needs them on the Spark. Its diarization would also need the new systems (01) for the consensus check.
- **Transcription errors** beyond what `align_prob` catches. Option: a second ASR to compare against.
- **pyannote** as a fifth diarization system, if a Hugging Face login is added.
