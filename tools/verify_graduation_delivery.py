"""Verify frozen DEV provenance and optionally render an offline-only demo.

Uses the existing evaluator digests, review queue and source inspector; never
executes HELDOUT, authenticates, opens a network connection or writes a database.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluation.analyzer.runner import REPO, annotation_digest, digest, load_manifest, validate_output
from evaluation.analyzer.grounding import review_queue
from evaluation.analyzer.inspection import render

PREFIX = "20261101-priority-"
MODES = ("rule_only", "rule_kb", "full_investigation")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_rows(rows, expected_ids):
    require(len(rows) == len(expected_ids) and {r['case_id'] for r in rows} == expected_ids,
            "DEV cohort missing or duplicated")
    for row in rows:
        require(row['status'] == 'OK', "prediction execution failed")
        require(digest({k: v for k, v in row.items() if k not in ('prediction_sha256', 'timing_seconds')})
                == row['prediction_sha256'], "prediction digest mismatch")


def verify():
    manifest = REPO / 'evaluation/analyzer/gold/manifest.v1.json'
    doc, payloads = load_manifest(manifest)
    cases = [c for c in doc['cases'] if c['split'] == 'dev']
    require(len(cases) == 12 and all(c['review_status'] == 'DRAFT' for c in cases),
            'Frozen baseline is 12 DRAFT DEV; reassess delivery when reviews change')
    sources = {'manifest_sha256': manifest, 'scorer_sha256': REPO/'evaluation/analyzer/scoring.py',
               'runner_sha256': REPO/'evaluation/analyzer/runner.py',
               'annotations_v2_sha256': manifest.with_name('manifest.v2.dev-draft.json'),
               'semantics_v2_code_sha256': REPO/'evaluation/analyzer/semantics_v2.py',
               'investigation_code_sha256': REPO/'evaluation/analyzer/investigation.py',
               'grounding_code_sha256': REPO/'evaluation/analyzer/grounding.py'}
    for mode in MODES:
        base = REPO/'evaluation/analyzer/results'/f'{PREFIX}{mode}'
        config = read(base/'config.json')
        for key, path in sources.items():
            if key in config:
                # Historical Windows configs hashed CRLF working-copy bytes even
                # though Git stores LF. Only these text metadata/code files may
                # use either representation; fixture bytes remain strict above.
                lf = path.read_bytes().replace(b'\r\n', b'\n')
                require(config[key] in {hashlib.sha256(lf).hexdigest(),
                        hashlib.sha256(lf.replace(b'\n', b'\r\n')).hexdigest()}, f'{mode}: {key} changed')
        require(config['annotation_sha256'] == {c['case_id']: annotation_digest(c) for c in cases},
                'annotation provenance mismatch')
        rows = [json.loads(line) for line in (base/'predictions.jsonl').read_text(encoding='utf-8').splitlines()]
        verify_rows(rows, {c['case_id'] for c in cases})
        metrics = read(base/'metrics.json')
        require(metrics['case_count'] == 0 and metrics['source']['accuracy']['value'] is None,
                'DRAFT must not produce reviewed accuracy')
    queue = read(base/'claim_grounding_queue.json')
    require(queue == review_queue(rows) and len(queue['judgments']) == 61, 'claim queue mismatch')
    require(all(j['support_judgment'] == 'NOT_REVIEWED' and j['reviewer'] is None for j in queue['judgments']),
            'Unexpected human judgment in frozen proposal')
    binding = read(REPO/'docs/research/REVIEW_BINDING_20261030.json')
    require(binding['prediction_snapshot'] == base.name, 'stale review binding')
    packet = (REPO/'docs/research'/binding['priority_packet']).read_text(encoding='utf-8')
    lookup = {r['case_id']: r for r in rows}
    for cid, sha in binding['priority_packet_hashes'].items():
        require(lookup[cid]['prediction_sha256'] == sha and sha in packet, 'stale priority packet')
        require(lookup[cid]['semantics_v2']['root_cause_status'] == 'UNKNOWN'
                and lookup[cid]['semantics_v2']['explicit_terminal_outcome'] is None, 'priority uncertainty changed')
    release = read(REPO/'docs/research/RELEASE_CANDIDATE_20261031.json')
    for path, sha in release['canonical_text_sha256'].items():
        require(hashlib.sha256((REPO/path).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == sha,
                f'release canonical text hash mismatch: {path}')
    return rows, payloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo-output', type=Path)
    args = parser.parse_args()
    rows, payloads = verify()
    if args.demo_output:
        output = validate_output(args.demo_output)
        output.mkdir(parents=True, exist_ok=False)
        for row in rows:
            (output/f"{row['case_id']}.html").write_text(render(row, payloads[row['case_id']]), encoding='utf-8')
        (output/'README.txt').write_text('OFFLINE FROZEN SYNTHETIC DRAFT DEMO ONLY\n'
            'Order: fort_config.html, esxi_tracker.html, win_policy.html, esxi_heartbeat.html, bundle_unrelated.html\n'
            'No live browser, PostgreSQL, human accuracy or USB acceptance. See tracked operator instructions.\n', encoding='utf-8')
    print('PASS: 36 frozen prediction digests; 12 DEV; 61 unreviewed claims; provenance and priority packet; accuracy NOT_MEASURED')


if __name__ == '__main__':
    main()
