from __future__ import annotations

from difflib import SequenceMatcher

from app.database import load_faq_entries
from app.schemas.types import FAQEntry, FAQMatch


class FAQService:
    def __init__(self) -> None:
        self.entries = [FAQEntry.model_validate(entry) for entry in load_faq_entries()]

    def list_entries(self) -> list[FAQEntry]:
        return self.entries

    def match(self, message: str) -> FAQMatch:
        normalized = message.strip().lower()
        best_match: FAQEntry | None = None
        best_score = 0.0
        for entry in self.entries:
            ratio = SequenceMatcher(None, normalized, entry.question.lower()).ratio()
            if entry.question.lower() in normalized:
                ratio = max(ratio, 0.92)
            if ratio > best_score:
                best_score = ratio
                best_match = entry
        if best_match and best_score >= 0.55:
            return FAQMatch(matched=True, question=best_match.question, answer=best_match.answer, score=best_score)
        return FAQMatch(matched=False, score=best_score)
