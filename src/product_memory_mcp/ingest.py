from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from product_memory_mcp.models import Feature
from product_memory_mcp.store import ProductMemoryStore


DECISION_PREFIXES = ("decision:", "approved:", "rejected:", "deferred:")
DEPENDENCY_PREFIXES = (
    ("depends on:", "dependency"),
    ("blocked by:", "blocker"),
)


def summarize_text(text: str, fallback: str) -> str:
    normalized = " ".join(text.split())
    if normalized:
        return normalized[:280]
    return fallback


def parse_decision_lines(text: str) -> list[str]:
    decisions: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        normalized_line = re.sub(r"^(comment:)\s*", "", line, flags=re.IGNORECASE)
        lower = normalized_line.lower()
        for prefix in DECISION_PREFIXES:
            if lower.startswith(prefix):
                extracted = normalized_line[len(prefix):].strip(" -")
                if extracted:
                    decisions.append(extracted)
                break
    return decisions


def parse_dependencies(text: str) -> list[tuple[str, str]]:
    dependencies: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        normalized_line = re.sub(r"^(comment:)\s*", "", line, flags=re.IGNORECASE)
        lower = normalized_line.lower()
        for prefix, dependency_type in DEPENDENCY_PREFIXES:
            if lower.startswith(prefix):
                remainder = normalized_line[len(prefix):].strip()
                for part in re.split(r",|;", remainder):
                    target = part.strip()
                    if target:
                        dependencies.append((dependency_type, target))
                break
    return dependencies


def merge_unique(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for value in values:
        if not value:
            continue
        if value not in seen:
            seen.add(value)
            merged.append(value)
    return merged


class IngestionService:
    def __init__(self, store: ProductMemoryStore) -> None:
        self.store = store

    def ingest_jira_issue_event(
        self,
        issue_key: str,
        summary: str,
        description: str,
        status: str | None,
        assignee: str | None,
        reporter: str | None,
        comments: list[str] | None,
        url: str | None,
        feature_id: str | None,
    ) -> dict[str, Any]:
        source_ref = f"jira:{issue_key}"
        feature = self._resolve_or_create_feature(
            feature_id=feature_id,
            source_ref=source_ref,
            title=summary,
            summary_text=description,
            status=status or "proposed",
            owner=assignee,
            stakeholders=merge_unique([assignee, reporter]),
        )

        body_parts = [description.strip()] if description.strip() else []
        for comment in comments or []:
            if comment.strip():
                body_parts.append(f"Comment: {comment.strip()}")
        content = "\n".join(body_parts) or summary

        artifact = self.store.record_artifact(
            feature_id=feature.feature_id,
            source_type="jira_issue",
            source_id=issue_key,
            title=summary,
            content=content,
            author=reporter,
            url=url,
        )

        decisions, dependencies = self._extract_and_persist(
            feature_id=feature.feature_id,
            artifact_id=artifact.artifact_id,
            text=content,
            actor=assignee or reporter,
            source_ref=source_ref,
        )

        return {
            "feature": asdict(feature),
            "artifact": asdict(artifact),
            "decisions_created": decisions,
            "dependencies_created": dependencies,
        }

    def ingest_confluence_page_event(
        self,
        page_id: str,
        title: str,
        body: str,
        author: str | None,
        labels: list[str] | None,
        url: str | None,
        feature_id: str | None,
    ) -> dict[str, Any]:
        source_ref = f"confluence:{page_id}"
        feature = self._resolve_or_create_feature(
            feature_id=feature_id,
            source_ref=source_ref,
            title=title,
            summary_text=body,
            status="documented",
            owner=author,
            stakeholders=merge_unique([author, *(labels or [])]),
        )

        artifact = self.store.record_artifact(
            feature_id=feature.feature_id,
            source_type="confluence_page",
            source_id=page_id,
            title=title,
            content=body,
            author=author,
            url=url,
        )

        decisions, dependencies = self._extract_and_persist(
            feature_id=feature.feature_id,
            artifact_id=artifact.artifact_id,
            text=body,
            actor=author,
            source_ref=source_ref,
        )

        return {
            "feature": asdict(feature),
            "artifact": asdict(artifact),
            "decisions_created": decisions,
            "dependencies_created": dependencies,
            "labels": labels or [],
        }

    def _resolve_or_create_feature(
        self,
        feature_id: str | None,
        source_ref: str,
        title: str,
        summary_text: str,
        status: str,
        owner: str | None,
        stakeholders: list[str] | None,
    ) -> Feature:
        existing = None
        if feature_id:
            existing = self.store.get_feature(feature_id)
        if existing is None:
            existing = self.store.find_feature_by_source_ref(source_ref)

        if existing is not None:
            merged_stakeholders = merge_unique([*existing.stakeholders, *(stakeholders or [])])
            merged_source_refs = merge_unique([*existing.source_refs, source_ref])
            return self.store.upsert_feature(
                feature_id=existing.feature_id,
                title=existing.title or title,
                summary=existing.summary or summarize_text(summary_text, title),
                status=status or existing.status,
                owner=owner or existing.owner,
                stakeholders=merged_stakeholders,
                source_refs=merged_source_refs,
            )

        return self.store.upsert_feature(
            feature_id=None,
            title=title,
            summary=summarize_text(summary_text, title),
            status=status,
            owner=owner,
            stakeholders=stakeholders,
            source_refs=[source_ref],
        )

    def _extract_and_persist(
        self,
        feature_id: str,
        artifact_id: str,
        text: str,
        actor: str | None,
        source_ref: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        decision_records: list[dict[str, Any]] = []
        dependency_records: list[dict[str, Any]] = []

        for decision_text in parse_decision_lines(text):
            evidence = self.store.add_evidence(
                feature_id=feature_id,
                artifact_id=artifact_id,
                excerpt=decision_text,
            )
            decision = self.store.add_decision(
                feature_id=feature_id,
                decision_text=decision_text,
                made_by=actor,
                rationale=None,
                evidence_ids=[evidence.evidence_id],
                source_refs=[source_ref],
                decision_date=None,
            )
            decision_records.append(asdict(decision))

        for dependency_type, target_name in parse_dependencies(text):
            dependency = self.store.add_dependency(
                feature_id=feature_id,
                dependency_type=dependency_type,
                target_name=target_name,
                status="active",
                notes=None,
                source_refs=[source_ref],
            )
            dependency_records.append(asdict(dependency))

        return decision_records, dependency_records
