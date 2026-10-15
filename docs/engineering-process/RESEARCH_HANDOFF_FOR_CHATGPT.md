# Focused research handoff (not implementation claims)

Research work is deliberately bounded to preserve development time. Ask ChatGPT Research to return primary-source URLs, version/date scope, uncertainty, and concrete acceptance criteria for these questions:

1. Windows unexpected shutdown: correlate 41, 6008 and 1074, bugcheck/WER/dump evidence; distinguish power loss, crash and forced shutdown without treating 41 as cause.
2. File-copy/exfiltration feasibility: required Advanced Audit Policy and object SACLs; 4656/4663/4660/5140/5145 semantics; USB/EDR/network/DLP corroboration; privacy/consent and false positive boundaries. A file-access event is not proof of transfer destination.
3. Confidence: distinguish source identification, observed signature match, cross-file association and causal certainty; propose explainable labels and an evaluation dataset, not arbitrary probability percentages.
4. Practical engineer evaluation: neutral T1–T4 scripts, success/assisted/failure definitions, time/error coding, small-sample limitations, and before/after counterbalancing. Separate ISO 9241-11 measures from claims of ISO compliance.
5. Vendor scope: supported Veeam, FortiOS, Cisco ASA and PAN-OS versions/formats; expected identifiers/timezones and documented error signatures. Return minimum sanitized fixture requirements.

Inputs for research: focused scope, traceability matrix, existing catalog official references and current test report. Do not upload private inventory, company logs, screenshots, consent or participant-identifiable responses. Research output must identify what is adopted, proposed or unsupported; it must not invent interviews or test results.

## After the consolidation continuation

Provider-qualified shutdown text scenarios and guarded SQLite History persistence are now implemented and tested; do not request duplicate broad research. Remaining useful research: deployed vendor version/format examples approved by the engineer; evidence sufficient for file-copy/transfer conclusions; usable confidence labels/calibration; and formative evaluation interpretation. These remain separate from actual user confirmation and PostgreSQL/deployment verification.
