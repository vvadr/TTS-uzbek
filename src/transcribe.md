# Transcription: what the code does and how inference works

This covers three things:

1. how `src/transcribe.ipynb` sends audio to the API and collects transcripts
2. what happens on the API server when it transcribes a file
3. how to run inference yourself from model files (`.safetensors`, `.pt`/`.pth`, Lightning `.ckpt`, `.pkl`, `.nemo`, CTranslate2)

---

## 1. The setup: two machines

```
 your machine (this repo)                          192.168.1.71 (API server, CUDA GPU)
 ┌──────────────────────────────┐   HTTP upload   ┌────────────────────────────────────┐
 │ src/transcribe.ipynb         │ ──────────────▶ │ FastAPI "Faster Whisper API"       │
 │ data/raw_audios/*.wav        │    POST /jobs   │  ├─ job queue                      │
 │                              │                 │  ├─ 4 workers (decode in parallel) │
 │ data/transcripts/*.json/.txt │ ◀────────────── │  └─ fine-tuned Whisper model,      │
 └──────────────────────────────┘  GET /jobs/{id} │     CTranslate2 format             │
                                     (polling)    │     (/models/ft_model)             │
                                                  └────────────────────────────────────┘
```

The model does **not** run on your machine. The notebook only uploads files and waits for results. All of the inference runs on 71. When 71 is busy with other people's jobs, your jobs wait in its queue. This is why a 69-second file can take minutes: the time is spent waiting in the queue, not decoding.

---

## 2. The notebook, cell by cell

### Cell 1: configuration

| Setting | Meaning |
|---|---|
| `API` | Base URL of the server (`http://192.168.1.71:8199`). |
| `ROOT` | The project root. The notebook walks up from its working folder until it finds `pyproject.toml`, so paths work wherever the kernel starts. |
| `INPUT_DIR` | `data/raw_audios/`: every `.wav/.mp3/.flac/...` file in it gets transcribed. |
| `OUTPUT_DIR` | `data/transcripts/`: results go here. |
| `LANGUAGE` | `"auto"`, `"uz"`, `"kk"` (Karakalpak) or `"ru"`. With `auto`, the server picks one of the three per file. |
| `WORD_PROBS` | If `True`, the response also has per-word `{word, start, end, probability}`. |
| `MIN_PROBABILITY` | The server drops words whose confidence is below this. `0.0` keeps everything. |
| `WORKERS` | How many files the notebook keeps in flight at once (6). The server decodes 4 at a time; the extra 2 stay in its queue, so a worker never sits idle. |
| `POLL_SECONDS` | How often the notebook asks "is my job done?" (5 s). |
| `JOB_TIMEOUT` | How long to wait for one job before giving up (6 h, including queue time). |
| `LOG_EVERY` | Prints a progress line every 30 s while a job waits. |

### Cell 2: talking to the API

- **`http_json(url, data, headers)`**: one HTTP request. Returns `(status_code, parsed_json)`. HTTP errors are returned, not raised, so the caller decides what to do with them.
- **`multipart_stream(fields, "file", path)`**: builds the `multipart/form-data` upload body, the same format a browser uses for file uploads. It does two things worth noting:
  - **It streams.** The raw audios are up to ~475 MB. Instead of `path.read_bytes()`, which loads the whole file into RAM, it yields the file in 1 MB blocks. It also computes `Content-Length` in advance, so the server knows how much to expect.
  - **It renames the upload to `audio.wav`.** Podcast titles contain `'`, `‘`, `#`, `%` and other non-ASCII characters, which can break the HTTP header. The server only needs the extension, and the real name is kept in our own output.
- **`retry(fn, attempts, what)`**: calls `fn` again on network errors, timeouts and server 5xx errors, waiting 2 s, 4 s, 8 s and so on (30 s at most). It does not retry 4xx errors such as `422 Validation Error`, because sending the same bad request again won't help.
- **`submit(path)`**: `POST /jobs` with the file plus `language`, `word_probs` and `min_probability`. The server answers right away with something like `{"job_id": "ca41f2e1-…", "status": "queued"}`. Each retry builds a new stream, because a generator can only be read once.
- **`wait(job_id)`**: polls `GET /jobs/{job_id}` every `POLL_SECONDS`:
  - `queued` / `running` / …: keep waiting, and print status, server `queue_size` and elapsed time every 30 s.
  - `completed` / `done` / …: return the response.
  - `failed` / `error`: raise, so the file is reported as failed.
  - `404`: the job is gone (the server restarted or forgot it), so raise.
- **`extract_text(response)`**: joins the `text` of every segment into one plain-text transcript.
  The server's finished response is flat:
  `job_id, status, error, language, language_probability, duration, segments, words, finished_at`.
  The notebook saves all of it. [Cleaning the transcripts](#cleaning-the-transcripts) covers stripping it down.

### Cell 3: running the batch

- **`audio_files()`**: sorted list of audio files in `INPUT_DIR`.
- **`process(path)`**: one file, start to finish: `submit` → `wait` → `extract_text` → write outputs:
  - `data/transcripts/<name>.json`: `{"audio", "job_id", "text", "response"}`, where `response` is the full server answer
  - `data/transcripts/<name>.txt`: just the text
  - The `.json` is written to `<name>.json.tmp` first and then renamed. A rename is atomic, so a crash mid-write never leaves a half-written `.json` that would look finished.
- **`run(limit=0, only=None)`**:
  1. checks `/health`: the server must report `"status": "ready"`
  2. skips every file that already has a `.json`. **This is what makes it resumable**: interrupt it, re-run it, and it continues where it left off.
  3. runs `process` for up to `WORKERS` files in parallel with a `ThreadPoolExecutor`. Threads are fine here because the work is waiting on the network, not CPU.
  4. prints `ok` / `FAIL` per file and a list of failures at the end. Failed files have no `.json`, so the next `run()` retries them.

### Cells 4–6: smoke test, inspection, full run

- `run(only="abuser")` transcribes only the small `abuser.wav` (12 MB, 69 s) as a quick end-to-end check.
- The next cell prints its text and the raw server response.
- `run()` does all the files.

### Cleaning the transcripts

The notebook keeps the full server response. A separate script, `scripts/edit_transcriptions.py`, strips each JSON down to what matters:

```bash
python scripts/edit_transcriptions.py              # rewrites data/transcripts/*.json in place
```

```json
{
    "audio": "28-son - GTA VI, Fransiyadagi noroziliklar, ... tahlili.wav",
    "language": "uz",
    "language_probability": 1.0,
    "duration": 2367.55,
    "text": "Ay, qo'rqinchli zamonlar kelmoqda, bilmadim. Mashinalar uchmoqda. ..."
}
```

| Field | Meaning |
|---|---|
| `audio` | source file name in `data/raw_audios/` |
| `language` | language the whole file was decoded in (`uz` / `kk` / `ru`) |
| `language_probability` | how sure the model was of that language (0–1, rounded to 3 decimals) |
| `duration` | audio length in seconds |
| `text` | the full transcript, with whitespace normalized |

Dropped: `job_id`, `status`, `error`, `finished_at` (a server clock value with no meaning outside the server), `segments`/`formatted_segments` and `words`, so every start/end timestamp is gone. This step can't be undone: to get timings back you'd have to transcribe again. Files that are already clean are skipped, so running it twice is safe.

**Caveat:** if you interrupt a cell, the job already submitted keeps running on the server, because the API has no cancel endpoint. Re-running the cell submits it again. Each re-run of the smoke test therefore adds one more job to 71's queue.

---

## 3. What the server does with your audio

This section is based on the API's own documentation (its `/docs` page). I haven't seen the server's code.

1. **Decode and resample.** Your WAVs are 44.1 kHz stereo. Whisper models expect **16 kHz mono**, so the server converts them; faster-whisper does this with PyAV/ffmpeg.
2. **Split into 30-second windows that overlap by 5 s.** Whisper can only "see" 30 s of audio at a time, so long files are cut into windows:

   ```
   window 1: 0s ─────────── 30s
   window 2:          25s ─────────── 55s
   window 3:                   50s ─────────── 80s
                       └5s┘     └5s┘   overlaps
   ```

   The overlap prevents losing words that fall on a cut. Words in an overlap are transcribed twice. The server uses **word timestamps** to keep one copy, which is why it always computes word timings, even when `word_probs=false`.
3. **No VAD per window.** VAD is voice-activity detection, which normally skips windows judged to be "not speech". The server deliberately turns it off, because VAD tends to drop speech that has background music under it. The trade-off is that near-silence can produce made-up ("hallucinated") words. `min_probability` exists to filter those low-confidence words back out.
4. **Language.** With `language=auto`, the model looks at the first few windows, picks `uz`, `kk` or `ru`, and then decodes the whole file in that language. The model was trained only on those three, so it never returns another language.
5. **Decode.** For each window, the model converts audio to a log-mel spectrogram and runs the encoder on it. The decoder then generates text tokens one by one. The model is a Whisper fine-tune converted from Hugging Face format to **CTranslate2**, a fast C++ inference engine, and **faster-whisper** is the Python library that drives it.
6. **Queue.** `/jobs` puts work in a queue. Exactly 4 jobs decode at once (`num_workers: 4` in `/health`), and `queue_size` is how many jobs are waiting.

---

## 4. Running inference yourself from model files

Calling the API is the easy path. You can also load a model and run it yourself on any machine with a suitable GPU.

### The general rule

A weights file contains only numbers. To run inference you need four things:

1. **The architecture.** This is the Python class or config that says how the numbers are wired together. Without it, a `state_dict` is just a dictionary of tensors.
2. **The weights**, from the file.
3. **The same preprocessing as in training.** For Whisper that means 16 kHz mono audio, a log-mel spectrogram and the tokenizer. For other models it could be normalization, image resizing, and so on.
4. **The same postprocessing**, for example decoding token ids back into text.

The core pattern for any PyTorch model:

```python
import torch

model = build_model(...)            # 1. architecture
model.load_state_dict(weights)      # 2. weights
model.eval()                        #    turns off dropout, freezes batchnorm stats (forgetting this gives wrong results)
model.to("cuda")

with torch.inference_mode():        #    no gradients: faster, less memory
    x = preprocess(raw_input).to("cuda")   # 3.
    y = model(x)
result = postprocess(y)             # 4.
```

### `.safetensors`: plain tensors (safe)

This is the modern format, used by Hugging Face. It contains only tensors and no code, so loading an untrusted file can't execute anything.

**A Hugging Face model folder** (`config.json` + `model.safetensors` + tokenizer files) is what our Whisper fine-tune was before it was converted:

```python
from transformers import pipeline

asr = pipeline(
    "automatic-speech-recognition",
    model="path/to/whisper-finetuned",   # folder with config.json, model.safetensors, tokenizer, preprocessor_config.json
    device=0,                            # GPU 0; use -1 for CPU
    chunk_length_s=30,                   # same idea as the server: 30 s windows…
    stride_length_s=5,                   # …with overlap
)
out = asr("data/raw_audios/abuser.wav",  # pipeline resamples to 16 kHz for you
          return_timestamps=True,
          generate_kwargs={"language": "uz", "task": "transcribe"})
print(out["text"])
```

**A bare `.safetensors` file**, where you have the model class yourself:

```python
from safetensors.torch import load_file
state_dict = load_file("model.safetensors", device="cpu")
model = MyModel(**config)
model.load_state_dict(state_dict)
model.eval()
```

How the fine-tune represents Karakalpak is unknown, because Whisper has no `kk` = Karakalpak language token by default. Check the model's `generation_config.json` or ask whoever trained it before passing `language="kk"`.

### `.pt` / `.pth`: PyTorch files

The extension tells you nothing about what's inside. Load it and look:

```python
import torch
obj = torch.load("model.pt", map_location="cpu", weights_only=True)
print(type(obj)); print(list(obj)[:10] if isinstance(obj, dict) else obj)
```

| What you see | What it is | How to use it |
|---|---|---|
| dict of `name → tensor` (`"encoder.layers.0.weight"`, …) | a **state_dict** (most common) | `model = MyModel(...); model.load_state_dict(obj)` |
| dict with keys like `"model"`/`"state_dict"`, `"optimizer"`, `"epoch"` | a **training checkpoint** | `model.load_state_dict(obj["model"])` (or `obj["state_dict"]`) |
| error with `weights_only=True`, works with `False` | a **whole pickled model object** | `torch.load(path, weights_only=False)`. The model's class must be importable. **Only for files you trust**: pickle can run arbitrary code. |
| `RuntimeError` mentioning TorchScript / archive | a **TorchScript** export | `model = torch.jit.load("model.pt")`. No class needed. |

Common errors:

- `Missing key(s)` / `Unexpected key(s)` with a `module.` prefix: the model was trained with `DataParallel`/DDP. Strip the prefix with `{k.removeprefix("module."): v for k, v in sd.items()}`.
- `size mismatch for ...`: your `MyModel(...)` config differs from the one used in training (hidden size, vocab size, number of layers).
- Wrong outputs with no error: you forgot `model.eval()`, or preprocessing differs from training.

### `.ckpt`: PyTorch Lightning

A Lightning checkpoint is a `torch.save`d dict with `"state_dict"`, `"hyper_parameters"`, `"epoch"`, optimizer state and so on.

```python
from my_project.lit_module import MyLitModule     # the LightningModule class used in training

model = MyLitModule.load_from_checkpoint("epoch=9.ckpt", map_location="cpu")   # rebuilds from saved hyper_parameters
model.eval()
with torch.inference_mode():
    y = model(x)
```

If you only have the plain `nn.Module` (not the Lightning wrapper), load the weights by hand. Lightning prefixes parameter names with the attribute name, for example `model.`:

```python
ckpt = torch.load("epoch=9.ckpt", map_location="cpu", weights_only=False)
sd = {k.removeprefix("model."): v for k, v in ckpt["state_dict"].items()}
net = MyNet(**ckpt["hyper_parameters"]); net.load_state_dict(sd); net.eval()
```

### `.pkl` / `.joblib`: pickled Python objects (scikit-learn, etc.)

```python
import joblib                      # or: import pickle; pickle.load(open(path, "rb"))
clf = joblib.load("model.pkl")
pred = clf.predict(X)              # X must be preprocessed exactly as in training
```

Two caveats:

- Loading a pickle **runs code from the file**, so only load files you trust.
- The library versions (scikit-learn, numpy) should match the ones used for training. Otherwise loading may fail or warn.

### `.nemo`: NVIDIA NeMo (used by this repo for diarization)

```python
import nemo.collections.asr as nemo_asr
model = nemo_asr.models.ASRModel.restore_from("model.nemo")   # or .from_pretrained("nvidia/...")
model.eval().to("cuda")
out = model.transcribe(["data/raw_audios/abuser.wav"])          # newer NeMo returns Hypothesis objects: out[0].text
```

A `.nemo` file is a tar archive that bundles the config, weights and tokenizer, so no separate architecture code is needed.

### CTranslate2 + faster-whisper: what the server runs

To run the same kind of inference as 71, but locally:

```bash
# 1) convert a Hugging Face Whisper folder (safetensors) to CTranslate2
pip install ctranslate2 faster-whisper transformers
ct2-transformers-converter --model path/to/whisper-finetuned --output_dir whisper-ct2 \
    --copy_files tokenizer.json preprocessor_config.json --quantization float16
```

```python
# 2) run it
from faster_whisper import WhisperModel

model = WhisperModel("whisper-ct2", device="cuda", compute_type="float16")
segments, info = model.transcribe(
    "data/raw_audios/abuser.wav",   # any format/sample rate; resampled to 16 kHz mono internally
    language="uz",                  # or None to auto-detect
    beam_size=5,
    word_timestamps=True,
    vad_filter=False,               # the server keeps VAD off to not lose speech over music
)
print(info.language, info.language_probability)
for s in segments:                  # generator: decoding happens as you iterate
    print(f"[{s.start:7.2f} → {s.end:7.2f}] {s.text}")
```

### API or local model?

| | API on 71 (current notebook) | Load the model yourself |
|---|---|---|
| Setup | none | need the model files and a GPU with enough memory |
| Speed | depends on 71's queue (shared with others) | depends on your GPU only |
| Control | the parameters the API exposes | every decoding option |
| Model | the server's fine-tune (`/models/ft_model`) | whatever files you have. The fine-tune lives on 71, so you would need a copy of it. |
