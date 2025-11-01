from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence


@dataclass
class ClassificationResult:
    label: str = "unknown"
    confidence: float = 0.0
    rationale: str | None = None
    suggested_schema_name: str | None = None
    suggested_fields: Sequence[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


class DocumentClassifier:
    """Lightweight heuristic classifier to prime schema selection before advanced models are wired."""

    def classify(
        self,
        text: str | None,
        *,
        snippets: Mapping[str, str | None] | None = None,
    ) -> ClassificationResult:
        if not text:
            return ClassificationResult(rationale="No OCR text available.")

        normalized = text.lower()
        snippets = snippets or {}

        rules: list[tuple[str, float, Sequence[str], str]] = [
            ("contract", 0.8, ["Effective Date", "Parties", "Term", "Signature"], "Contract"),
            ("master services agreement", 0.9, ["Service Scope", "Term", "Termination", "Fees"], "MSA"),
            ("statement of work", 0.85, ["Scope", "Deliverables", "Milestones", "Compensation"], "SOW"),
            ("invoice", 0.9, ["Invoice Number", "Invoice Date", "Total Due", "Payment Terms"], "Invoice"),
            ("purchase order", 0.75, ["PO Number", "Vendor", "Ship To", "Total"], "Purchase Order"),
        ]

        for keyword, confidence, fields, canonical in rules:
            if keyword in normalized:
                rationale = f"Matched keyword '{keyword}' in OCR text."
                return ClassificationResult(
                    label=canonical,
                    confidence=confidence,
                    rationale=rationale,
                    suggested_schema_name=canonical,
                    suggested_fields=fields,
                    metadata={
                        "matched_keyword": keyword,
                        "source": self._prime_source(snippets, keyword),
                    },
                )

        # fallback: detect by structural hints
        if re.search(r"\b(total due|balance due|invoice number)\b", normalized):
            return ClassificationResult(
                label="Invoice",
                confidence=0.6,
                rationale="Detected billing-oriented phrases.",
                suggested_schema_name="Invoice",
                suggested_fields=["Invoice Number", "Invoice Date", "Total Due", "Billing Address"],
                metadata={"source": self._prime_source(snippets, "invoice")},
            )

        if re.search(r"\b(scope of work|deliverable)\b", normalized):
            return ClassificationResult(
                label="Statement of Work",
                confidence=0.55,
                rationale="Found SOW terminology.",
                suggested_schema_name="Statement of Work",
                suggested_fields=["Scope", "Deliverables", "Timeline", "Payment"],
                metadata={"source": self._prime_source(snippets, "scope of work")},
            )

        return ClassificationResult(
            rationale="No matching heuristic rule.",
        )

    @staticmethod
    def _prime_source(snippets: Mapping[str, str | None], keyword: str) -> str | None:
        for source, text in snippets.items():
            if text and keyword in text.lower():
                return source
        return None
