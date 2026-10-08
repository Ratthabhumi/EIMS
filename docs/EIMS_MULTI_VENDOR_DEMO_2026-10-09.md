# EIMS supervision demo — October 9, 2026

Primary sequence: Windows → Veeam/VMware bundle → knowledge catalog → history.
Use sanitized synthetic examples only. Keep the primary demonstration under five minutes.

## Start the app

From the repository root, with the existing infrastructure available:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd clients/dashboard
npm run dev -- --hostname 127.0.0.1 --port 3001
```

Open http://127.0.0.1:3001/analyzer. Preserve the existing authentication mode;
log in normally if secure mode is enabled. No database migration, reset, seed,
volume deletion or authentication bypass is required by this change.
Before the presentation, confirm the API and existing database are available.
Do not advertise a successful persisted live workflow until this check is done.

## Five-minute English script

**0:00–0:50 — Windows, raw text, English language**

Paste this synthetic example:

```text
Log Name: System
Source: Microsoft-Windows-GroupPolicy
Event ID: 1129
Level: Error
Computer: WIN-SYNTHETIC.example.invalid
Description: The processing of Group Policy failed because of lack of network connectivity to a domain controller.
```

“This is the project's original Windows capability. EIMS recognizes the source
and preserves the event identifier. The message reports a Group Policy failure;
we still need network and domain-controller evidence to establish the cause.”

**0:50–2:25 — Veeam/VMware Evidence Bundle**

Use the existing synthetic two-file bundle prepared in
`EIMS_supervision_synthetic_demo_files_2026-10-09/`; review its READ_ME_FIRST
instructions. Do not substitute company logs. Show source files, original line
numbers, the first meaningful failure, terminal failure and correlation limitations.

“The bundle brings two sources into one investigation. These diagnostic codes
are defined by EIMS; they are not official vendor event IDs. We preserve the
failure sequence and distinguish snapshot operations. An earlier CBT error
does not prove that it caused a later missing-file failure. References are
selected only when their operation context matches.”

**2:25–3:35 — Diagnostic Knowledge Catalog**

Select Veeam, VMware, Cisco and PAN-OS filters. Show code-type labels, search,
scope in a detail view, and an official reference. Select Windows to show 141 entries.
Select Structured JSON to show its explicit parser-only indication.

“This is reference knowledge, separate from analyzed records. Products have
different identifiers and different coverage. Windows keeps its 141 original
definitions. Cisco entries use documented ASA message IDs. Fortinet and PAN-OS
start with documented log categories. Parser support, diagnostic knowledge and
confirmed root cause are three different capabilities.”

**3:35–4:40 — Analysis History**

Show the default History tab, newest-first sorting, optional oldest-first order,
search, duplicate IDs and a saved synthetic record. Reload a record only after
confirming the earlier upload persisted successfully. Keep the synthetic label visible.

“History contains actual saved analyses, including repeated event IDs. These
entries are synthetic demonstrations and are labeled accordingly. The static
catalog does not contribute to Total Logs Analyzed.”

**4:40–5:00 — Close**

“The automated regressions and the browser tests use sanitized synthetic data.
They do not certify company logs or production operation. The next validation
step is a supervised run in the target environment with appropriate evidence.”

## Optional PAN-OS example

Generate a sanitized fixture without reading the database:

```powershell
.\venv\Scripts\python.exe -c "from tests.test_diagnostic_catalog import pan_fixture; print(pan_fixture('SYSTEM'))"
```

Paste the output into Raw Text. It intentionally carries observed event identifier
1129; it must remain PAN-OS SYSTEM, with no Windows Group Policy remedy.
Only show this live if an earlier local smoke test has succeeded. The main demo
does not depend on PAN-OS. Default CSV syslog is supported within the report's
specified scope; arbitrary custom formats are not supported.
