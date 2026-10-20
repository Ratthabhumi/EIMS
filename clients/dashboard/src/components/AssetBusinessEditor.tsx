"use client";

import { useEffect, useState } from "react";
import { apiUrl } from "@/lib/api";

const groups: Record<string, Record<string, string>> = {
  customer: { company: "Customer / Company", site: "Site / Branch", department: "Department", contact_name: "Contact Person / PC Owner", contact_email: "Contact Email" },
  asset_context: { asset_tag: "Asset Tag", assigned_user: "Assigned User", business_location: "Business Location", device_role: "Device Purpose / Role" },
  audit_context: { engineer: "Engineer Name", ticket_id: "Ticket / Job Reference", purpose: "Audit Purpose", notes: "Engineer Notes" },
};
const statuses = ["Open", "Investigating", "Resolved", "Accepted Risk", "False Positive"];

export default function AssetBusinessEditor({ asset, onSaved }: { asset: { asset_id: string; business_metadata?: Record<string, any> }; onSaved: (value: any) => void }) {
  const [value, setValue] = useState<Record<string, any>>({});
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { setValue(asset.business_metadata || {}); setMessage(""); }, [asset.asset_id, asset.business_metadata]);
  async function save() {
    setSaving(true); setMessage("");
    try {
      const response = await fetch(apiUrl(`/api/v1/assets/${asset.asset_id}/business-context`), { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) });
      if (!response.ok) throw new Error(`Save failed (${response.status})`);
      onSaved(await response.json()); setMessage("Saved. Original scanner evidence is unchanged.");
    } catch (error) { setMessage(error instanceof Error ? error.message : "Save failed"); }
    finally { setSaving(false); }
  }
  function changeNote(index: number, key: string, text: string) {
    setValue({ ...value, manual_annotations: (value.manual_annotations || []).map((item: any, i: number) => i === index ? { ...item, [key]: text } : item) });
  }
  return <section className="border border-eims-border rounded-lg p-4 my-4">
    <h3 className="font-semibold mb-2">Customer, Asset &amp; Engineering Review</h3>
    <p className="text-xs text-eims-text-muted mb-3">Optional business data. Keep credentials out of notes. Edits are saved separately from scan evidence.</p>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {Object.entries(groups).flatMap(([group, fields]) => Object.entries(fields).map(([key, label]) => <label key={`${group}.${key}`} className="text-xs">{label}
        <input type="text" maxLength={key === "notes" ? 2000 : 500} value={value[group]?.[key] || ""} onChange={e => setValue({ ...value, [group]: { ...value[group], [key]: e.target.value } })} className="block w-full border border-eims-border bg-eims-bg rounded p-2 mt-1" />
      </label>))}
    </div>
    <label className="block text-xs mt-4">Finding reference (select an event or check ID to add a review)
      <input id="new-finding-review" className="border border-eims-border bg-eims-bg rounded p-2 ml-2" maxLength={200} placeholder="e.g. security.defender" />
    </label>
    <button type="button" className="text-xs underline my-2" onClick={() => {
      const input = document.getElementById("new-finding-review") as HTMLInputElement;
      const id = input.value.trim(); if (!id) return;
      if (!(value.manual_annotations || []).some((item: any) => item.finding_id === id)) setValue({ ...value, manual_annotations: [...(value.manual_annotations || []), { finding_id: id, review_status: "Open", note: "" }] });
      input.value = "";
    }}>Add finding review</button>
    {(value.manual_annotations || []).map((item: any, index: number) => <fieldset key={item.finding_id} className="border border-eims-border p-3 my-2 text-xs">
      <legend>{item.finding_id}</legend>
      <label>Review Status <select value={item.review_status || "Open"} onChange={e => changeNote(index, "review_status", e.target.value)} className="bg-eims-bg p-2 border border-eims-border">{statuses.map(s => <option key={s}>{s}</option>)}</select></label>
      {[ ["note", "Engineer Note"], ["remediation", "Remediation Recommendation"], ["ticket_reference", "Ticket Reference"], ["manual_correction", "Proposed Correction + Explanation"] ].map(([key, label]) => <label key={key} className="block mt-2">{label}<textarea maxLength={2000} value={item[key] || ""} onChange={e => changeNote(index, key, e.target.value)} className="block w-full bg-eims-bg border border-eims-border rounded p-2" /></label>)}
    </fieldset>)}
    <button type="button" disabled={saving} onClick={save} className="bg-eims-accent text-white rounded px-4 py-2 mt-3">{saving ? "Saving…" : "Save business information & review"}</button>
    <p role="status" className="text-xs mt-2">{message}</p>
  </section>;
}
