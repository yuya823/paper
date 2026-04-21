"""Translation service abstraction layer."""
import re
import asyncio
from abc import ABC, abstractmethod
from typing import Optional
import httpx


class TranslationService(ABC):
    """Abstract base class for translation services."""

    @abstractmethod
    async def translate(self, text: str, source_lang: str = "EN", target_lang: str = "JA") -> str:
        pass

    @abstractmethod
    async def translate_batch(self, texts: list[str], source_lang: str = "EN", target_lang: str = "JA") -> list[str]:
        pass


class MockTranslator(TranslationService):
    """Mock translator for development/testing without API keys."""

    # Common academic terms for realistic mock translation
    MOCK_TERMS = {
        "abstract": "要旨",
        "introduction": "はじめに",
        "methods": "方法",
        "results": "結果",
        "discussion": "考察",
        "conclusion": "結論",
        "references": "参考文献",
        "figure": "図",
        "table": "表",
        "the": "",
        "is": "である",
        "are": "である",
        "was": "であった",
        "were": "であった",
        "this": "この",
        "that": "その",
        "these": "これらの",
        "study": "研究",
        "research": "研究",
        "analysis": "分析",
        "data": "データ",
        "significant": "有意な",
        "effect": "効果",
        "patient": "患者",
        "treatment": "治療",
        "exercise": "運動",
        "muscle": "筋肉",
        "training": "トレーニング",
        "performance": "パフォーマンス",
        "in": "において",
        "of": "の",
        "and": "および",
        "with": "を伴う",
        "for": "のための",
    }

    async def translate(self, text: str, source_lang: str = "EN", target_lang: str = "JA") -> str:
        # Simulate API latency
        await asyncio.sleep(0.05)

        if not text or not text.strip():
            return text

        # Simple word-by-word mock translation for development
        words = text.split()
        translated_words = []
        for word in words:
            clean = word.lower().strip(".,;:!?()[]{}\"'")
            if clean in self.MOCK_TERMS:
                replacement = self.MOCK_TERMS[clean]
                if replacement:
                    translated_words.append(replacement)
            else:
                # Keep original word with katakana-style marking
                translated_words.append(word)

        result = "".join(translated_words) if target_lang == "JA" else " ".join(translated_words)

        # For Japanese, add some structure
        if target_lang == "JA":
            # Re-join with proper spacing for readability
            result = " ".join(translated_words)

        return f"【翻訳】{result}"

    async def translate_batch(self, texts: list[str], source_lang: str = "EN", target_lang: str = "JA") -> list[str]:
        results = []
        for text in texts:
            result = await self.translate(text, source_lang, target_lang)
            results.append(result)
        return results


class DeepLTranslator(TranslationService):
    """DeepL API translator."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api-free.deepl.com/v2"  # Use api.deepl.com for Pro
        if not api_key.endswith(":fx"):
            self.base_url = "https://api.deepl.com/v2"

    async def translate(self, text: str, source_lang: str = "EN", target_lang: str = "JA") -> str:
        if not text or not text.strip():
            return text

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/translate",
                data={
                    "auth_key": self.api_key,
                    "text": text,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["translations"][0]["text"]

    async def translate_batch(self, texts: list[str], source_lang: str = "EN", target_lang: str = "JA") -> list[str]:
        if not texts:
            return []

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/translate",
                data={
                    "auth_key": self.api_key,
                    "text": texts,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                },
            )
            response.raise_for_status()
            data = response.json()
            return [t["text"] for t in data["translations"]]


def create_translator(mode: str = "mock", api_key: str = "") -> TranslationService:
    """Factory function to create the appropriate translator."""
    if mode == "google":
        from services.google_translate import GoogleTranslator
        return GoogleTranslator()
    if mode == "deepl" and api_key:
        return DeepLTranslator(api_key)
    return MockTranslator()

