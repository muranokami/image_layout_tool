"""生成AI（Google Imagen）で背景・イラスト画像を作成するモジュール。

同一プロンプトは assets/cache/ 配下にハッシュ名で保存し、以後は再生成せず使い回す。
これにより数千行のバッチでも、ユニークなプロンプト数の分しかAPI呼び出しが発生しない。
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from PIL import Image

from .utils import prompt_hash

logger = logging.getLogger("image_layout_tool")


class AIGeneratorError(Exception):
    pass


class AIGenerator:
    def __init__(self, settings: dict):
        self.api_key = settings.get("gemini_api_key", "")
        self.model = settings.get("image_model", "imagen-4.0-generate-001")
        self.aspect_ratio = settings.get("generation_aspect_ratio", "1:1")
        self.enable_cache = settings.get("enable_cache", True)
        self.cache_dir = Path(settings.get("cache_dir", "assets/cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.request_interval = float(settings.get("request_interval_sec", 1.0))
        self.max_retries = int(settings.get("max_retries", 3))
        self.retry_backoff = float(settings.get("retry_backoff_sec", 5))

        self._client = None  # 遅延初期化（--dry-run 時にAPIキー不要にするため）

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key or self.api_key == "YOUR_API_KEY_HERE":
            raise AIGeneratorError(
                "Gemini APIキーが未設定です。config/settings.yaml の gemini_api_key を設定してください。"
            )
        try:
            from google import genai
        except ImportError as e:
            raise AIGeneratorError(
                "google-genai がインストールされていません。pip install -r requirements.txt を実行してください。"
            ) from e
        self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _cache_path(self, prompt: str) -> Path:
        h = prompt_hash(prompt, self.model, self.aspect_ratio)
        return self.cache_dir / f"{h}.png"

    def generate(self, prompt: str, transparent: bool = False) -> Image.Image:
        """プロンプトから画像を生成（またはキャッシュから読み込み）してPIL.Imageで返す。

        transparent=True の場合、背景を透過させたいイラスト用途を意図している。
        Imagen自体は必ずしも透過PNGを返さないため、プロンプト側に
        「背景は透明」「背景は単色白」等を明示し、必要であれば別途背景除去処理を
        追加することを推奨（本ツールでは簡易実装として素通ししている）。
        """
        if not prompt.strip():
            raise AIGeneratorError("空のプロンプトが渡されました")

        cache_file = self._cache_path(prompt)
        if self.enable_cache and cache_file.exists():
            logger.info(f"  [cache hit] {prompt[:40]}...")
            return Image.open(cache_file).convert("RGBA")

        logger.info(f"  [AI生成] {prompt[:40]}...")
        image = self._generate_with_retry(prompt)

        if self.enable_cache:
            image.save(cache_file)

        time.sleep(self.request_interval)
        return image

    def _generate_with_retry(self, prompt: str) -> Image.Image:
        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._call_api(prompt)
            except Exception as e:  # noqa: BLE001
                last_err = e
                logger.warning(f"  生成失敗（{attempt}/{self.max_retries}）: {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * attempt)
        raise AIGeneratorError(f"画像生成に失敗しました: {last_err}") from last_err

    def _call_api(self, prompt: str) -> Image.Image:
        client = self._get_client()
        # google-genai SDK の Imagen 画像生成呼び出し。
        # SDKバージョンにより引数名が変わる場合があるため、エラー時は
        # https://ai.google.dev/gemini-api/docs/image-generation を参照して調整してください。
        response = client.models.generate_images(
            model=self.model,
            prompt=prompt,
            config={
                "number_of_images": 1,
                "aspect_ratio": self.aspect_ratio,
                "output_mime_type": "image/png",
            },
        )
        if not getattr(response, "generated_images", None):
            raise AIGeneratorError("APIレスポンスに画像が含まれていません")

        image_bytes = response.generated_images[0].image.image_bytes
        import io

        return Image.open(io.BytesIO(image_bytes)).convert("RGBA")
