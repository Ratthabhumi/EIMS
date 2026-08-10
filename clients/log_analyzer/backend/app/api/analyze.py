from fastapi import APIRouter, File, UploadFile, Form, Depends, Header
from typing import Optional
from sqlalchemy.orm import Session
import io
import time
import xml.etree.ElementTree as ET

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.history import AnalysisHistory
from app.schemas.analyze import AnalyzeResponse, FollowUpRequest, FollowUpResponse
from app.services.parser import parse_event_metadata
from app.services.evtx_parser import parse_evtx
from app.services.summary import (
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
            img = Image.open(io.BytesIO(content))
            extracted_text = pytesseract.image_to_string(img)
            description = "(Extracted from Image via OCR)"
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
            from app.services.evtx_parser import _event_xml_to_text
            formatted_text = _event_xml_to_text(text)
            if formatted_text:
                return formatted_text, f"Parsed XML file: {filename}"
            return text, f"Uploaded file: {filename}"
        except Exception as e:
            raise ValueError(f"XML Parse Failed: {e}")

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
    db: Session = Depends(get_db),
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

    # Prevent DB bloat
    if len(combined_text) > 50000:
        combined_text = combined_text[:50000] + "... (truncated)"
        
    metadata = parse_event_metadata(combined_text)
    lang = language if language in ("th", "en") else "th"

    start_time = time.time()
    results, combined_snippets = search_solutions(metadata.eventId, metadata.provider)
    solution = build_summary(metadata.eventId, metadata.provider, combined_snippets, results, lang, metadata.faultingApp, x_gemini_api_key, combined_text, db)
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
    db.commit()
    db.refresh(db_history)

    # Auto-export to Vector DB
    from app.services.vector_db import add_solution
    try:
        # Auto export to Vector DB (score 0 means unverified, but it's now saved auto)
        add_solution(
            db=db,
            event_id=metadata.eventId,
            description=combined_text or "No raw text",
            solution_summary=solution.model_dump(),
            feedback_score=0,
            api_key=x_gemini_api_key
        )
    except Exception as e:
        print(f"Failed to auto-export to Vector DB: {e}")

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


@router.post("/followup", response_model=FollowUpResponse)
def followup_question(
    body: FollowUpRequest,
    _user: str = Depends(get_current_user),
    x_gemini_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    results, combined_snippets = search_solutions(body.eventId, body.provider)
    summary = build_summary(body.eventId, body.provider, combined_snippets, results, body.language, "", x_gemini_api_key, "", db)
    answer = build_followup_answer(body.question, summary, results, body.language, x_gemini_api_key)
    return FollowUpResponse(answer=answer)
