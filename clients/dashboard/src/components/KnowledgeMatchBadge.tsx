import React from "react";

export type KnowledgeMatch = {
  classification?: string;
  catalogId?: string | null;
  lifecycleStatus?: string | null;
  stale?: boolean;
  versionScope?: string | null;
  versionCompatible?: boolean | null;
  overlayAvailable?: boolean;
  /** Server-only provider match provenance (direct | contextual | none). */
  matchKind?: "direct" | "contextual" | "none" | string;
  matchBasis?: string | null;
  note?: string;
};

const MATCH_KIND_EN: Record<string, string> = {
  direct: "Exact Provider match",
  contextual: "Contextual match (not provider-specific diagnosis)",
  none: "No Provider match",
};

const LABELS: Record<string, { en: string; th: string; tone: "trusted" | "partial" | "none" }> = {
  version_compatible_match: { en: "Approved · version-compatible", th: "อนุมัติแล้ว · เวอร์ชันเข้ากันได้", tone: "trusted" },
  approved_diagnostic_match: { en: "Approved knowledge (version not confirmed)", th: "ความรู้ที่อนุมัติแล้ว (ยังไม่ยืนยันเวอร์ชัน)", tone: "trusted" },
  validated_diagnostic_match: { en: "Validated, not yet approved", th: "ผ่านการตรวจสอบ ยังไม่อนุมัติ", tone: "partial" },
  source_verified_match: { en: "Source verified, not yet validated", th: "ยืนยันแหล่งอ้างอิงแล้ว ยังไม่ผ่านการตรวจสอบ", tone: "partial" },
  diagnostic_candidate_match: { en: "Unreviewed candidate knowledge", th: "ความรู้ผู้สมัคร ยังไม่ผ่านการตรวจสอบ", tone: "none" },
  context_match: { en: "Reference context only", th: "บริบทอ้างอิงเท่านั้น", tone: "none" },
  no_verified_match: { en: "No verified knowledge match", th: "ไม่พบความรู้ที่ผ่านการยืนยัน", tone: "none" },
};

const TONES = {
  trusted: "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400",
  partial: "bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-400",
  none: "bg-slate-500/10 border-slate-500/30 text-slate-600 dark:text-slate-300",
};

/** Server-assigned trust level. Display only: the client never derives or upgrades it. */
export default function KnowledgeMatchBadge({ match, isEn }: { match?: KnowledgeMatch | null; isEn: boolean }) {
  if (!match || !match.classification) return null;
  const label = LABELS[match.classification] ?? LABELS.no_verified_match;
  const notes: string[] = [];
  if (match.stale) notes.push(isEn ? "Review is stale after a content change." : "การตรวจสอบเดิมล้าสมัยหลังเนื้อหาเปลี่ยน");
  if (match.overlayAvailable === false) notes.push(isEn ? "Review state unavailable; trust not assumed." : "ไม่พบสถานะการตรวจสอบ จึงไม่ถือว่าเชื่อถือได้");
  if (match.versionCompatible === false) notes.push(isEn ? "Approved only for a different product version." : "อนุมัติเฉพาะผลิตภัณฑ์เวอร์ชันอื่น");
  if (match.versionScope) notes.push(`${isEn ? "Version scope" : "ขอบเขตเวอร์ชัน"}: ${match.versionScope}`);
  if (match.matchKind) {
    notes.push(
      MATCH_KIND_EN[match.matchKind]
        || (isEn ? `Match: ${match.matchKind}` : `การจับคู่: ${match.matchKind}`),
    );
  }
  if (match.matchBasis) notes.push(`${isEn ? "Basis" : "เหตุผล"}: ${match.matchBasis}`);
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs" data-testid="knowledge-match">
      <span className={`border px-2.5 py-0.5 rounded font-semibold ${TONES[label.tone]}`}>
        {isEn ? "Knowledge" : "ความรู้"}: {isEn ? label.en : label.th}
      </span>
      {notes.map((n) => (
        <span key={n} className="text-eims-text-secondary">{n}</span>
      ))}
    </div>
  );
}

/** Plain-text line for Markdown exports; empty when the server supplied no classification. */
export function knowledgeMatchMarkdown(match?: KnowledgeMatch | null): string {
  if (!match || !match.classification) return "";
  const label = (LABELS[match.classification] ?? LABELS.no_verified_match).en;
  const extra = [
    match.stale ? "review stale" : "",
    match.overlayAvailable === false ? "review state unavailable" : "",
    match.versionScope ? `version scope ${match.versionScope}` : "",
  ].filter(Boolean).join("; ");
  return `**Knowledge trust:** ${label}${extra ? ` (${extra})` : ""}\n`;
}

const MEANING_EN: Record<string, string> = {
  version_compatible_match: "Approved knowledge whose declared version scope matches the detected product version.",
  approved_diagnostic_match: "Approved knowledge; the detected product version was not confirmed against its scope.",
  validated_diagnostic_match: "Validated by test, but not yet approved for operational use.",
  source_verified_match: "The vendor source was verified, but the diagnostic procedure has not been validated.",
  diagnostic_candidate_match: "Unreviewed candidate knowledge. Treat as an investigative direction, not an established cause.",
  context_match: "Event reference material only. It does not describe a fault or a procedure.",
  no_verified_match: "No verified knowledge applies to this evidence.",
};

/**
 * HTML block for the PDF templates. Pass the match from an object already run
 * through escapeReportData(): this helper does not escape, so unescaped input
 * must never be passed to it. Server-assigned; never recomputed here.
 */
export function knowledgeMatchHtml(match?: KnowledgeMatch | null): string {
  if (!match || !match.classification) return "";
  const known = LABELS[match.classification];
  const label = known ? known.en : "No verified knowledge match";
  const meaning = MEANING_EN[match.classification] ?? MEANING_EN.no_verified_match;
  const warnings: string[] = [];
  if (match.stale) warnings.push("The earlier review is stale after a content change, so trust was lowered.");
  if (match.overlayAvailable === false) warnings.push("Review state was unavailable; trust was not assumed.");
  if (match.versionCompatible === false) warnings.push("Approved only for a different product version.");
  if (match.versionScope) warnings.push(`Declared version scope: ${match.versionScope}`);
  const id = match.catalogId ? `<div style="font-size:11px;color:#716E66;">Catalog record: ${match.catalogId}</div>` : "";
  return `
        <h2 style="font-size:14px;font-weight:600;margin:16px 0 8px;">Knowledge Trust</h2>
        <div style="border:1px solid #D8D4CA;border-radius:8px;padding:10px 14px;margin-bottom:12px;">
          <div><strong>${label}</strong></div>
          <div>${meaning}</div>
          ${warnings.map((w) => `<div style="color:#92400e;">${w}</div>`).join("")}
          ${id}
        </div>`;
}
