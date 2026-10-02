from fastapi import APIRouter, File, HTTPException, UploadFile, Form, Depends, Header
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import io
import time
import xml.etree.ElementTree as ET

from backend.domain.analyzer.auth import get_current_user
from backend.infrastructure.database import get_db_session as get_db
from backend.domain.analyzer.models.history import AnalysisHistory
from backend.domain.analyzer.schemas.analyze import (
    AnalyzeResponse,
    BundleFileResult,
    BundleResponse,
    EvidenceItem,
    FollowUpRequest,
    FollowUpResponse,
    IncidentAssessment,
    SearchResult,
    SolutionSummary,
)
from backend.domain.analyzer.services.parser import parse_event_metadata
from backend.domain.analyzer.services.evtx_parser import parse_evtx
from backend.domain.analyzer.services.compaction import compact_log_evidence
from backend.domain.analyzer.services.incident_extract import extract_incident
from backend.domain.analyzer.services.bundle import (
    BUNDLE_MAX_FILES,
    build_evidence_items,
    correlate_bundle,
    summarize_file_evidence,
    validate_bundle,
)
from backend.domain.analyzer.services.summary import (
    search_solutions,
    build_summary,
    format_summary_text,
    build_followup_answer,
)

try:
    from PIL import Image
    import pytesseract
except ImportError:
    pass

router = APIRouter()


def _process_upload(content: bytes, filename: str, content_type: str | None) -> tuple[str, str]:
    lower_name = (filename or "").lower()

    if content_type and content_type.startswith("image/"):
        try:
            from PIL import ImageEnhance, ImageFilter, ImageOps
            img = Image.open(io.BytesIO(content))
            
            # 1. Convert to Grayscale & Resize if too small for better OCR sharpness
            gray_img = ImageOps.grayscale(img)
            if gray_img.width < 1000:
                scale = 1000 / gray_img.width
                gray_img = gray_img.resize((int(gray_img.width * scale), int(gray_img.height * scale)), Image.Resampling.LANCZOS)
            
            # 2. Increase Contrast & Sharpness
            enhancer = ImageEnhance.Contrast(gray_img)
            contrast_img = enhancer.enhance(1.8)
            sharp_img = contrast_img.filter(ImageFilter.SHARPEN)

            # 3. Apply Adaptive Thresholding (Binarization)
            threshold = 140
            bin_img = sharp_img.point(lambda p: 255 if p > threshold else 0)

            # Extract via Tesseract with Thai + English support
            extracted_text = pytesseract.image_to_string(bin_img, config="--psm 6")
            if not extracted_text.strip():
                # Fallback to grayscale if binarization was too aggressive
                extracted_text = pytesseract.image_to_string(gray_img)
                
            description = "(Extracted from Image via Preprocessed OCR)"
            return extracted_text, description
        except Exception as e:
            raise ValueError(
                f"OCR Failed: {e}. Install Tesseract-OCR: "
                "https://github.com/UB-Mannheim/tesseract/wiki"
            )

    if lower_name.endswith(".evtx"):
        extracted, description = parse_evtx(content)
        return extracted, description

    if lower_name.endswith(".xml"):
        try:
            text = content.decode("utf-8", errors="ignore")
            # Try to format it as standard event text
            from backend.domain.analyzer.services.evtx_parser import _event_xml_to_text
            formatted_text = _event_xml_to_text(text)
            if formatted_text:
                return formatted_text, f"Parsed XML file: {filename}"
            return text, f"Uploaded file: {filename}"
        except Exception as e:
            raise ValueError(f"XML Parse Failed: {e}")

    if lower_name.endswith((".html", ".htm")):
        try:
            from backend.domain.analyzer.services.vendor_parsers import html_to_text
            raw_html = content.decode("utf-8", errors="ignore")
            extracted = html_to_text(raw_html)
            if not extracted.strip():
                return raw_html, f"Uploaded HTML file (no text extracted): {filename}"
            return extracted, f"Parsed HTML report: {filename}"
        except Exception as e:
            raise ValueError(f"HTML Parse Failed: {e}")

    if lower_name.endswith(".csv"):
        try:
            import csv, io as _io
            text_raw = content.decode("utf-8", errors="ignore")
            reader = csv.DictReader(_io.StringIO(text_raw))
            rows = list(reader)
            if rows:
                # Convert first 50 rows to readable text
                lines = []
                for i, row in enumerate(rows[:50]):
                    line = "  ".join(f"{k}: {v}" for k, v in row.items() if v)
                    lines.append(line)
                return "\n".join(lines), f"Parsed CSV file: {filename} ({len(rows)} rows)"
            # Fallback: plain text
            return text_raw, f"Uploaded CSV file: {filename}"
        except Exception:
            pass

    # .txt, .log, and any other plaintext files
    text = content.decode("utf-8", errors="ignore")
    return text, f"Uploaded file: {filename}"


@router.post("/", response_model=AnalyzeResponse)
async def submit_analysis(
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    language: str = Form("th"),
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
    x_gemini_api_key: Optional[str] = Header(None),
):
    description = ""
    combined_text = text or ""

    if file:
        # Prevent Memory Exhaustion / DoS (max 5MB)
        MAX_FILE_SIZE = 5 * 1024 * 1024
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            return AnalyzeResponse(
                eventId="Unknown",
                provider="Unknown",
                description="File is too large (max 5MB allowed).",
            )
            
        try:
            extracted, description = _process_upload(
                content, file.filename or "", file.content_type
            )
            combined_text = (combined_text + "\n" + extracted).strip()
        except ValueError as e:
            return AnalyzeResponse(
                eventId="Unknown",
                provider="Unknown",
                description=str(e),
            )

    if not description and combined_text:
        description = "Submitted via Text"

    # Bounded evidence-aware compaction: header + signal windows + tail.
    # Never silently discards failures located past a fixed head offset.
    combined_text = compact_log_evidence(combined_text)

    metadata = parse_event_metadata(combined_text, (file.filename or "") if file else "")
    lang = language if language in ("th", "en") else "th"

    start_time = time.time()
    evidence_text_ctx = combined_text or description or ""
    results, combined_snippets = await asyncio.to_thread(
        search_solutions,
        metadata.eventId,
        metadata.provider,
        source_family=metadata.sourceFamily or None,
        diagnostic_code=metadata.diagnosticCode or None,
        evidence_text=evidence_text_ctx,
        product=metadata.product or "",
    )
    solution = await build_summary(
        metadata.eventId, metadata.provider, combined_snippets, results, lang,
        metadata.faultingApp, x_gemini_api_key, combined_text, db,
        source_family=metadata.sourceFamily or None,
        diagnostic_code=metadata.diagnosticCode or None,
        product=metadata.product or "",
        evidence_text=evidence_text_ctx,
    )
    # Evidence-first attachment: deterministic incident sketch fills fields
    # the synthesis path did not provide (curated vendor paths already do).
    incident = extract_incident(combined_text, metadata.sourceFamily or "")
    if not solution.evidence and incident.get("evidence"):
        solution.evidence = [str(x) for x in incident["evidence"][:8]]
    if not solution.nextEvidence and incident.get("nextEvidence"):
        solution.nextEvidence = [str(x) for x in incident["nextEvidence"][:6]]
    if not solution.limitations and incident.get("unknowns"):
        solution.limitations = [str(x) for x in incident["unknowns"][:4]]
    if not solution.confidence and metadata.sourceFamily in ("veeam_vbr", "vmware"):
        solution.confidence = "medium"
    try:
        solution.incident = IncidentAssessment(
            firstMeaningfulFailure=str(incident.get("firstMeaningfulFailure", "")),
            terminalFailure=str(incident.get("terminalFailure", "")),
            timeline=[str(x) for x in incident.get("timeline", [])][:12],
            operationStage=str(incident.get("operationStage", "")),
            diagnosticSignatures=[str(x) for x in incident.get("diagnosticSignatures", [])][:8],
            observedPaths=[str(x) for x in incident.get("observedPaths", [])][:8],
            unknowns=[str(x) for x in incident.get("unknowns", [])][:6],
            nextEvidence=[str(x) for x in incident.get("nextEvidence", [])][:6],
        )
    except Exception:
        pass
    final_summary = format_summary_text(solution, lang)
    search_time_ms = (time.time() - start_time) * 1000

    db_history = AnalysisHistory(
        event_id=metadata.eventId,
        provider=metadata.provider,
        parse_method=description,
        description=combined_text or "No raw text",
        ai_summary=final_summary,
        solution_summary=solution.model_dump(),
        event_metadata=metadata.model_dump(),
        search_results=[res.model_dump() for res in results],
        search_time_ms=search_time_ms,
        username=_user,
    )
    db.add(db_history)
    await db.commit()
    await db.refresh(db_history)

    # Auto-export to Vector DB (safely isolated)
    try:
        from backend.domain.analyzer.services.vector_db import add_solution
        await add_solution(
            db=db,
            event_id=metadata.eventId,
            description=combined_text or "No raw text",
            solution_summary=solution.model_dump(),
            feedback_score=0,
            api_key=x_gemini_api_key
        )
    except Exception as e:
        print(f"Failed to auto-export to Vector DB (safe ignore): {e}")

    return AnalyzeResponse(
        eventId=metadata.eventId,
        provider=metadata.provider,
        description=description,
        eventMetadata=metadata,
        aiSummary=final_summary,
        solutionSummary=solution,
        searchResults=results,
        historyId=db_history.id,
    )


@router.post("/bundle", response_model=BundleResponse)
async def submit_bundle(
    files: List[UploadFile] = File(...),
    language: str = Form("th"),
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
    x_gemini_api_key: Optional[str] = Header(None),
):
    raw: List[tuple] = []
    for upload in files or []:
        try:
            content = await upload.read()
        except Exception:
            raise HTTPException(status_code=400, detail="Failed to read an uploaded file.")
        raw.append((upload.filename or "unnamed", content))
    try:
        cleaned = validate_bundle(raw)
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e))

    lang = language if language in ("th", "en") else "th"
    per_file = []
    combined_parts: List[str] = []
    for filename, content in cleaned:
        try:
            extracted, _desc = _process_upload(content, filename, None)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"{filename}: {e}")
        compacted = compact_log_evidence(extracted or "")
        meta = parse_event_metadata(compacted, filename)
        per_file.append(
            summarize_file_evidence(
                filename=filename,
                content=content,
                text=compacted,
                source_family=meta.sourceFamily or "",
                product=meta.product or "",
                diagnostic_code=meta.diagnosticCode or "",
                parser_confidence=float(meta.parserConfidence or 0.0),
            )
        )
        combined_parts.append(f"===== FILE: {filename} =====\n{compacted}")

    correlation = correlate_bundle(per_file)
    combined_text = compact_log_evidence("\n\n".join(combined_parts))

    # Primary identity: majority diagnostic code, else first file.
    primary = per_file[0]
    code_votes: dict = {}
    for entry in per_file:
        if entry.diagnosticCode:
            code_votes[entry.diagnosticCode] = code_votes.get(entry.diagnosticCode, 0) + 1
    if code_votes:
        top_code = sorted(code_votes.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        for entry in per_file:
            if entry.diagnosticCode == top_code:
                primary = entry
                break
    primary_meta = parse_event_metadata(primary.text, primary.filename)

    start_time = time.time()
    results, combined_snippets = await asyncio.to_thread(
        search_solutions,
        primary_meta.eventId,
        primary_meta.provider,
        source_family=primary_meta.sourceFamily or None,
        diagnostic_code=primary_meta.diagnosticCode or None,
        evidence_text=combined_text,
        product=primary_meta.product or "",
    )
    solution = await build_summary(
        primary_meta.eventId,
        primary_meta.provider,
        combined_snippets,
        results,
        lang,
        primary_meta.faultingApp,
        x_gemini_api_key,
        combined_text,
        db,
        source_family=primary_meta.sourceFamily or None,
        diagnostic_code=primary_meta.diagnosticCode or None,
        product=primary_meta.product or "",
        evidence_text=combined_text,
    )
    incident = extract_incident(combined_text, primary_meta.sourceFamily or "")
    if not solution.evidence and incident.get("evidence"):
        solution.evidence = [str(x) for x in incident["evidence"][:8]]
    if not solution.nextEvidence and incident.get("nextEvidence"):
        solution.nextEvidence = [str(x) for x in incident["nextEvidence"][:6]]
    if not solution.limitations and incident.get("unknowns"):
        solution.limitations = [str(x) for x in incident["unknowns"][:4]]
    if not solution.confidence and primary_meta.sourceFamily in ("veeam_vbr", "vmware"):
        solution.confidence = "medium"
    try:
        items = build_evidence_items(per_file)
        solution.evidenceItems = [EvidenceItem(**item) for item in items]
    except Exception:
        pass
    try:
        solution.incident = IncidentAssessment(
            firstMeaningfulFailure=str(incident.get("firstMeaningfulFailure", "")),
            terminalFailure=str(incident.get("terminalFailure", "")),
            timeline=[str(x) for x in incident.get("timeline", [])][:12],
            operationStage=str(incident.get("operationStage", "")),
            diagnosticSignatures=[str(x) for x in incident.get("diagnosticSignatures", [])][:8],
            observedPaths=[str(x) for x in incident.get("observedPaths", [])][:8],
            unknowns=[str(x) for x in incident.get("unknowns", [])][:6],
            nextEvidence=[str(x) for x in incident.get("nextEvidence", [])][:6],
        )
    except Exception:
        pass
    final_summary = format_summary_text(solution, lang)
    search_time_ms = (time.time() - start_time) * 1000

    # Bundle provenance lives inside attributes["bundle"] so HistoryResponse
    # reconstruction (EventMetadata(**...)) preserves it across reloads.
    bundle_attrs = dict(primary_meta.attributes or {})
    bundle_attrs["bundle"] = {
        "files": [
            {
                "filename": e.filename,
                "sizeBytes": e.sizeBytes,
                "sha256": e.sha256,
                "sourceFamily": e.sourceFamily,
                "product": e.product,
                "diagnosticCode": e.diagnosticCode,
                "parserConfidence": e.parserConfidence,
            }
            for e in per_file
        ],
        "correlationConfidence": correlation.get("correlationConfidence"),
        "correlationReasons": correlation.get("correlationReasons"),
        "correlatedSources": correlation.get("correlatedSources"),
    }
    primary_meta.attributes = bundle_attrs
    db_history = AnalysisHistory(
        event_id=primary_meta.eventId,
        provider=primary_meta.provider,
        parse_method=f"Evidence bundle ({len(per_file)} files)",
        description=combined_text or "No raw text",
        ai_summary=final_summary,
        solution_summary=solution.model_dump(),
        event_metadata=primary_meta.model_dump(),
        search_results=[res.model_dump() for res in results],
        search_time_ms=search_time_ms,
        username=_user,
    )
    db.add(db_history)
    await db.commit()
    await db.refresh(db_history)

    try:
        from backend.domain.analyzer.services.vector_db import add_solution
        await add_solution(
            db=db,
            event_id=primary_meta.eventId,
            description=combined_text or "No raw text",
            solution_summary=solution.model_dump(),
            feedback_score=0,
            api_key=x_gemini_api_key
        )
    except Exception as e:
        print(f"Failed to auto-export to Vector DB (safe ignore): {e}")

    return BundleResponse(
        bundleId=db_history.id,
        historyId=db_history.id,
        eventId=primary_meta.eventId,
        provider=primary_meta.provider,
        files=[
            BundleFileResult(
                filename=e.filename,
                sizeBytes=e.sizeBytes,
                sha256=e.sha256,
                sourceFamily=e.sourceFamily,
                product=e.product,
                diagnosticCode=e.diagnosticCode,
                parserConfidence=e.parserConfidence,
            )
            for e in per_file
        ],
        correlationConfidence=str(correlation.get("correlationConfidence", "none")),
        correlationReasons=[str(x) for x in correlation.get("correlationReasons", [])],
        correlatedSources=[str(x) for x in correlation.get("correlatedSources", [])],
        eventMetadata=primary_meta,
        aiSummary=final_summary,
        solutionSummary=solution,
        searchResults=results,
    )


@router.post("/followup", response_model=FollowUpResponse)
async def followup_question(
    body: FollowUpRequest,
    _user: str = Depends(get_current_user),
    x_gemini_api_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    lang = body.language if body.language in ("th", "en") else "th"

    # Authoritative path: the stored history row wins.  Caller-supplied
    # eventId/provider NEVER override the recorded analysis, and no fresh
    # web search or rebuild runs for ordinary follow-up.
    if getattr(body, "historyId", None) and db:
        try:
            h = await db.get(AnalysisHistory, body.historyId)
        except Exception:
            h = None
        if h is not None:
            em = (h.event_metadata or {}) if isinstance(h.event_metadata, dict) else {}
            sol_dict = (h.solution_summary or {}) if isinstance(h.solution_summary, dict) else {}
            try:
                stored_summary = SolutionSummary(**sol_dict)
            except Exception:
                stored_summary = SolutionSummary(
                    overview=str(sol_dict.get("overview", "")),
                    causes=[str(x) for x in sol_dict.get("causes", [])][:5],
                    steps=[str(x) for x in sol_dict.get("steps", [])][:8],
                )
            stored_results: List[SearchResult] = []
            try:
                raw_refs = h.search_results or []
                for ref in raw_refs[:8]:
                    if isinstance(ref, dict):
                        stored_results.append(SearchResult(**ref))
            except Exception:
                stored_results = []
            answer = build_followup_answer(
                body.question,
                stored_summary,
                stored_results,
                lang,
                x_gemini_api_key,
                source_family=em.get("sourceFamily"),
                event_id=h.event_id or "Unknown",
                provider=h.provider or "Unknown",
                diagnostic_code=em.get("diagnosticCode"),
            )
            return FollowUpResponse(answer=answer)

    # Legacy path (no historyId): derive context from the request body.
    results, combined_snippets = await asyncio.to_thread(
        search_solutions,
        body.eventId,
        body.provider,
        language=lang,
    )
    summary = await build_summary(
        body.eventId,
        body.provider,
        combined_snippets,
        results,
        lang,
        "",
        x_gemini_api_key,
        "",
        db,
    )
    answer = build_followup_answer(
        body.question,
        summary,
        results,
        lang,
        x_gemini_api_key,
        event_id=body.eventId,
        provider=body.provider,
    )
    return FollowUpResponse(answer=answer)
