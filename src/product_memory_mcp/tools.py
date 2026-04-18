from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from product_memory_mcp.ingest import IngestionService
from product_memory_mcp.integrations import (
    AtlassianAPI,
    AtlassianConfig,
    ConfluenceIntegration,
    IntegrationError,
    JiraIntegration,
)
from product_memory_mcp.store import ProductMemoryStore


class ToolError(Exception):
    pass


class ProductMemoryTools:
    def __init__(self, store: ProductMemoryStore) -> None:
        self.store = store
        self.ingestion = IngestionService(store)
        self._jira_integration: JiraIntegration | None = None
        self._confluence_integration: ConfluenceIntegration | None = None

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "health_check",
                "description": "Return server health and storage readiness.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "get_atlassian_integration_status",
                "description": "Report whether Atlassian credentials are configured for Jira and Confluence sync.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "upsert_feature",
                "description": "Create or update a feature memory record.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string"},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "status": {"type": "string"},
                        "owner": {"type": "string"},
                        "stakeholders": {"type": "array", "items": {"type": "string"}},
                        "source_refs": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "summary"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_feature",
                "description": "Fetch a feature memory record by feature_id.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"feature_id": {"type": "string"}},
                    "required": ["feature_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "add_decision",
                "description": "Attach a decision to a feature memory record.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string"},
                        "decision_text": {"type": "string"},
                        "made_by": {"type": "string"},
                        "rationale": {"type": "string"},
                        "decision_date": {"type": "string"},
                        "evidence_ids": {"type": "array", "items": {"type": "string"}},
                        "source_refs": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["feature_id", "decision_text"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "record_artifact",
                "description": "Record a normalized source artifact such as a Jira ticket snapshot or Confluence page revision.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string"},
                        "source_type": {"type": "string"},
                        "source_id": {"type": "string"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "author": {"type": "string"},
                        "url": {"type": "string"},
                    },
                    "required": ["feature_id", "source_type", "source_id", "title", "content"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "add_evidence",
                "description": "Create evidence linked to an existing artifact.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string"},
                        "artifact_id": {"type": "string"},
                        "excerpt": {"type": "string"},
                    },
                    "required": ["feature_id", "artifact_id", "excerpt"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "add_dependency",
                "description": "Attach a dependency to a feature memory record.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string"},
                        "dependency_type": {"type": "string"},
                        "target_name": {"type": "string"},
                        "status": {"type": "string"},
                        "notes": {"type": "string"},
                        "source_refs": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["feature_id", "dependency_type", "target_name"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "list_feature_decisions",
                "description": "List decisions linked to a feature.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"feature_id": {"type": "string"}},
                    "required": ["feature_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_feature_memory",
                "description": "Return the structured feature memory bundle for a feature.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"feature_id": {"type": "string"}},
                    "required": ["feature_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "get_feature_graph",
                "description": "Return the graph-shaped context bundle for a feature, including nodes and edges.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"feature_id": {"type": "string"}},
                    "required": ["feature_id"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "ingest_jira_issue_event",
                "description": "Normalize a Jira issue update into feature memory, artifact, decisions, and dependencies.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string"},
                        "issue_key": {"type": "string"},
                        "summary": {"type": "string"},
                        "description": {"type": "string"},
                        "status": {"type": "string"},
                        "assignee": {"type": "string"},
                        "reporter": {"type": "string"},
                        "comments": {"type": "array", "items": {"type": "string"}},
                        "url": {"type": "string"},
                    },
                    "required": ["issue_key", "summary"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "ingest_confluence_page_event",
                "description": "Normalize a Confluence page update into feature memory, artifact, decisions, and dependencies.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string"},
                        "page_id": {"type": "string"},
                        "title": {"type": "string"},
                        "body": {"type": "string"},
                        "author": {"type": "string"},
                        "labels": {"type": "array", "items": {"type": "string"}},
                        "url": {"type": "string"},
                    },
                    "required": ["page_id", "title", "body"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "sync_jira_issue",
                "description": "Fetch a Jira issue from Atlassian and ingest it into product memory.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string"},
                        "issue_key": {"type": "string"},
                    },
                    "required": ["issue_key"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "sync_confluence_page",
                "description": "Fetch a Confluence page from Atlassian and ingest it into product memory.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "feature_id": {"type": "string"},
                        "page_id": {"type": "string"},
                    },
                    "required": ["page_id"],
                    "additionalProperties": False,
                },
            },
        ]

    def list_resources(self) -> list[dict[str, Any]]:
        resources = [
            {
                "uri": "memory://features",
                "name": "Feature Index",
                "description": "List all known feature memory entities.",
                "mimeType": "application/json",
            }
        ]
        for feature in self.store.list_features():
            resources.append(
                {
                    "uri": f"memory://feature/{feature.feature_id}",
                    "name": f"Feature Memory: {feature.title}",
                    "description": "Structured memory bundle for a feature.",
                    "mimeType": "application/json",
                }
            )
            resources.append(
                {
                    "uri": f"memory://feature/{feature.feature_id}/page",
                    "name": f"Feature Page: {feature.title}",
                    "description": "Rendered feature memory page in Markdown.",
                    "mimeType": "text/markdown",
                }
            )
            resources.append(
                {
                    "uri": f"memory://feature/{feature.feature_id}/graph",
                    "name": f"Feature Graph: {feature.title}",
                    "description": "Structured graph view for a feature.",
                    "mimeType": "application/json",
                }
            )
            resources.append(
                {
                    "uri": f"memory://feature/{feature.feature_id}/graph-text",
                    "name": f"Feature Graph Text: {feature.title}",
                    "description": "Text rendering of the feature decision graph.",
                    "mimeType": "text/markdown",
                }
            )
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "memory://features":
            payload = {
                "features": [asdict(feature) for feature in self.store.list_features()],
            }
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(payload, indent=2, sort_keys=True),
                    }
                ]
            }

        feature_id, mode = self._parse_feature_resource_uri(uri)
        if mode == "page":
            text = self.store.render_feature_memory_page(feature_id)
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/markdown",
                        "text": text,
                    }
                ]
            }
        if mode == "graph":
            payload = self.store.get_feature_graph(feature_id)
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(payload, indent=2, sort_keys=True),
                    }
                ]
            }
        if mode == "graph-text":
            text = self.store.render_feature_graph_text(feature_id)
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/markdown",
                        "text": text,
                    }
                ]
            }

        payload = self.store.get_feature_memory(feature_id)
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": json.dumps(payload, indent=2, sort_keys=True),
                }
            ]
        }

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        arguments = arguments or {}

        if name == "health_check":
            return self._success(
                {
                    "status": "ok",
                    "store_path": str(self.store.path),
                }
            )
        if name == "get_atlassian_integration_status":
            configured = self._atlassian_configured()
            return self._success(
                {
                    "configured": configured,
                    "required_env": [
                        "ATLASSIAN_BASE_URL",
                        "ATLASSIAN_EMAIL",
                        "ATLASSIAN_API_TOKEN",
                    ],
                }
            )
        if name == "upsert_feature":
            feature = self.store.upsert_feature(
                feature_id=arguments.get("feature_id"),
                title=self._require(arguments, "title"),
                summary=self._require(arguments, "summary"),
                status=arguments.get("status", "proposed"),
                owner=arguments.get("owner"),
                stakeholders=arguments.get("stakeholders"),
                source_refs=arguments.get("source_refs"),
            )
            return self._success(asdict(feature))
        if name == "get_feature":
            feature = self.store.get_feature(self._require(arguments, "feature_id"))
            if feature is None:
                raise ToolError("Feature not found.")
            return self._success(asdict(feature))
        if name == "add_decision":
            try:
                decision = self.store.add_decision(
                    feature_id=self._require(arguments, "feature_id"),
                    decision_text=self._require(arguments, "decision_text"),
                    made_by=arguments.get("made_by"),
                    rationale=arguments.get("rationale"),
                    evidence_ids=arguments.get("evidence_ids"),
                    source_refs=arguments.get("source_refs"),
                    decision_date=arguments.get("decision_date"),
                )
            except KeyError as exc:
                raise ToolError(str(exc)) from exc
            return self._success(asdict(decision))
        if name == "record_artifact":
            try:
                artifact = self.store.record_artifact(
                    feature_id=self._require(arguments, "feature_id"),
                    source_type=self._require(arguments, "source_type"),
                    source_id=self._require(arguments, "source_id"),
                    title=self._require(arguments, "title"),
                    content=self._require(arguments, "content"),
                    author=arguments.get("author"),
                    url=arguments.get("url"),
                )
            except KeyError as exc:
                raise ToolError(str(exc)) from exc
            return self._success(asdict(artifact))
        if name == "add_evidence":
            try:
                evidence = self.store.add_evidence(
                    feature_id=self._require(arguments, "feature_id"),
                    artifact_id=self._require(arguments, "artifact_id"),
                    excerpt=self._require(arguments, "excerpt"),
                )
            except (KeyError, ValueError) as exc:
                raise ToolError(str(exc)) from exc
            return self._success(asdict(evidence))
        if name == "add_dependency":
            try:
                dependency = self.store.add_dependency(
                    feature_id=self._require(arguments, "feature_id"),
                    dependency_type=self._require(arguments, "dependency_type"),
                    target_name=self._require(arguments, "target_name"),
                    status=arguments.get("status", "active"),
                    notes=arguments.get("notes"),
                    source_refs=arguments.get("source_refs"),
                )
            except KeyError as exc:
                raise ToolError(str(exc)) from exc
            return self._success(asdict(dependency))
        if name == "list_feature_decisions":
            decisions = self.store.list_feature_decisions(self._require(arguments, "feature_id"))
            return self._success({"feature_id": arguments["feature_id"], "decisions": [asdict(item) for item in decisions]})
        if name == "get_feature_memory":
            try:
                memory = self.store.get_feature_memory(self._require(arguments, "feature_id"))
            except KeyError as exc:
                raise ToolError(str(exc)) from exc
            return self._success(memory)
        if name == "get_feature_graph":
            try:
                graph = self.store.get_feature_graph(self._require(arguments, "feature_id"))
            except KeyError as exc:
                raise ToolError(str(exc)) from exc
            return self._success(graph)
        if name == "ingest_jira_issue_event":
            result = self.ingestion.ingest_jira_issue_event(
                issue_key=self._require(arguments, "issue_key"),
                summary=self._require(arguments, "summary"),
                description=arguments.get("description", ""),
                status=arguments.get("status"),
                assignee=arguments.get("assignee"),
                reporter=arguments.get("reporter"),
                comments=arguments.get("comments"),
                url=arguments.get("url"),
                feature_id=arguments.get("feature_id"),
            )
            return self._success(result)
        if name == "ingest_confluence_page_event":
            result = self.ingestion.ingest_confluence_page_event(
                page_id=self._require(arguments, "page_id"),
                title=self._require(arguments, "title"),
                body=self._require(arguments, "body"),
                author=arguments.get("author"),
                labels=arguments.get("labels"),
                url=arguments.get("url"),
                feature_id=arguments.get("feature_id"),
            )
            return self._success(result)
        if name == "sync_jira_issue":
            try:
                result = self._jira().sync_issue(
                    issue_key=self._require(arguments, "issue_key"),
                    feature_id=arguments.get("feature_id"),
                )
            except IntegrationError as exc:
                raise ToolError(str(exc)) from exc
            return self._success(result)
        if name == "sync_confluence_page":
            try:
                result = self._confluence().sync_page(
                    page_id=self._require(arguments, "page_id"),
                    feature_id=arguments.get("feature_id"),
                )
            except IntegrationError as exc:
                raise ToolError(str(exc)) from exc
            return self._success(result)

        raise ToolError(f"Unknown tool: {name}")

    def _require(self, arguments: dict[str, Any], key: str) -> Any:
        value = arguments.get(key)
        if value in (None, ""):
            raise ToolError(f"Missing required argument: {key}")
        return value

    def _success(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(payload, indent=2, sort_keys=True),
                }
            ],
            "structuredContent": payload,
        }

    def _parse_feature_resource_uri(self, uri: str) -> tuple[str, str]:
        prefix = "memory://feature/"
        if not uri.startswith(prefix):
            raise ToolError(f"Unknown resource URI: {uri}")
        suffix = uri[len(prefix):]
        if suffix.endswith("/page"):
            feature_id = suffix[:-5]
            mode = "page"
        elif suffix.endswith("/graph-text"):
            feature_id = suffix[:-11]
            mode = "graph-text"
        elif suffix.endswith("/graph"):
            feature_id = suffix[:-6]
            mode = "graph"
        else:
            feature_id = suffix
            mode = "json"
        if not feature_id:
            raise ToolError(f"Invalid feature resource URI: {uri}")
        return feature_id, mode

    def _atlassian_configured(self) -> bool:
        try:
            AtlassianConfig.from_env()
        except IntegrationError:
            return False
        return True

    def _jira(self) -> JiraIntegration:
        if self._jira_integration is None:
            config = AtlassianConfig.from_env()
            api = AtlassianAPI(config)
            self._jira_integration = JiraIntegration(api, self.ingestion)
        return self._jira_integration

    def _confluence(self) -> ConfluenceIntegration:
        if self._confluence_integration is None:
            config = AtlassianConfig.from_env()
            api = AtlassianAPI(config)
            self._confluence_integration = ConfluenceIntegration(api, self.ingestion)
        return self._confluence_integration
