"""Google Translate client using free endpoint (no API key required)."""
import asyncio
import httpx
import json
import re
from services.translator import TranslationService


class GoogleTranslator(TranslationService):
    """Free Google Translate - no API key required."""

    TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

    # Language code mapping
    LANG_MAP = {
        "EN": "en",
        "JA": "ja",
        "ZH": "zh-CN",
        "KO": "ko",
        "DE": "de",
        "FR": "fr",
        "ES": "es",
    }

    def __init__(self):
        self.max_chars_per_request = 4500  # Google limit per request

    def _map_lang(self, lang: str) -> str:
        return self.LANG_MAP.get(lang.upper(), lang.lower())

    async def _translate_chunk(
        self,
        client: httpx.AsyncClient,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """Translate a single chunk of text."""
        params = {
            "client": "gtx",
            "sl": self._map_lang(source_lang),
            "tl": self._map_lang(target_lang),
            "dt": "t",
            "q": text,
        }

        response = await client.get(self.TRANSLATE_URL, params=params)
        response.raise_for_status()

        # Parse response - it's a nested array
        result = response.json()
        translated_parts = []
        if result and result[0]:
            for part in result[0]:
                if part[0]:
                    translated_parts.append(part[0])

        return "".join(translated_parts)

    def _split_text(self, text: str) -> list[str]:
        """Split text into chunks that fit within the character limit."""
        if len(text) <= self.max_chars_per_request:
            return [text]

        chunks = []
        sentences = re.split(r'(?<=[.!?。！？\n])\s*', text)
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) > self.max_chars_per_request:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks if chunks else [text[:self.max_chars_per_request]]

    async def translate(
        self, text: str, source_lang: str = "EN", target_lang: str = "JA"
    ) -> str:
        if not text or not text.strip():
            return text

        chunks = self._split_text(text)

        async with httpx.AsyncClient(timeout=30.0) as client:
            results = []
            for chunk in chunks:
                result = await self._translate_chunk(
                    client, chunk, source_lang, target_lang
                )
                results.append(result)
                # Small delay to avoid rate limiting
                if len(chunks) > 1:
                    await asyncio.sleep(0.1)

            return "".join(results)

    async def translate_batch(
        self,
        texts: list[str],
        source_lang: str = "EN",
        target_lang: str = "JA",
    ) -> list[str]:
        results = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i, text in enumerate(texts):
                if not text or not text.strip():
                    results.append(text)
                    continue

                chunks = self._split_text(text)
                translated_chunks = []
                for chunk in chunks:
                    result = await self._translate_chunk(
                        client, chunk, source_lang, target_lang
                    )
                    translated_chunks.append(result)

                results.append("".join(translated_chunks))

                # Rate limiting: small delay between requests
                if i < len(texts) - 1:
                    await asyncio.sleep(0.05)

        return results
