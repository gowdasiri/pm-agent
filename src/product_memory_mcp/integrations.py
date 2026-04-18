from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from product_memory_mcp.ingest import IngestionService


class IntegrationError(Exception):
    pass


@dataclass
class AtlassianConfig:
    base_url: str
    email: str
    api_token: str

    @classmethod
    def from_env(cls) -> "AtlassianConfig":
        base_url = os.environ.get("ATLASSIAN_BASE_URL", "").strip().rstrip("/")
        email = os.environ.get("ATLASSIAN_EMAIL", "").strip()
        api_token = os.environ.get("ATLASSIAN_API_TOKEN", "").strip()
        if not base_url or not email or not api_token:
            raise IntegrationError(
                "Missing Atlassian credentials. Set ATLASSIAN_BASE_URL, ATLASSIAN_EMAIL, and ATLASSIAN_API_TOKEN."
            )
        return cls(base_url=base_url, email=email, api_token=api_token)

    def authorization_header(self) -> str:
        raw = f"{self.email}:{self.api_token}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")


class _HTMLToTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.parts.append(value)

    def text(self) -> str:
        return "\n".join(self.parts)


def extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        node_type = value.get("type")
        if node_type == "text":
            return value.get("text", "")
        content = value.get("content")
        if isinstance(content, list):
            parts = [extract_text(item) for item in content]
            joined = "\n".join(part for part in parts if part)
            if node_type in {"paragraph", "heading", "listItem"}:
                return joined
            return joined
        for key in ("value", "text"):
            if isinstance(value.get(key), str):
                return value[key]
        return ""
    if isinstance(value, list):
        return "\n".join(part for part in (extract_text(item) for item in value) if part)
    return str(value)


def html_to_text(html: str) -> str:
    parser = _HTMLToTextParser()
    parser.feed(html)
    parser.close()
    return parser.text()


class AtlassianAPI:
    def __init__(
        self,
        config: AtlassianConfig,
        fetcher: Callable[[Request], Any] | None = None,
    ) -> None:
        self.config = config
        self.fetcher = fetcher or urlopen

    def get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        request = Request(
            url,
            headers={
                "Authorization": self.config.authorization_header(),
                "Accept": "application/json",
            },
        )
        try:
            with self.fetcher(request) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            raise IntegrationError(f"Atlassian API returned HTTP {exc.code} for {url}.") from exc
        except URLError as exc:
            raise IntegrationError(f"Unable to reach Atlassian API at {url}: {exc.reason}") from exc
        return json.loads(payload)


class JiraIntegration:
    def __init__(self, api: AtlassianAPI, ingestion: IngestionService) -> None:
        self.api = api
        self.ingestion = ingestion

    def sync_issue(self, issue_key: str, feature_id: str | None) -> dict[str, Any]:
        path = (
            f"/rest/api/3/issue/{quote(issue_key)}"
            "?fields=summary,description,status,assignee,reporter,comment"
        )
        payload = self.api.get_json(path)
        fields = payload.get("fields", {})

        comments = [
            extract_text(comment.get("body"))
            for comment in fields.get("comment", {}).get("comments", [])
            if extract_text(comment.get("body"))
        ]

        result = self.ingestion.ingest_jira_issue_event(
            issue_key=payload.get("key", issue_key),
            summary=fields.get("summary") or issue_key,
            description=extract_text(fields.get("description")),
            status=(fields.get("status") or {}).get("name"),
            assignee=(fields.get("assignee") or {}).get("emailAddress") or (fields.get("assignee") or {}).get("displayName"),
            reporter=(fields.get("reporter") or {}).get("emailAddress") or (fields.get("reporter") or {}).get("displayName"),
            comments=comments,
            url=f"{self.api.config.base_url}/browse/{payload.get('key', issue_key)}",
            feature_id=feature_id,
        )
        result["integration"] = {"source": "jira", "issue_key": payload.get("key", issue_key)}
        return result


class ConfluenceIntegration:
    def __init__(self, api: AtlassianAPI, ingestion: IngestionService) -> None:
        self.api = api
        self.ingestion = ingestion

    def sync_page(self, page_id: str, feature_id: str | None) -> dict[str, Any]:
        path = f"/wiki/rest/api/content/{quote(page_id)}?expand=body.storage,metadata.labels,version"
        payload = self.api.get_json(path)
        labels = [item.get("name", "") for item in payload.get("metadata", {}).get("labels", {}).get("results", [])]
        body_html = payload.get("body", {}).get("storage", {}).get("value", "")
        body_text = html_to_text(body_html)
        result = self.ingestion.ingest_confluence_page_event(
            page_id=payload.get("id", page_id),
            title=payload.get("title") or page_id,
            body=body_text,
            author=((payload.get("version") or {}).get("by") or {}).get("email") or ((payload.get("version") or {}).get("by") or {}).get("displayName"),
            labels=[label for label in labels if label],
            url=f"{self.api.config.base_url}/wiki{payload.get('_links', {}).get('webui', '')}" if payload.get("_links", {}).get("webui") else None,
            feature_id=feature_id,
        )
        result["integration"] = {"source": "confluence", "page_id": payload.get("id", page_id)}
        return result
