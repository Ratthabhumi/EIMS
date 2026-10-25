'use client';

import React from 'react';

type SourceLine = { lineNumber: number; text: string; truncated?: boolean };
type Evidence = {
  sourceFile?: string; lineNumber?: number; message?: string;
  sourceContextOrigin?: string; sourceContext?: SourceLine[];
};

/** Only show the persisted original excerpt; never reconstruct raw History. */
export default function EvidenceSourceReview({ item, isEn }: { item: Evidence; isEn: boolean }) {
  const details = React.useRef<HTMLDetailsElement>(null);
  const finding = React.useRef<HTMLElement>(null);
  const redacted = item.sourceContextOrigin === 'redacted_extracted_source_excerpt';
  const rows = (item.sourceContextOrigin === 'extracted_source_excerpt' || redacted) && Array.isArray(item.sourceContext)
    ? item.sourceContext.slice(0, 3) : [];
  return (
    <details ref={details} className="mt-1 rounded border border-eims-border p-2">
      <summary ref={finding} className="cursor-pointer text-eims-info break-all focus-visible:outline-2">
        {item.sourceFile || (isEn ? 'Submitted text' : 'ข้อความที่ส่งวิเคราะห์')}
        {item.lineNumber ? `:${item.lineNumber}` : ''}
        {' · '}{isEn ? 'Inspect source evidence' : 'ตรวจหลักฐานต้นทาง'}
      </summary>
      {rows.length ? <>
        <p className="my-2 text-eims-text-muted">
          {isEn ? 'Saved excerpt of decoded/extracted input; not the complete original file.' : 'ข้อความบางส่วนที่บันทึกจากข้อมูลที่ถอดอ่าน ไม่ใช่ไฟล์ต้นฉบับทั้งหมด'}
        </p>
        {redacted && <p className="my-2 text-eims-text-muted">{isEn ? 'Sensitive credentials masked / control characters replaced before analysis.' : 'ปิดบังข้อมูลรับรองหรือแทนอักขระควบคุมก่อนวิเคราะห์'}</p>}
        <pre className="whitespace-pre-wrap break-words text-eims-text" aria-label={isEn ? 'Source context' : 'บริบทหลักฐาน'}>
          {rows.map(row => <span key={row.lineNumber} className="block">
            {row.lineNumber === item.lineNumber
              ? <mark className="bg-amber-100 text-slate-950 dark:bg-amber-900 dark:text-amber-50">{`${row.lineNumber} | ${row.text}`}</mark>
              : `${row.lineNumber} | ${row.text}`}
            {row.truncated ? (isEn ? ' [line truncated]' : ' [ตัดข้อความท้ายบรรทัด]') : ''}
          </span>)}
        </pre>
      </> : <p className="my-2 text-eims-text-muted">
        {item.sourceContextOrigin === 'withheld_by_policy'
          ? (isEn ? 'Source context was not retained under the privacy policy.' : 'ไม่ได้เก็บบริบทต้นทางตามนโยบายความเป็นส่วนตัว')
          : (isEn ? 'Original source context is unavailable for this record. The displayed finding is an excerpt only.' : 'ระเบียนนี้ไม่มีบริบทต้นทางที่บันทึกไว้ ข้อความที่แสดงเป็นเพียงข้อความหลักฐานบางส่วน')}
      </p>}
      <button type="button" className="mt-2 text-eims-info underline focus-visible:outline-2" onClick={() => {
        if (details.current) details.current.open = false;
        finding.current?.focus();
      }}>{isEn ? 'Back to finding' : 'กลับไปที่หลักฐาน'}</button>
    </details>
  );
}
