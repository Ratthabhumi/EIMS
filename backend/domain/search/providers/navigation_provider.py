"""
==============================================================================
EIMS Query Layer - Navigation & Operational Command Provider
Governed by EIMS Documentation System (EDS v1.0.0) - Core Law 5 Compliance
Source-Available All Rights Reserved Policy
==============================================================================
"""

from dataclasses import dataclass
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from backend.domain.search.provider import SearchProvider, SearchResult


@dataclass(frozen=True)
class NavigationRoute:
    id: str
    title: str
    subtitle: str
    url: str
    keywords: tuple[str, ...]


# Canonical catalogue of verified operational routes across the EIMS application
_CANONICAL_ROUTES: tuple[NavigationRoute, ...] = (
    NavigationRoute(
        id="nav-home",
        title="Home Portal",
        subtitle="Operational overview, quick metrics, and system activity",
        url="/",
        keywords=("home", "portal", "dashboard", "overview", "main", "summary", "stats", "index"),
    ),
    NavigationRoute(
        id="nav-endpoints",
        title="Asset Registry & Endpoints",
        subtitle="Hardware nodes, endpoint inventory, compliance scores, and lifecycle states",
        url="/endpoints",
        keywords=("asset", "assets", "endpoint", "endpoints", "inventory", "hardware", "nodes", "servers", "compliance", "host"),
    ),
    NavigationRoute(
        id="nav-usb-auditor",
        title="USB Auditor",
        subtitle="Offline USB auditor reports, hardware specifications, and system diagnostics",
        url="/endpoints",
        keywords=("usb", "usb auditor", "auditor", "removable media", "offline audit", "usb evidence", "flash drive"),
    ),
    NavigationRoute(
        id="nav-timeline",
        title="Unified Timeline",
        subtitle="Chronological audit, telemetry, and Windows security event timeline",
        url="/timeline",
        keywords=("timeline", "events", "audit log", "history", "chronological", "event log", "stream", "activity"),
    ),
    NavigationRoute(
        id="nav-analyzer",
        title="AI Log Analyzer",
        subtitle="AI-assisted incident analysis, log inspection, and anomaly detection",
        url="/analyzer",
        keywords=("analyzer", "ai log analyzer", "ai", "llm", "analysis", "incident", "investigate", "log analysis", "ai summary"),
    ),
    NavigationRoute(
        id="nav-evaluations-admin",
        title="Service Evaluations Admin",
        subtitle="Customer satisfaction sessions, evaluation templates, and engineer performance",
        url="/evaluations/admin",
        keywords=("evaluation", "evaluations", "service evaluation", "feedback", "rating", "csat", "survey", "session", "admin"),
    ),
    NavigationRoute(
        id="nav-evaluate",
        title="Service Evaluation Form",
        subtitle="Customer evaluation submission portal via QR Code / direct link",
        url="/evaluate",
        keywords=("evaluate", "survey form", "customer feedback", "rating form", "qr code"),
    ),
    NavigationRoute(
        id="nav-agents",
        title="Client Agents & Collectors",
        subtitle="Endpoint telemetry agents, background services, and executable launchers",
        url="/agents",
        keywords=("agent", "agents", "client agents", "collector", "collectors", "daemon", "service", "heartbeat"),
    ),
    NavigationRoute(
        id="nav-ocr-history",
        title="Sticker OCR & Hardware Recognition",
        subtitle="Asset barcode, serial number sticker OCR extraction history",
        url="/ocr-history",
        keywords=("ocr", "sticker", "sticker ocr", "ocr history", "scanner", "barcode", "label", "tesseract", "extraction"),
    ),
    NavigationRoute(
        id="nav-observability",
        title="Observability & System Vitals",
        subtitle="Live telemetry streams, host CPU/RAM vitals, and anomaly alerts",
        url="/observability",
        keywords=("observability", "metrics", "alerts", "telemetry", "vitals", "streams", "monitoring", "cpu", "ram", "gpu"),
    ),
    NavigationRoute(
        id="nav-settings",
        title="System Settings",
        subtitle="Platform configuration, appearance, auth mode, and connection parameters",
        url="/settings",
        keywords=("settings", "preferences", "config", "configuration", "theme", "appearance"),
    ),
)


class NavigationSearchProvider(SearchProvider):
    """
    Command-center navigation provider discovering first-class EIMS operational
    pages by route title, description, and curated operational aliases.
    Always assigns `result_kind='navigation'`.
    """
    name = "navigation"

    async def search(self, db: AsyncSession, query: str, limit: int) -> list[SearchResult]:
        q = query.strip().lower()
        if not q:
            return []

        scored: list[tuple[float, NavigationRoute]] = []
        for route in _CANONICAL_ROUTES:
            relevance = self._score_route(route, q)
            if relevance > 0.0:
                scored.append((relevance, route))

        # Highest relevance first
        scored.sort(key=lambda item: item[0], reverse=True)

        results: list[SearchResult] = []
        for relevance, route in scored[:limit]:
            results.append(
                SearchResult(
                    type=self.name,
                    id=route.id,
                    title=route.title,
                    subtitle=route.subtitle,
                    url=route.url,
                    timestamp=None,
                    relevance=relevance,
                    result_kind="navigation",
                    metadata={
                        "keywords": list(route.keywords),
                        "route": route.url,
                    },
                )
            )
        return results

    @staticmethod
    def _score_route(route: NavigationRoute, query: str) -> float:
        title_lower = route.title.lower()
        url_lower = route.url.lower()

        # 1. Exact match on title or keywords
        if query == title_lower:
            return 1.00
        for kw in route.keywords:
            if query == kw:
                return 1.00

        # 2. Prefix match on title or keywords
        if title_lower.startswith(query):
            return 0.95
        for kw in route.keywords:
            if kw.startswith(query):
                return 0.92

        # 3. Substring match on keywords or title
        for kw in route.keywords:
            if query in kw:
                return 0.85
        if query in title_lower:
            return 0.82

        # 4. Path match
        if query in url_lower:
            return 0.80

        # 5. Description match
        if query in route.subtitle.lower():
            return 0.70

        return 0.0
