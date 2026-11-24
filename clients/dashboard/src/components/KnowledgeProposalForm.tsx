'use client';

import React from 'react';
import { apiUrl } from '../lib/api';

interface KnowledgeProposalFormProps {
  historyId: number;
  title: string;
  sourceFamily: string;
  diagnosticIdentity: string;
  isEn: boolean;
}

export default function KnowledgeProposalForm({
  historyId,
  title,
  sourceFamily,
  diagnosticIdentity,
  isEn,
}: KnowledgeProposalFormProps) {
  const [open, setOpen] = React.useState(false);
  const [proposalTitle, setProposalTitle] = React.useState(title);
  const [resolutionStatus, setResolutionStatus] = React.useState<'resolved' | 'partially_resolved' | 'unresolved'>('resolved');
  const [rootCause, setRootCause] = React.useState('');
  const [steps, setSteps] = React.useState('');
  const [impact, setImpact] = React.useState('');
  const [prevention, setPrevention] = React.useState('');
  const [productName, setProductName] = React.useState('');
  const [productVersion, setProductVersion] = React.useState('');
  const [environment, setEnvironment] = React.useState('');
  const [prerequisites, setPrerequisites] = React.useState('');
  const [riskLevel, setRiskLevel] = React.useState<'low' | 'medium' | 'high' | 'critical'>('medium');
  const [validationSteps, setValidationSteps] = React.useState('');
  const [rollbackSteps, setRollbackSteps] = React.useState('');
  const [evidence, setEvidence] = React.useState('');
  const [references, setReferences] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);
  const [message, setMessage] = React.useState('');
  const [error, setError] = React.useState('');

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError('');
    setMessage('');
    const splitLines = (value: string) => value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    try {
      const response = await fetch(apiUrl('/api/v1/knowledge/proposals'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          history_id: historyId,
          title: proposalTitle,
          resolution_status: resolutionStatus,
          root_cause: rootCause,
          solution_steps: splitLines(steps),
          impact,
          prevention,
          product_name: productName || null,
          product_version: productVersion || null,
          environment: environment || null,
          prerequisites: splitLines(prerequisites),
          risk_level: riskLevel,
          validation_steps: splitLines(validationSteps),
          rollback_steps: splitLines(rollbackSteps),
          evidence_notes: splitLines(evidence),
          references: splitLines(references),
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || `Knowledge proposal failed (${response.status})`);
      }
      setMessage(isEn
        ? 'Proposal saved as pending. It will not be shared or reused until an independent admin approves it.'
        : 'บันทึกข้อเสนอเป็น Pending แล้ว จะยังไม่เผยแพร่หรือถูกนำไปแนะนำจนกว่าผู้ดูแลอีกคนจะอนุมัติ');
      setOpen(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Knowledge proposal failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="bg-eims-surface border border-eims-border rounded-lg p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-eims-text">
            {isEn ? 'Contribute a verified incident lesson' : 'เสนอความรู้จาก Incident ที่ตรวจสอบแล้ว'}
          </h4>
          <p className="text-xs text-eims-text-secondary mt-1">
            {isEn
              ? 'Your saved incident is the private source record. Only curated notes and references are submitted for review.'
              : 'Incident ต้นฉบับยังเป็นข้อมูลส่วนตัว ระบบส่งเฉพาะข้อสรุปและหลักฐานที่คัดเลือกเพื่อให้ตรวจสอบ'}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="px-3 py-2 rounded-md border border-eims-border text-sm text-eims-text hover:bg-eims-surface-subtle"
        >
          {open ? (isEn ? 'Close' : 'ปิด') : (isEn ? 'Propose knowledge' : 'เสนอเป็น Knowledge')}
        </button>
      </div>

      <div className="mt-3 text-xs text-eims-text-secondary">
        {sourceFamily || 'unknown_text'} · {diagnosticIdentity || 'Unknown'}
      </div>

      {open && (
        <form onSubmit={submit} className="mt-4 grid grid-cols-1 gap-3">
          <label className="text-xs text-eims-text-secondary">
            {isEn ? 'Knowledge title' : 'ชื่อหัวข้อความรู้'}
            <input required minLength={3} maxLength={200} value={proposalTitle} onChange={(event) => setProposalTitle(event.target.value)}
              className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>
          <label className="text-xs text-eims-text-secondary">
            {isEn ? 'Resolution outcome' : 'ผลหลังดำเนินการ'}
            <select
              value={resolutionStatus}
              onChange={(event) => setResolutionStatus(event.target.value as typeof resolutionStatus)}
              className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2"
            >
              <option value="resolved">{isEn ? 'Resolved' : 'แก้ไขสำเร็จ'}</option>
              <option value="partially_resolved">{isEn ? 'Partially resolved' : 'แก้ไขได้บางส่วน'}</option>
              <option value="unresolved">{isEn ? 'Unresolved' : 'ยังแก้ไม่ได้'}</option>
            </select>
          </label>

          <label className="text-xs text-eims-text-secondary">
            {isEn ? 'Root cause' : 'สาเหตุราก (Root Cause)'}
            <textarea required minLength={3} maxLength={4000} value={rootCause} onChange={(event) => setRootCause(event.target.value)} rows={3}
              className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>

          <label className="text-xs text-eims-text-secondary">
            {isEn ? 'Resolution steps (one per line)' : 'ขั้นตอนการแก้ไข (หนึ่งขั้นตอนต่อบรรทัด)'}
            <textarea required value={steps} onChange={(event) => setSteps(event.target.value)} rows={4}
              className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>

          <label className="text-xs text-eims-text-secondary">
            {isEn ? 'Impact' : 'ผลกระทบ'}
            <textarea value={impact} onChange={(event) => setImpact(event.target.value)} rows={2}
              className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>

          <label className="text-xs text-eims-text-secondary">
            {isEn ? 'Prevention / recurrence control' : 'แนวทางป้องกันการเกิดซ้ำ'}
            <textarea value={prevention} onChange={(event) => setPrevention(event.target.value)} rows={2}
              className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <label className="text-xs text-eims-text-secondary">{isEn ? 'Product' : 'ผลิตภัณฑ์'}
              <input value={productName} onChange={(event) => setProductName(event.target.value)} maxLength={128} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
            </label>
            <label className="text-xs text-eims-text-secondary">{isEn ? 'Product version' : 'เวอร์ชัน'}
              <input value={productVersion} onChange={(event) => setProductVersion(event.target.value)} maxLength={64} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
            </label>
            <label className="text-xs text-eims-text-secondary">{isEn ? 'Environment' : 'สภาพแวดล้อม'}
              <input value={environment} onChange={(event) => setEnvironment(event.target.value)} maxLength={64} placeholder="e.g. Windows Server 2022 / production" className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
            </label>
          </div>
          <label className="text-xs text-eims-text-secondary">{isEn ? 'Prerequisites (one per line)' : 'เงื่อนไขก่อนเริ่ม (หนึ่งรายการต่อบรรทัด)'}
            <textarea value={prerequisites} onChange={(event) => setPrerequisites(event.target.value)} rows={2} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>
          <label className="text-xs text-eims-text-secondary">{isEn ? 'Remediation risk level' : 'ระดับความเสี่ยงของการแก้ไข'}
            <select value={riskLevel} onChange={(event) => setRiskLevel(event.target.value as typeof riskLevel)} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2">
              <option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option>
            </select>
          </label>
          <label className="text-xs text-eims-text-secondary">{isEn ? 'Validation steps (required for High/Critical; one per line)' : 'ขั้นตอนตรวจยืนยันผล (บังคับสำหรับ High/Critical)'}
            <textarea value={validationSteps} onChange={(event) => setValidationSteps(event.target.value)} required={riskLevel === 'high' || riskLevel === 'critical'} rows={2} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>
          <label className="text-xs text-eims-text-secondary">{isEn ? 'Rollback steps (required for High/Critical; one per line)' : 'ขั้นตอนย้อนกลับ (บังคับสำหรับ High/Critical)'}
            <textarea value={rollbackSteps} onChange={(event) => setRollbackSteps(event.target.value)} required={riskLevel === 'high' || riskLevel === 'critical'} rows={2} className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>

          <label className="text-xs text-eims-text-secondary">
            {isEn ? 'Evidence notes (one per line; do not paste secrets or raw customer logs)' : 'บันทึกหลักฐาน (หนึ่งรายการต่อบรรทัด ห้ามใส่ Secret หรือ Log ลูกค้าดิบ)'}
            <textarea required value={evidence} onChange={(event) => setEvidence(event.target.value)} rows={3}
              className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>

          <label className="text-xs text-eims-text-secondary">
            {isEn ? 'HTTPS references (one URL per line)' : 'เอกสารอ้างอิง HTTPS (หนึ่ง URL ต่อบรรทัด)'}
            <textarea value={references} onChange={(event) => setReferences(event.target.value)} rows={2} placeholder="https://docs.vendor.example/"
              className="mt-1 w-full rounded-md border border-eims-border bg-eims-bg text-eims-text p-2" />
          </label>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-[11px] text-eims-text-secondary">
              {isEn ? 'Approval requires a different admin reviewer.' : 'การอนุมัติต้องใช้ผู้ดูแลอีกคนที่ไม่ใช่ผู้เสนอ'}
            </p>
            <button type="submit" disabled={submitting}
              className="px-4 py-2 rounded-md bg-eims-primary text-white text-sm disabled:opacity-50">
              {submitting ? (isEn ? 'Submitting…' : 'กำลังส่ง…') : (isEn ? 'Submit for review' : 'ส่งให้ตรวจสอบ')}
            </button>
          </div>
        </form>
      )}

      {message && <p role="status" className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{message}</p>}
      {error && <p role="alert" className="mt-3 text-sm text-rose-600 dark:text-rose-400">{error}</p>}
    </section>
  );
}
