import React from "react";

/** One operational answer as returned by the Analyzer. `status` is decided by the server; the client never upgrades it. */
export type GuidanceField = {
  status?: "stated" | "not_stated" | "unverified" | string;
  items?: string[];
  source?: string;
  basis?: string;
  origin?: string;
};

export type OperationalGuidanceData = {
  whatHappened?: string;
  why?: GuidanceField;
  inspect?: GuidanceField;
  recommendedAction?: GuidanceField;
  risk?: GuidanceField;
  rollback?: GuidanceField;
  recoveryVerification?: GuidanceField;
  requiredPermission?: GuidanceField;
  humanApproval?: GuidanceField;
  recoveryEvidence?: GuidanceField;
  recoverySuccessCriteria?: GuidanceField;
  operationalImpact?: GuidanceField;
  destructiveRisk?: GuidanceField;
  evidenceAndSource?: { title?: string; url?: string; scope?: string }[];
  versionScope?: string;
  confidenceLimitations?: { maturity?: string; limitations?: string[] };
  destructiveActions?: string[];
  reviewState?: string;
  catalogId?: string;
  missing?: string[];
};

type Status = "stated" | "not_stated" | "unverified";

const BADGE: Record<Status, { en: string; th: string; cls: string }> = {
  stated: { en: "STATED", th: "ระบุแล้ว", cls: "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400" },
  not_stated: { en: "NOT STATED", th: "ยังไม่ระบุ", cls: "bg-slate-500/10 border-slate-500/30 text-slate-600 dark:text-slate-300" },
  unverified: { en: "UNVERIFIED", th: "ยังไม่ยืนยัน", cls: "bg-amber-500/10 border-amber-500/30 text-amber-700 dark:text-amber-400" },
};

function statusOf(field?: GuidanceField): Status {
  return field?.status === "stated" || field?.status === "unverified" ? (field.status as Status) : "not_stated";
}

/** Combine several fields into one displayed section; the weakest status wins so nothing unconfirmed looks confirmed. */
function section(fields: (GuidanceField | undefined)[]): { status: Status; items: string[]; sources: string[]; origins: string[] } {
  const present = fields.filter((f) => statusOf(f) !== "not_stated") as GuidanceField[];
  if (present.length === 0) return { status: "not_stated", items: [], sources: [], origins: [] };
  const anyUnverified = present.some((f) => statusOf(f) === "unverified");
  return {
    status: anyUnverified ? "unverified" : "stated",
    items: present.flatMap((f) => (f.items || []).map((i) => (statusOf(f) === "unverified" ? `${i}` : i))),
    sources: present.map((f) => f.source || "").filter(Boolean),
    origins: present.map((f) => f.origin || "").filter(Boolean),
  };
}

function Row({ title, status, children, testId }: { title: string; status: Status; children?: React.ReactNode; testId: string }) {
  const b = BADGE[status];
  return (
    <li className="py-3 border-b border-eims-border last:border-b-0" data-testid={testId} data-status={status}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-eims-text">{title}</span>
        <span className={`border px-2 py-0.5 rounded text-[11px] font-semibold ${b.cls}`}>{b.en}</span>
      </div>
      {children}
    </li>
  );
}

function Items({ items, status, isEn }: { items: string[]; status: Status; isEn: boolean }) {
  if (status === "not_stated") {
    return <p className="text-xs text-eims-text-muted mt-1">{isEn ? "No source-backed information in the catalog. Nothing is suggested." : "ไม่มีข้อมูลที่มีแหล่งอ้างอิงรองรับในแคตตาล็อก จึงไม่เสนอคำแนะนำ"}</p>;
  }
  return (
    <>
      {status === "unverified" && (
        <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">{isEn ? "Unconfirmed: composed or human-supplied, not verified against a source. Do not treat as confirmed guidance." : "ยังไม่ยืนยัน: เรียบเรียงหรือมนุษย์ระบุ ยังไม่ตรวจกับแหล่งอ้างอิง ห้ามถือเป็นคำแนะนำที่ยืนยันแล้ว"}</p>
      )}
      <ul className="mt-1 list-disc pl-5 text-sm text-eims-text-secondary space-y-1">
        {items.map((i, idx) => (<li key={idx}>{i}</li>))}
      </ul>
    </>
  );
}

/**
 * Catalog-derived operational guidance. Display only: every status comes from the server. A reference-only or unmapped lookup has no
 * guidance object and renders nothing, so it can never look like a diagnostic capability.
 */
export default function OperationalGuidancePanel({ guidance, isEn }: { guidance?: OperationalGuidanceData | null; isEn: boolean }) {
  if (!guidance || !guidance.catalogId) return null;
  const g = guidance;
  const why = section([g.why]);
  const inspect = section([g.inspect]);
  const action = section([g.recommendedAction]);
  const permission = section([g.requiredPermission]);
  const risk = section([g.risk, g.operationalImpact, g.destructiveRisk]);
  const approval = section([g.humanApproval]);
  const rollback = section([g.rollback]);
  const recovery = section([g.recoveryVerification, g.recoveryEvidence, g.recoverySuccessCriteria]);
  const hasWhat = !!(g.whatHappened && g.whatHappened.trim());
  const sources = (g.evidenceAndSource || []).filter((s) => s.url);
  const limits = [g.confidenceLimitations?.maturity ? `${isEn ? "Maturity" : "ระดับหลักฐาน"}: ${g.confidenceLimitations.maturity}` : "", ...(g.confidenceLimitations?.limitations || [])].filter(Boolean);
  const unreviewed = !g.reviewState || g.reviewState.startsWith("PENDING_HUMAN_REVIEW");
  const destructiveWithoutRollback = (g.destructiveActions || []).length > 0 && rollback.status !== "stated";
  return (
    <div className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm" data-testid="operational-guidance">
      <h4 className="text-md font-semibold text-eims-text mb-1">{isEn ? "Operational guidance" : "คำแนะนำเชิงปฏิบัติการ"}</h4>
      <p className="text-xs text-eims-text-muted mb-2" data-testid="guidance-review-state">
        {unreviewed
          ? (isEn ? "Catalog guidance pending human review — not approved. Read each status before acting." : "คำแนะนำจากแคตตาล็อก รอการตรวจโดยมนุษย์ ยังไม่อนุมัติ โปรดอ่านสถานะแต่ละข้อก่อนปฏิบัติ")
          : g.reviewState}
      </p>
      {destructiveWithoutRollback && (
        <div className="mb-2 border border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-400 rounded p-2 text-xs" data-testid="destructive-warning" role="alert">
          {isEn ? "This guidance includes a state-changing action and no rollback is stated. Do not execute it without a verified recovery plan and human approval." : "คำแนะนำนี้มีการเปลี่ยนสถานะระบบ แต่ไม่ระบุวิธี rollback ห้ามดำเนินการหากไม่มีแผนกู้คืนที่ยืนยันแล้วและการอนุมัติโดยมนุษย์"}
        </div>
      )}
      <ol className="list-none p-0 m-0">
        <Row title={isEn ? "1. What happened" : "1. เกิดอะไรขึ้น"} status={hasWhat ? "stated" : "not_stated"} testId="g-what">
          {hasWhat ? <p className="mt-1 text-sm text-eims-text-secondary">{g.whatHappened}</p> : <Items items={[]} status="not_stated" isEn={isEn} />}
        </Row>
        <Row title={isEn ? "2. Why it happened" : "2. ทำไมจึงเกิด"} status={why.status} testId="g-why"><Items items={why.items} status={why.status} isEn={isEn} /></Row>
        <Row title={isEn ? "3. What to inspect" : "3. ต้องตรวจอะไร"} status={inspect.status} testId="g-inspect"><Items items={inspect.items} status={inspect.status} isEn={isEn} /></Row>
        <Row title={isEn ? "4. Recommended remediation" : "4. วิธีแก้ที่แนะนำ"} status={action.status} testId="g-action"><Items items={action.items} status={action.status} isEn={isEn} /></Row>
        <Row title={isEn ? "5. Required permission" : "5. สิทธิ์ที่ต้องใช้"} status={permission.status} testId="g-permission"><Items items={permission.items} status={permission.status} isEn={isEn} /></Row>
        <Row title={isEn ? "6. Operational risk" : "6. ความเสี่ยงเชิงปฏิบัติการ"} status={risk.status} testId="g-risk"><Items items={risk.items} status={risk.status} isEn={isEn} /></Row>
        <Row title={isEn ? "7. Human approval requirement" : "7. ต้องได้รับอนุมัติโดยมนุษย์หรือไม่"} status={approval.status} testId="g-approval">
          <Items items={approval.items} status={approval.status} isEn={isEn} />
          {approval.origins.includes("eims_policy") && <p className="text-xs text-eims-text-muted mt-1">{isEn ? "Origin: EIMS policy, not a vendor statement." : "ที่มา: นโยบาย EIMS ไม่ใช่ข้อความจากผู้ผลิต"}</p>}
        </Row>
        <Row title={isEn ? "8. Rollback steps" : "8. ขั้นตอน rollback"} status={rollback.status} testId="g-rollback"><Items items={rollback.items} status={rollback.status} isEn={isEn} /></Row>
        <Row title={isEn ? "9. Recovery verification" : "9. การตรวจสอบการฟื้นตัว"} status={recovery.status} testId="g-recovery"><Items items={recovery.items} status={recovery.status} isEn={isEn} /></Row>
        <Row title={isEn ? "10. Evidence and source" : "10. หลักฐานและแหล่งอ้างอิง"} status={sources.length ? "stated" : "not_stated"} testId="g-source">
          {sources.length ? (
            <ul className="mt-1 list-disc pl-5 text-sm text-eims-text-secondary space-y-1">
              {sources.map((s, idx) => (<li key={idx}><a className="underline" href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a>{s.scope ? ` — ${s.scope}` : ""}</li>))}
            </ul>
          ) : <Items items={[]} status="not_stated" isEn={isEn} />}
        </Row>
        <Row title={isEn ? "11. Product / version applicability" : "11. ผลิตภัณฑ์ / เวอร์ชันที่ใช้ได้"} status={g.versionScope && g.versionScope.trim() ? "stated" : "not_stated"} testId="g-version">
          {g.versionScope && g.versionScope.trim() ? <p className="mt-1 text-sm text-eims-text-secondary">{g.versionScope}</p> : <Items items={[]} status="not_stated" isEn={isEn} />}
        </Row>
        <Row title={isEn ? "12. Confidence and limitations" : "12. ความเชื่อมั่นและข้อจำกัด"} status={limits.length ? "stated" : "not_stated"} testId="g-limits">
          {limits.length ? <Items items={limits} status="stated" isEn={isEn} /> : <Items items={[]} status="not_stated" isEn={isEn} />}
        </Row>
      </ol>
      {g.missing && g.missing.length > 0 && (
        <p className="mt-2 text-xs text-eims-text-muted" data-testid="guidance-missing">{isEn ? "Missing for operational use" : "ยังขาดสำหรับการใช้งานจริง"}: {g.missing.join(", ")}</p>
      )}
    </div>
  );
}
