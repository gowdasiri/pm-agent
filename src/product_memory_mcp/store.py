from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from product_memory_mcp.models import Artifact, Decision, Dependency, Evidence, Feature, utc_now_iso


class ProductMemoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(self._empty_payload())

    def _empty_payload(self) -> dict:
        return {
            "features": {},
            "decisions": {},
            "feature_decisions": {},
            "artifacts": {},
            "feature_artifacts": {},
            "evidence": {},
            "feature_evidence": {},
            "dependencies": {},
            "feature_dependencies": {},
        }

    def _read(self) -> dict:
        with self.path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        for key, default_value in self._empty_payload().items():
            payload.setdefault(key, default_value)
        return payload

    def _write(self, payload: dict) -> None:
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        temp_path.replace(self.path)

    def upsert_feature(
        self,
        feature_id: str | None,
        title: str,
        summary: str,
        status: str,
        owner: str | None,
        stakeholders: list[str] | None,
        source_refs: list[str] | None,
    ) -> Feature:
        payload = self._read()
        features = payload["features"]

        if feature_id and feature_id in features:
            raw_feature = features[feature_id]
            raw_feature["title"] = title
            raw_feature["summary"] = summary
            raw_feature["status"] = status
            raw_feature["owner"] = owner
            raw_feature["stakeholders"] = stakeholders or []
            raw_feature["source_refs"] = source_refs or []
            raw_feature["updated_at"] = utc_now_iso()
            feature = Feature(**raw_feature)
        else:
            feature = Feature.create(
                title=title,
                summary=summary,
                status=status,
                owner=owner,
                stakeholders=stakeholders,
                source_refs=source_refs,
            )
            feature_id = feature.feature_id

        features[feature_id] = feature.to_dict()
        payload.setdefault("feature_decisions", {}).setdefault(feature_id, [])
        payload.setdefault("feature_artifacts", {}).setdefault(feature_id, [])
        payload.setdefault("feature_evidence", {}).setdefault(feature_id, [])
        payload.setdefault("feature_dependencies", {}).setdefault(feature_id, [])
        self._write(payload)
        return feature

    def get_feature(self, feature_id: str) -> Feature | None:
        payload = self._read()
        raw_feature = payload["features"].get(feature_id)
        if not raw_feature:
            return None
        return Feature(**raw_feature)

    def add_decision(
        self,
        feature_id: str,
        decision_text: str,
        made_by: str | None,
        rationale: str | None,
        evidence_ids: list[str] | None,
        source_refs: list[str] | None,
        decision_date: str | None,
    ) -> Decision:
        payload = self._read()
        if feature_id not in payload["features"]:
            raise KeyError(f"Unknown feature_id: {feature_id}")

        decision = Decision.create(
            feature_id=feature_id,
            decision_text=decision_text,
            made_by=made_by,
            rationale=rationale,
            evidence_ids=evidence_ids,
            source_refs=source_refs,
            decision_date=decision_date,
        )
        payload["decisions"][decision.decision_id] = asdict(decision)
        payload.setdefault("feature_decisions", {}).setdefault(feature_id, []).append(decision.decision_id)
        payload["features"][feature_id]["updated_at"] = utc_now_iso()
        self._write(payload)
        return decision

    def list_feature_decisions(self, feature_id: str) -> list[Decision]:
        payload = self._read()
        decision_ids = payload.setdefault("feature_decisions", {}).get(feature_id, [])
        return [Decision(**payload["decisions"][decision_id]) for decision_id in decision_ids]

    def record_artifact(
        self,
        feature_id: str,
        source_type: str,
        source_id: str,
        title: str,
        content: str,
        author: str | None,
        url: str | None,
    ) -> Artifact:
        payload = self._read()
        if feature_id not in payload["features"]:
            raise KeyError(f"Unknown feature_id: {feature_id}")

        artifact = Artifact.create(
            feature_id=feature_id,
            source_type=source_type,
            source_id=source_id,
            title=title,
            content=content,
            author=author,
            url=url,
        )
        payload["artifacts"][artifact.artifact_id] = artifact.to_dict()
        payload.setdefault("feature_artifacts", {}).setdefault(feature_id, []).append(artifact.artifact_id)
        payload["features"][feature_id]["updated_at"] = utc_now_iso()
        self._write(payload)
        return artifact

    def list_feature_artifacts(self, feature_id: str) -> list[Artifact]:
        payload = self._read()
        artifact_ids = payload.setdefault("feature_artifacts", {}).get(feature_id, [])
        return [Artifact(**payload["artifacts"][artifact_id]) for artifact_id in artifact_ids]

    def add_evidence(self, feature_id: str, artifact_id: str, excerpt: str) -> Evidence:
        payload = self._read()
        if feature_id not in payload["features"]:
            raise KeyError(f"Unknown feature_id: {feature_id}")
        artifact = payload["artifacts"].get(artifact_id)
        if artifact is None:
            raise KeyError(f"Unknown artifact_id: {artifact_id}")
        if artifact["feature_id"] != feature_id:
            raise ValueError("Artifact does not belong to the supplied feature.")

        evidence = Evidence.create(feature_id=feature_id, artifact_id=artifact_id, excerpt=excerpt)
        payload["evidence"][evidence.evidence_id] = evidence.to_dict()
        payload.setdefault("feature_evidence", {}).setdefault(feature_id, []).append(evidence.evidence_id)
        payload["features"][feature_id]["updated_at"] = utc_now_iso()
        self._write(payload)
        return evidence

    def list_feature_evidence(self, feature_id: str) -> list[Evidence]:
        payload = self._read()
        evidence_ids = payload.setdefault("feature_evidence", {}).get(feature_id, [])
        return [Evidence(**payload["evidence"][evidence_id]) for evidence_id in evidence_ids]

    def add_dependency(
        self,
        feature_id: str,
        dependency_type: str,
        target_name: str,
        status: str,
        notes: str | None,
        source_refs: list[str] | None,
    ) -> Dependency:
        payload = self._read()
        if feature_id not in payload["features"]:
            raise KeyError(f"Unknown feature_id: {feature_id}")

        dependency = Dependency.create(
            feature_id=feature_id,
            dependency_type=dependency_type,
            target_name=target_name,
            status=status,
            notes=notes,
            source_refs=source_refs,
        )
        payload["dependencies"][dependency.dependency_id] = dependency.to_dict()
        payload.setdefault("feature_dependencies", {}).setdefault(feature_id, []).append(dependency.dependency_id)
        payload["features"][feature_id]["updated_at"] = utc_now_iso()
        self._write(payload)
        return dependency

    def list_feature_dependencies(self, feature_id: str) -> list[Dependency]:
        payload = self._read()
        dependency_ids = payload.setdefault("feature_dependencies", {}).get(feature_id, [])
        return [Dependency(**payload["dependencies"][dependency_id]) for dependency_id in dependency_ids]

    def list_features(self) -> list[Feature]:
        payload = self._read()
        return [Feature(**raw_feature) for raw_feature in payload["features"].values()]

    def find_feature_by_source_ref(self, source_ref: str) -> Feature | None:
        payload = self._read()
        for raw_feature in payload["features"].values():
            if source_ref in raw_feature.get("source_refs", []):
                return Feature(**raw_feature)
        return None

    def get_feature_memory(self, feature_id: str) -> dict:
        feature = self.get_feature(feature_id)
        if feature is None:
            raise KeyError(f"Unknown feature_id: {feature_id}")

        decisions = [asdict(item) for item in self.list_feature_decisions(feature_id)]
        dependencies = [asdict(item) for item in self.list_feature_dependencies(feature_id)]
        artifacts = [asdict(item) for item in self.list_feature_artifacts(feature_id)]
        evidence = [asdict(item) for item in self.list_feature_evidence(feature_id)]

        return {
            "feature": asdict(feature),
            "decisions": decisions,
            "dependencies": dependencies,
            "artifacts": artifacts,
            "evidence": evidence,
            "counts": {
                "decisions": len(decisions),
                "dependencies": len(dependencies),
                "artifacts": len(artifacts),
                "evidence": len(evidence),
            },
        }

    def get_feature_graph(self, feature_id: str) -> dict:
        memory = self.get_feature_memory(feature_id)
        feature = memory["feature"]
        decisions = memory["decisions"]
        dependencies = memory["dependencies"]
        artifacts = memory["artifacts"]
        evidence = memory["evidence"]

        nodes: list[dict] = [
            {
                "id": feature["feature_id"],
                "type": "feature",
                "label": feature["title"],
                "attributes": {
                    "status": feature["status"],
                    "owner": feature["owner"],
                    "summary": feature["summary"],
                },
            }
        ]
        edges: list[dict] = []

        for stakeholder in feature["stakeholders"]:
            stakeholder_id = f"stakeholder:{stakeholder}"
            nodes.append(
                {
                    "id": stakeholder_id,
                    "type": "stakeholder",
                    "label": stakeholder,
                    "attributes": {},
                }
            )
            edges.append(
                {
                    "type": "involves",
                    "from": feature["feature_id"],
                    "to": stakeholder_id,
                }
            )

        artifact_map = {artifact["artifact_id"]: artifact for artifact in artifacts}
        for artifact in artifacts:
            nodes.append(
                {
                    "id": artifact["artifact_id"],
                    "type": "artifact",
                    "label": artifact["title"],
                    "attributes": {
                        "source_type": artifact["source_type"],
                        "source_id": artifact["source_id"],
                        "url": artifact["url"],
                    },
                }
            )
            edges.append(
                {
                    "type": "described_in",
                    "from": feature["feature_id"],
                    "to": artifact["artifact_id"],
                }
            )

        for decision in decisions:
            nodes.append(
                {
                    "id": decision["decision_id"],
                    "type": "decision",
                    "label": decision["decision_text"],
                    "attributes": {
                        "made_by": decision["made_by"],
                        "decision_date": decision["decision_date"],
                    },
                }
            )
            edges.append(
                {
                    "type": "has_decision",
                    "from": feature["feature_id"],
                    "to": decision["decision_id"],
                }
            )
            if decision["made_by"]:
                stakeholder_id = f"stakeholder:{decision['made_by']}"
                if not any(node["id"] == stakeholder_id for node in nodes):
                    nodes.append(
                        {
                            "id": stakeholder_id,
                            "type": "stakeholder",
                            "label": decision["made_by"],
                            "attributes": {},
                        }
                    )
                edges.append(
                    {
                        "type": "made_by",
                        "from": decision["decision_id"],
                        "to": stakeholder_id,
                    }
                )
            for evidence_id in decision["evidence_ids"]:
                edges.append(
                    {
                        "type": "supported_by",
                        "from": decision["decision_id"],
                        "to": evidence_id,
                    }
                )

        for dependency in dependencies:
            nodes.append(
                {
                    "id": dependency["dependency_id"],
                    "type": "dependency",
                    "label": dependency["target_name"],
                    "attributes": {
                        "dependency_type": dependency["dependency_type"],
                        "status": dependency["status"],
                    },
                }
            )
            edges.append(
                {
                    "type": "depends_on",
                    "from": feature["feature_id"],
                    "to": dependency["dependency_id"],
                }
            )

        for evidence_item in evidence:
            artifact = artifact_map.get(evidence_item["artifact_id"])
            nodes.append(
                {
                    "id": evidence_item["evidence_id"],
                    "type": "evidence",
                    "label": evidence_item["excerpt"],
                    "attributes": {
                        "artifact_id": evidence_item["artifact_id"],
                        "source_title": artifact["title"] if artifact else None,
                    },
                }
            )
            edges.append(
                {
                    "type": "evidenced_by",
                    "from": feature["feature_id"],
                    "to": evidence_item["evidence_id"],
                }
            )
            edges.append(
                {
                    "type": "evidence_from",
                    "from": evidence_item["evidence_id"],
                    "to": evidence_item["artifact_id"],
                }
            )

        return {
            "feature_id": feature_id,
            "nodes": nodes,
            "edges": edges,
            "counts": {
                "nodes": len(nodes),
                "edges": len(edges),
            },
        }

    def render_feature_graph_text(self, feature_id: str) -> str:
        graph = self.get_feature_graph(feature_id)
        lines = ["# Feature Decision Graph", ""]
        lines.append("## Nodes")
        for node in graph["nodes"]:
            lines.append(f"- [{node['type']}] {node['id']} :: {node['label']}")
        lines.extend(["", "## Edges"])
        for edge in graph["edges"]:
            lines.append(f"- {edge['from']} -[{edge['type']}]-> {edge['to']}")
        return "\n".join(lines)

    def render_feature_memory_page(self, feature_id: str) -> str:
        memory = self.get_feature_memory(feature_id)
        feature = memory["feature"]
        decisions = memory["decisions"]
        dependencies = memory["dependencies"]
        artifacts = memory["artifacts"]

        stakeholders = ", ".join(feature["stakeholders"]) if feature["stakeholders"] else "None recorded"
        lines = [
            f"# Feature Memory: {feature['title']}",
            "",
            "## Current State",
            f"- Feature ID: `{feature['feature_id']}`",
            f"- Status: {feature['status']}",
            f"- Owner: {feature['owner'] or 'Unassigned'}",
            f"- Stakeholders: {stakeholders}",
            f"- Updated At: {feature['updated_at']}",
            "",
            "## Summary",
            feature["summary"],
            "",
            "## Decision Timeline",
        ]

        if decisions:
            for decision in decisions:
                lines.extend(
                    [
                        f"- {decision['decision_date']}: {decision['decision_text']}",
                        f"  Made by: {decision['made_by'] or 'Unknown'}",
                        f"  Rationale: {decision['rationale'] or 'Not recorded'}",
                        f"  Evidence IDs: {', '.join(decision['evidence_ids']) if decision['evidence_ids'] else 'None'}",
                    ]
                )
        else:
            lines.append("- No decisions recorded.")

        lines.extend(["", "## Dependencies"])
        if dependencies:
            for dependency in dependencies:
                lines.append(
                    f"- [{dependency['status']}] {dependency['dependency_type']}: {dependency['target_name']}"
                )
        else:
            lines.append("- No dependencies recorded.")

        lines.extend(["", "## Supporting Artifacts"])
        if artifacts:
            for artifact in artifacts:
                source_label = f"{artifact['source_type']}:{artifact['source_id']}"
                suffix = f" ({artifact['url']})" if artifact["url"] else ""
                lines.append(f"- {artifact['title']} [{source_label}]{suffix}")
        else:
            lines.append("- No supporting artifacts recorded.")

        return "\n".join(lines)
