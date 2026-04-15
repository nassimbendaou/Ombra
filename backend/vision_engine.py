"""
Ombra Vision Engine
===================
Image analysis using multimodal models (GPT-4o vision, LLaVA).
Accept image paths, URLs, or base64 data and return analysis.
"""

import os
import json
import base64
import asyncio
from typing import Optional
from dataclasses import dataclass


class VisionEngine:
    """
    Multi-modal image analysis engine.
    Uses OpenAI GPT-4o vision by default, with fallback to local models via Ollama.
    """

    def __init__(self):
        self._openai_client = None
        self._ollama_base = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    async def _get_openai_client(self):
        if self._openai_client is None:
            from openai import AsyncOpenAI
            self._openai_client = AsyncOpenAI()
        return self._openai_client

    def _load_image_as_base64(self, path: str) -> tuple[str, str]:
        """Load an image file and return (base64_data, mime_type)."""
        ext = os.path.splitext(path)[1].lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        mime_type = mime_map.get(ext, "image/png")

        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("ascii")
        return data, mime_type

    def _build_image_content(self, image_source: str) -> dict:
        """Build OpenAI image_url content block from path, URL, or base64."""
        if image_source.startswith(("http://", "https://")):
            return {"type": "image_url", "image_url": {"url": image_source, "detail": "high"}}

        elif image_source.startswith("data:image/"):
            return {"type": "image_url", "image_url": {"url": image_source, "detail": "high"}}

        elif os.path.isfile(image_source):
            b64_data, mime_type = self._load_image_as_base64(image_source)
            data_url = f"data:{mime_type};base64,{b64_data}"
            return {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}

        else:
            raise ValueError(f"Invalid image source: {image_source}")

    async def analyze(self, image_source: str, prompt: str = "Describe this image in detail.",
                      model: str = None) -> dict:
        """
        Analyze an image with a vision model.
        image_source: file path, URL, or base64 data URI.
        """
        model = model or os.environ.get("VISION_MODEL", "gpt-4o")

        try:
            if "gpt" in model or "o1" in model or "o3" in model or "o4" in model:
                return await self._analyze_openai(image_source, prompt, model)
            else:
                return await self._analyze_ollama(image_source, prompt, model)
        except Exception as e:
            return {"success": False, "error": str(e), "model": model}

    async def _analyze_openai(self, image_source: str, prompt: str, model: str) -> dict:
        """Analyze using OpenAI vision models."""
        client = await self._get_openai_client()
        image_content = self._build_image_content(image_source)

        response = await client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    image_content,
                ],
            }],
            max_tokens=2048,
        )

        text = response.choices[0].message.content
        return {
            "success": True,
            "analysis": text,
            "model": model,
            "tokens": {
                "prompt": response.usage.prompt_tokens,
                "completion": response.usage.completion_tokens,
            },
        }

    async def _analyze_ollama(self, image_source: str, prompt: str, model: str) -> dict:
        """Analyze using Ollama local vision models (LLaVA, etc.)."""
        import httpx

        # Get base64 image data
        if image_source.startswith(("http://", "https://")):
            async with httpx.AsyncClient() as client:
                resp = await client.get(image_source, timeout=30)
                resp.raise_for_status()
                b64_data = base64.b64encode(resp.content).decode("ascii")
        elif image_source.startswith("data:image/"):
            # Extract base64 from data URI
            b64_data = image_source.split(",", 1)[1] if "," in image_source else image_source
        elif os.path.isfile(image_source):
            b64_data, _ = self._load_image_as_base64(image_source)
        else:
            return {"success": False, "error": f"Cannot load image: {image_source}"}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._ollama_base}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [b64_data],
                    "stream": False,
                },
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()

        return {
            "success": True,
            "analysis": data.get("response", ""),
            "model": model,
            "tokens": {
                "prompt": data.get("prompt_eval_count", 0),
                "completion": data.get("eval_count", 0),
            },
        }

    async def compare_images(self, images: list[str], prompt: str = None) -> dict:
        """Compare multiple images side by side."""
        model = os.environ.get("VISION_MODEL", "gpt-4o")
        if not prompt:
            prompt = "Compare these images. Describe their differences and similarities."

        try:
            client = await self._get_openai_client()
            content = [{"type": "text", "text": prompt}]
            for img in images[:4]:  # Max 4 images
                content.append(self._build_image_content(img))

            response = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                max_tokens=2048,
            )
            return {
                "success": True,
                "analysis": response.choices[0].message.content,
                "model": model,
                "image_count": len(images),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def extract_text(self, image_source: str) -> dict:
        """OCR: extract text from an image."""
        return await self.analyze(
            image_source,
            prompt="Extract ALL text visible in this image. Return only the extracted text, preserving layout where possible.",
        )

    async def analyze_ui(self, image_source: str) -> dict:
        """Analyze a UI screenshot for accessibility, layout, design issues."""
        return await self.analyze(
            image_source,
            prompt=(
                "Analyze this UI screenshot. Identify:\n"
                "1. UI elements and their layout\n"
                "2. Color scheme and typography\n"
                "3. Potential accessibility issues\n"
                "4. Design suggestions for improvement\n"
                "5. Any visible errors or broken elements"
            ),
        )


# ── Global instance ───────────────────────────────────────────────────────────
vision_engine = VisionEngine()
