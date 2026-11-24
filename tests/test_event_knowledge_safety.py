import json
from pathlib import Path

EVENT_FILE = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "domain"
    / "analyzer"
    / "services"
    / "event_knowledge.json"
)


def test_all_static_event_causes_are_explicitly_hypotheses():
    data = json.loads(EVENT_FILE.read_text(encoding="utf-8"))
    for event_id, localized in data.items():
        for language in ("th", "en"):
            prefix = "สมมติฐานที่ต้องตรวจสอบ: " if language == "th" else "Possible cause to verify: "
            for cause in localized[language].get("causes", []):
                assert cause.startswith(prefix), (event_id, language, cause)


def test_high_impact_static_remediation_does_not_recommend_unscoped_destructive_actions():
    data = json.loads(EVENT_FILE.read_text(encoding="utf-8"))
    forbidden = {
        "1511": ("Delete the corrupted profile key", "ลบคีย์ที่พัง"),
        "20": ("Temporarily disable third-party Antivirus/Firewall", "ปิด Antivirus หรือ Firewall"),
        "7009": ("add DWORD 'ServicesPipeTimeout'", "เพิ่ม DWORD 'ServicesPipeTimeout'"),
        "11": ("Update Storage Controller firmware", "อัปเดต Firmware ของ Storage Controller"),
        "51": ("chkdsk /f /r", "chkdsk /f /r"),
        "55": ("chkdsk D: /f /r", "chkdsk D: /f /r"),
        "10016": ("Adjust Launch and Activation permissions", "ปรับ Launch และ Activation permissions"),
        "4771": ("Block source IP if aggressive", "บล็อก IP ต้นทาง"),
        "4688": ("Block encoded PowerShell on production hosts", "บล็อกการรัน PowerShell ที่ถูก Encoded"),
    }
    for event_id, phrases in forbidden.items():
        for language, phrase in zip(("en", "th"), phrases):
            steps = " ".join(data[event_id][language]["steps"])
            assert phrase.lower() not in steps.lower(), (event_id, language, phrase)


def test_authentication_events_do_not_assert_brute_force_from_single_event():
    data = json.loads(EVENT_FILE.read_text(encoding="utf-8"))
    for event_id in ("4625", "4740"):
        for language in ("th", "en"):
            overview = data[event_id][language]["overview"].lower()
            assert "does not" in overview or "ไม่ยืนยัน" in overview or "ไม่ควรสรุป" in overview


OPERATIONAL_CATALOG_FILE = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "domain"
    / "analyzer"
    / "services"
    / "operational_event_catalog.json"
)


def test_operational_catalog_does_not_direct_automatic_block_or_storage_repair():
    data = json.loads(OPERATIONAL_CATALOG_FILE.read_text(encoding="utf-8"))
    by_id = {item["event_id"]: item for item in data}
    assert "do not block a source" in by_id["4625"]["operator_context"].lower()
    assert "do not replace hardware" in by_id["51"]["operator_context"].lower()
    assert "state-changing recovery action" in by_id["55"]["operator_context"].lower()
    assert "do not enable integrity streams or rebuild" in by_id["98"]["operator_context"].lower()
