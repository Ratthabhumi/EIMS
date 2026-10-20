# Bundled image identity repair

The previous verifier required `docker image inspect .Id` to equal the archive's
top-level index digest. It did not distinguish index, platform manifest and image
configuration identities. The saved archive contains all three digest types.
[Docker documents](https://docs.docker.com/desktop/features/containerd/) that the
classic store does not support indices/manifest lists; a single displayed ID is
therefore an unsuitable cross-store identity contract.

On this PC, all three existing transfer tags still returned the expected index ID;
the reported failure was **not reproduced on this daemon**. The exact ID returned
on the failing PC was not supplied. Archive inspection establishes a representation
compatibility defect; attributing that particular incident to a specific engine
store remains an inference, not a confirmed observation.

| Transfer tag | Expected/actual on this PC (index prefix) | Archive config digest prefix |
|---|---|---|
| `eims-transfer/postgres:ccc6e83d6e35e931` | `ccc6e83d6e35` / `ccc6e83d6e35` | `9b05db12a354` |
| `eims-transfer/redis:e7723ff73d963f5c` | `e7723ff73d96` / `e7723ff73d96` | `2a51817f7925` |
| `eims-transfer/minio:14cea493d9a34af3` | `14cea493d9a3` / `14cea493d9a3` | `69b2ec208575` |

Full verified identities are generated into the private package's
`Tools/container-images.json` under `verification` (these vendor digests are not
customer secrets). Its existing `imageId` remains the original index digest.

The new stdlib verifier hashes every archived blob, validates index/tag binding,
linux/amd64 manifest/config links, descriptor sizes, Docker archive mapping and
required layer presence. Local inspection accepts only the exact archive-bound
index, platform-manifest or config digest, **and** requires matching OS,
architecture and ordered RootFS layer digests. Arbitrary IDs, wrong platforms and
different layers fail. Missing/mismatched local images trigger the existing offline
load followed by mandatory re-verification. Invalid archives/catalogs block loading.
Per-tag expected and actual digests are now visible without printing credentials.
No registry query, pull, Docker store switch, reinstall, prune or database reset.
`pull_policy: never`, runtime/images, application code and media identity are preserved.

Validation: **51 passed**, zero skipped/failures, 23.108 seconds:

`dist/usb-auditor-exe/build-env/Scripts/python.exe -m pytest tools/tests/test_container_images.py tools/tests/test_offline_prerequisites.py tools/tests/test_handover_process_identity.py tools/tests/test_prepared_runtime.py tools/tests/test_usb_backup.py tools/tests/test_command_runner.py -q --disable-warnings --junitxml=Final_CO-OP/verification/image-identity-tests.xml`

Fourteen new synthetic cases reproduce the former config-ID rejection and check all
three identity forms, incorrect platform/ID/layers, corrupt archive content,
inconsistent tag metadata, missing layers and catalog substitution. Real offline
`docker load` succeeded and subsequent inspection verified all three images against
the archive. A real alternate/classic daemon was not tested.

Isolated SETUP passed image verification, infrastructure health and checkpoint
restoration. Its initial backend launch failed because the deliberately nested test
cache exceeded a native Windows DLL path limit. Using a shorter local junction to
the same test cache, `Start` then passed backend/frontend health, authenticated
synthetic Analyzer/History/evidence smoke checks and reached READY. No application
code or restored credentials were changed for this workaround. This is not a claim
that the initial SETUP exited successfully. The native long-path limitation is
outside this image-only repair. A clean second physical PC remains NOT RUN. No additional research
is required for this bounded fix; if the failing PC still rejects an image, collect
the new per-tag digest line and Docker store/version details, without private logs.

The isolated test instance was stopped with its own Stop action. Original USB
recovery and local credential/session metadata hashes were unchanged (25 files);
all seven pre-existing running Docker containers retained their IDs. Test data,
the short junction and logs remain private and excluded from Git.

Final staged package: 84 files, 1,276,109,160 bytes, manifest SHA-256
`8db42de9888320280f67190997d1dd2c99ca71f630e39cdfc12131de51642ff4`.
Prepared runtime, container TAR and Compose file remain byte-identical to the
previous USB release. D: Auditor 1.3.3 passed its ONEDIR manifest/hash verification
and Standard/Admin executable privilege checks; no Auditor source change was needed.
The old legacy script-package validator does not apply to this dual-EXE package.

Physical E: update was authorized by the owner's final direct instructions.
The verified 84-file candidate is now active at `E:\Final_EIMS_Project`;
the former 83-file release is preserved with verified hashes at
`E:\Final_EIMS_Project_Backup_2026-10-20_ImageIdentity`. The 18 original recovery
files under `E:\EIMS_Data` retained their hashes. Running the image verifier with
the bootstrap Python directly from the updated USB verified all three images.
D: remains the verified existing Auditor release. No unrelated package/data was
copied onto it. Local receipt: `Final_CO-OP/verification/image-identity-usb-delivery.json`.
