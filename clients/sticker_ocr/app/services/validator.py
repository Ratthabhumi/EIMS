import re
from typing import Optional

_SN_PATTERN = re.compile(r"\b([A-Z0-9]{8})\b")
_ID_PATTERN = re.compile(r"\b(\d{2}S-[A-Z]\d{3})\b")

# Common 8-letter English words on stickers/labels that are NOT serial numbers
_SN_BLACKLIST = {
    "NOTEBOOK", "WARRANTY", "CUSTOMER", "THAILAND", "COMPUTE",
    "SECURITY", "SOFTWARE", "HARDWARE", "DOCUMENT", "RESEARCH",
    "DISCOUNT", "OVERSEAS", "DIRECTOR", "DATABASE", "BUSINESS",
    "STANDARD", "REGIONAL", "STRATEGY", "PERSONAL", "DELIVERY",
    "ORIGINAL", "INTERNAL", "EXTERNAL", "FUNCTION", "SCHEDULE",
    "ETHERNET", "WIRELESS", "TERMINAL", "ASSEMBLY", "GIGABIT",
    "AMERICAN", "CANADIAN", "JAPANESE", "CHINESE", "SINGAPORE",
    "MALAYSIA", "GERMANY", "REPUBLIC", "INDUSTRY", "PRODUCER",
}

_IGNORED_SUBSTRINGS = (
    "THAI", "LAND", "THA", "MADE", "ASSM", "NOTE", "WARR", "ETHER",
    "ROUT", "SWIT", "GIGA", "WIRE", "ADAP", "VOLT", "CURR", "CUST",
)


def _to_letters_only(text: str) -> str:
    """Convert digit OCR typos back to letters to catch OCR typos of blacklisted English words."""
    t = text.upper()
    return t.replace("0", "O").replace("1", "I").replace("2", "Z").replace("5", "S").replace("8", "B").replace("4", "A")


def _is_ignored_keyword(candidate: str) -> bool:
    cand_upper = candidate.upper()
    letters_only = _to_letters_only(cand_upper)
    if cand_upper in _SN_BLACKLIST or letters_only in _SN_BLACKLIST:
        return True
    for sub in _IGNORED_SUBSTRINGS:
        if sub in cand_upper or sub in letters_only:
            return True
    return False


def sanitize_filename_str(text: str) -> str:
    """Remove Windows illegal path characters: \\ / : * ? " < > |"""
    return re.sub(r'[\\/:*?"<>|]', "", text).strip()


def extract_serial_number(text: str) -> Optional[str]:
    raw = text.upper()
    for header in ("SERIAL NUMBER", "SERIAL NO.", "SERIAL NO", "SERIAL", "S/N:", "S/N", "SN:", "SN"):
        raw = raw.replace(header, " ")
    cleaned = raw.replace(" ", "").replace("—", "-").replace(":", "")
    matches = _SN_PATTERN.findall(cleaned)

    # 1. Look for valid 8-char candidate not in blacklist or ignored keywords
    candidates = [m for m in matches if not _is_ignored_keyword(m)]
    
    # In network equipment, letter O is avoided in favor of 0 (zero)
    candidates = [cand.replace("O", "0") for cand in candidates]

    # Prefer candidates with at least one digit
    for cand in candidates:
        if any(c.isdigit() for c in cand):
            return cand

    if candidates:
        return candidates[0]

    # 2. Try fallback regex with character swaps (O->0, I->1, Z->2, L->1)
    fallback = cleaned.replace("O", "0").replace("I", "1").replace("Z", "2").replace("L", "1")
    matches_fb = _SN_PATTERN.findall(fallback)
    candidates_fb = [m for m in matches_fb if not _is_ignored_keyword(m)]
    candidates_fb = [cand.replace("O", "0") for cand in candidates_fb]

    for cand in candidates_fb:
        if any(c.isdigit() for c in cand):
            return cand

    if candidates_fb:
        return candidates_fb[0]

    return None


def extract_device_id(text: str) -> Optional[str]:
    raw = text.upper()
    for header in ("DEVICE ID", "ID NO.", "ID NO", "ID:", "ID"):
        raw = raw.replace(header, " ")
    # In network equipment and IDs, O is avoided in favor of 0 (zero)
    cleaned = raw.replace(" ", "").replace("—", "-").replace(":", "").replace("O", "0")
    match = _ID_PATTERN.search(cleaned)
    if match:
        return sanitize_filename_str(match.group(1))

    # Handle OCR common misread where 'S' looks like '5' or 'A' looks like '4'
    flex_match = re.search(r"(\d{2})[S5]-([A-Z0-9])(\d{3})", cleaned)
    if flex_match:
        d1, char1, d2 = flex_match.group(1), flex_match.group(2), flex_match.group(3)
        char_clean = "A" if char1 == "4" else ("B" if char1 == "8" else char1)
        res = f"{d1}S-{char_clean}{d2}"
        return sanitize_filename_str(res).replace("O", "0")

    return None


def validate_serial_number(sn: str) -> bool:
    clean = sanitize_filename_str(sn.strip().upper()).replace("O", "0")
    return bool(_SN_PATTERN.fullmatch(clean)) and not _is_ignored_keyword(clean)


def validate_device_id(device_id: str) -> bool:
    clean = sanitize_filename_str(device_id.strip().upper()).replace("O", "0")
    return bool(_ID_PATTERN.fullmatch(clean))


def build_folder_name(sn: str, device_id: str) -> str:
    clean_sn = sanitize_filename_str(sn.strip().upper()).replace("O", "0")
    clean_id = sanitize_filename_str(device_id.strip().upper()).replace("O", "0")
    return f"{clean_sn}({clean_id})"
