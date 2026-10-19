# Admin Auditor and qualified Windows/Fortinet KB patch — 19 October 2026

## Delivered source changes
The maintained USB Auditor now launches through normal Windows UAC without a typed scan confirmation. Already-elevated execution scans directly; a failed elevation marker or denied UAC stops without claiming success. Encoded PowerShell preserves literal paths/arguments without changing execution policy. The nine collection stages, embedded runtime, offline default and original report format remain.

Reports use unique exclusive JSON creation. JSON, logs and automatic Excel export stay in a new private local directory owned by the elevated account and SYSTEM. The account may differ under alternate-credential UAC. The actual path is printed. Excel does not overwrite an existing unrelated workbook. No reports or consent records are published.

Unreadable controls and missing registry values are UNKNOWN, not proven FAIL/PASS. A missing SMBv1 value remains UNKNOWN until effective state is verified. Demand-start BITS/Windows Update being stopped is not itself a violation. Organization post-clone checks retain their observed policy_result, clearly separated as advisory NOT APPLICABLE to the general baseline. The project score is not a universal CIS/NIST security certification.

## Knowledge changes
- Windows profiles require provider + channel + matching message: DNS-Client 8016, Time-Service 129, FilterManager 11, GroupPolicy 1129, SCM 7031, WindowsUpdateClient 20 and NETLOGON 5719.
- APCPBEAgent 3005 remains explicitly UNVERIFIED; product context is not an invented event definition.
- Security 4946/4947/4948/4950 are optional audit references. Administrator execution does not enable Security-channel collection.
- FortiOS 7.6.6 profiles match exact raw strings 0100044544–0100044547 with type=event/subtype=system, Information reference severity. Other formats retain generic classification.
- Policy actions require firewall.policy context, an explicit supported action and object. Original cfgattr strings preserve observed before/after text; absent values, material baseline changes and unauthorized actors are never inferred.
- Reference URLs, applicability and review dates are in windows_provider_knowledge.json and diagnostic_knowledge_catalog.json. This pass uses the owner's supplied research; Microsoft Q&A examples are context, not universal event definitions. Device/version matching remains necessary.
- No frontend redesign, dependency installation, Docker rebuild or operational database modification was performed in this patch.

## Measured verification
- Auditor/build tests: 115 passed, zero failures/skips.
- Targeted KB/provider/Analyzer/History/upload tests: 108 passed, zero failures/skips.
- Additional catalog/offline compatibility tests: 15 passed, zero failures/skips.
- Total: 238 passing tests. Deprecation/package-rename warnings remain.
- PowerShell parsing: PASS. Denied-UAC simulation: PASS. Standard-user elevation-loop rejection: PASS.
- Actual normal-UAC administrator run: PASS; one new JSON and one Excel workbook, 416 System/Application events, firewall evidence OK. Audit result PARTIAL because effective SMBv1 state could not be verified from its missing registry value. This is not a proven disabled/enabled feature or fatal scan failure.
- Live UAC denial by the operator, clean Windows Server and alternate-admin-account output access: NOT RUN; do not confuse simulated branch tests with these live cases.
- The older offline HTTP E2E suite was BLOCKED before startup because its guard requires operational port 8000 to be free. The existing service was not stopped. The separate isolated History/API tests above passed; the blocked five cases are not counted as passes.
- Existing dashboard TypeScript/production build results are from the preceding verified pass; no frontend files changed during this patch and no rebuild was repeated.

## Package boundaries and owner checks
Auditor 1.1.0 is staged using the existing verified embedded runtime; runtime/dependencies were not reinstalled. The prior verified Auditor is retained in an owner-only backup. USB replacement requires the owner's explicit device approval and destination hash checks; owner copy receipts record the actual result. Full EIMS on the second USB remains frozen. A source-only KB overlay is staged separately; it does not authorize updating that USB or imply fresh full installation acceptance.

Private outputs, device identities, raw reports and the local owner permission record remain local and ignored. Only an empty owner-permission template is public. Historical deployment credential rotation and production approval remain unverified; this source publication does not change those states.

## Remaining research / field evidence
Obtain the actual FortiOS version and 2–3 redacted configuration-change records for version matching. APCPBEAgent 3005 still needs a product/version-specific authoritative event definition. Arrange clean Windows Server, alternate-account UAC and fresh Full EIMS/import/browser acceptance on approved machines. No broad new architecture or research work is needed for this patch.

## Final delivery verification
- Reviewed implementation source was published on development branch `work/eims-engineering-process-2026-10`, commit `450f4ce`. The eight earlier local commits were preserved and delivered by a normal fast-forward push; main was not merged or changed.
- After explicit owner approval, the previous D: Auditor folder was renamed to `EIMS_USB_Auditor_Backup_2026-10-19_Admin`. No formatting or deletion occurred. Auditor 1.1.0 was copied to `D:\EIMS_USB_Auditor`; the complete 286-file destination inventory and hashes match the reviewed stage.
- The previous Auditor backup manifest matches the former verified release. The Full EIMS E: manifest is unchanged and every Full package file still passes integrity verification.
- A reviewed 15-file source-only KB overlay and checksums are retained in private local staging. It was not applied to the frozen E: USB. This is deliberate separation of the approved Auditor replacement from Full delivery.
- Owner-only receipts, live reports and private backup archives remain excluded from GitHub. The public report contains no raw machine report, hostname, account, IP address, recovery key or private authorization record.
