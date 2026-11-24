"""Guards Analyzer UX: no application login UI; product name is Log Analyzer."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PAGE = ROOT / "clients" / "dashboard" / "src" / "app" / "analyzer" / "page.tsx"
ANALYZER_SESSION = ROOT / "clients" / "dashboard" / "src" / "components" / "AnalyzerSession.tsx"
SIDEBAR = ROOT / "clients" / "dashboard" / "src" / "components" / "SidebarNav.tsx"
HOME = ROOT / "clients" / "dashboard" / "src" / "app" / "page.tsx"

PROHIBITED = (
    "Username / ชื่อผู้ใช้",
    "Password / รหัสผ่าน",
    "Sign in / เข้าสู่ระบบ",
    "Session expired or sign-in required",
    "Session service unavailable",
    "ต้องเข้าสู่ระบบหรือ session หมดอายุ",
    "ไม่สามารถตรวจ session ได้",
    "AI Log Analyzer (EventIQ)",
    "Vector RAG",
)


def test_analyzer_page_has_no_login_ui_and_uses_log_analyzer_name():
    text = ANALYZER_PAGE.read_text(encoding="utf-8")
    for needle in PROHIBITED:
        assert needle not in text, f"Prohibited UI copy still present: {needle}"
    assert "Log Analyzer" in text
    assert "AnalyzerSession" not in text


def test_analyzer_session_component_is_noop():
    text = ANALYZER_SESSION.read_text(encoding="utf-8")
    for needle in PROHIBITED:
        assert needle not in text, f"Prohibited UI copy still present in AnalyzerSession: {needle}"
    assert "return null" in text


def test_nav_and_home_use_log_analyzer_name():
    assert "Log Analyzer" in SIDEBAR.read_text(encoding="utf-8")
    assert "AI Log Analyzer" not in SIDEBAR.read_text(encoding="utf-8")
    assert "Log Analyzer" in HOME.read_text(encoding="utf-8")
    assert "AI Log Analyzer" not in HOME.read_text(encoding="utf-8")
