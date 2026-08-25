import re
from typing import List
from urllib.parse import urlparse
import json
import requests
from sqlalchemy.ext.asyncio import AsyncSession

from deep_translator import GoogleTranslator
from duckduckgo_search import DDGS

from backend.domain.analyzer.schemas.analyze import SearchResult, SolutionSummary
from backend.domain.analyzer.services.event_knowledge import get_curated_summary
from backend.domain.analyzer.services.vector_db import search_similar_logs

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

SEARCH_TIERS = (
    ("official", "site:learn.microsoft.com troubleshoot"),
    ("official", "site:support.microsoft.com"),
    ("community", "site:stackoverflow.com OR site:superuser.com"),
)


def _classify_source(link: str, tier: str) -> str:
    domain = urlparse(link).netloc.lower()
    if any(official in domain for official in OFFICIAL_DOMAINS):
        return "official"
    return tier


def search_solutions(event_id: str, provider: str) -> tuple[List[SearchResult], str]:
    results: List[SearchResult] = []
    combined_snippets = ""
    provider_part = provider if provider not in ("Unknown", "DistributedCOM") else "DCOM"

    # Search web for relevant solutions
    try:
        query = f"Windows Event ID {event_id} {provider_part} learn.microsoft.com"
        with DDGS(timeout=3) as ddgs:
            raw = list(ddgs.text(query, max_results=4))
            for item in raw:
                title = (item.get("title") or "").strip()
                link = (item.get("href") or item.get("url") or "").strip()
                snippet = (item.get("body") or item.get("snippet") or "").strip()
                if not link or any(r.link == link for r in results):
                    continue
                source_type = _classify_source(link, "official")
                results.append(
                    SearchResult(
                        title=title,
                        link=link,
                        snippet=snippet,
                        sourceType=source_type,  # type: ignore[arg-type]
                    )
                )
                if snippet:
                    combined_snippets += f"{snippet}\n"
                if len(results) >= 3:
                    break
    except Exception:
        pass

    # If results are still fewer than 3, add reliable official reference resources
    default_fallbacks = [
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

    for fallback in default_fallbacks:
        if len(results) >= 3:
            break
        if not any(r.link == fallback.link for r in results):
            results.append(fallback)

    results.sort(key=lambda r: 0 if r.sourceType == "official" else 1)
    results = results[:3]

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


def _build_from_web(
    event_id: str,
    provider: str,
    snippets: str,
    results: List[SearchResult],
    language: str,
    faulting_app: str = "",
) -> SolutionSummary:
    official_text = snippets
    for result in results:
        if result.snippet:
            official_text += f"\n{result.snippet}"

    sentences = [_clean_sentence(s) for s in _split_sentences(official_text)]
    sentences = [s for s in sentences if _is_usable_sentence(s)]

    target = "th" if language == "th" else "en"
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

    # Enhance causes with specific app causes or fallback causes
    if faulting_app:
        app_causes = _get_specific_causes(faulting_app, language)
        causes = app_causes + causes
        causes = _unique_items(causes, 3)

    if len(causes) < 2:
        fb_causes = _fallback_causes(event_id, provider, language)
        causes = _unique_items(causes + fb_causes, 3)

    if len(steps) < 3:
        steps = _fallback_steps(language)
    
    # Add specific recommendations if faulting app is provided
    if faulting_app:
        specific_recs = _get_specific_recommendations(faulting_app, language)
        if specific_recs:
            steps = specific_recs + steps
            steps = _unique_items(steps, 5)

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
    rag_context: str = ""
) -> SolutionSummary | None:
    is_fortinet = "FortiGate" in provider or "fortinet" in provider.lower()
    is_cisco = "Cisco" in provider or "ASA" in provider or "FTD" in provider

    if is_fortinet:
        system_context = "You are an expert Fortinet/FortiGate Firewall Administrator and Network Security Engineer."
        log_type_hint = (
            "\nThis is a Fortinet FortiGate firewall log. Focus on: traffic policy decisions, "
            "IPS/UTM events, blocked connections, threat signatures, and network security recommendations."
        )
        log_desc = f"Fortinet FortiGate log (Log ID: {event_id})"
    elif is_cisco:
        system_context = "You are an expert Cisco ASA/FTD Firewall Administrator and Network Security Engineer."
        log_type_hint = (
            "\nThis is a Cisco ASA/FTD syslog message. Focus on: access control policies, "
            "NAT translations, VPN events, connection tracking, threat detection, and Cisco firewall recommendations."
        )
        log_desc = f"Cisco ASA log (Message ID: {event_id})"
    else:
        system_context = "You are an expert Windows Server Administrator and SOC Analyst."
        log_type_hint = ""
        log_desc = f"Windows Event ID {event_id} from {provider}"

    prompt = f"""{system_context}
Analyze {log_desc}.
{'Faulting App: ' + faulting_app if not is_fortinet and not is_cisco else ''}{log_type_hint}

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
        prompt = f"""You are an expert IT assistant. The user is asking a follow up question about Windows Event ID {summary.overview}.
Known causes: {summary.causes}
Known steps: {summary.steps}

User Question: {text}
Language: {'Thai' if language == 'th' else 'English'}
Answer the question directly and professionally."""
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
) -> SolutionSummary:
    lang = language if language in ("th", "en") else "th"

    curated = get_curated_summary(event_id, lang)
    if curated:
        return curated

    rag_context = ""
    similar = []
    if description and db:
        try:
            similar = await search_similar_logs(db=db, description=description, api_key=api_key, event_id=event_id)
            if similar:
                rag_context = json.dumps(similar, ensure_ascii=False)
        except Exception as e:
            print(f"RAG search error: {e}")

    if api_key:
        gemini_summary = _build_from_gemini(event_id, provider, snippets, results, lang, faulting_app, api_key, rag_context)
        if gemini_summary:
            return gemini_summary
            
    # If no Gemini API but we found a similar past solution in our local vector DB, use it!
    if similar:
        try:
            return SolutionSummary(**similar[0])
        except Exception:
            pass

    return _build_from_web(event_id, provider, snippets, results, lang, faulting_app)


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
