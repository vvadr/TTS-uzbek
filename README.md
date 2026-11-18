# Podcast audio collection

The links are in `data/podcasts.md`. Install the project dependencies with
`uv sync`. Both downloaders also need `ffmpeg` on your PATH to make WAV files.

## Notebook (yt-dlp)

Open `src/data_collection/data_collection.ipynb`, select the project `.venv`
as the Python kernel, and run the cells in order. The downloader uses Node.js
when it is available and may fetch yt-dlp's EJS component from GitHub.

If YouTube asks you to sign in, sign in to YouTube in your browser and set
`cookies_from_browser = "chrome"` (or `"firefox"`) in the last cell. Then
run the cells in order again. The browser may ask you to allow access to its
stored cookies. YouTube may still reject the request.

## PytubeFix alternative

Open `src/data_collection/pytubefix.ipynb`, select the project `.venv` kernel,
and run its cells in order. WAV files are saved in `audio_pytubefix/`. Failed
links are reported and the notebook continues to the next link. YouTube can
also block this library with a bot check.
