# 商品画像レイアウト自動合成ツール

生成AI（Google Gemini / Imagen）で作成した背景・イラストと、あらかじめ用意した商品写真・
固定テキストを、位置固定テンプレートに従って自動合成し、最終画像（PNG）を大量生成するツールです。

500〜3000件規模の一括処理を想定し、以下を備えています。

- **位置固定テンプレート**：座標をJSONで指定するレイアウト方式（商品ごとに動的にAIへ配置判断させない）
- **AI画像のキャッシュ**：同一プロンプトの背景/イラストは1度だけ生成し使い回すことで、API コストと処理時間を削減
- **再開可能なバッチ処理**：途中で中断しても、生成済みの行はスキップして再実行できる
- **透過PNG出力**：商品写真の切り抜き（アルファチャンネル）をそのまま活かして合成

---

## 1. セットアップ

```bash
cd image_layout_tool
python -m venv venv
source venv/bin/activate   # Windowsは venv\Scripts\activate
pip install -r requirements.txt
```

### APIキーの設定

`config/settings.example.yaml` を `config/settings.yaml` にコピーし、
Google AI Studio で発行した Gemini API キーを設定してください。

```bash
cp config/settings.example.yaml config/settings.yaml
```

```yaml
gemini_api_key: "YOUR_API_KEY_HERE"
```

### 日本語フォントの配置

Pillow は標準で日本語グリフを持たないため、`assets/fonts/` に日本語対応フォント
（例：[Noto Sans JP](https://fonts.google.com/noto/specimen/Noto+Sans+JP)）の `.otf`/`.ttf` を
配置してください。テンプレートJSON内の `font` はこのフォルダ内のファイル名を指します。

```
assets/fonts/NotoSansJP-Bold.otf
assets/fonts/NotoSansJP-Regular.otf
```

---

## 2. データの準備（Excel/CSV）

`data/sample_input.csv` を参考に、以下の列を持つ Excel(.xlsx) または CSV を用意します。

| 列名 | 必須 | 説明 |
|---|---|---|
| id | ○ | 商品ID（出力ファイル名の元にもなる） |
| template_id | ○ | 使用するテンプレート名（`config/templates/<template_id>.json`） |
| product_image_path | ○ | 商品写真（透過PNG推奨）へのローカルパス |
| title_text | - | メインテキスト（テンプレート側の `field` と対応） |
| sub_text | - | サブテキスト |
| bg_prompt | - | 背景をAI生成する場合のプロンプト |
| bg_asset_path | - | 既存の背景画像を使う場合はこちらにパスを指定（`bg_prompt` より優先） |
| illust_prompt | - | イラストをAI生成する場合のプロンプト |
| illust_asset_path | - | 既存イラストを使う場合のパス |
| output_filename | - | 省略時は `<id>.png` |

**ポイント**：`bg_prompt` / `illust_prompt` が複数行で同一文言なら、AI呼び出しは1回だけ行い
キャッシュされた画像を全行で使い回します（3000件でも背景パターンが10種類なら生成は10回のみ）。

---

## 3. テンプレートの作成

`config/templates/template_default.json` がサンプルです。キャンバスサイズ、各レイヤー
（背景／イラスト／商品写真／テキスト）の座標(x1,y1,x2,y2)を固定値で指定します。
テンプレートを複数用意し、`template_id` で商品ごとに切り替えられます。

---

## 4. 実行

```bash
python main.py --input data/sample_input.csv --output-dir output
```

主なオプション：

```
--input            入力Excel/CSVのパス（必須）
--output-dir        出力先フォルダ（デフォルト: output）
--limit N           先頭N件のみ処理（動作確認用）
--force              既存の出力ファイルがあっても再生成する
--dry-run            AI生成・合成をせず処理内容だけ表示
```

途中でエラーが出ても他の行の処理は継続し、`logs/run_log.csv` に成功/失敗が記録されます。
失敗した行だけ後で再実行することも可能です（`--only-failed`）。

---

## 5. ディレクトリ構成

```
image_layout_tool/
├── main.py                  # 実行エントリポイント
├── requirements.txt
├── config/
│   ├── settings.yaml         # APIキー等（要作成）
│   └── templates/
│       └── template_default.json
├── modules/
│   ├── data_loader.py        # Excel/CSV読み込み
│   ├── ai_generator.py       # Gemini/Imagenでの背景・イラスト生成＋キャッシュ
│   ├── compositor.py         # Pillowでのレイヤー合成
│   ├── text_renderer.py      # 日本語テキスト描画（折り返し・中央揃え対応）
│   └── utils.py
├── assets/
│   ├── fonts/                # 日本語フォント（要配置）
│   └── cache/                 # AI生成画像のキャッシュ（プロンプトのハッシュ単位）
├── data/
│   └── sample_input.csv
├── output/                   # 生成結果
└── logs/
    └── run_log.csv            # 実行ログ（再開用）
```
