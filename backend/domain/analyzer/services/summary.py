import re
from typing import List, Optional, Tuple
from urllib.parse import urlparse
import json
import requests
from sqlalchemy.ext.asyncio import AsyncSession

from deep_translator import GoogleTranslator
from duckduckgo_search import DDGS

from backend.domain.analyzer.schemas.analyze import SearchResult, SolutionSummary
from backend.domain.analyzer.services.event_knowledge import get_curated_summary
from backend.domain.analyzer.services.vector_db import search_similar_logs
from backend.domain.analyzer.services.vendor_knowledge import (
    get_vendor_summary,
    vendor_reference_results,
)
from backend.domain.analyzer.services.vendor_parsers import is_vendor_diagnostic_code

ACTION_KEYWORDS = re.compile(
    r"\b(fix|resolve|open|run|enable|disable|restart|check|configure|set|modify|"
    r"update|install|reinstall|grant|allow|edit|navigate|click|select|type|enter|"
    r"right-click|registry|services\.msc|dcomcnfg|gpedit|powershell|cmd)\b",
    re.IGNORECASE,
)
CAUSE_KEYWORDS = re.compile(
    r"\b(because|due to|caused by|happens when|occurs when|issue in which|"
    r"problem is|reason|when a|permission settings do not grant)\b",
    re.IGNORECASE,
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
SKIP_PATTERNS = re.compile(
    r"\b(i use|i noticed|i have|my computer|my server|what i.?ve done|saw this error|"
    r"thank you|specs:|windows 11|windows 10|intel vga|nvidia|reset the pc|"
    r"faq|question|how to fix\?|this tutorial|go through the faq|"
    r"i recommend|you may need|however, if you see|"
    r"log name:|source:|date:|event id:|level:|computer:|description:|task category:|user:|keyword:)\b",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(
    r"\b(?:january|february|march|april|may|june|july|august|september|october|"
    r"november|december|\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))\b",
    re.IGNORECASE,
)

OFFICIAL_DOMAINS = (
    "learn.microsoft.com",
    "support.microsoft.com",
    "docs.microsoft.com",
)

# Vendor-owned documentation domains per source family.  Only these may
# ever be labeled "official"; everything else is "community".
FAMILY_OFFICIAL_DOMAINS = {
    "windows_event": (
        "learn.microsoft.com",
        "support.microsoft.com",
        "docs.microsoft.com",
    ),
    "veeam_vbr": (
        "helpcenter.veeam.com",
        "veeam.com",
        "www.veeam.com",
        "knowledge.broadcom.com",
        "support.broadcom.com",
    ),
    "vmware": (
        "knowledge.broadcom.com",
        "support.broadcom.com",
        "kb.vmware.com",
    ),
    "cisco_asa": (
        "cisco.com",
    ),
    "fortinet": (
        "docs.fortinet.com",
        "fortinet.com",
    ),
}

# Vendor documentation roots used as fallback references (roots only so no
# deep article URL is ever fabricated).
FAMILY_FALLBACK_REFS = {
    "veeam_vbr": [
        ("Veeam Help Center: Backup & Replication documentation", "https://helpcenter.veeam.com/"),
        ("Veeam: Backup & Replication knowledge and support", "https://www.veeam.com/"),
        ("Broadcom Support (VMware subsystem reference)", "https://support.broadcom.com/"),
    ],
    "vmware": [
        ("Broadcom Support: VMware troubleshooting", "https://support.broadcom.com/"),
    ],
    "cisco_asa": [
        ("Cisco: ASA documentation and troubleshooting", "https://www.cisco.com/"),
        ("Cisco Community discussions", "https://community.cisco.com/"),
    ],
    "fortinet": [
        ("Fortinet Docs: FortiGate troubleshooting", "https://docs.fortinet.com/"),
        ("Fortinet Community discussions", "https://community.fortinet.com/"),
    ],
    "linux_syslog": [],
    "json": [],
}

# DDGS site-restricted tiers per source family (query, tier).
FAMILY_SEARCH_TIERS = {
    "windows_event": (
        ("official", "site:learn.microsoft.com troubleshoot"),
        ("official", "site:support.microsoft.com"),
        ("community", "site:stackoverflow.com OR site:superuser.com"),
    ),
    "veeam_vbr": (
        ("official", "site:helpcenter.veeam.com"),
        ("official", "site:support.broadcom.com"),
        ("community", "site:forums.veeam.com"),
    ),
    "vmware": (
        ("official", "site:support.broadcom.com"),
        ("official", "site:kb.vmware.com"),
        ("community", "site:communities.vmware.com"),
    ),
    "cisco_asa": (
        ("official", "site:cisco.com"),
        ("community", "site:community.cisco.com"),
    ),
    "fortinet": (
        ("official", "site:docs.fortinet.com"),
        ("community", "site:community.fortinet.com"),
    ),
    "linux_syslog": (),
    "json": (),
}

SEARCH_TIERS = FAMILY_SEARCH_TIERS["windows_event"]


def _host_matches(domain: str, expected: str) -> bool:
    d = (domain or "").lower()
    e = (expected or "").lower()
    if not d or not e:
        return False
    if d == e:
        return True
    if d.endswith("." + e):
        return True
    return False


FAMILY_COMMUNITY_DOMAINS = {
    "windows_event": ("stackoverflow.com", "superuser.com", "answers.microsoft.com"),
    "veeam_vbr": ("forums.veeam.com",),
    "vmware": ("communities.vmware.com",),
    "cisco_asa": ("community.cisco.com",),
    "fortinet": ("community.fortinet.com",),
}


def _classify_source(link: str, tier: str, official_domains=None, community_domains=None) -> str:
    """Classify a search result URL by its hostname.

    STRICT ALLOWLIST: if the domain is not in the official or community
    allowlist for this family, the result is DROPPED by the caller.  This
    function signals a "drop" by returning the sentinel value "REJECT".
    Results labeled "REJECT" must be discarded before being added to
    SearchResult lists.
    """
    domain = urlparse(link).netloc.lower()
    community = tuple(community_domains) if community_domains else tuple()
    allowed = tuple(official_domains) if official_domains else OFFICIAL_DOMAINS

    if community and any(_host_matches(domain, c) for c in community):
        return "community"
    if any(_host_matches(domain, off) for off in allowed):
        return "official"
    # Domain is not in the allowlist for this family — reject it.
    return "REJECT"


def _family_query(event_id: str, provider: str, source_family: str) -> str:
    """Build a vendor-appropriate web query.  Never Windows-wash vendors."""
    if source_family == "veeam_vbr":
        code = event_id if event_id and event_id != "Unknown" else "replication snapshot"
        return f"Veeam Backup Replication {code}"
    if source_family == "vmware":
        code = event_id if event_id and event_id != "Unknown" else "ESXi snapshot"
        return f"VMware ESXi {code}"
    if source_family == "cisco_asa":
        return f"Cisco ASA {event_id} {provider}"
    if source_family == "fortinet":
        return f"FortiGate {event_id} {provider}"
    if source_family in ("linux_syslog", "json"):
        return f"{provider} {event_id} syslog"
    provider_part = provider if provider not in ("Unknown", "DistributedCOM") else "DCOM"
    return f"Windows Event ID {event_id} {provider_part} learn.microsoft.com"


def search_solutions(
    event_id: str,
    provider: str,
    source_family: str | None = None,
    diagnostic_code: str | None = None,
    evidence_text: str = "",
    product: str = "",
    language: str = "th",
) -> tuple[List[SearchResult], str]:
    family = source_family or "windows_event"

    # Unknown sources must NOT run blind Windows searches.
    if family == "unknown_text":
        return [], ""

    results: List[SearchResult] = []
    combined_snippets = ""
    seen_links = set()

    def _canonical_url(url: str) -> str:
        u = (url or "").strip().lower()
        if u.endswith("/"):
            u = u[:-1]
        return u

    # 1. Deterministic gated KB official references (highest priority)
    kb_refs: List[SearchResult] = []
    if diagnostic_code:
        try:
            raw_kb = vendor_reference_results(diagnostic_code, evidence_text or "", language) or []
            for r in raw_kb:
                can_link = _canonical_url(r.link)
                if can_link and can_link not in seen_links:
                    seen_links.add(can_link)
                    kb_refs.append(r)
                    if r.snippet:
                        combined_snippets += f"{r.snippet}\n"
        except Exception:
            pass

    tiers = FAMILY_SEARCH_TIERS.get(family, ())
    official_domains = FAMILY_OFFICIAL_DOMAINS.get(family, OFFICIAL_DOMAINS)
    community_domains = FAMILY_COMMUNITY_DOMAINS.get(family, ())
    base_query = _family_query(event_id, provider, family)

    # 2. Live web search results
    web_results: List[SearchResult] = []
    if tiers:
        try:
            for tier, site in tiers:
                if len(web_results) >= 6:
                    break
                query = f"{base_query} {site}"
                with DDGS(timeout=3) as ddgs:
                    raw = list(ddgs.text(query, max_results=4))
                    for item in raw:
                        title = (item.get("title") or "").strip()
                        link = (item.get("href") or item.get("url") or "").strip()
                        snippet = (item.get("body") or item.get("snippet") or "").strip()
                        can_link = _canonical_url(link)
                        if not link or not can_link or can_link in seen_links:
                            continue
                        source_type = _classify_source(link, tier, official_domains, community_domains)
                        # STRICT: reject any result from an unlisted domain.
                        if source_type == "REJECT":
                            continue
                        seen_links.add(can_link)
                        web_results.append(
                            SearchResult(
                                title=title,
                                link=link,
                                snippet=snippet,
                                sourceType=source_type,  # type: ignore[arg-type]
                            )
                        )
                        if snippet:
                            combined_snippets += f"{snippet}\n"
                        if len(web_results) >= 6:
                            break
        except Exception:
            pass

    # 3. Fallback references (if needed)
    fallback_results: List[SearchResult] = []
    default_fallbacks_list = []
    family_fallbacks = FAMILY_FALLBACK_REFS.get(family, None)
    if family_fallbacks:
        default_fallbacks_list = [
            SearchResult(
                title=title,
                link=link,
                snippet=f"Vendor documentation starting point for {provider or family} diagnostics.",
                sourceType=_classify_source(link, "community", official_domains, community_domains),  # type: ignore[arg-type]
            )
            for title, link in family_fallbacks
        ]
    elif family == "windows_event":
        default_fallbacks_list = [
            SearchResult(
                title=f"Microsoft Learn: Troubleshoot Event ID {event_id}",
                link=f"https://learn.microsoft.com/en-us/search/?terms=Event%20ID%20{event_id}",
                snippet="Official Microsoft documentation and troubleshooting guide for this Windows Event ID.",
                sourceType="official",
            ),
            SearchResult(
                title=f"Windows Support: {provider} Diagnostics & Solutions",
                link=f"https://support.microsoft.com/en-us/search?query=Windows%20Event%20{event_id}",
                snippet="Search knowledge base articles, known issues, and recovery steps on Microsoft Support.",
                sourceType="official",
            ),
            SearchResult(
                title="Microsoft Q&A: Windows Event Logging & System Errors",
                link="https://learn.microsoft.com/en-us/answers/tags/318/windows-server-event-logging",
                snippet="Community and Microsoft engineer discussions regarding Windows system and application events.",
                sourceType="community",
            ),
        ]

    for fb in default_fallbacks_list:
        can_link = _canonical_url(fb.link)
        if can_link and can_link not in seen_links:
            seen_links.add(can_link)
            fallback_results.append(fb)

    # Sort web results (official first, then community)
    web_results.sort(key=lambda r: 0 if r.sourceType == "official" else 1)

    # 4. Pipeline assembly: deterministic KB refs remain highest priority!
    for r in kb_refs:
        if len(results) < 3:
            results.append(r)
    for r in web_results:
        if len(results) < 3:
            results.append(r)
    for r in fallback_results:
        if len(results) < 3:
            results.append(r)

    return results, combined_snippets


def _translate(text: str, target: str) -> str:
    text = text.strip()
    if not text:
        return ""
    if target == "en":
        return text
    try:
        return GoogleTranslator(source="auto", target=target).translate(text)
    except Exception:
        return text


def _split_sentences(text: str) -> List[str]:
    parts = SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 25]


def _clean_sentence(sentence: str) -> str:
    sentence = re.sub(r"\s+", " ", sentence).strip(" -•")
    sentence = re.sub(
        r"^(describes an issue in which|describes|this tutorial|if you are facing)\s+",
        "",
        sentence,
        flags=re.IGNORECASE,
    )
    return sentence[:350]


def _is_usable_sentence(sentence: str) -> bool:
    if len(sentence) < 30 or len(sentence) > 350:
        return False
    if sentence.strip().endswith("?"):
        return False
    if SKIP_PATTERNS.search(sentence):
        return False
    if DATE_PATTERN.search(sentence) and not ACTION_KEYWORDS.search(sentence):
        return False
    return True


def _unique_items(items: List[str], limit: int) -> List[str]:
    seen = set()
    output: List[str] = []
    for item in items:
        key = item.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
        if len(output) >= limit:
            break
    return output


def _get_specific_recommendations(faulting_app: str, language: str) -> List[str]:
    """Get specific recommendations based on faulting application name."""
    app_lower = faulting_app.lower()
    
    if language == "th":
        recommendations = []
        
        # Acer Quick Access Agent
        if "acerqaagent" in app_lower or "qaagent" in app_lower:
            recommendations.extend([
                "ถ้าไม่ใช้ Acer Quick Access ให้ uninstall ผ่าน Control Panel",
                "หรือ update Acer Quick Access เป็นเวอร์ชันล่าสุดจากเว็บ Acer",
                "ตรวจสอบว่ามี Acer bloatware อื่นๆ ที่อาจขัดแย้งกัน",
            ])
        
        # NVIDIA drivers
        elif "nvidia" in app_lower or "nvlddmkm" in app_lower or "nvwgf2um" in app_lower:
            recommendations.extend([
                "Update NVIDIA GPU driver เป็นเวอร์ชันล่าสุด",
                "ลอง clean install NVIDIA driver ด้วย DDU (Display Driver Uninstaller)",
                "ตรวจสอบว่า GPU ไม่ overheat",
            ])
        
        # AMD drivers
        elif "amd" in app_lower or "atiumdag" in app_lower:
            recommendations.extend([
                "Update AMD GPU driver เป็นเวอร์ชันล่าสุด",
                "ลอง clean install AMD driver",
                "ตรวจสอบว่า GPU ไม่ overheat",
            ])
        
        # Antivirus
        elif any(av in app_lower for av in ["avast", "avg", "mcafee", "norton", "kaspersky"]):
            recommendations.extend([
                "Update antivirus software เป็นเวอร์ชันล่าสุด",
                "ลอง disable antivirus ชั่วคราวเพื่อทดสอบ",
                "หรือ reinstall antivirus software",
            ])
        
        # Generic application-specific
        if not recommendations:
            recommendations.extend([
                f"Update {faulting_app} เป็นเวอร์ชันล่าสุด",
                f"Reinstall {faulting_app} ถ้ายังมีปัญหา",
                "ตรวจสอบว่ามี software อื่นขัดแย้งกัน",
            ])
        
        return recommendations
    else:
        recommendations = []
        
        if "acerqaagent" in app_lower or "qaagent" in app_lower:
            recommendations.extend([
                "Uninstall Acer Quick Access if not needed via Control Panel",
                "Or update Acer Quick Access to the latest version from Acer's website",
                "Check for other Acer bloatware that might conflict",
            ])
        elif "nvidia" in app_lower or "nvlddmkm" in app_lower or "nvwgf2um" in app_lower:
            recommendations.extend([
                "Update NVIDIA GPU driver to the latest version",
                "Try clean installing NVIDIA driver with DDU (Display Driver Uninstaller)",
                "Check if GPU is not overheating",
            ])
        elif "amd" in app_lower or "atiumdag" in app_lower:
            recommendations.extend([
                "Update AMD GPU driver to the latest version",
                "Try clean installing AMD driver",
                "Check if GPU is not overheating",
            ])
        elif any(av in app_lower for av in ["avast", "avg", "mcafee", "norton", "kaspersky"]):
            recommendations.extend([
                "Update antivirus software to the latest version",
                "Try temporarily disabling antivirus to test",
                "Or reinstall antivirus software",
            ])
        
        if not recommendations:
            recommendations.extend([
                f"Update {faulting_app} to the latest version",
                f"Reinstall {faulting_app} if issue persists",
                "Check for conflicting software",
            ])
        
        return recommendations


def _get_specific_causes(faulting_app: str, language: str) -> List[str]:
    app_lower = faulting_app.lower()
    if language == "th":
        if "acerqaagent" in app_lower or "qaagent" in app_lower:
            return [
                "โปรแกรม Acer Quick Access Agent เกิดข้อผิดพลาดในการโหลดโมดูลหรือ Access Violation",
                "ไฟล์ไดรเวอร์หรือเซอร์วิสของ Acer เบื้องหลังขัดข้องหรือไม่เข้ากันกับเวอร์ชันของ Windows",
            ]
        if "nvidia" in app_lower or "nvlddmkm" in app_lower or "nvwgf2um" in app_lower:
            return [
                "ไดรเวอร์การ์ดจอ NVIDIA ขัดข้องหรือเกิด Timeout Detection and Recovery (TDR)",
                "ความร้อนของ GPU สูงเกินไป หรือไฟล์ไดรเวอร์กราฟิกเสียหาย",
            ]
        if "amd" in app_lower or "atiumdag" in app_lower:
            return [
                "ไดรเวอร์กราฟิก AMD Radeon เกิดข้อผิดพลาดในการประมวลผล",
                "การตั้งค่า Radeon Software ขัดแย้งกับการแสดงผลของระบบ",
            ]
        return [
            f"แอปพลิเคชัน {faulting_app} ขัดข้องจากการเข้าถึงหน่วยความจำผิดพลาด (Memory Access Violation)",
            "ความเข้ากันไม่ได้ของซอฟต์แวร์หลังการอัปเดต หรือไฟล์ไลบรารี (.dll) เสียหาย",
        ]
    else:
        if "acerqaagent" in app_lower or "qaagent" in app_lower:
            return [
                "Acer Quick Access Agent encountered a module crash or access violation.",
                "Background Acer service or driver conflict with current Windows build.",
            ]
        if "nvidia" in app_lower or "nvlddmkm" in app_lower or "nvwgf2um" in app_lower:
            return [
                "NVIDIA display driver crash or Timeout Detection and Recovery (TDR) event.",
                "GPU overheating or corrupted graphics driver files.",
            ]
        if "amd" in app_lower or "atiumdag" in app_lower:
            return [
                "AMD Radeon graphics driver processing failure.",
                "Conflicting Radeon Software configurations with OS display pipeline.",
            ]
        return [
            f"Application {faulting_app} crashed due to an unhandled exception or memory access violation.",
            "Software incompatibility or corrupted dependent library (.dll) files.",
        ]


def _fallback_causes(event_id: str, provider: str, language: str) -> List[str]:
    if language == "th":
        return [
            f"กระบวนการของ {provider or 'ระบบ'} หยุดทำงานกะทันหัน หรือเกิดข้อผิดพลาดในการเรียกใช้เซอร์วิส",
            "สิทธิ์การเข้าถึงระบบไม่เพียงพอ (Permission Denied) หรือไฟล์คอนฟิกูเรชันของระบบเสียหาย",
            "ทรัพยากรระบบ (CPU / Memory / Disk) ไม่เพียงพอขณะกำลังประมวลผลคำขอ",
        ]
    return [
        f"The {provider or 'system'} process crashed or encountered an unexpected service error.",
        "Insufficient system permissions or corrupted system/component configuration files.",
        "System resource depletion (CPU / Memory / Disk I/O) during operation execution.",
    ]


def _fallback_steps(language: str) -> List[str]:
    if language == "th":
        return [
            "ตรวจสอบรายละเอียด Event ใน Event Viewer ให้ครบถ้วน",
            "ค้นหา Event ID นี้ใน Microsoft Learn เพื่อดูวิธีแก้ไขอย่างเป็นทางการ",
            "ทำตามขั้นตอนในลิงก์อ้างอิงด้านล่าง แล้วรีสตาร์ทเครื่องหากจำเป็น",
        ]
    return [
        "Review full event details in Event Viewer",
        "Search this Event ID on Microsoft Learn for official guidance",
        "Follow the reference links below and restart if required",
    ]


def _fallback_vendor_causes(family: str, who: str, language: str) -> List[str]:
    """Honest fallback causes: do not invent storage/file/snapshot conditions."""
    if language == "th":
        return [
            f"จากหลักฐานที่มี ยืนยันได้เพียงว่า session/job ของ {who or family} ล้มเหลว "
            "แต่ยังไม่พบข้อความ root-cause ที่เฉพาะเจาะจงเพียงพอ",
        ]
    return [
        f"The supplied evidence confirms that the {who or family} session/job failed, "
        "but does not yet contain a sufficiently specific root-cause signature.",
    ]


def _fallback_vendor_steps(family: str, language: str) -> List[str]:
    docs = {
        "veeam_vbr": "Veeam Help Center",
        "vmware": "Broadcom Support",
        "cisco_asa": "Cisco documentation",
        "fortinet": "Fortinet Docs",
    }.get(family, "the vendor documentation")
    if language == "th":
        return [
            "เก็บ log ต้นฉบับฉบับเต็มและบันทึกลำดับเหตุการณ์ตามเวลา",
            f"ค้นหาข้อความ error หลักใน {docs}",
            "ทำตามลิงก์อ้างอิงด้านล่าง อย่าดำเนินการที่ทำลายข้อมูลก่อนสำรองหลักฐาน",
        ]
    return [
        "Preserve the complete original log and record the event sequence",
        f"Search the primary error line in {docs}",
        "Follow the references below; avoid destructive actions before preserving evidence",
    ]


def _build_from_web(
    event_id: str,
    provider: str,
    snippets: str,
    results: List[SearchResult],
    language: str,
    faulting_app: str = "",
    source_family: str | None = None,
    diagnostic_code: str | None = None,
    product: str = "",
) -> SolutionSummary:
    family = source_family or "windows_event"
    official_text = snippets
    for result in results:
        if result.snippet:
            official_text += f"\n{result.snippet}"


    sentences = [_clean_sentence(s) for s in _split_sentences(official_text)]
    sentences = [s for s in sentences if _is_usable_sentence(s)]

    target = "th" if language == "th" else "en"

    if family == "unknown_text":
        # Honest triage only: never fabricate a Windows identity or RCA.
        if target == "th":
            overview = (
                "รูปแบบ log นี้ยังไม่ถูกระบุแหล่งที่มา (unknown source) "
                "จึงยังสรุปสาเหตุไม่ได้ โปรดระบุผลิตภัณฑ์ต้นทางของไฟล์นี้"
            )
            causes = [
                "ยังไม่ทราบผลิตภัณฑ์/ระบบที่สร้าง log นี้",
                "รูปแบบข้อความไม่ตรงกับ Windows Event, Veeam, VMware, Fortinet, Cisco หรือ Linux syslog ที่รู้จัก",
            ]
            steps = [
                "ระบุว่าซอฟต์แวร์หรืออุปกรณ์ใดสร้างไฟล์ log นี้ แล้วอัปโหลดพร้อมชื่อผลิตภัณฑ์",
                "เก็บไฟล์ต้นฉบับไว้ครบถ้วน อย่าตัดเฉพาะบางส่วน",
                "ค้นหาเอกสารของผู้ผลิต (vendor documentation) ด้วยข้อความ error หลัก",
            ]
        else:
            overview = (
                "This log format has an unidentified source (unknown source), "
                "so no cause can be concluded yet. Please identify the emitting product."
            )
            causes = [
                "The product/system that emitted this log is still unknown",
                "The text does not match known Windows Event, Veeam, VMware, Fortinet, Cisco, or Linux syslog shapes",
            ]
            steps = [
                "Identify which software or appliance produced this log file and re-submit with the product name",
                "Preserve the complete original file instead of excerpts",
                "Search the vendor documentation with the primary error line",
            ]
        return SolutionSummary(overview=overview, causes=causes, steps=steps)

    if family in ("veeam_vbr", "vmware", "cisco_asa", "fortinet"):
        label = diagnostic_code or event_id
        who = product or provider
        # Phase 2: for generic/unknown codes, do NOT prepend web snippet text
        # as the primary overview.  Use an honest evidence-based statement.
        _generic_codes = {"VEEAM-UNKNOWN", "VMWARE-UNKNOWN", "VEEAM-SESSION-FAILED", ""}
        if label in _generic_codes or not label:
            if target == "th":
                overview = (
                    f"{who}: session/job ล้มเหลว "
                    "หลักฐานที่มีอยู่ยืนยันได้เพียงนี้ ยังไม่พบ root-cause signature ที่เฉพาะเจาะจง"
                )
            else:
                overview = (
                    f"{who}: The task/session completed with a Failed status. "
                    "The supplied evidence does not yet contain a recognized root-cause signature."
                )
            causes = _fallback_vendor_causes(family, who, language)
            steps = _fallback_vendor_steps(family, language)
            return SolutionSummary(overview=overview, causes=causes, steps=steps)

        # Specific diagnostic code: use search snippets for enrichment.
        overview_base = f"{who}: diagnostic {label}."
        if sentences:
            overview_base += f" {sentences[0]}"
        overview = _translate(overview_base, target)
        cause_candidates = [s for s in sentences if CAUSE_KEYWORDS.search(s)]
        step_candidates = [s for s in sentences if ACTION_KEYWORDS.search(s) and _is_usable_sentence(s)]
        causes = _unique_items([_translate(c, target) for c in cause_candidates], 3)
        steps = _unique_items([_translate(s, target) for s in step_candidates], 5)
        steps = [s for s in steps if len(s) >= 25][:5]
        if len(causes) < 2:
            causes = _unique_items(causes + _fallback_vendor_causes(family, who, language), 3)
        if len(steps) < 3:
            steps = _fallback_vendor_steps(family, language)
        return SolutionSummary(overview=overview, causes=causes, steps=steps)

    if family == "windows_event":
        provider_label = provider if provider != "Unknown" else "Windows"
        overview_base = (
            f"Event ID {event_id} from {provider_label} is a Windows event log entry."
        )
        if sentences:
            overview_base += f" {sentences[0]}"
        overview = _translate(overview_base, target)

        cause_candidates = [s for s in sentences if CAUSE_KEYWORDS.search(s)]
        step_candidates = [s for s in sentences if ACTION_KEYWORDS.search(s) and _is_usable_sentence(s)]

        causes = _unique_items([_translate(c, target) for c in cause_candidates], 3)
        steps = _unique_items([_translate(s, target) for s in step_candidates], 5)
        steps = [s for s in steps if len(s) >= 25][:5]

        if faulting_app:
            app_causes = _get_specific_causes(faulting_app, language)
            causes = app_causes + causes
            causes = _unique_items(causes, 3)

        if len(causes) < 2:
            fb_causes = _fallback_causes(event_id, provider, language)
            causes = _unique_items(causes + fb_causes, 3)

        if len(steps) < 3:
            steps = _fallback_steps(language)

        if faulting_app:
            specific_recs = _get_specific_recommendations(faulting_app, language)
            if specific_recs:
                steps = specific_recs + steps
                steps = _unique_items(steps, 5)

        return SolutionSummary(overview=overview, causes=causes, steps=steps)
    else:
        provider_label = product or provider or family
        overview_base = (
            f"{provider_label} diagnostic record ({family})."
        )
        if sentences:
            overview_base += f" {sentences[0]}"
        overview = _translate(overview_base, target)
        cause_candidates = [s for s in sentences if CAUSE_KEYWORDS.search(s)]
        step_candidates = [s for s in sentences if ACTION_KEYWORDS.search(s) and _is_usable_sentence(s)]
        causes = _unique_items([_translate(c, target) for c in cause_candidates], 3)
        steps = _unique_items([_translate(s, target) for s in step_candidates], 5)
        steps = [s for s in steps if len(s) >= 25][:5]
        if len(causes) < 2:
            causes = _unique_items(causes + _fallback_vendor_causes(family, provider_label, language), 3)
        if len(steps) < 3:
            steps = _fallback_vendor_steps(family, language)
        return SolutionSummary(overview=overview, causes=causes, steps=steps)


def _call_gemini(prompt: str, api_key: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2}
    }
    headers = {"Content-Type": "application/json"}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini API Error: {e}")
        return ""

def _build_from_gemini(
    event_id: str,
    provider: str,
    snippets: str,
    results: List[SearchResult],
    language: str,
    faulting_app: str,
    api_key: str,
    rag_context: str = "",
    source_family: Optional[str] = None,
    diagnostic_code: Optional[str] = None,
    product: str = "",
) -> SolutionSummary | None:
    fam = (source_family or "").strip()
    if not fam:
        p_low = (provider or "").lower()
        if "veeam" in p_low:
            fam = "veeam_vbr"
        elif "vmware" in p_low or "esxi" in p_low:
            fam = "vmware"
        elif "fortigate" in p_low or "fortinet" in p_low:
            fam = "fortinet"
        elif "cisco" in p_low or "asa" in p_low or "ftd" in p_low:
            fam = "cisco_asa"
        elif "syslog" in p_low or "linux" in p_low:
            fam = "linux_syslog"
        elif "json" in p_low:
            fam = "json"
        elif event_id.isdigit():
            fam = "windows_event"
        else:
            fam = "unknown_text"

    if fam == "windows_event":
        system_context = "You are an expert Windows Server Administrator and SOC Analyst."
        log_type_hint = ""
        log_desc = f"Windows Event ID {event_id} from {provider or 'Windows'}"
    elif fam == "veeam_vbr":
        system_context = "You are an expert Veeam Backup & Replication engineer and VMware infrastructure specialist."
        log_type_hint = (
            "\nThis is a Veeam Backup & Replication log (replication/backup job). Focus on: "
            "job/session stages, snapshot cleanup and revert operations, change-tracking (CBT) errors, "
            "and VMware snapshot chain health. Describe observed evidence only; do not invent filenames, "
            "do not claim a causal link between failure phases unless the log proves it."
        )
        code_part = f" ({diagnostic_code})" if diagnostic_code else ""
        prod_part = f" ({product})" if product else ""
        log_desc = f"Veeam diagnostic {event_id}{code_part}{prod_part}"
    elif fam == "vmware":
        system_context = "You are an expert VMware vSphere/ESXi engineer."
        log_type_hint = (
            "\nThis is a VMware ESXi/host log. Focus on: DISKLIB/CBT errors, snapshot operations, "
            "missing-file conditions, and datastore file state. Describe observed evidence only; "
            "do not invent filenames or lock owners."
        )
        code_part = f" ({diagnostic_code})" if diagnostic_code else ""
        prod_part = f" ({product})" if product else ""
        log_desc = f"VMware diagnostic {event_id}{code_part}{prod_part}"
    elif fam == "fortinet":
        system_context = "You are an expert Fortinet/FortiGate Firewall Administrator and Network Security Engineer."
        log_type_hint = (
            "\nThis is a Fortinet FortiGate firewall log. Focus on: traffic policy decisions, "
            "IPS/UTM events, blocked connections, threat signatures, and network security recommendations."
        )
        log_desc = f"Fortinet FortiGate log (Log ID: {event_id})"
    elif fam == "cisco_asa":
        system_context = "You are an expert Cisco ASA/FTD Firewall Administrator and Network Security Engineer."
        log_type_hint = (
            "\nThis is a Cisco ASA/FTD syslog message. Focus on: access control policies, "
            "NAT translations, VPN events, connection tracking, threat detection, and Cisco firewall recommendations."
        )
        log_desc = f"Cisco ASA log (Message ID: {event_id})"
    elif fam == "linux_syslog":
        system_context = "You are an expert Linux Systems Administrator and SRE."
        log_type_hint = (
            "\nThis is a Linux syslog entry. Focus on: Linux/system context, systemd service units, "
            "kernel messages, auth/daemon logging, and host state. Describe observed errors and system state only."
        )
        log_desc = f"Linux syslog event from {provider or 'system'} (Identifier: {event_id})"
    elif fam == "json":
        system_context = "You are an expert Application Reliability and Cloud Systems Engineer."
        log_type_hint = (
            "\nThis is a structured JSON application or service log. Focus on: structured application/service context, "
            "payload attributes, HTTP/RPC status codes, stack traces, and microservice error conditions."
        )
        log_desc = f"Structured JSON log event from {provider or 'application'} (ID: {event_id})"
    else:  # unknown_text
        system_context = "You are an expert Technical Incident Triage Specialist."
        log_type_hint = (
            "\nThis is an unstructured log entry. Perform conservative generic incident triage: "
            "focus strictly on explicit error messages and facts present in the text, avoiding domain-specific assumptions."
        )
        log_desc = f"Unidentified log entry (ID: {event_id})"

    fault_line = f"Faulting App: {faulting_app}\n" if (faulting_app and fam == "windows_event") else ""
    prompt = f"""{system_context}
Analyze {log_desc}.
{fault_line}{log_type_hint}

Internal Knowledge Base (Past Solved Issues):
{rag_context}

Web Context: {snippets}

Output ONLY valid JSON with no markdown formatting. The JSON must match this structure:
{{
  "overview": "1-2 sentences explaining what the event means.",
  "causes": ["cause 1", "cause 2"],
  "steps": ["step 1", "step 2", "step 3"]
}}
Language required: {'Thai' if language == 'th' else 'English'}.
"""
    response_text = _call_gemini(prompt, api_key)
    if not response_text:
        return None
        
    try:
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        data = json.loads(cleaned.strip())
        return SolutionSummary(
            overview=data.get("overview", "No overview provided by AI."),
            causes=data.get("causes", []),
            steps=data.get("steps", [])
        )
    except Exception as e:
        print(f"Gemini Parse Error: {e}")
        return None


def build_followup_answer(
    question: str,
    summary: SolutionSummary,
    results: List[SearchResult],
    language: str = "th",
    api_key: str | None = None,
    source_family: str | None = None,
    event_id: str = "Unknown",
    provider: str = "Unknown",
    diagnostic_code: str | None = None,
) -> str:
    text = question.strip()
    if not text:
        return ""

    normalized = text.lower()
    needs_causes = bool(re.search(r"\b(cause|why|reason|because|why does|why is|why did|สาเหตุ|ทำไม|เพราะอะไร|เหตุผล)\b", normalized))
    needs_steps = bool(re.search(r"\b(fix|solve|how|step|repair|resolve|แก้|วิธี|ทำอย่างไร|คำแนะนำ|แก้ไข|fixing|solve)\b", normalized))
    needs_references = bool(re.search(
        r"\b(link|reference|where|หา|ลิงก์|เอกสาร|documentation|อ้างอิง|source)\b", normalized
    ))

    if api_key:
        sysdesc = (summary.overview or "")[:1500]
        bounded_causes = list(summary.causes or [])[:5]
        bounded_steps = list(summary.steps or [])[:8]
        incident = summary.incident
        incident_block = ""
        if incident is not None:
            try:
                incident_block = (
                    f"First observed failure: {incident.firstMeaningfulFailure}\n"
                    f"Terminal failure: {incident.terminalFailure}\n"
                    f"Operation stage: {incident.operationStage}\n"
                    f"Observed paths: {list(incident.observedPaths or [])[:5]}"
                )
            except Exception:
                incident_block = ""
        bounded_evidence = list(summary.evidence or [])[:6]
        try:
            bounded_items = [
                f"{i.sourceFile}:{i.lineNumber} {i.message}"
                for i in list(summary.evidenceItems or [])[:6]
            ]
        except Exception:
            bounded_items = []
        prompt = f"""You are an expert IT assistant. The user is asking a follow-up question about an analyzed log entry.
Context overview: {sysdesc}
Known causes: {bounded_causes}
Known steps: {bounded_steps}
{incident_block}
Observed evidence: {bounded_evidence}
Evidence with source files: {bounded_items}
Still unknown: {list(summary.limitations or [])[:4]}
Next evidence to collect: {list(summary.nextEvidence or [])[:4]}

User Question: {text}
Language: {'Thai' if language == 'th' else 'English'}
Answer the question directly and professionally. Never invent facts not present in the context."""
        ai_ans = _call_gemini(prompt, api_key)
        if ai_ans:
            return ai_ans

    lines: List[str] = []
    if language == "th":
        if needs_causes and summary.causes:
            lines.append("จากข้อมูลที่วิเคราะห์ได้ สาเหตุที่เป็นไปได้มีดังนี้:")
            lines.extend([f"- {cause}" for cause in summary.causes])
        if needs_steps and summary.steps:
            if lines:
                lines.append("")
            lines.append("คำแนะนำการแก้ไขที่แนะนำ:")
            lines.extend([f"- {step}" for step in summary.steps])
        if not lines:
            lines.append(f"สรุป: {summary.overview}")
            if summary.steps:
                lines.append("")
                lines.append("วิธีแก้ไขหลักที่แนะนำ:")
                lines.extend([f"- {step}" for step in summary.steps[:3]])
        if needs_references and results:
            lines.append("")
            lines.append("เอกสารอ้างอิงที่แนะนำ:")
            lines.extend([f"- {result.title}: {result.link}" for result in results[:3]])
        if not lines:
            lines.append(
                "ขอโทษครับ/ค่ะ ยังตอบคำถามนี้โดยตรงไม่ได้ แต่สามารถดูสรุปและลิงก์อ้างอิงด้านล่างได้"
            )
    else:
        if needs_causes and summary.causes:
            lines.append("Based on the analysis, these are the likely causes:")
            lines.extend([f"- {cause}" for cause in summary.causes])
        if needs_steps and summary.steps:
            if lines:
                lines.append("")
            lines.append("Recommended resolution steps:")
            lines.extend([f"- {step}" for step in summary.steps])
        if not lines:
            lines.append(f"Summary: {summary.overview}")
            if summary.steps:
                lines.append("")
                lines.append("Key steps to resolve:")
                lines.extend([f"- {step}" for step in summary.steps[:3]])
        if needs_references and results:
            lines.append("")
            lines.append("Useful references:")
            lines.extend([f"- {result.title}: {result.link}" for result in results[:3]])
        if not lines:
            lines.append(
                "Sorry, I cannot answer that directly yet, but you can review the summary and references for more details."
            )

    return "\n".join(lines)


async def build_summary(
    event_id: str,
    provider: str,
    snippets: str,
    results: List[SearchResult],
    language: str = "th",
    faulting_app: str = "",
    api_key: str | None = None,
    description: str = "",
    db: AsyncSession | None = None,
    source_family: str | None = None,
    diagnostic_code: str | None = None,
    product: str = "",
    evidence_text: str = "",
    **kwargs,
) -> SolutionSummary:
    lang = language if language in ("th", "en") else "th"
    family = source_family or "windows_event"

    # Deterministic vendor knowledge wins for recognized diagnostics:
    # offline, no hallucinated filenames, honest confidence.
    if diagnostic_code and is_vendor_diagnostic_code(diagnostic_code):
        vendor = get_vendor_summary(diagnostic_code, lang, evidence_text or description or "")
        if vendor:
            return vendor

    curated = get_curated_summary(event_id, lang)
    if curated:
        return curated

    rag_context = ""
    similar = []
    if description and db and family != "unknown_text":
        try:
            similar = await search_similar_logs(
                db=db,
                description=description,
                api_key=api_key,
                event_id=event_id,
                source_family=family,
                diagnostic_code=diagnostic_code,
            )
            if similar:
                rag_context = json.dumps(similar, ensure_ascii=False)
        except Exception as e:
            print(f"RAG search error: {e}")

    if api_key:
        gemini_summary = _build_from_gemini(
            event_id,
            provider,
            snippets,
            results,
            lang,
            faulting_app,
            api_key,
            rag_context,
            source_family=family,
            diagnostic_code=diagnostic_code,
            product=product,
        )
        if gemini_summary:
            return gemini_summary

    # If no Gemini API but we found a similar past solution in our local vector DB, use it!
    if similar:
        try:
            return SolutionSummary(**similar[0])
        except Exception:
            pass

    return _build_from_web(
        event_id, provider, snippets, results, lang, faulting_app,
        source_family=family, diagnostic_code=diagnostic_code, product=product,
    )


def format_summary_text(summary: SolutionSummary, language: str = "th") -> str:
    if language == "th":
        lines = ["สรุปวิธีการแก้ไขเบื้องต้น (จากผลการค้นหา):", "", "📋 สรุปปัญหา", summary.overview]
        if summary.causes:
            lines.extend(["", "🔍 สาเหตุที่เป็นไปได้"])
            lines.extend(f"{i}. {cause}" for i, cause in enumerate(summary.causes, 1))
        if summary.steps:
            lines.extend(["", "✅ วิธีแก้ไข (ทำตามลำดับ)"])
            lines.extend(f"{i}. {step}" for i, step in enumerate(summary.steps, 1))
    else:
        lines = ["Solution summary (from web search):", "", "Overview", summary.overview]
        if summary.causes:
            lines.extend(["", "Possible causes"])
            lines.extend(f"{i}. {cause}" for i, cause in enumerate(summary.causes, 1))
        if summary.steps:
            lines.extend(["", "Recommended steps"])
            lines.extend(f"{i}. {step}" for i, step in enumerate(summary.steps, 1))
    return "\n".join(lines)
