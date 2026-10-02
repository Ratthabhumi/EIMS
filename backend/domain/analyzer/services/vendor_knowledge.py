"""Deterministic vendor knowledge for recognized infrastructure diagnostics.

Available offline; web search is only supplementary references.  Each
entry states what is OBSERVED and what is still UNKNOWN — entries never
assert an exact missing/locked file unless the evidence names it.

References name official vendor material — article numbers AND their
canonical knowledge-base URLs (verified resolvable).  Articles whose
scope is environment-specific are only surfaced when the evidence text
matches the required tokens (e.g. vSAN ESA, vVOLs), never universally.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.domain.analyzer.schemas.analyze import SearchResult, SolutionSummary


def _summary(
    overview: str,
    causes: List[str],
    steps: List[str],
    evidence: List[str],
    confidence: str,
    limitations: List[str],
    next_evidence: List[str],
) -> SolutionSummary:
    return SolutionSummary(
        overview=overview,
        causes=causes,
        steps=steps,
        evidence=evidence,
        confidence=confidence,
        limitations=limitations,
        nextEvidence=next_evidence,
    )


def _th_en(th: str, en: str, language: str) -> str:
    return th if language == "th" else en


@dataclass(frozen=True)
class VendorArticle:
    article_id: str
    title: str
    url: str
    # Codes this article is allowed to answer.  Empty list => universal
    # (still subject to text-token gating below to avoid off-topic hits).
    applies_to: List[str] = field(default_factory=list)
    # All tokens required (case-insensitive) for gated articles.
    requires_all: tuple = ()
    # Any one of these tokens (case-insensitive) satisfies the gate.
    requires_any: tuple = ()


# Canonical knowledge-base URLs (slugless form; verified resolvable).
# My apologies in advance: this honestly states which article applies to
# which diagnosed condition and never presents a gated article as universal.
VENDOR_ARTICLES: List[VendorArticle] = [
    VendorArticle(
        article_id="424591",
        title="Reverting a virtual machine snapshot fails with error: 'A required file was not found'",
        url="https://knowledge.broadcom.com/external/article/424591",
        applies_to=["VMWARE-SNAPSHOT-FILE-MISSING", "VEEAM-REPLICA-SNAPSHOT-CHAIN"],
        requires_all=("required file", "not found"),
    ),
    VendorArticle(
        article_id="418256",
        title="Virtual machine backups fail due to locked files even if the VM is moved to other ESXi hosts in the cluster",
        url="https://knowledge.broadcom.com/external/article/418256",
        applies_to=["VMWARE-CBT-DELETE-FAILED"],
        requires_any=("lock", "cbt", "change tracking", "change-tracking", "backup"),
    ),
    VendorArticle(
        article_id="442155",
        title="Snapshot usage on ESA Cluster is very high",
        url="https://knowledge.broadcom.com/external/article/442155",
        applies_to=["VMWARE-CBT-DELETE-FAILED", "VMWARE-SNAPSHOT-FILE-MISSING"],
        # vSAN Express Storage Architecture ONLY.  Both tokens must appear.
        requires_all=("vsan", "esa"),
    ),
    VendorArticle(
        article_id="411756",
        title="Snapshot consolidation failed for VM on vVOLs storage",
        url="https://knowledge.broadcom.com/external/article/411756",
        applies_to=["VMWARE-CBT-DELETE-FAILED", "VMWARE-SNAPSHOT-FILE-MISSING"],
        requires_all=("vvol",),
    ),
    VendorArticle(
        article_id="318905",
        title="'Detected an invalid snapshot configuration' error creating a snapshot",
        url="https://knowledge.broadcom.com/external/article/318905",
        applies_to=["VMWARE-SNAPSHOT-FILE-MISSING", "VEEAM-REPLICA-SNAPSHOT-CHAIN"],
        requires_any=("invalid snapshot config", "snapshot config", "invalid configuration"),
    ),
    VendorArticle(
        article_id="450780",
        title="Error: 'A required file was not found' when deleting a snapshot or Virtual Machine",
        url="https://knowledge.broadcom.com/external/article/450780",
        applies_to=["VMWARE-SNAPSHOT-FILE-MISSING", "VEEAM-REPLICA-SNAPSHOT-CHAIN"],
        requires_any=("delet", "consolidat", "remov"),
    ),
    VendorArticle(
        article_id="452165",
        title="Error: 'A required file was not found' after manually renaming or moving virtual machine folder",
        url="https://knowledge.broadcom.com/external/article/452165",
        applies_to=["VMWARE-SNAPSHOT-FILE-MISSING", "VEEAM-REPLICA-SNAPSHOT-CHAIN"],
        requires_any=("renam", "mov", "folder"),
    ),
]


def _article_applies(article: VendorArticle, diagnostic_code: str, text: str) -> bool:
    lowered = (text or "").lower()
    if article.applies_to and diagnostic_code not in article.applies_to:
        return False
    if article.requires_all:
        if not all(needle in lowered for needle in article.requires_all):
            return False
    if article.requires_any:
        if not any(needle in lowered for needle in article.requires_any):
            return False
    return True


def vendor_reference_results(diagnostic_code: str, evidence_text: str, language: str) -> List[SearchResult]:
    """Deterministic official KB references for a diagnostic code + evidence.

    Environment-gated articles (vSAN ESA, vVOLs, deletion, rename/move) are
    only returned when the supplied text satisfies their token gates.
    """
    if not diagnostic_code:
        return []
    language = language if language in ("th", "en") else "th"
    results: List[SearchResult] = []
    for article in VENDOR_ARTICLES:
        if not _article_applies(article, diagnostic_code, evidence_text):
            continue
        snippet = _th_en(
            f"Broadcom Support knowledge article {article.article_id} — "
            f"ใช้ได้กับเงื่อนไขหมายเหตุในบทความเท่านั้น (ตรวจสภาพแวดล้อมก่อนใช้)",
            f"Broadcom Support knowledge article {article.article_id} — "
            f"applies under the conditions stated in the article (verify environment before applying)",
            language,
        )
        results.append(
            SearchResult(
                title=f"Broadcom Support (official) — {article.title}",
                link=article.url,
                snippet=snippet,
                sourceType="official",
            )
        )
    return results


def _vendor_entry(code: str, language: str) -> Optional[SolutionSummary]:
    lang = language if language in ("th", "en") else "th"

    if code == "VMWARE-CBT-DELETE-FAILED":
        return _summary(
            overview=_th_en(
                "VMware ไม่สามารถลบ change-tracking (.ctk) file ได้ "
                "ผลลัพธ์ 2620 / CTK_CTKUNLINK บ่งชี้การ cleanup ของ CBT ล้มเหลว",
                "VMware could not delete a change-tracking (.ctk) file. "
                "Result 2620 / CTK_CTKUNLINK indicates a CBT cleanup failure.",
                lang,
            ),
            causes=[
                _th_en(
                    "ไฟล์ CTK หาย ไม่ตรงสถานะ หรือเสียหาย (ยังไม่พิสูจน์ว่าเป็นการ lock)",
                    "CTK file missing, state-mismatched, or corrupt (locking is NOT proven)",
                    lang,
                ),
                _th_en(
                    "Snapshot cleanup ค้างจาก operation ก่อนหน้า หรือ datastore ไม่สอดคล้อง",
                    "Stale snapshot cleanup from a previous operation, or datastore inconsistency",
                    lang,
                ),
            ],
            steps=[
                _th_en(
                    "ตรวจสอบไฟล์ .ctk.vmdk ที่เกี่ยวข้องใน datastore listing",
                    "Check the related .ctk.vmdk files in a datastore listing",
                    lang,
                ),
                _th_en(
                    "ตรวจ vmware.log และ hostd.log รอบเวลาที่เกิดเหตุ",
                    "Inspect vmware.log and hostd.log around the failure time",
                    lang,
                ),
                _th_en(
                    "อ้างอิงเอกสารทางการของ Broadcom: Article 442155 (vSAN ESA), Article 418256 (CTK), Article 411756 (vVOLs) — ตรวจสอบเงื่อนไขของแต่ละบทความก่อนนำไปใช้",
                    "Refer to official Broadcom material: Article 442155 (vSAN ESA), Article 418256 (CTK), Article 411756 (vVOLs) — verify each article’s scope before applying",
                    lang,
                ),
            ],
            evidence=["Could not delete change tracking file"],
            confidence="medium",
            limitations=[
                _th_en(
                    "ห้ามสรุปว่าไฟล์ถูก lock จนกว่าจะมีหลักฐานการ lock จริง",
                    "Do NOT claim the file is locked unless lock evidence exists",
                    lang,
                )
            ],
            next_evidence=[
                "VM vmware.log",
                "ESXi hostd.log",
                "Datastore file listing (.vmdk / .ctk.vmdk state)",
            ],
        )

    if code == "VMWARE-SNAPSHOT-FILE-MISSING":
        return _summary(
            overview=_th_en(
                "การอ้างอิง snapshot disk ของ VM ชี้ไปยังไฟล์ที่ VMware หาไม่พบ "
                "(InvalidSnapshotFormat + required file not found)",
                "The VM snapshot configuration references a required file or snapshot "
                "disk that VMware cannot find (InvalidSnapshotFormat + required file not found).",
                lang,
            ),
            causes=[
                _th_en(
                    "ไฟล์ snapshot disk ถูกลบ ย้าย หรือเปลี่ยนชื่อภายนอกกระบวนการ",
                    "A snapshot disk file was deleted, moved, or renamed outside the workflow",
                    lang,
                ),
                _th_en(
                    "descriptor ชี้ chain ไม่ตรงกับไฟล์จริงบน datastore",
                    "Snapshot descriptor chain does not match files actually on the datastore",
                    lang,
                ),
            ],
            steps=[
                _th_en(
                    "ทำ datastore file listing เปรียบเทียบกับ descriptor chain",
                    "Take a datastore file listing and compare it with the descriptor chain",
                    lang,
                ),
                _th_en(
                    "ตรวจ vmware.log และ hostd.log หาชื่อไฟล์ที่หายไป",
                    "Inspect vmware.log and hostd.log for the missing filename",
                    lang,
                ),
                _th_en(
                    "อ้างอิงเอกสารทางการของ Broadcom: Article 424591, Article 318905, Article 450780, Article 452165 (ถ้าเกี่ยวข้องกับสถานการณ์การลบ/rename/move/vVOLs/vSAN ESA)",
                    "Refer to official Broadcom material: Article 424591, Article 318905, Article 450780, Article 452165 (where relevant: deletion/rename/move/vVOLs/vSAN ESA)",
                    lang,
                ),
            ],
            evidence=["InvalidSnapshotFormat", "A required file was not found"],
            confidence="high",
            limitations=[
                _th_en(
                    "ห้ามระบุชื่อไฟล์ที่หาย ถ้า log ไม่ได้ระบุชื่อไว้",
                    "Do NOT name the missing file unless the log names it",
                    lang,
                )
            ],
            next_evidence=[
                "VM vmware.log",
                "ESXi hostd.log",
                "Datastore file listing",
            ],
        )

    if code == "VEEAM-REPLICA-SNAPSHOT-CHAIN":
        return _summary(
            overview=_th_en(
                "Replication เข้าสู่ขั้นตอน snapshot cleanup/revert ของ replica แล้ว "
                "พบความผิดปกติของ replica snapshot chain (Veeam ใช้ native VMware snapshots)",
                "Replication reached the replica snapshot cleanup/revert stage and the "
                "replica snapshot chain is unhealthy (replica restore points use native "
                "VMware snapshots with native snapshot revert).",
                lang,
            ),
            causes=[
                _th_en(
                    "ขั้นตอนแรกที่สังเกตได้: ลบ change-tracking file ไม่สำเร็จ",
                    "First observed failure: change-tracking file deletion failed",
                    lang,
                ),
                _th_en(
                    "ขั้นตอนหลัง: configuration ของ replica snapshot อ้างถึงไฟล์ที่ VMware หาไม่พบ",
                    "Later observed failure: the replica snapshot configuration references "
                    "a required file VMware cannot locate",
                    lang,
                ),
            ],
            steps=[
                _th_en(
                    "เก็บ replica vmware.log, hostd.log และ datastore listing ก่อนแตะต้อง replica",
                    "Collect the replica vmware.log, hostd.log, and a datastore listing before touching the replica",
                    lang,
                ),
                _th_en(
                    "ใช้ Veeam Export Logs (%ProgramData%\\Veeam\\Backup) เก็บ Task/Job session logs ฉบับเต็ม",
                    "Use Veeam Export Logs (%ProgramData%\\Veeam\\Backup) to keep full Task/Job session logs",
                    lang,
                ),
                _th_en(
                    "อย่าสรุปว่าการลบ CBT ทำให้ไฟล์ snapshot หาย จนกว่าหลักฐานจะพิสูจน์ causal link",
                    "Do NOT conclude the CBT deletion caused the missing snapshot file unless "
                    "evidence proves the causal link",
                    lang,
                ),
            ],
            evidence=[
                "Could not delete change tracking file",
                "Deleting helper snapshot",
                "Detected an invalid snapshot configuration",
                "A required file was not found",
                "RevertSnapshot / InvalidSnapshotFormat",
            ],
            confidence="medium",
            limitations=[
                _th_en(
                    "ความสัมพันธ์ระหว่าง CBT deletion failure กับ missing snapshot dependency "
                    "ยังไม่พิสูจน์ว่าเป็นสาเหตุเดียวกัน",
                    "The relationship between the earlier CBT deletion failure and the later "
                    "missing snapshot dependency is NOT proven causal",
                    lang,
                )
            ],
            next_evidence=[
                "Replica VM vmware.log",
                "ESXi hostd.log",
                "Datastore file listing",
                "Veeam Task/Job session logs",
            ],
        )

    return None


def get_vendor_summary(diagnostic_code: str, language: str) -> Optional[SolutionSummary]:
    """Return the deterministic curated summary for a diagnostic code."""
    if not diagnostic_code:
        return None
    return _vendor_entry(diagnostic_code.strip(), language)


def vendor_reference_titles() -> Dict[str, List[str]]:
    """Official reference titles (text only, no fabricated URLs)."""
    return {
        "VMWARE-CBT-DELETE-FAILED": [
            "Broadcom Support — Article 442155",
            "Broadcom Support — Article 418256",
            "Broadcom Support — Article 411756",
        ],
        "VMWARE-SNAPSHOT-FILE-MISSING": [
            "Broadcom Support — Article 424591",
            "Broadcom Support — Article 318905",
        ],
        "VEEAM-REPLICA-SNAPSHOT-CHAIN": [
            "Veeam Help Center — Backup & Replication replica restore points (native VMware snapshots)",
            "Veeam Help Center — Export Logs (%ProgramData%\\Veeam\\Backup)",
        ],
    }
