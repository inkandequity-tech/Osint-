FROM python:3.11-slim

# Hugging Face Spaces runs containers as user 1000
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    PORT=7860 \
    REQUIRE_AUTH=1
WORKDIR /home/user/app

# CPU-only PyTorch keeps the image small
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

USER user

# Bake the CLIP model into the image so the first search is fast
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('clip-ViT-B-32')"

COPY --chown=user app.py .

EXPOSE 7860
# One worker (the model lives in memory), several threads, long timeout for slow searches
CMD ["sh", "-c", "gunicorn -w 1 --threads 4 -t 300 -b 0.0.0.0:${PORT} app:app"]
