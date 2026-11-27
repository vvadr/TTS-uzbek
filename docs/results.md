# Results of the runs

## Full run `runs/main48k`: 33 audios, 41.6 h of raw audio at 48 kHz
The 30 podcasts of the main dataset, downloaded again at 48 kHz, plus `OyQOvi9Qhxs` and the 2 test audios. Started 2026-11-27 16:36; results are added here when it finishes.

## Test run `runs/test`: 2 audios, 110.8 min of raw audio
- `neyrobiologiya_va_qaysi_kunlik` (43.1 min): a podcast monologue, 1 speaker, clean.
- `shaytanat_qism_milliy_serial` (67.7 min): a TV drama episode with 8+ actors, a music bed and sound effects.

### Diarization agreement (01, 2026-11-27)
Many-to-one agreement with Nemotron, the reference (1.0 = the same split of the speech):

| System | Podcast: speakers | Podcast: agreement | Series: speakers | Series: speech | Series: agreement |
|---|---|---|---|---|---|
| nemotron | 1 | — | 8 | 22.7 min | — |
| sortformer_v2 | 1 | 1.0 | 4 | 23.1 min | 0.57 |
| sortformer_v2_1 | 1 | 1.0 | 4 | 24.0 min | 0.42 |
| clustering (guided) | 1 | 1.0 | 8 | 22.7 min | 0.64 |
| consensus (DOVER-Lap) | 1 | 1.0 | 8 | 23.6 min | 0.69 |

- **Unguided clustering** heard the series as 1 speaker with 39.1 min of "speech", because its VAD took the music for speech.
- **The first consensus**, built with the unguided clustering and greedy label mapping, had 4 speakers.
- **On the 48 kHz audio** (version 3): the podcast is the same; on the series, Nemotron has 8 speakers in 21.3 min of speech, and the systems agree 0.47–0.80.
- **Reading:** the podcast's speaker is certain. The series' speaker labels are uncertain for about half of its speech, so 06 checks every chunk and lets the voice decide where the systems doubt.

### Version 1 (2026-11-26): Nemotron only, before the diarization check
110.8 min → **68.4 min** (62%) in `dataset_train/`: 517 chunks, 7 speakers. That `dataset_train` is kept in `~/projects/tts/backups/2026-11-27_before_diar_ensemble/dataset_train_v1/`.

| Stage | Removed | Left |
|---|---|---|
| raw audio | — | 110.8 min |
| 01–02: outside speech turns (music, effects, pauses > 3 s); 43 short interjections, 15 empty transcripts, 2 Whisper loops | 28.7 min | 82.1 min, 430 chunks |
| 03: 22 chunks where the denoiser removed more than it kept | 1.2 min | 80.9 min |
| 04: 4 without speech, 2 mostly not speech | 0.3 min | 80.6 min |
| 05: 2 chunks dropped, 1.3 min of fillers / bursts / coughs / laughs cut from 120 chunks | 1.7 min | 78.9 min, 400 chunks |
| 05 step 5: silence at the edges trimmed to 0.2 s, 15 pieces < 1 s | 5.8 min | 73.1 min, 596 chunks |
| 06: wrong speaker 25, text ≠ audio 38, speakers < 1 min 14, overlap 2 | 4.7 min | **68.4 min, 517 chunks** |

- **Per audio:** the podcast kept 42.1 of 43.1 min (98%); the series kept 26.4 of 67.7 min (39%).
- **Speech:** about 8 min was dropped for quality (≈ 10% of the speech); the rest of the loss is music and silence.

### Version 2 (2026-11-27): 4 diarization systems, check with relabeling, small speakers kept, text from ASR 8201
From the 24 kHz audio (now in `backups/2026-11-27_test_v2_24k/`): 110.8 min → **68.2 min** (62%), 503 chunks, 8 speakers, 493 train / 10 val. The run took 34 min (02 at 14:45 → 06 at 15:19). An earlier pass on the 8199 text, stopped in 05, is kept in `backups/2026-11-27_test_asr8199/`.

| Stage | Removed | Left |
|---|---|---|
| raw audio | — | 110.8 min |
| 01–02: outside speech turns (music, effects, pauses > 3 s); 44 short interjections, 13 empty transcripts, 3 Whisper loops | 28.7 min | 82.1 min, 430 chunks |
| 03: 22 chunks where the denoiser removed more than it kept | 1.3 min | 80.9 min, 408 chunks |
| 04: 7 chunks with too little speech | 0.4 min | 80.5 min, 401 chunks |
| 05: 2 chunks dropped (filler only, untranscribed speech); fillers, bursts, laughs and coughs cut | 1.8 min | 78.7 min, 399 chunks |
| 05 step 5: silence at the edges trimmed to 0.2 s, 14 pieces < 1 s | 5.8 min | 72.9 min, 589 chunks |
| 06: text ≠ audio 41 (1.5 min), uncertain speaker 34 (1.8 min), mixed speakers 9 (1.2 min), overlap 2 (0.3 min) | 4.7 min | **68.2 min, 503 chunks** |

**Per audio:** the podcast kept 42.1 of 43.1 min (98%); the series kept 26.1 of 67.7 min (39%).

**Speech vs silence:** the speech dropped for quality (03 to 06) is about 8 min. The rest of the loss is music, effects and silence: 28.7 min in 01–02 and 5.8 min in step 5.

**06 diarization check:**
- 589 chunks were checked against clustering, Sortformer v2 and v2.1.
- For 163 of them, most systems disagree with the speaker label. Those 163 ended up as:

  | Outcome | Chunks |
  |---|---|
  | kept: the voice confirms the label | 49 |
  | **relabeled** to the speaker whose voice they are closer to | 66 (4.6 min) |
  | dropped as `uncertain_speaker` | 34 |
  | dropped earlier for another reason | the rest |
- The relabels are decided by TitaNet alone and have not been checked by ear. Listen to `outputs/train/review/index.html`. With `RELABEL = False`, these chunks would be dropped instead.
- 9 chunks dropped as mixed speakers, 2 for overlap.

**Compared with v1:**
- The total is the same (68.2 vs 68.4 min).
- Small speakers are now kept: `002_speaker_0` has 0.4 min.
- Wrong-speaker chunks are now relabeled or dropped as uncertain, depending on how clear the voice is, instead of all being dropped.
- The text comes from ASR 8201; v1's came from 8199. The two differ on 2.4% of the words on the podcast and 8.9% on the series (see `docs/changes.md`).

**Speakers in `dataset_train/`:**

| Speaker | Min | Chunks | Labels |
|---|---|---|---|
| spk000 | 42.1 | 145 | 001_speaker_0 |
| spk001 | 5.2 | 86 | 002_speaker_2, 002_speaker_4 |
| spk002 | 7.4 | 88 | 002_speaker_1 |
| spk003 | 5.9 | 67 | 002_speaker_6 |
| spk004 | 2.3 | 45 | 002_speaker_3 |
| spk005 | 1.6 | 25 | 002_speaker_5 |
| spk006 | 3.3 | 40 | 002_speaker_7 |
| spk007 | 0.4 | 7 | 002_speaker_0 |

### Version 3 (2026-11-27): 48 kHz from input to output
The same two videos, downloaded again as YouTube's Opus at 48 kHz (content up to 20 kHz); 01–06 run again from scratch, with MossFormer2_SE_48K for music. 110.8 min → **66.0 min** (60%) in `dataset_train/`: 506 chunks, 9 speakers, 495 train / 11 val. **Every wav is 48 kHz**: all 506 were checked, and none was resampled. The run took 23 min (15:57 → 16:20); 03 took 3.6 min instead of 17.

| Stage | Removed | Left |
|---|---|---|
| raw audio (48 kHz) | — | 110.8 min |
| 01–02: outside speech turns (music, effects, pauses > 3 s); 34 short interjections, 15 empty transcripts | 30.2 min | 80.6 min, 436 chunks |
| 03: 19 chunks where the denoiser removed more than it kept | 0.9 min | 79.7 min, 417 chunks |
| 04: 5 chunks with too little speech | 0.4 min | 79.4 min, 412 chunks |
| 05: 2 chunks dropped; fillers, bursts, laughs and coughs cut | 1.6 min | 77.7 min, 410 chunks |
| 05 step 5: silence at the edges trimmed to 0.2 s, short pieces | 6.1 min | 71.7 min, 604 chunks |
| 06: uncertain speaker 55 (2.7 min), text ≠ audio 31 (1.1 min), mixed speakers 10 (1.6 min), overlap 2 (0.2 min) | 5.6 min | **66.0 min, 506 chunks** |

**Per audio:** the podcast kept 42.1 of 43.1 min (98%); the series kept 24.0 of 67.7 min (35%).

**High band:** the 12–20 kHz level relative to 1–4 kHz is a median of −19.7 dB on the podcast and −42.9 dB on the series, where denoising takes out the music bed. The 24 kHz version had nothing above 12 kHz.

**Compared with version 2 (24 kHz):** 2.2 min less.
- In 01–02, 1.5 min less: on the 48 kHz copy, Nemotron hears 21.3 min of speech in the series instead of 22.7.
- In 06, 0.9 min less: 55 uncertain speakers instead of 34.
- 69 chunks were relabeled (4.2 min), against 66.
- `002_speaker_4` stays its own speaker: the voices were not merged this time.
