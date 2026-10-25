"""Run synthetic candidates through the existing offline native adapter; no scoring."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation.analyzer.investigation import predict_full


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = ROOT / 'evaluation/analyzer/candidates/counterexamples-20261026.json'
    manifest = json.loads(source.read_text(encoding='utf-8'))
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    for entry in manifest['cases']:
        case = {'case_id': entry['case_id'], 'files': [{'path': n} for n in entry['files']]}
        files = {n: (t.encode('utf-8'), t) for n, t in entry['files'].items()}
        prediction = predict_full(case, files)
        unknowns = prediction['native_response']['solutionSummary']['incident']['unknowns']
        assert any(entry['expected_uncertainty'] in item for item in unknowns), (entry['case_id'], unknowns)
        assert prediction['isolated_history_roundtrip']
        results.append(prediction)
    (args.output / 'predictions.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf-8')
    config = {'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'candidate_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'count': len(results), 'status': 'PASS', 'human_judgments': 0,
              'scope': 'synthetic candidates; real offline routes, local KB, memory History; no accuracy score'}
    (args.output / 'config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    print(json.dumps(config))


if __name__ == '__main__':
    main()
