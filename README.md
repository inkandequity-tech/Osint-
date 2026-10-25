---
title: Video Finder
emoji: 🎞️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Osint-: Video Finder

A small web app for finding videos across the open web from an image and a short description.

Upload a reference image, type the scene or action you need, and get a ranked grid of matching videos.

## Features

- Image upload and a text box for the scene you need
- Unfiltered web video search (DuckDuckGo with safe-search off)
- Local re-ranking with CLIP: thumbnails are compared to your image, titles to your text
- Image-only mode: CLIP picks keywords that fit the image and searches those
- Text-only mode: results ranked by title match
- No API keys, no paid services, everything except the web search runs on your machine

## Quick start

Requires Python 3.9+.

```bash
git clone https://github.com/inkandequity-tech/Osint-.git
cd Osint-
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

The first search downloads the CLIP model (about 600 MB, once). After that it is cached.

## Host it online (use it from your phone in Chrome)

The easiest free option is a Hugging Face Space (Docker, free CPU tier with 16 GB RAM, enough for CLIP).
The header at the top of this file is what Hugging Face reads, so leave it in place.

1. Make a free account at https://huggingface.co and create a token with **write** access
   (Settings > Access Tokens).
2. Create a new Space: https://huggingface.co/new-space
   - SDK: **Docker** (Blank)
   - Hardware: **CPU basic (free)**
   - Visibility: **Private** (recommended, the app searches unfiltered)
3. In the Space, open **Settings > Variables and secrets** and add two **secrets**:
   - `APP_PASSWORD`: a long password of your choice
   - `APP_USER`: a username (optional, defaults to `admin`)
4. Push this repo to the Space:
   ```bash
   git remote add space https://huggingface.co/spaces/<your-hf-username>/<space-name>
   git push space main
   ```
   When asked for a password, paste your Hugging Face write token.
5. Wait for the build to finish (about 5 to 10 minutes the first time). Then open the Space URL
   in Chrome on your phone, enter the username and password, and use it like any website.
   Tip: Chrome menu > **Add to Home screen** gives it an app icon.

The app refuses to start if `APP_PASSWORD` is missing, so a hosted copy is never left open.
Free Spaces go to sleep after inactivity; the first visit afterwards takes a minute to wake it.

## Usage

1. Tap the upload box and choose an image (optional if you type a description).
2. Describe what you need in the text box, for example `man running through rain at night`.
3. Press **Search the web for videos**.
4. Open any card to watch the video at its source. Results are sorted best match first, with a match percentage.

## How it works

1. `POST /search` receives the image and text.
2. DuckDuckGo video search returns up to 40 candidates with safe-search off.
3. CLIP (`clip-ViT-B-32` via `sentence-transformers`) embeds your image, your text, each thumbnail and each title.
4. Score = 0.7 x image/thumbnail similarity + 0.3 x text/title similarity (text only: 100% title similarity).
5. Results are sorted and returned to the page.

If the CLIP model cannot be loaded (for example, offline on first run), text searches still work and return results in the search engine's own order.

## Configuration

- Host and port: bottom of `app.py` (`host="0.0.0.0", port=5000`). Use `127.0.0.1` to keep it private to your machine.
- Upload limit: `MAX_CONTENT_LENGTH` in `app.py` (15 MB).
- Result count: `limit` in `search_videos()` (40).
- Image/text weighting: `w_img` in the `search` route (0.7).

## Limitations

- It searches through a search engine; it does not crawl the entire internet.
- Only one thumbnail per video is compared, so very specific scenes match better when you also write a description.
- Result quality and availability depend on DuckDuckGo and can change or rate-limit.
- Unfiltered search can return adult or disturbing content. Use responsibly and keep the app private.

## Responsible use

Use this to find publicly available videos only. Do not use it to identify, track or harass private individuals, and follow the laws and platform terms that apply to you.

## Project layout

```
app.py             Flask app, search + ranking logic, single-page UI, optional login
requirements.txt   Python dependencies
Dockerfile         Container for hosting (Hugging Face Spaces, or any Docker host)
README.md          This file
```
