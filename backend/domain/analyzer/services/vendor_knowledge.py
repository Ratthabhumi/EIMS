"""Deterministic vendor knowledge for recognized infrastructure diagnostics.

Available offline; web search is only supplementary references.  Each
entry states what is OBSERVED and what is still UNKNOWN — entries never
assert an exact missing/locked file unless the evidence names it.

References name official vendor material — article numbers AND their
canonical knowledge-base URLs (verified resolvable).  Articles whose
scope is environment-specific are only surfaced when the evidence text
matches the required tokens (e.g. vSAN ESA, vVOLs), never universally.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

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
        # Supports CTK missing/corrupt/mismatch assessment.  Locking is NEVER
        # claimed by EIMS unless lock evidence exists (see entry text).
        requires_any=("lock", "cbt", "change tracking", "change-tracking", "backup", "ctk", "missing", "corrupt", "mismatch"),
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
        # Create-snapshot path only (custom gate in _article_applies).
        requires_any=("invalid snapshot", "invalidsnapshotformat"),
    ),
    VendorArticle(
        article_id="450780",
        title="Error: 'A required file was not found' when deleting a snapshot or Virtual Machine",
        url="https://knowledge.broadcom.com/external/article/450780",
        applies_to=["VMWARE-SNAPSHOT-FILE-MISSING", "VEEAM-REPLICA-SNAPSHOT-CHAIN"],
        # Snapshot deletion/consolidation only (custom gate).
        requires_any=("delet", "consolidat", "remov"),
    ),
    VendorArticle(
        article_id="452165",
        title="Error: 'A required file was not found' after manually renaming or moving virtual machine folder",
        url="https://knowledge.broadcom.com/external/article/452165",
        applies_to=["VMWARE-SNAPSHOT-FILE-MISSING", "VEEAM-REPLICA-SNAPSHOT-CHAIN"],
        # Rename/move/folder evidence only (custom word-boundary gate;
        # bare "mov" would falsely match "remove").
        requires_any=("renam", "folder", "path mismatch"),
    ),
]


def _has_word(lowered: str, word: str) -> bool:
    return re.search(r"\b" + re.escape(word) + r"\b", lowered) is not None


def _article_applies(article: VendorArticle, diagnostic_code: str, text: str) -> bool:
    lowered = (text or "").lower()
    if article.applies_to and diagnostic_code not in article.applies_to:
        return False

    # Context gates verified against the official articles.  Gated
    # articles are never surfaced universally.
    if article.article_id == "424591":
        # RevertSnapshot + InvalidSnapshotFormat + required file not found.
        if "revert" not in lowered:
            return False
        if "required file" not in lowered or "not found" not in lowered:
            return False
        if "invalidsnapshotformat" not in lowered and "invalid snapshot" not in lowered:
            return False
        return True
    if article.article_id == "318905":
        # Create-snapshot path only.  Generic words alone ("creating",
        # "creation" — e.g. "Creating job lease keeper") never qualify;
        # only explicit snapshot-creation semantics do.
        if "invalidsnapshotformat" not in lowered and "invalid snapshot" not in lowered:
            return False
        if not any(
            token in lowered
            for token in (
                "createsnapshot",
                "create snapshot",
                "creating a snapshot",
                "creating snapshot",
                "vim.virtualmachine.createsnapshot",
            )
        ):
            return False
        return True
    if article.article_id == "450780":
        # Snapshot deletion/consolidation only, AND the required-file
        # condition must belong to that same operation context.  A prior
        # "Deleting helper snapshot" line must never justify this article
        # for a later unrelated RevertSnapshot failure.
        if "snapshot" not in lowered:
            return False
        if not any(token in lowered for token in ("delet", "consolidat", "remov")):
            return False
        if "a required file" not in lowered or "not found" not in lowered:
            return False
        return True
    if article.article_id == "452165":
        # Required-file failure AND actual manual move/rename or mismatch.
        missing = "required file" in lowered and "not found" in lowered
        manual_change = re.search(
            r"\bmanual(?:ly)?\b.{0,100}(?:\brenam\w*|\bmov(?:e|ed|ing)\b)|"
            r"(?:\brenam\w*|\bmov(?:e|ed|ing)\b).{0,100}\bmanual(?:ly)?\b",
            lowered,
        )
        return bool(missing and (manual_change or "path mismatch" in lowered))

    if article.requires_all:
        if not all(needle in lowered for needle in article.requires_all):
            return False
    if article.requires_any:
        if not any(needle in lowered for needle in article.requires_any):
            return False
    return True


def _article_allowed(article_id: str, diagnostic_code: str, evidence_text: str) -> bool:
    """Reuse the retrieval context gates for deterministic summary text.

    Environment-specific articles (vSAN ESA, vVOLs, ...) must never be
    named in canned guidance unless the evidence satisfies their gates.
    Fails closed on empty evidence.  Evaluation is operation-local
    (same policy as retrieval), never whole-bundle keyword coincidence.
    """
    for article in VENDOR_ARTICLES:
        if article.article_id == article_id:
            return _article_applies_local(article, diagnostic_code, evidence_text or "")
    return False


#: Articles evaluated per file segment (environment scope: the host/cluster
#: context lives with that file's logs).  Operation articles below use
#: bounded line windows around anchor lines instead.
_SEGMENT_SCOPE_ARTICLE_IDS = frozenset({"442155", "411756", "418256"})

#: Anchor signals per operation-gated article.  Anchors are intentionally
#: broad — _article_applies stays the precise gate, evaluated on the
#: bounded window so an operation in one file/attempt can never satisfy a
#: gate with keywords from an unrelated file or attempt.
_ARTICLE_ANCHOR_RES = {
    "424591": (
        r"required file",
        r"not found",
        r"invalidsnapshotformat",
        r"invalid snapshot",
        r"revert",
    ),
    "318905": (
        r"invalidsnapshotformat",
        r"invalid snapshot",
        r"createsnapshot",
        r"create snapshot",
        r"creating a snapshot",
        r"creating snapshot",
    ),
    "450780": (
        r"required file",
        r"not found",
        r"delet",
        r"consolidat",
        r"remov",
        r"snapshot",
    ),
    "452165": (
        r"required file",
        r"not found",
        r"renam",
        r"folder",
        r"path mismatch",
        r"move",
        r"moved",
        r"moving",
    ),
}

_KB_WINDOW_RADIUS_LINES = 15


def _article_applies_local(
    article: VendorArticle, diagnostic_code: str, evidence_text: str
) -> bool:
    """Operation-local article applicability.

    Bundle combined_text carries "===== FILE:" segment markers; segments
    isolate files so cross-file keyword coincidence can never satisfy a
    gate.  Within a segment, operation-gated articles must satisfy their
    gate inside ONE bounded line window around anchor lines (same
    operation/attempt), while environment articles use the whole segment.
    Text without markers behaves exactly as before.
    """
    from backend.domain.analyzer.services import evidence as _evidence

    segments = _evidence.split_file_segments(evidence_text or "")
    for _filename, segment in segments:
        if article.article_id in _SEGMENT_SCOPE_ARTICLE_IDS:
            if _article_applies(article, diagnostic_code, segment):
                return True
            continue
        records = _evidence.build_evidence_records([(_filename or "", segment)])
        for operation in _evidence.operation_segments(records):
            lines = [rec.raw_text for rec in operation]
            anchors = _evidence.anchor_line_indexes(
                lines, _ARTICLE_ANCHOR_RES.get(article.article_id, ())
            )
            for window in _evidence.window_texts(lines, anchors, _KB_WINDOW_RADIUS_LINES):
                if _article_applies(article, diagnostic_code, window):
                    return True
    return False


def vendor_reference_results(diagnostic_code: str, evidence_text: str, language: str) -> List[SearchResult]:
    """Deterministic official KB references for a diagnostic code + evidence.

    Environment-gated articles (vSAN ESA, vVOLs, deletion, rename/move) are
    only returned when the evidence satisfies their token gates in local
    operation context — never by combining unrelated keywords from
    different files or attempts across a bundle.
    """
    if not diagnostic_code:
        return []
    language = language if language in ("th", "en") else "th"
    results: List[SearchResult] = []
    for article in VENDOR_ARTICLES:
        if not _article_applies_local(article, diagnostic_code, evidence_text):
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


def _vendor_entry(code: str, language: str, evidence_text: str = "") -> Optional[SolutionSummary]:
    lang = language if language in ("th", "en") else "th"

    if code == "VMWARE-CBT-DELETE-FAILED":
        # Evidence-conditioned wording: the code triggers on the CBT deletion
        # line alone, so result codes / unlink ops / lock / environment facts
        # are stated ONLY when the evidence contains them.
        _ev = (evidence_text or "").lower()
        _sig2620 = re.search(r"result\s*:?\s*2620", _ev) is not None
        _sigunlink = "ctk_ctkunlink" in _ev
        _overview_extra_en = ""
        _overview_extra_th = ""
        if _sig2620:
            _overview_extra_en += " Result 2620 was recorded in the evidence."
            _overview_extra_th += " พบผลลัพธ์ 2620 ในหลักฐานที่ให้มา"
        if _sigunlink:
            _overview_extra_en += " A CTK_CTKUNLINK operation result was recorded in the evidence."
            _overview_extra_th += " พบผลการทำงาน CTK_CTKUNLINK ในหลักฐานที่ให้มา"
        # Name only the Broadcom articles whose environment gates the
        # evidence satisfies.  418256 (CTK) passes whenever this code's
        # own trigger text is present; 442155 needs vSAN + ESA, 411756
        # needs vVOLs — never cite them without that environment evidence.
        _articles = []
        if _article_allowed("418256", code, evidence_text):
            _articles.append("Article 418256 (CTK)")
        if _article_allowed("442155", code, evidence_text):
            _articles.append("Article 442155 (vSAN ESA)")
        if _article_allowed("411756", code, evidence_text):
            _articles.append("Article 411756 (vVOLs)")
        if _articles:
            _articles_en = (
                "Refer to official Broadcom material: "
                + ", ".join(_articles)
                + " — verify each article’s scope before applying"
            )
            _articles_th = (
                "อ้างอิงเอกสารทางการของ Broadcom: "
                + ", ".join(_articles)
                + " — ตรวจสอบเงื่อนไขของแต่ละบทความก่อนนำไปใช้"
            )
        else:
            _articles_en = (
                "Refer to official Broadcom VMware CBT troubleshooting "
                "documentation — verify scope before applying"
            )
            _articles_th = (
                "อ้างอิงเอกสาร troubleshooting CBT ของ Broadcom "
                "— ตรวจสอบเงื่อนไขก่อนนำไปใช้"
            )
        return _summary(
            overview=_th_en(
                "VMware ไม่สามารถลบ change-tracking (.ctk) file ได้"
                + _overview_extra_th,
                "VMware could not delete a change-tracking (.ctk) file."
                + _overview_extra_en,
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
                    _articles_th,
                    _articles_en,
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
        # Causes and article mentions follow the SAME context gates as
        # retrieval: deletion/move/rename/vVOLs/create-path are possibilities
        # ONLY when the evidence supports that context.  Never state them
        # as established facts.
        _sm_causes = [
            _th_en(
                "descriptor ชี้ chain ไม่ตรงกับไฟล์จริงบน datastore",
                "Snapshot descriptor chain does not match files actually on the datastore",
                lang,
            ),
        ]
        if _article_allowed("452165", code, evidence_text):
            _sm_causes.append(
                _th_en(
                    "ไฟล์อาจถูกเปลี่ยนชื่อหรือย้าย (ดูเอกสารอ้างอิงที่ตรงบริบท)",
                    "The file may have been renamed or moved (see the context-matching reference)",
                    lang,
                )
            )
        if _article_allowed("450780", code, evidence_text):
            _sm_causes.append(
                _th_en(
                    "ไฟล์อาจถูกลบระหว่าง snapshot consolidation (ดูเอกสารอ้างอิงที่ตรงบริบท)",
                    "The file may have been deleted during snapshot consolidation (see the context-matching reference)",
                    lang,
                )
            )
        if _article_allowed("411756", code, evidence_text):
            _sm_causes.append(
                _th_en(
                    "datastore อาจเป็นแบบ vVOLs (ดูเอกสารอ้างอิงที่ตรงบริบท)",
                    "The datastore may be vVOLs-based (see the context-matching reference)",
                    lang,
                )
            )
        if len(_sm_causes) == 1:
            _sm_causes.append(
                _th_en(
                    "ยืนยันสถานะไฟล์จริงด้วย datastore listing ก่อนดำเนินการ",
                    "Confirm the exact file state with a datastore listing before acting",
                    lang,
                )
            )

        _sm_articles = []
        if _article_allowed("424591", code, evidence_text):
            _sm_articles.append("Article 424591")
        if _article_allowed("318905", code, evidence_text):
            _sm_articles.append("Article 318905")
        if _article_allowed("450780", code, evidence_text):
            _sm_articles.append("Article 450780")
        if _article_allowed("452165", code, evidence_text):
            _sm_articles.append("Article 452165")
        if _article_allowed("411756", code, evidence_text):
            _sm_articles.append("Article 411756 (vVOLs)")
        if _sm_articles:
            _sm_ref_en = (
                "Refer to official Broadcom material: "
                + ", ".join(_sm_articles)
                + " — verify each article’s scope before applying"
            )
            _sm_ref_th = (
                "อ้างอิงเอกสารทางการของ Broadcom: "
                + ", ".join(_sm_articles)
                + " — ตรวจสอบเงื่อนไขของแต่ละบทความก่อนนำไปใช้"
            )
        else:
            _sm_ref_en = (
                "Refer to official Broadcom VMware snapshot troubleshooting "
                "documentation — verify scope before applying"
            )
            _sm_ref_th = (
                "อ้างอิงเอกสาร troubleshooting snapshot ของ Broadcom "
                "— ตรวจสอบเงื่อนไขก่อนนำไปใช้"
            )

        return _summary(
            overview=_th_en(
                "การอ้างอิง snapshot disk ของ VM ชี้ไปยังไฟล์ที่ VMware หาไม่พบ "
                "(InvalidSnapshotFormat + required file not found)",
                "The VM snapshot configuration references a required file or snapshot "
                "disk that VMware cannot find (InvalidSnapshotFormat + required file not found).",
                lang,
            ),
            causes=_sm_causes,
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
                    _sm_ref_th,
                    _sm_ref_en,
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
        # Evidence-conditioned wording: this code can resolve WITHOUT any
        # CBT deletion error, so CBT / helper-snapshot / missing-file facts
        # are stated ONLY when the evidence contains them.
        _ev = (evidence_text or "").lower()
        _has_cbt = "could not delete change tracking file" in _ev
        _has_helper = "deleting helper snapshot" in _ev
        _has_bad_config = "invalid snapshot configuration" in _ev
        _has_missing = "a required file" in _ev and "not found" in _ev
        _has_revert_invalid = "revertsnapshot" in _ev and (
            "invalidsnapshotformat" in _ev or "invalid snapshot" in _ev
        )

        _rc_causes = []
        if _has_cbt:
            _rc_causes.append(
                _th_en(
                    "ขั้นตอนแรกที่สังเกตได้: ลบ change-tracking file ไม่สำเร็จ",
                    "First observed failure: change-tracking file deletion failed",
                    lang,
                )
            )
        if _has_missing:
            _rc_causes.append(
                _th_en(
                    "ขั้นตอนหลังที่สังเกตได้: configuration ของ replica snapshot "
                    "อ้างถึงไฟล์ที่ VMware หาไม่พบ" if _has_cbt else
                    "configuration ของ replica snapshot อ้างถึงไฟล์ที่ VMware หาไม่พบ",
                    "Later observed failure: the replica snapshot configuration references "
                    "a required file VMware cannot locate" if _has_cbt else
                    "Observed failure: the replica snapshot configuration references "
                    "a required file VMware cannot locate",
                    lang,
                )
            )
        elif _has_bad_config:
            _rc_causes.append(
                _th_en(
                    "configuration ของ replica snapshot ไม่ถูกต้องตามที่สังเกตได้",
                    "Observed failure: the replica snapshot configuration is invalid",
                    lang,
                )
            )
        if not _rc_causes:
            _rc_causes.append(
                _th_en(
                    "replica snapshot chain ผิดปกติ (ดู signatures ที่สังเกตได้ด้านล่าง)",
                    "Replica snapshot chain is unhealthy (see observed signatures below)",
                    lang,
                )
            )

        _rc_evidence = []
        if _has_cbt:
            _rc_evidence.append("Could not delete change tracking file")
        if _has_helper:
            _rc_evidence.append("Deleting helper snapshot")
        if _has_bad_config:
            _rc_evidence.append("Detected an invalid snapshot configuration")
        if _has_missing:
            _rc_evidence.append("A required file was not found")
        if _has_revert_invalid:
            _rc_evidence.append("RevertSnapshot / InvalidSnapshotFormat")

        _rc_steps = [
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
        ]
        if _has_cbt:
            _rc_steps.append(
                _th_en(
                    "อย่าสรุปว่าการลบ CBT ทำให้ไฟล์ snapshot หาย จนกว่าหลักฐานจะพิสูจน์ causal link",
                    "Do NOT conclude the CBT deletion caused the missing snapshot file unless "
                    "evidence proves the causal link",
                    lang,
                )
            )

        _rc_limitations = []
        if _has_cbt and _has_missing:
            _rc_limitations.append(
                _th_en(
                    "ความสัมพันธ์ระหว่าง CBT deletion failure กับ missing snapshot dependency "
                    "ยังไม่พิสูจน์ว่าเป็นสาเหตุเดียวกัน",
                    "The relationship between the earlier CBT deletion failure and the later "
                    "missing snapshot dependency is NOT proven causal",
                    lang,
                )
            )
        else:
            _rc_limitations.append(
                _th_en(
                    "ห้ามระบุชื่อไฟล์ที่หาย ถ้า log ไม่ได้ระบุชื่อไว้",
                    "Do NOT name the missing file unless the log names it",
                    lang,
                )
            )

        return _summary(
            overview=_th_en(
                "Replication เข้าสู่ขั้นตอน snapshot cleanup/revert ของ replica แล้ว "
                "พบความผิดปกติของ replica snapshot chain (Veeam ใช้ native VMware snapshots)",
                "Replication reached the replica snapshot cleanup/revert stage and the "
                "replica snapshot chain is unhealthy (replica restore points use native "
                "VMware snapshots with native snapshot revert).",
                lang,
            ),
            causes=_rc_causes,
            steps=_rc_steps,
            evidence=_rc_evidence,
            confidence="medium",
            limitations=_rc_limitations,
            next_evidence=[
                "Replica VM vmware.log",
                "ESXi hostd.log",
                "Datastore file listing",
                "Veeam Task/Job session logs",
            ],
        )

    return None


def get_vendor_summary(
    diagnostic_code: str, language: str, evidence_text: str = ""
) -> Optional[SolutionSummary]:
    """Return the deterministic curated summary for a diagnostic code.

    evidence_text gates environment-specific article mentions (vSAN ESA,
    vVOLs); empty evidence fails those gates closed.
    """
    if not diagnostic_code:
        return None
    return _vendor_entry(diagnostic_code.strip(), language, evidence_text or "")
