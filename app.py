"""
Video Finder: upload an image + describe the scene, get matching videos from across the web.

- Image matching runs locally with CLIP (open source, no API key, no cloud AI).
- Video discovery uses DuckDuckGo video search with safe-search OFF (unfiltered).
- Results are re-ranked by how similar each video's thumbnail is to your image
  and how well its title matches your text.
"""
import hmac
import io
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import requests
from flask import Flask, Response, jsonify, render_template_string, request
from PIL import Image
from sentence_transformers import SentenceTransformer, util

try:
    from ddgs import DDGS  # newer package name
except ImportError:  # pragma: no cover
    from duckduckgo_search import DDGS

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15 MB upload cap

# --- Password protection (for hosting online) --------------------------------
# Set APP_PASSWORD (and optionally APP_USER) to require a login in the browser.
# With REQUIRE_AUTH=1 (set in the Dockerfile) the app refuses to start without
# a password, so a hosted copy can never be left open by accident.
APP_USER = os.environ.get("APP_USER", "admin")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

if os.environ.get("REQUIRE_AUTH") == "1" and not APP_PASSWORD:
    sys.exit("APP_PASSWORD is not set. Add it as a secret/environment variable and restart.")


@app.before_request
def require_login():
    if not APP_PASSWORD:
        return None  # local use, no auth
    auth = request.authorization
    ok = (
        auth is not None
        and hmac.compare_digest(auth.username or "", APP_USER)
        and hmac.compare_digest(auth.password or "", APP_PASSWORD)
    )
    if ok:
        return None
    return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Video Finder"'})


_model = None


def model():
    """Load CLIP once. Returns None if it can't be loaded (e.g. offline first run)."""
    global _model
    if _model is None:
        try:
            _model = SentenceTransformer("clip-ViT-B-32")  # downloads once, then cached
        except Exception as e:
            print("CLIP unavailable, falling back to plain search order:", e)
            _model = False
    return _model or None


def fetch_thumb(url):
    try:
        r = requests.get(url, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def search_videos(query, limit=40):
    with DDGS() as ddgs:
        return list(ddgs.videos(query, region="wt-wt", safesearch="off", max_results=limit))


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/search", methods=["POST"])
def search():
    text = (request.form.get("query") or "").strip()
    file = request.files.get("image")
    if not text and not file:
        return jsonify(error="Upload an image or describe the scene."), 400

    img = None
    if file and file.filename:
        try:
            img = Image.open(file.stream).convert("RGB")
        except Exception:
            return jsonify(error="Couldn't read that image."), 400

    m = model()

    # With no text, let CLIP pick the best-fitting keywords for the image itself.
    query = text
    if not query and img is not None and m is None:
        return jsonify(error="Image model couldn't load (needs internet on first run). Type a description instead."), 503
    if not query and img is not None:
        vocab = [
            "beach", "city street at night", "forest", "mountain", "car chase", "concert",
            "kitchen cooking", "football match", "wedding", "classroom", "office", "snow",
            "ocean waves", "fireworks", "crowd", "dance", "animal", "airplane", "train",
            "rain", "desert", "interview", "street fight", "fashion show", "gym workout",
            "sunset", "motorbike", "explosion", "swimming pool", "party", "cartoon", "gameplay",
        ]
        sims = util.cos_sim(m.encode(img), m.encode(vocab))[0]
        top = sims.topk(3).indices.tolist()
        query = " ".join(vocab[i] for i in top) + " video"

    try:
        videos = search_videos(query)
    except Exception as e:
        return jsonify(error=f"Search failed: {e}"), 502
    if not videos:
        return jsonify(query=query, results=[])

    if m is None:  # no CLIP: return results in the search engine's own order
        return jsonify(query=query, results=[{
            "title": v.get("title"), "url": v.get("content"),
            "thumb": (v.get("images") or {}).get("medium") or (v.get("images") or {}).get("small"),
            "duration": v.get("duration"), "source": v.get("publisher") or v.get("provider"),
            "score": 0.0,
        } for v in videos])

    thumb_urls = [(v.get("images") or {}).get("medium") or (v.get("images") or {}).get("small") for v in videos]
    with ThreadPoolExecutor(max_workers=12) as pool:
        thumbs = list(pool.map(lambda u: fetch_thumb(u) if u else None, thumb_urls))

    text_emb = m.encode(text or query)
    title_emb = m.encode([v.get("title", "") for v in videos])
    text_scores = util.cos_sim(text_emb, title_emb)[0].tolist()

    img_scores = [0.0] * len(videos)
    if img is not None:
        img_emb = m.encode(img)
        ok = [i for i, t in enumerate(thumbs) if t is not None]
        if ok:
            thumb_emb = m.encode([thumbs[i] for i in ok])
            sims = util.cos_sim(img_emb, thumb_emb)[0].tolist()
            for i, s in zip(ok, sims):
                img_scores[i] = s

    w_img = 0.7 if img is not None else 0.0
    w_txt = 1.0 - w_img
    results = []
    for v, ts, is_ in zip(videos, text_scores, img_scores):
        results.append({
            "title": v.get("title"),
            "url": v.get("content"),
            "thumb": (v.get("images") or {}).get("medium") or (v.get("images") or {}).get("small"),
            "duration": v.get("duration"),
            "source": v.get("publisher") or v.get("provider"),
            "score": round(w_img * is_ + w_txt * ts, 4),
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return jsonify(query=query, results=results)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Video Finder</title>
<style>
  :root{color-scheme:dark}
  body{margin:0;font-family:system-ui,sans-serif;background:#0e0f13;color:#eee}
  main{max-width:1000px;margin:0 auto;padding:20px 16px}
  h1{font-size:22px;margin:0 0 16px}
  form{display:grid;gap:12px;background:#171922;padding:16px;border-radius:12px}
  #drop{border:2px dashed #3a3f55;border-radius:10px;padding:18px;text-align:center;cursor:pointer;color:#9aa}
  #drop img{max-width:100%;max-height:220px;border-radius:8px}
  textarea{width:100%;box-sizing:border-box;min-height:70px;border-radius:8px;border:1px solid #333;background:#0e0f13;color:#eee;padding:10px;font:inherit}
  button{background:#4f7cff;border:0;color:#fff;padding:12px;border-radius:8px;font-size:16px;cursor:pointer}
  button:disabled{opacity:.5}
  #status{margin:14px 0;color:#9aa}
  #grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
  .card{background:#171922;border-radius:10px;overflow:hidden;text-decoration:none;color:inherit;display:block}
  .card img{width:100%;aspect-ratio:16/9;object-fit:cover;background:#222}
  .card div{padding:10px;font-size:14px}
  .meta{color:#8a90a5;font-size:12px;margin-top:4px}
</style></head><body><main>
<h1>Video Finder</h1>
<form id="f">
  <label id="drop">
    <input id="file" name="image" type="file" accept="image/*" hidden>
    <span id="hint">Tap to upload an image</span>
  </label>
  <textarea name="query" placeholder="Describe what you need: scene, action, setting..."></textarea>
  <button id="go">Search the web for videos</button>
</form>
<div id="status"></div>
<div id="grid"></div>
</main>
<script>
const f=document.getElementById('f'),file=document.getElementById('file'),
hint=document.getElementById('hint'),st=document.getElementById('status'),
grid=document.getElementById('grid'),go=document.getElementById('go');
file.onchange=()=>{const x=file.files[0];if(!x)return;
  hint.innerHTML='';const i=new Image();i.src=URL.createObjectURL(x);hint.appendChild(i);};
f.onsubmit=async e=>{e.preventDefault();go.disabled=true;grid.innerHTML='';
  st.textContent='Searching and matching... first run downloads the model, so it can take a minute.';
  try{
    const r=await fetch('/search',{method:'POST',body:new FormData(f)});
    const d=await r.json();
    if(!r.ok){st.textContent=d.error||'Error';return;}
    st.textContent=d.results.length?`Query used: "${d.query}"  -  ${d.results.length} results, best match first`:'No videos found.';
    d.results.forEach(v=>{
      const a=document.createElement('a');a.className='card';a.href=v.url;a.target='_blank';a.rel='noopener';
      a.innerHTML=`<img src="${v.thumb||''}" loading="lazy"><div>${v.title||''}
        <div class="meta">${[v.source,v.duration].filter(Boolean).join(' - ')} - match ${(v.score*100).toFixed(0)}%</div></div>`;
      grid.appendChild(a);
    });
  }catch(err){st.textContent='Request failed: '+err;}
  finally{go.disabled=false;}
};
</script></body></html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
