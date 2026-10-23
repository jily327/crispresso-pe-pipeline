"""Measure one report in an isolated Linux process; timing is evidence only."""
import argparse
import json
from pathlib import Path
import resource
import time

from peanalyzer.reporting import generate_report, load_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--result', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    source = load_result(args.result.read_bytes())
    start = time.monotonic()
    manifest = generate_report(result_path=args.result, output=args.output)
    result = dict(biological_samples=len({o.sample_name for o in source.observations}),
        targets=len({o.target_name for o in source.observations}), observations=len(source.observations),
        group_summaries=len(source.group_summaries), figures=sum(a.artifact_kind == 'figure' for a in manifest.artifacts),
        elapsed_seconds=round(time.monotonic()-start, 3),
        peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        rss_method='Linux getrusage(RUSAGE_SELF).ru_maxrss; process peak including imports',
        timing_role='descriptive evidence only')
    args.evidence.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
