from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Decision:
    decision_id: str
    feature_id: str
    decision_text: str
    made_by: str | None = None
    rationale: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    decision_date: str = field(default_factory=utc_now_iso)
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        feature_id: str,
        decision_text: str,
        made_by: str | None,
        rationale: str | None,
        evidence_ids: list[str] | None,
        source_refs: list[str] | None,
        decision_date: str | None,
    ) -> "Decision":
        return cls(
            decision_id=str(uuid4()),
            feature_id=feature_id,
            decision_text=decision_text,
            made_by=made_by,
            rationale=rationale,
            evidence_ids=evidence_ids or [],
            source_refs=source_refs or [],
            decision_date=decision_date or utc_now_iso(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Feature:
    feature_id: str
    title: str
    summary: str
    status: str = "proposed"
    owner: str | None = None
    stakeholders: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        title: str,
        summary: str,
        status: str,
        owner: str | None,
        stakeholders: list[str] | None,
        source_refs: list[str] | None,
    ) -> "Feature":
        now = utc_now_iso()
        return cls(
            feature_id=str(uuid4()),
            title=title,
            summary=summary,
            status=status,
            owner=owner,
            stakeholders=stakeholders or [],
            source_refs=source_refs or [],
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Artifact:
    artifact_id: str
    feature_id: str
    source_type: str
    source_id: str
    title: str
    content: str
    author: str | None = None
    url: str | None = None
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        feature_id: str,
        source_type: str,
        source_id: str,
        title: str,
        content: str,
        author: str | None,
        url: str | None,
    ) -> "Artifact":
        return cls(
            artifact_id=str(uuid4()),
            feature_id=feature_id,
            source_type=source_type,
            source_id=source_id,
            title=title,
            content=content,
            author=author,
            url=url,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    evidence_id: str
    feature_id: str
    artifact_id: str
    excerpt: str
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(cls, feature_id: str, artifact_id: str, excerpt: str) -> "Evidence":
        return cls(
            evidence_id=str(uuid4()),
            feature_id=feature_id,
            artifact_id=artifact_id,
            excerpt=excerpt,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Dependency:
    dependency_id: str
    feature_id: str
    dependency_type: str
    target_name: str
    status: str = "active"
    notes: str | None = None
    source_refs: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(
        cls,
        feature_id: str,
        dependency_type: str,
        target_name: str,
        status: str,
        notes: str | None,
        source_refs: list[str] | None,
    ) -> "Dependency":
        return cls(
            dependency_id=str(uuid4()),
            feature_id=feature_id,
            dependency_type=dependency_type,
            target_name=target_name,
            status=status,
            notes=notes,
            source_refs=source_refs or [],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
