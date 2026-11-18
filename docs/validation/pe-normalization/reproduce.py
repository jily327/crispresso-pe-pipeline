"""Re-run synthetic native forward/reverse parity with pinned Core 2.3.4.

Usage: python reproduce.py NEW_OUTPUT_DIRECTORY /path/to/peanalyzer-crispresso
"""
import argparse
import csv
import io
import json
from pathlib import Path
from zipfile import ZipFile

from peanalyzer.analysis_fastq import prepare_analysis_fastqs
from peanalyzer.backend.comparator import run_comparator
from peanalyzer.backend.pooled import resolve_executable
from peanalyzer.backend.synthetic import write_synthetic_run
from peanalyzer.demux import demultiplex
from peanalyzer.docker_runtime import IMAGE
from peanalyzer.schemas import Config, reverse_complement


def main(output, exe):
    output.mkdir(parents=True, exist_ok=False)
    targets, _ = write_synthetic_run(output / 'artificial')
    demultiplex(r1=output/'artificial/raw_R1.fastq.gz', r2=output/'artificial/raw_R2.fastq.gz',
                samples_path=output/'artificial/samples.csv',config=Config(schema_version=1),output=output/'demux')
    prepare_analysis_fastqs(output/'demux', output/'prepared')
    core = resolve_executable(exe)
    summary = {}
    for label, window, reverse in [('forward_default',None,False),('reverse_default',None,True),
                                   ('forward_explicit','120-124',False),('reverse_explicit','115-119',True)]:
        target = targets[0].model_copy(update=dict(quantification_window_coordinates=window))
        if reverse:
            target = target.model_copy(update=dict(wt_sequence=reverse_complement(target.wt_sequence),
                                                    prime_edited_sequence=reverse_complement(target.prime_edited_sequence)))
        result = run_comparator(output/'prepared', '1B', [target], output/label, core,
                                runtime_identity={'image_digest': IMAGE})
        assert not result['anchor_failures'], result['anchor_failures']
        stats = result['backend_metrics'][target.copy_name]
        child = output/label/target.copy_name/'output/CRISPResso_on_unrouted'
        info = json.loads((child/'CRISPResso2_info.json').read_text())
        running = info['running_info']
        with ZipFile(child/running['allele_frequency_table_zip_filename']) as archive:
            alleles=list(csv.DictReader(io.StringIO(archive.read(running['allele_frequency_table_filename']).decode()),delimiter='\t'))
        # Independent raw table counts, including all aligned alleles in the native denominator.
        aligned = sum(int(row['#Reads']) for row in alleles)
        prime = sum(int(row['#Reads']) for row in alleles if row['Reference_Name']=='Prime-edited')
        pe_exact = sum(int(row['#Reads']) for row in alleles if row['Aligned_Sequence'].replace('-','')==targets[0].prime_edited_sequence)
        wt_exact = sum(int(row['#Reads']) for row in alleles if row['Aligned_Sequence'].replace('-','')==targets[0].wt_sequence)
        assert (prime,aligned)==(stats['native']['numerator'],stats['native']['denominator'])
        assert (pe_exact,pe_exact+wt_exact)==(stats['exact_haplotype']['numerator'],stats['exact_haplotype']['denominator'])
        audit=stats['window_audit']
        summary[label]=dict(executable_version=running['version'],image_digest=IMAGE,input=stats['native']['backend_input_reads'],
                            native_pe=prime,aligned=aligned,exact_wt=wt_exact,exact_pe=pe_exact,
                            backend_window=audit['backend_positions'],original_window=audit['original_wt_positions'],
                            intended_outside=[row['wt_position'] for row in audit['outside_intended_edits']])
    for window in ('default','explicit'):
        f,r = summary['forward_'+window],summary['reverse_'+window]
        for key in ('input','native_pe','aligned','exact_wt','exact_pe','backend_window'):
            assert f[key]==r[key]
        assert sorted(239-p for p in f['original_window'])==r['original_window']
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path);parser.add_argument('core')
    args=parser.parse_args();main(args.output,args.core)
