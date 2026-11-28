"""Source-bound inventory and independent Docker replay command for each native execution."""
import json
import shlex
from pathlib import Path

from peanalyzer.backend.native_artifacts import extract_native
from peanalyzer.demux_verify import sha256_file
from peanalyzer.docker_runtime import IMAGE

CORE = '/CRISPResso2/.pixi/envs/default/bin/CRISPResso'
CONTRACT = 'native-runs-v1'


def reproduction_command(argv, inputs):
    """Stage original bytes in an exclusively created directory; never reuse native output."""
    lines = ['#!/bin/sh', 'set -eu', 'test "$#" -eq 1 || { echo "Usage: sh reproduce.sh NEW_DIRECTORY" >&2; exit 2; }',
             'src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)', 'mkdir -- "$1"', 'cd -- "$1"']
    for name, digest in inputs:
        if Path(name).name != name or not name.startswith('input_R'):
            raise ValueError('Expected staged mate filenames in native argv')
        lines.append(f'cp -- "$src"/{shlex.quote(name)} .')
        lines.append('printf "%s\\n" ' + shlex.quote(f'{digest}  {name}') + ' | sha256sum -c -')
    lines.append('exec docker run --rm --network none --user "$(id -u):$(id -g)" '
                 '--volume "$PWD:/work" --workdir /work --entrypoint ' + CORE + ' ' +
                 shlex.join([IMAGE, *argv[1:]]))
    return '\n'.join(lines) + '\n'


def execution_records(cell):
    for path in sorted(cell.rglob('execution.json')):
        yield path, json.loads(path.read_text())
    for path in sorted(cell.rglob('aligned_site_counts.json')):
        if not (path.parent/'execution.json').exists():
            yield path, json.loads(path.read_text())['execution']


def describe_run(cell, path, run, targets, sample, *, write_scripts):
    work = path.parent
    relative = work.relative_to(cell)
    parts = relative.parts
    selected = bool(parts and parts[0] in ('copies', 'extension_alleles'))
    identity = relative.as_posix() if parts else 'single_reference'
    copy = parts[1] if len(parts) >= 2 and parts[0] in ('copies', 'comparator', 'extension_alleles', 'references') else None
    population = 'confident_copy_cohort' if selected else 'all_prepared_pairs'
    mode = run.get('analysis_mode') or ('native_prime_editing' if 'native_reference' in run else 'conventional_wt_alignment')
    args = run.get('argv', [])
    targets = [t for t in targets if copy is None or t.copy_name == copy]
    definitions = [t.model_dump(mode='json') for t in targets]
    row = dict(id=identity, copy=copy, mode=mode, population=population, input_pairs=None,
               original_reference=definitions, effective_references=[], include_idxs={}, argv=args,
               counts={}, per_reference={}, execution_status='NOT_RUN', extraction_status='NOT_RUN',
               recount_status='NOT_RUN', direct_parity_status='NOT_RUN', runtime_identity_status='UNVERIFIED',
               version=None, required_image=IMAGE, paths={'execution':path.relative_to(cell).as_posix()},
               sha256={}, reasons=[])
    if not args:
        row['reasons'].append(run.get('reason_code', 'MISSING_NATIVE_EXECUTION'))
        return row
    # Each runner stages physical mates under these local names. Validate native
    # effective arguments against those bytes independently of the caller's cwd.
    mate_paths = []
    for i in (1, 2):
        option = '-r'+str(i) if '-r'+str(i) in args else '--fastq_r'+str(i)
        name = args[args.index(option)+1]
        if name not in (f'input_R{i}.fastq', f'input_R{i}.fastq.gz'):
            raise ValueError('Unsupported native mate filename or order')
        p = work/name
        if p.is_symlink():
            raise ValueError('Symlink in staged native inputs')
        mate_paths.append(p)
        row['paths'][f'r{i}'] = p.relative_to(cell).as_posix()
        row['sha256'][f'r{i}'] = sha256_file(p)
    inputs = run.get('inputs') if selected else sample
    if inputs is None or any(inputs['files'][f'r{i}']['sha256'] != row['sha256'][f'r{i}'] for i in (1, 2)):
        raise ValueError('Native mates differ from the declared prepared population')
    row['input_pairs'] = inputs['pairs']
    row['physical_mate_order'] = ['R1', 'R2']
    script = work/'reproduce.sh'
    command = reproduction_command(args, [(p.name, row['sha256'][f'r{i}']) for i,p in enumerate(mate_paths, 1)])
    if write_scripts:
        with script.open('x') as handle:
            handle.write(command)
    elif script.is_symlink() or script.read_text() != command:
        raise ValueError('Native reproduction command changed')
    row['paths']['script'] = script.relative_to(cell).as_posix()
    row['sha256']['script'] = sha256_file(script)
    if run.get('return_code') != 0:
        row.update(execution_status='FAILED' if run.get('return_code') is not None else 'NOT_RUN')
        row['reasons'].append(run.get('reason_code', 'NATIVE_EXECUTION_INCOMPLETE'))
        return row
    row['execution_status'] = 'COMPLETED'
    out = work / (args[args.index('--output_folder')+1] if '--output_folder' in args else '')
    name = args[args.index('--name')+1]
    child = out/('CRISPResso_on_'+name)
    info_path = child/'CRISPResso2_info.json'
    row['paths']['info'] = info_path.relative_to(cell).as_posix()
    try:
        info = json.loads(info_path.read_text())
        ri, results = info['running_info'], info['results']
        effective = ri['args']['value']
        row['version'] = ri['version']
        if [effective['fastq_r1'], effective['fastq_r2']] != [p.name for p in mate_paths]:
            raise ValueError('Core effective input filenames differ')
        refs = results['refs']
        row['effective_parameters'] = effective
        row['effective_references'] = [dict(name=r, sequence=refs[r]['sequence']) for r in results['ref_names']]
        row['include_idxs'] = {r: v['include_idxs']['value'] for r,v in refs.items()}
        row['sha256']['info'] = sha256_file(info_path)
        report = next((p for p in (out/(child.name+'.html'), child/'CRISPResso2_report.html') if p.is_file()), None)
        if report:
            row['paths']['report'] = report.relative_to(cell).as_posix()
            row['sha256']['report'] = sha256_file(report)
        else:
            row['reasons'].append('NATIVE_HTML_REPORT_UNAVAILABLE')
        for key, field in [('alleles','allele_frequency_table_zip_filename'), ('mapping','mapping_stats_filename'),
                           ('quantification','quant_of_editing_freq_filename')]:
            if Path(ri[field]).name != ri[field]:
                raise ValueError('Invalid native artifact path')
            p = child/ri[field]
            row['paths'][key] = p.relative_to(cell).as_posix()
            row['sha256'][key] = sha256_file(p)
        parsed = extract_native(info_path)
        if parsed['counts']['backend_input_reads'] != inputs['pairs']:
            raise ValueError('Native input count differs from prepared population')
        parsed.pop('paths')
        row.update(**parsed, extraction_status='PASS', recount_status='PASS')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        row.update(extraction_status='FAILED', recount_status='FAILED')
        row['reasons'].append(str(exc))
    for logfile in ('stderr.txt', 'core.log', 'stdout.txt'):
        log = work/logfile
        if log.is_file():
            with log.open(errors='replace') as stream:
                for line in stream:
                    if line.startswith('PEAnalyzer pinned Docker receipt '):
                        receipt = json.loads(line.removeprefix('PEAnalyzer pinned Docker receipt '))
                        if receipt['image'] == IMAGE and receipt['argv'] == args[1:] and receipt['core'] == CORE:
                            row.update(runtime_identity_status='VERIFIED', runtime_receipt=receipt)
    return row


def _inventory(cell, sample_id, target_name, targets, sample, *, write_scripts):
    cell = Path(cell)
    runs = [describe_run(cell, path, ex, targets, sample, write_scripts=write_scripts) for path, ex in execution_records(cell)]
    document = dict(contract=CONTRACT, sample_id=sample_id, target_name=target_name, runs=runs,
                    input_pairs=sample['pairs'], reasons=[] if runs else [
                        'ZERO_PREPARED_PAIRS' if not sample['pairs'] else 'NO_NATIVE_EXECUTION_RECORDED'])
    return document


def verify_native_runs(cell, sample_id, target_name, targets, sample):
    path = Path(cell)/'native_runs.json'
    expected = _inventory(cell, sample_id, target_name, targets, sample, write_scripts=False)
    if path.is_symlink() or json.loads(path.read_text()) != expected:
        raise ValueError('Native measurement inventory differs from original artifacts')
    if any(row['extraction_status'] == 'FAILED' for row in expected['runs']):
        raise ValueError('Native measurement extraction failed; original artifacts preserved')
    return expected


def write_native_runs(cell, sample_id, target_name, targets, sample):
    cell = Path(cell)
    document = _inventory(cell, sample_id, target_name, targets, sample, write_scripts=True)
    (cell/'native_runs.json').write_text(json.dumps(document, indent=2, allow_nan=False)+'\n')
    return document
