#!/usr/bin/env python3
"""商品画像レイアウト自動合成ツール — 簡易Web UI

ブラウザから商品画像・テキスト・背景/イラスト画像をアップロードして
テンプレート合成を試せる確認用サーバー。

使い方:
    ./venv/bin/python webapp.py
    -> http://localhost:5050 をブラウザで開く
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, send_from_directory, url_for
from PIL import Image

from modules.compositor import compose, save_output

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "config" / "templates"
UPLOAD_DIR = BASE_DIR / "assets" / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
FONT_DIR = BASE_DIR / "assets" / "fonts"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB


def list_templates() -> list[str]:
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.json"))


def load_template(template_id: str) -> dict:
    with open(TEMPLATES_DIR / f"{template_id}.json", encoding="utf-8") as f:
        return json.load(f)


def list_outputs() -> list[str]:
    files = sorted(OUTPUT_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.name for p in files]


PAGE = """
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>商品画像レイアウト自動合成ツール</title>
<style>
  body { font-family: -apple-system, "Hiragino Sans", "Noto Sans JP", sans-serif;
         background: #f4f5f7; color: #222; margin: 0; padding: 0; }
  header { background: #222; color: #fff; padding: 20px 24px; }
  header h1 { margin: 0; font-size: 20px; }
  main { max-width: 960px; margin: 24px auto; padding: 0 16px; }
  .card { background: #fff; border-radius: 10px; padding: 20px 24px; margin-bottom: 24px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  label { display: block; font-weight: 600; margin: 14px 0 6px; font-size: 14px; }
  input[type=text], input[type=file], select, textarea {
      width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1px solid #ccc;
      border-radius: 6px; font-size: 14px; }
  .hint { color: #888; font-size: 12px; margin-top: 4px; }
  button { margin-top: 20px; background: #2563eb; color: #fff; border: none;
           padding: 10px 22px; border-radius: 6px; font-size: 15px; cursor: pointer; }
  button:hover { background: #1d4ed8; }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .result img { max-width: 100%; border-radius: 8px; border: 1px solid #eee; }
  .gallery { display: flex; flex-wrap: wrap; gap: 14px; }
  .gallery figure { margin: 0; width: 160px; }
  .gallery img { width: 100%; border-radius: 6px; border: 1px solid #eee; }
  .gallery figcaption { font-size: 12px; color: #666; word-break: break-all; margin-top: 4px; }
  .error { background: #fee; border: 1px solid #f99; color: #900; padding: 10px 14px;
           border-radius: 6px; margin-bottom: 16px; }
  @media (max-width: 640px) { .grid { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header><h1>🖼️ 商品画像レイアウト自動合成ツール</h1></header>
<main>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}

  <div class="card">
    <h2 style="margin-top:0;">画像を合成する</h2>
    <form method="post" action="{{ url_for('generate') }}" enctype="multipart/form-data">
      <div class="grid">
        <div>
          <label>テンプレート</label>
          <select name="template_id">
            {% for t in templates %}<option value="{{ t }}">{{ t }}</option>{% endfor %}
          </select>

          <label>商品画像（必須・透過PNG推奨）</label>
          <input type="file" name="product_image" accept="image/*" required>

          <label>背景画像（任意）</label>
          <input type="file" name="bg_image" accept="image/*">
          <div class="hint">未指定の場合は背景なし（AI生成は使用しません）</div>

          <label>イラスト画像（任意・透過PNG推奨）</label>
          <input type="file" name="illust_image" accept="image/*">
        </div>
        <div>
          <label>メインテキスト（title_text）</label>
          <input type="text" name="title_text" placeholder="例: 春の新作コート">

          <label>サブテキスト（sub_text）</label>
          <input type="text" name="sub_text" placeholder="例: 数量限定 早期予約特典あり">
        </div>
      </div>
      <button type="submit">合成する</button>
    </form>
  </div>

  {% if result %}
  <div class="card result">
    <h2 style="margin-top:0;">合成結果</h2>
    <img src="{{ url_for('output_file', filename=result) }}" alt="result">
    <p><a href="{{ url_for('output_file', filename=result) }}" download>PNGをダウンロード</a></p>
  </div>
  {% endif %}

  <div class="card">
    <h2 style="margin-top:0;">これまでの生成結果</h2>
    {% if outputs %}
    <div class="gallery">
      {% for f in outputs %}
      <figure>
        <a href="{{ url_for('output_file', filename=f) }}" target="_blank">
          <img src="{{ url_for('output_file', filename=f) }}" alt="{{ f }}">
        </a>
        <figcaption>{{ f }}</figcaption>
      </figure>
      {% endfor %}
    </div>
    {% else %}
    <p style="color:#888;">まだ生成された画像はありません。</p>
    {% endif %}
  </div>
</main>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, templates=list_templates(), outputs=list_outputs(), result=None, error=None)


@app.route("/generate", methods=["POST"])
def generate():
    templates = list_templates()
    try:
        template_id = request.form.get("template_id", "")
        template = load_template(template_id)

        product_file = request.files.get("product_image")
        if not product_file or not product_file.filename:
            raise ValueError("商品画像を選択してください。")

        ts = time.strftime("%Y%m%d_%H%M%S")
        product_path = UPLOAD_DIR / f"{ts}_product_{product_file.filename}"
        product_file.save(product_path)

        background_image = None
        bg_file = request.files.get("bg_image")
        if bg_file and bg_file.filename:
            background_image = Image.open(bg_file.stream)
            background_image.load()

        illustration_image = None
        illust_file = request.files.get("illust_image")
        if illust_file and illust_file.filename:
            illustration_image = Image.open(illust_file.stream)
            illustration_image.load()

        text_fields = {
            "title_text": request.form.get("title_text", ""),
            "sub_text": request.form.get("sub_text", ""),
        }

        final_image = compose(
            template,
            product_image_path=str(product_path),
            background_image=background_image,
            illustration_image=illustration_image,
            text_fields=text_fields,
            font_dir=str(FONT_DIR),
        )

        output_name = f"webapp_{ts}.png"
        save_output(final_image, str(OUTPUT_DIR / output_name))

        return render_template_string(
            PAGE, templates=templates, outputs=list_outputs(), result=output_name, error=None
        )

    except Exception as e:  # noqa: BLE001
        return render_template_string(
            PAGE, templates=templates, outputs=list_outputs(), result=None, error=f"エラー: {e}"
        )


@app.route("/output/<path:filename>")
def output_file(filename: str):
    return send_from_directory(OUTPUT_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
