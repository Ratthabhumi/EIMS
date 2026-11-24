/**
 * Portal UI localization (TH/EN). Technical identifiers stay untranslated.
 * Analyzer language preference drives these strings; raw logs / Event IDs / products do not.
 */

export type UiLang = "th" | "en";

/** Limits aligned with backend/domain/analyzer/services/bundle.py */
export const EVIDENCE_LIMITS = {
  maxFiles: 12,
  maxFileMb: 5,
  maxTotalMb: 30,
  extensions: "LOG, TXT, HTML, XML, CSV, EVTX",
  acceptAttr: ".log,.txt,.html,.htm,.xml,.csv,.evtx",
} as const;

const en = {
  // Nav
  "nav.main": "Main",
  "nav.home": "Home Portal",
  "nav.operations": "Operations",
  "nav.analyzer": "Log Analyzer",
  "nav.observability": "Observability & Alerts",
  "nav.evaluations": "Service Evaluations",
  "nav.timeline": "Timeline",
  "nav.endpoint": "Endpoint Evidence",
  "nav.usb": "USB Auditor",
  "nav.system": "System & Infra",
  "nav.grafana": "Grafana Metrics",
  "nav.minio": "MinIO Console",
  "nav.prometheus": "Prometheus DB",
  "nav.apiDocs": "Core API Docs",
  "nav.settings": "Settings",

  // Analyzer shell
  "analyzer.title": "Log Analyzer",
  "analyzer.subtitle": "Drop in your evidence and find the root cause fast. One input area, with a dedicated parser for every log type.",
  "analyzer.showIncident": "Show Incident",
  "analyzer.loading": "Loading Log Analyzer…",
  "analyzer.engine": "Analysis Engine",
  "analyzer.engineLocal": "Local Offline DB",
  "analyzer.language": "Language",
  "analyzer.knowledgeMatch": "Knowledge match",
  "analyzer.available": "Available",
  "analyzer.systemStatus": "System Status",
  "analyzer.commonEvents": "Common Event IDs",
  "analyzer.diagnosticReport": "Diagnostic Report",
  "analyzer.exportMd": "Export MD",
  "analyzer.exportPdf": "Export PDF",

  // Evidence Input (unified)
  "evidence.title": "Evidence Input",
  "evidence.intro": "One submission path for Analyzer. Choose how you provide evidence; parsers and provenance stay separate by file type.",
  "evidence.mode.text": "Paste Log Text",
  "evidence.mode.file": "Upload Files",
  "evidence.mode.bundle": "Upload Evidence Bundle",
  "evidence.text.hint": "Paste Event Viewer / log text. Original text is retained for analysis provenance.",
  "evidence.text.placeholder": "Paste raw Event Viewer log text…",
  "evidence.file.hint": "Single file. Supported: {ext}. Max {fileMb} MB.",
  "evidence.file.click": "Click to choose a file (or paste image with Ctrl+V)",
  "evidence.file.ocr": "Images require server-side Tesseract OCR. If unavailable, use text or a UTF-8 file.",
  "evidence.bundle.hint": "Multiple related files as one evidence set (not a ZIP). Up to {maxFiles} files · {fileMb} MB each · {totalMb} MB total. Types: {ext}.",
  "evidence.bundle.click": "Click to add related evidence files",
  "evidence.bundle.noZip": "ZIP archives are not accepted — select individual files so each keeps its own metadata and hash.",
  "evidence.submit": "Analyze Evidence",
  "evidence.uploading": "Uploading…",
  "evidence.analyzing": "Analyzing…",
  "evidence.toast.needFile": "Please select a file first",
  "evidence.toast.needText": "Please paste some text first",
  "evidence.toast.needBundle": "Please add at least one evidence file",
  "evidence.toast.uploadingBundle": "Uploading evidence bundle…",
  "evidence.toast.uploadingFile": "Uploading file…",
  "evidence.toast.sendingText": "Sending text…",
  "evidence.toast.done": "Analysis complete",
  "evidence.toast.fail": "Error during upload or analysis.",

  // Incident actions
  "incident.actions": "Incident actions",
  "incident.actionsHint": "Create, open, or link from this analysis event",
  "incident.checking": "Checking linked incidents…",
  "incident.open": "Open Incident",
  "incident.create": "Create Incident",
  "incident.link": "Link to Incident",
  "incident.notLinked": "This event is not linked to an incident yet.",
  "incident.title": "Title",
  "incident.severity": "Severity",
  "incident.correlate": "Let Incident Core correlate with an open incident that has the same event signature within its time window (otherwise this always creates a separate incident)",
  "incident.orLink": "Or link to an existing open incident",
  "incident.noneOpen": "No open incidents",
  "incident.choose": "Choose an incident…",
  "incident.rootCause": "root cause",
  "incident.created": "Incident created from this event.",
  "incident.alreadyLinked": "This event was already linked; the existing incident was opened.",
  "incident.correlated": "Incident Core correlated this event with an open incident",
  "incident.linkedOk": "Event linked to the incident.",
  "incident.linkedDup": "That event was already linked to this incident.",
  "incident.showPanel": "Show Incident",
  "incident.closeBackdrop": "Close incident backdrop",
  "incident.workspace": "Incident Workspace",

  // History modal / tabs
  "history.tabHistory": "Analysis History",
  "history.tabCatalog": "Diagnostic Knowledge Catalog",
  "history.search": "Search analysis history",
  "history.searchPh": "Search Event ID, title, provider, keyword...",
  "history.sortLabel": "History sort order",
  "history.recordDetails": "Analysis Record Details — Event {id}",
  "history.knowledge": "Diagnostic Knowledge — {id}",
  "history.synthetic": "Suspicious Authentication Activity · Synthetic Demo",
  "history.close": "Close details",
  "history.count": "{n} analysis records · Sorted by analysis date",

  // Timeline
  "timeline.title": "Unified Timeline",
  "timeline.subtitle": "Read-only engineering timeline: audit journal, incident transitions, evidence, verification, plus legacy telemetry/winlog.",
  "timeline.loading": "Loading timeline…",
  "timeline.failed": "Failed to load timeline. Please try again.",
  "timeline.empty": "No timeline events found.",
  "timeline.events": "{n} events",
  "timeline.page": "Page {page} of {total}",
  "timeline.allSources": "All sources",
  "timeline.allSeverities": "All severities",
  "timeline.filterSeverity": "Filter by severity",
  "timeline.filterType": "Filter by source type",
  "timeline.prev": "Previous page",
  "timeline.next": "Next page",
  "timeline.honesty": "Showing {shown} of {total} records returned by the API for the current filters. Only sources with real rows appear — empty sources are omitted, not hidden by a second timeline.",
  "timeline.sourceMix": "Source mix in this page: {mix}",
  "timeline.usbNote": "USB Auditor historical audit entries are preserved with original timestamps. Missing actor identity stays “not available in historical source”.",

  // Settings
  "settings.title": "Settings",
  "settings.subtitle": "Separate personal UI preferences from deployment-controlled application configuration. Diagnostics are read-only.",
  "settings.tab.prefs": "User Interface Preferences",
  "settings.tab.diagnostics": "Runtime Diagnostics",
  "settings.prefs.heading": "User Interface Preferences",
  "settings.prefs.note": "Stored in this browser (localStorage). Not operational system configuration.",
  "settings.prefs.language": "Default analysis language",
  "settings.prefs.languageHint": "Applied when you open Log Analyzer (upload language selector).",
  "settings.prefs.sort": "Default history sort",
  "settings.prefs.sortHint": "Default for Analysis History sort (still changeable on the Analyzer page).",
  "settings.prefs.newest": "Newest first",
  "settings.prefs.oldest": "Oldest first",
  "settings.prefs.theme": "Theme",
  "settings.prefs.system": "System",
  "settings.prefs.light": "Light",
  "settings.prefs.dark": "Dark",
  "settings.prefs.saved": "Saved. Analyzer language/sort apply on next Analyzer interaction; theme applies immediately.",
  "settings.app.heading": "Application Configuration",
  "settings.app.note": "These values are managed by deployment/environment. This Portal does not expose editable operational config or secrets.",
  "settings.app.noneEditable": "No browser-editable application configuration is published by the current API contract.",
  "settings.app.envLabel": "Deployment-controlled",
  "settings.notEditable": "Not editable here (by design)",
  "settings.diag.heading": "Runtime Diagnostics",
  "settings.diag.note": "Read-only health and readiness. This is not configuration.",
  "settings.diag.refresh": "Refresh",
  "settings.diag.last": "Last observed",
} as const;

type MsgKey = keyof typeof en;

const th: Record<MsgKey, string> = {
  "nav.main": "หลัก",
  "nav.home": "หน้าหลัก Portal",
  "nav.operations": "การปฏิบัติงาน",
  "nav.analyzer": "Log Analyzer",
  "nav.observability": "Observability และแจ้งเตือน",
  "nav.evaluations": "การประเมินบริการ",
  "nav.timeline": "ไทม์ไลน์",
  "nav.endpoint": "หลักฐาน Endpoint",
  "nav.usb": "USB Auditor",
  "nav.system": "ระบบและ Infra",
  "nav.grafana": "Grafana Metrics",
  "nav.minio": "MinIO Console",
  "nav.prometheus": "Prometheus DB",
  "nav.apiDocs": "Core API Docs",
  "nav.settings": "การตั้งค่า",

  "analyzer.title": "Log Analyzer",
  "analyzer.subtitle": "ส่งหลักฐานเพื่อวิเคราะห์สาเหตุ — จุดรับหลักฐานเดียว แต่ตัวแยกวิเคราะห์ยังแยกตามชนิดไฟล์",
  "analyzer.showIncident": "แสดง Incident",
  "analyzer.loading": "กำลังโหลด Log Analyzer…",
  "analyzer.engine": "เครื่องมือวิเคราะห์",
  "analyzer.engineLocal": "ฐานข้อมูลออฟไลน์ภายใน",
  "analyzer.language": "ภาษา",
  "analyzer.knowledgeMatch": "การจับคู่ความรู้",
  "analyzer.available": "พร้อมใช้",
  "analyzer.systemStatus": "สถานะระบบ",
  "analyzer.commonEvents": "Event ID ที่พบบ่อย",
  "analyzer.diagnosticReport": "รายงานวินิจฉัย",
  "analyzer.exportMd": "ส่งออก MD",
  "analyzer.exportPdf": "ส่งออก PDF",

  "evidence.title": "ส่งหลักฐาน (Evidence Input)",
  "evidence.intro": "ช่องทางเดียวสำหรับ Analyzer เลือกวิธีส่งหลักฐาน — การแยกวิเคราะห์และ provenance ยังแยกตามชนิดไฟล์",
  "evidence.mode.text": "วางข้อความล็อก",
  "evidence.mode.file": "อัปโหลดไฟล์",
  "evidence.mode.bundle": "อัปโหลด Evidence Bundle",
  "evidence.text.hint": "วางข้อความจาก Event Viewer / ล็อก เก็บข้อความต้นฉบับไว้เป็น provenance",
  "evidence.text.placeholder": "วางข้อความล็อกจาก Event Viewer…",
  "evidence.file.hint": "ไฟล์เดียว รองรับ: {ext} สูงสุด {fileMb} MB",
  "evidence.file.click": "คลิกเพื่อเลือกไฟล์ (หรือวางรูปด้วย Ctrl+V)",
  "evidence.file.ocr": "รูปภาพต้องมี Tesseract OCR บนเซิร์ฟเวอร์ หากไม่พร้อม ให้ใช้ข้อความหรือไฟล์ UTF-8",
  "evidence.bundle.hint": "หลายไฟล์ที่เกี่ยวข้องเป็นชุดหลักฐานเดียว (ไม่ใช่ ZIP) สูงสุด {maxFiles} ไฟล์ · ไฟล์ละ {fileMb} MB · รวม {totalMb} MB ประเภท: {ext}",
  "evidence.bundle.click": "คลิกเพื่อเพิ่มไฟล์หลักฐานที่เกี่ยวข้อง",
  "evidence.bundle.noZip": "ไม่รับไฟล์ ZIP — เลือกไฟล์ทีละไฟล์เพื่อคง metadata และ hash ของแต่ละไฟล์",
  "evidence.submit": "วิเคราะห์หลักฐาน",
  "evidence.uploading": "กำลังอัปโหลด…",
  "evidence.analyzing": "กำลังวิเคราะห์…",
  "evidence.toast.needFile": "กรุณาเลือกไฟล์ก่อน",
  "evidence.toast.needText": "กรุณาวางข้อความก่อน",
  "evidence.toast.needBundle": "กรุณาเพิ่มอย่างน้อยหนึ่งไฟล์หลักฐาน",
  "evidence.toast.uploadingBundle": "กำลังอัปโหลด Evidence Bundle…",
  "evidence.toast.uploadingFile": "กำลังอัปโหลดไฟล์…",
  "evidence.toast.sendingText": "กำลังส่งข้อความ…",
  "evidence.toast.done": "วิเคราะห์เสร็จสิ้น",
  "evidence.toast.fail": "เกิดข้อผิดพลาดระหว่างอัปโหลดหรือวิเคราะห์",

  "incident.actions": "การดำเนินการ Incident",
  "incident.actionsHint": "สร้าง เปิด หรือเชื่อมจาก Event การวิเคราะห์นี้",
  "incident.checking": "กำลังตรวจสอบ Incident ที่เชื่อมอยู่…",
  "incident.open": "เปิด Incident",
  "incident.create": "สร้าง Incident",
  "incident.link": "เชื่อมกับ Incident",
  "incident.notLinked": "Event นี้ยังไม่ได้เชื่อมกับ Incident",
  "incident.title": "ชื่อเรื่อง",
  "incident.severity": "ความรุนแรง",
  "incident.correlate": "ให้ Incident Core จับคู่กับ Incident ที่เปิดอยู่ซึ่งมีลายเซ็น Event เดียวกันในช่วงเวลาที่กำหนด (มิฉะนั้นจะสร้าง Incident แยกเสมอ)",
  "incident.orLink": "หรือเชื่อมกับ Incident ที่เปิดอยู่",
  "incident.noneOpen": "ไม่มี Incident ที่เปิดอยู่",
  "incident.choose": "เลือก Incident…",
  "incident.rootCause": "สาเหตุราก",
  "incident.created": "สร้าง Incident จาก Event นี้แล้ว",
  "incident.alreadyLinked": "Event นี้อยู่ใน Incident อยู่แล้ว จึงเปิด Incident เดิม",
  "incident.correlated": "Incident Core จับคู่ Event นี้กับ Incident ที่เปิดอยู่",
  "incident.linkedOk": "เชื่อม Event กับ Incident แล้ว",
  "incident.linkedDup": "Event นี้อยู่ใน Incident นี้แล้ว",
  "incident.showPanel": "แสดง Incident",
  "incident.closeBackdrop": "ปิดพื้นหลัง Incident",
  "incident.workspace": "พื้นที่ทำงาน Incident",

  "history.tabHistory": "ประวัติการวิเคราะห์",
  "history.tabCatalog": "แคตตาล็อกความรู้วินิจฉัย",
  "history.search": "ค้นหาประวัติการวิเคราะห์",
  "history.searchPh": "ค้นหา Event ID, ชื่อเรื่อง, provider, คำสำคัญ...",
  "history.sortLabel": "ลำดับการเรียงประวัติ",
  "history.recordDetails": "รายละเอียดผลวิเคราะห์ — Event {id}",
  "history.knowledge": "ความรู้วินิจฉัย — {id}",
  "history.synthetic": "กิจกรรมยืนยันตัวตนที่น่าสงสัย · Synthetic Demo",
  "history.close": "ปิดรายละเอียด",
  "history.count": "{n} รายการวิเคราะห์ · เรียงตามวันที่วิเคราะห์",

  "timeline.title": "ไทม์ไลน์รวม (Unified Timeline)",
  "timeline.subtitle": "ไทม์ไลน์วิศวกรรมแบบอ่านอย่างเดียว: สมุดบันทึก audit, การเปลี่ยนสถานะ Incident, หลักฐาน, การยืนยัน รวมถึง telemetry/winlog เดิม",
  "timeline.loading": "กำลังโหลดไทม์ไลน์…",
  "timeline.failed": "โหลดไทม์ไลน์ไม่สำเร็จ กรุณาลองใหม่",
  "timeline.empty": "ไม่พบเหตุการณ์ในไทม์ไลน์",
  "timeline.events": "{n} เหตุการณ์",
  "timeline.page": "หน้า {page} จาก {total}",
  "timeline.allSources": "ทุกแหล่ง",
  "timeline.allSeverities": "ทุกระดับความรุนแรง",
  "timeline.filterSeverity": "กรองตามความรุนแรง",
  "timeline.filterType": "กรองตามแหล่งข้อมูล",
  "timeline.prev": "หน้าก่อน",
  "timeline.next": "หน้าถัดไป",
  "timeline.honesty": "แสดง {shown} จาก {total} รายการที่ API คืนตามตัวกรองปัจจุบัน แสดงเฉพาะแหล่งที่มีข้อมูลจริง — ไม่มีไทม์ไลน์ที่สอง",
  "timeline.sourceMix": "สัดส่วนแหล่งในหน้านี้: {mix}",
  "timeline.usbNote": "รายการประวัติ USB Auditor ถูกเก็บไว้พร้อมเวลาเดิม หากไม่มีตัวตนผู้กระทำ จะแสดงว่าไม่พร้อมในแหล่งประวัติ",

  "settings.title": "การตั้งค่า",
  "settings.subtitle": "แยกค่าปรับแต่งส่วนตัวของ UI จากการตั้งค่าแอปที่ควบคุมโดยการติดตั้ง Diagnostics เป็นแบบอ่านอย่างเดียว",
  "settings.tab.prefs": "ค่าปรับแต่งส่วนตัว (Preferences)",
  "settings.tab.diagnostics": "Runtime Diagnostics",
  "settings.prefs.heading": "ค่าปรับแต่งส่วนตัวของ UI",
  "settings.prefs.note": "เก็บในเบราว์เซอร์นี้ (localStorage) ไม่ใช่การตั้งค่าระบบปฏิบัติการ",
  "settings.prefs.language": "ภาษาการวิเคราะห์เริ่มต้น",
  "settings.prefs.languageHint": "มีผลเมื่อเปิด Log Analyzer (ตัวเลือกภาษาในหน้าอัปโหลด)",
  "settings.prefs.sort": "การเรียงประวัติเริ่มต้น",
  "settings.prefs.sortHint": "ค่าเริ่มต้นของ Analysis History (ยังเปลี่ยนได้ในหน้า Analyzer)",
  "settings.prefs.newest": "ใหม่สุดก่อน",
  "settings.prefs.oldest": "เก่าสุดก่อน",
  "settings.prefs.theme": "ธีม",
  "settings.prefs.system": "ตามระบบ",
  "settings.prefs.light": "สว่าง",
  "settings.prefs.dark": "มืด",
  "settings.prefs.saved": "บันทึกแล้ว ภาษา/การเรียงของ Analyzer มีผลเมื่อใช้งานครั้งถัดไป ธีมมีผลทันที",
  "settings.app.heading": "การตั้งค่าแอปพลิเคชัน (Operational)",
  "settings.app.note": "ค่าเหล่านี้จัดการผ่านการติดตั้ง/สภาพแวดล้อม Portal นี้ไม่เปิดให้แก้การตั้งค่าปฏิบัติการหรือความลับ",
  "settings.app.noneEditable": "สัญญา API ปัจจุบันไม่เผยแพร่การตั้งค่าแอปที่แก้ไขได้จากเบราว์เซอร์",
  "settings.app.envLabel": "ควบคุมโดยการติดตั้ง",
  "settings.notEditable": "แก้ไขที่นี่ไม่ได้ (โดยออกแบบ)",
  "settings.diag.heading": "Runtime Diagnostics",
  "settings.diag.note": "สุขภาพและความพร้อมแบบอ่านอย่างเดียว ไม่ใช่หน้าตั้งค่า",
  "settings.diag.refresh": "รีเฟรช",
  "settings.diag.last": "สังเกตล่าสุด",
};

const dictionaries: Record<UiLang, Record<MsgKey, string>> = { en: { ...en }, th };

export type UiMessageKey = MsgKey;

export function normalizeUiLang(value: string | null | undefined): UiLang {
  return value === "en" ? "en" : "th";
}

export function t(lang: UiLang, key: MsgKey, vars?: Record<string, string | number>): string {
  const raw = dictionaries[lang][key] ?? dictionaries.en[key] ?? key;
  if (!vars) return raw;
  return Object.entries(vars).reduce(
    (s, [k, v]) => s.replaceAll(`{${k}}`, String(v)),
    raw,
  );
}

/** Used by the i18n completeness self-check. */
export function uiI18nKeyInventory(): { keys: MsgKey[]; missingInTh: MsgKey[]; missingInEn: MsgKey[] } {
  const keys = Object.keys(en) as MsgKey[];
  const missingInTh = keys.filter((k) => !th[k]);
  const missingInEn = keys.filter((k) => !en[k]);
  return { keys, missingInTh, missingInEn };
}

export function assertUiI18nParity(): void {
  const { missingInTh, missingInEn, keys } = uiI18nKeyInventory();
  if (missingInTh.length || missingInEn.length) {
    throw new Error(
      `ui-i18n parity failed: missingTh=${missingInTh.join(",")} missingEn=${missingInEn.join(",")} total=${keys.length}`,
    );
  }
  // Encoding sanity: Thai strings must contain Thai script for core keys.
  const sample = th["evidence.title"];
  if (!/[\u0E00-\u0E7F]/.test(sample)) {
    throw new Error("ui-i18n Thai sample missing Thai script (possible mojibake)");
  }
}
