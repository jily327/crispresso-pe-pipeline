"""Separate nuclease contracts; PE metric validators are never generalized."""
from collections import Counter
import ast
import math
import re
from typing import Literal
from pathlib import PurePosixPath
from pydantic import Field, JsonValue, model_validator
from peanalyzer.statistical_models import (Model, Hash, Observation, Provenance as M5Provenance,
    StatisticsResult as M5Result)
from peanalyzer.schemas import Identifier
from peanalyzer.nuclease.targets import NucleaseTarget
from peanalyzer.metrics.models import Count
from peanalyzer.reporting_models import ReportManifest

METRICS=('indel_fraction','unmodified_fraction','substitution_only_fraction','indel_only_fraction',
    'indel_plus_substitution_fraction','substitution_containing_fraction','insertion_containing_fraction',
    'deletion_containing_fraction','insertion_and_deletion_containing_fraction','any_modification_fraction')
CLASSES=('unmodified','substitution_only','indel_only','indel_plus_substitution')
DETAILED=('ref_positions','insertion_positions','insertion_coordinates','insertion_sizes',
    'deletion_positions','deletion_coordinates','deletion_sizes','substitution_positions','substitution_values')
REQUIRED=('#Reads','Aligned_Sequence','Reference_Sequence','n_inserted','n_deleted','n_mutated',
          'Reference_Name','Read_Status','%Reads',*DETAILED)


def nonnegative(text):
    if not isinstance(text,str) or not text.isdecimal():raise ValueError('invalid authoritative nonnegative integer')
    return int(text)


class Allele(Model):
    authoritative_fields: dict[str,str]
    reads: Count
    n_inserted: Count
    n_deleted: Count
    n_mutated: Count
    net_delta_bp: int
    product_class: Literal['unmodified','substitution_only','indel_only','indel_plus_substitution','ambiguous','discarded']

    @model_validator(mode='after')
    def consistent(self):
        r=self.authoritative_fields
        if not set(REQUIRED)<=r.keys():raise ValueError('MISSING_AUTHORITATIVE_ALLELE_FIELD')
        for name,attr in (('#Reads','reads'),('n_inserted','n_inserted'),('n_deleted','n_deleted'),('n_mutated','n_mutated')):
            if nonnegative(r[name])!=getattr(self,attr):raise ValueError('ALLELE_COUNT_MISMATCH')
        if self.reads==0:raise ValueError('empty allele row')
        pct=float(r['%Reads'])
        if not math.isfinite(pct) or not 0<=pct<=100:raise ValueError('invalid percentage display')
        a,b=r['Aligned_Sequence'],r['Reference_Sequence']
        if len(a)!=len(b) or not re.fullmatch('[ACGTN-]+',a) or not re.fullmatch('[ACGTN-]+',b):
            raise ValueError('malformed authoritative aligned sequences')
        if self.net_delta_bp!=self.n_inserted-self.n_deleted:raise ValueError('net size mismatch')
        # Validate CRISPResso's own event lists against its own counters only.
        # No sequence realignment, gap interpretation or replacement variant call.
        parsed={}
        for key in DETAILED:
            if key=='substitution_values':
                text=r[key].strip()
                if not re.fullmatch(r"\[(?:\s*'[ACGTN]'(?:,?\s*))*\]",text):
                    raise ValueError('malformed substitution_values')
                parsed[key]=re.findall(r"'([ACGTN])'",text)
            else:
                try: parsed[key]=ast.literal_eval(r[key])
                except (ValueError,SyntaxError) as exc: raise ValueError('malformed authoritative event list') from exc
                if not isinstance(parsed[key],list):raise ValueError('malformed authoritative event list')
        for key in ('ref_positions','insertion_positions','insertion_sizes','deletion_positions','deletion_sizes','substitution_positions'):
            if any(type(x) is not int or (x<0 and key!='ref_positions') for x in parsed[key]):raise ValueError('invalid event integer')
        for event in ('insertion','deletion'):
            coordinates=parsed[event+'_coordinates'];sizes=parsed[event+'_sizes']
            if len(coordinates)!=len(sizes) or any(type(n) is not int or n<=0 for n in sizes):raise ValueError('invalid event sizes')
            if any(not isinstance(c,(tuple,list)) or len(c)!=2 or any(type(x) is not int or x<0 for x in c) or c[0]>=c[1] for c in coordinates):
                raise ValueError('invalid event coordinates')
            if event=='insertion' and (any(b-a!=1 for a,b in coordinates) or parsed['insertion_positions']!=[p for c in coordinates for p in c]):raise ValueError('invalid insertion anchors')
            if event=='deletion' and (sizes!=[b-a for a,b in coordinates] or parsed['deletion_positions']!=[p for a,b in coordinates for p in range(a,b)]):raise ValueError('invalid deletion events')
        if (sum(parsed['insertion_sizes'])!=self.n_inserted or sum(parsed['deletion_sizes'])!=self.n_deleted
            or len(parsed['substitution_positions'])!=self.n_mutated or len(parsed['substitution_values'])!=self.n_mutated
            or len(parsed['ref_positions'])!=len(a)):
            raise ValueError('authoritative event lists disagree with counters')
        name=r['Reference_Name']
        expected=('ambiguous' if name=='AMBIGUOUS_Reference' else 'discarded' if name=='DISCARDED_Reference' else
            ('indel_plus_substitution' if self.n_mutated else 'indel_only') if self.n_inserted or self.n_deleted else
            'substitution_only' if self.n_mutated else 'unmodified')
        if name not in ('Reference','AMBIGUOUS_Reference','DISCARDED_Reference') or expected!=self.product_class:
            raise ValueError('unknown/inconsistent allele category')
        if name=='Reference' and r['Read_Status']!=('MODIFIED' if self.n_inserted+self.n_deleted+self.n_mutated else 'UNMODIFIED'):
            raise ValueError('allele Read_Status disagrees with authoritative counts')
        return self


def allele(row):
    if not set(REQUIRED)<=row.keys():raise ValueError('MISSING_AUTHORITATIVE_ALLELE_FIELD')
    ins,dele,sub=(nonnegative(row[k]) for k in ('n_inserted','n_deleted','n_mutated'))
    name=row['Reference_Name']
    kind=('ambiguous' if name=='AMBIGUOUS_Reference' else 'discarded' if name=='DISCARDED_Reference' else
          ('indel_plus_substitution' if sub else 'indel_only') if ins or dele else 'substitution_only' if sub else 'unmodified')
    return Allele(authoritative_fields=row,reads=nonnegative(row['#Reads']),n_inserted=ins,n_deleted=dele,
                  n_mutated=sub,net_delta_bp=ins-dele,product_class=kind)


class Ratio(Model):
    numerator: Count
    denominator: Count
    fraction: float | None

    @model_validator(mode='after')
    def ratio(self):
        if self.numerator>self.denominator or self.fraction!=(self.numerator/self.denominator if self.denominator else None):
            raise ValueError('invalid exact ratio')
        return self


def ratio(n,d):return Ratio(numerator=n,denominator=d,fraction=n/d if d else None)


def aggregate(alleles,aligned):
    counts=Counter({k:0 for k in (*CLASSES,'ambiguous','discarded')});metrics=Counter({k:0 for k in METRICS});sizes=Counter()
    for a in alleles:
        counts[a.product_class]+=a.reads
        if a.product_class not in CLASSES:continue
        ins,dele,sub=a.n_inserted>0,a.n_deleted>0,a.n_mutated>0
        flags=(ins or dele,a.product_class=='unmodified',a.product_class=='substitution_only',a.product_class=='indel_only',
               a.product_class=='indel_plus_substitution',sub,ins,dele,ins and dele,ins or dele or sub)
        for k,flag in zip(METRICS,flags):metrics[k]+=a.reads*flag
        if ins or dele:sizes[a.net_delta_bp]+=a.reads
    if sum(counts.values())!=aligned:raise ValueError('ALLELE_ALIGNED_RECONCILIATION_FAILED')
    return dict(counts),{k:ratio(v,aligned) for k,v in metrics.items()}, {str(k):ratio(v,metrics['indel_fraction']) for k,v in sorted(sizes.items())}


class Provenance(Model):
    analysis_mode: Literal['indel_nuclease']='indel_nuclease'
    target_definitions_sha256: Hash
    wt_sha256: Hash
    prepared_manifest_sha256: Hash
    prepared_sample: dict[str,JsonValue]
    runtime_digest: str
    crispresso_version: Literal['2.3.4']
    scientific_identity: dict[str,JsonValue]
    execution: dict[str,JsonValue]
    artifacts: dict[str,Hash]

    @model_validator(mode='after')
    def paths(self):
        for name in self.artifacts:
            path=PurePosixPath(name)
            if not name or path.is_absolute() or '..' in path.parts or '\\' in name or str(path)!=name:
                raise ValueError('invalid relative evidence path')
        return self


class NucleaseMetricResult(Model):
    schema_version: Literal[1]=1
    metric_contract_version: Literal['indel-nuclease-v1']='indel-nuclease-v1'
    analysis_mode: Literal['indel_nuclease']='indel_nuclease'
    sample_id: Identifier
    target_id: Identifier
    analysis_id: str = Field(min_length=1)
    target: NucleaseTarget
    identity_mechanism: Literal['single_copy_identity']='single_copy_identity'
    status: Literal['REPORTABLE','NOT_ASSESSABLE','BLOCKED']
    reason_codes: list[str]
    backend_input_reads: Count
    reads_after_preprocessing: Count
    aligned_reads: Count
    unaligned_reads: Count
    alignment_counters: dict[str,Count]
    mapping_statistics: dict[str,Count]
    class_counts: dict[str,Count]
    metrics: dict[str,Ratio]
    fraction_of_indel_reads_by_net_size: dict[str,Ratio]
    alleles: list[Allele]
    provenance: Provenance
    limitations: list[str]

    @model_validator(mode='after')
    def reconcile(self):
        if self.target_id!=self.target.target_name:raise ValueError('target identity mismatch')
        if self.aligned_reads+self.unaligned_reads!=self.reads_after_preprocessing or self.reads_after_preprocessing>self.backend_input_reads:
            raise ValueError('backend population mismatch')
        from peanalyzer.metrics.production import digest,RUNTIME_DIGEST
        import hashlib
        p=self.provenance
        required={'execution.json','input_R1.fastq.gz','input_R2.fastq.gz',
            'output/CRISPResso_on_nuclease/CRISPResso2_info.json',
            'output/CRISPResso_on_nuclease/Alleles_frequency_table.zip',
            'output/CRISPResso_on_nuclease/CRISPResso_mapping_statistics.txt',
            'output/CRISPResso_on_nuclease/CRISPResso_quantification_of_editing_frequency.txt'}
        if not required<=p.artifacts.keys():raise ValueError('missing authoritative evidence inventory')
        if (type(p.prepared_sample.get('pairs')) is not int or p.execution.get('scientific_identity')!=p.scientific_identity
            or p.execution.get('runtime_digest')!=p.runtime_digest or p.execution.get('status')!='completed'):
            raise ValueError('execution provenance mismatch')
        for mate in (1,2):
            if p.artifacts[f'input_R{mate}.fastq.gz']!=p.prepared_sample['files'][f'r{mate}']['sha256']:
                raise ValueError('backend input lineage mismatch')
        if (p.target_definitions_sha256!=digest([self.target.model_dump()]) or p.wt_sha256!=hashlib.sha256(self.target.wt_sequence.encode()).hexdigest()
            or p.scientific_identity!=self.target.scientific_identity or p.runtime_digest!=RUNTIME_DIGEST
            or p.prepared_sample['pairs']!=self.backend_input_reads):raise ValueError('nuclease provenance mismatch')
        if any(a.authoritative_fields['Reference_Sequence'].replace('-','')!=self.target.wt_sequence for a in self.alleles):
            raise ValueError('allele reference identity mismatch')
        stats=self.alignment_counters;m=self.mapping_statistics
        from peanalyzer.backend.metrics import COUNTERS
        if set(stats)!=set(COUNTERS) or any(m.get(k)!=stats[k] for k in COUNTERS[1:]):raise ValueError('cache counter mismatch')
        if (stats['N_TOT_READS']!=self.reads_after_preprocessing or stats['N_CACHED_ALN']+stats['N_COMPUTED_ALN']!=self.aligned_reads
            or stats['N_CACHED_NOTALN']+stats['N_COMPUTED_NOTALN']!=self.unaligned_reads
            or m['READS IN INPUTS']!=self.backend_input_reads or m['READS AFTER PREPROCESSING']!=self.reads_after_preprocessing
            or m['READS ALIGNED']!=self.aligned_reads):raise ValueError('mapping/counter mismatch')
        c,metrics,sizes=aggregate(self.alleles,self.aligned_reads)
        if c!=self.class_counts or metrics!=self.metrics or sizes!=self.fraction_of_indel_reads_by_net_size:
            raise ValueError('nuclease aggregation mismatch')
        if self.aligned_reads:
            if self.status!='REPORTABLE' or self.reason_codes:raise ValueError('unexpected reportability')
        elif self.status!='NOT_ASSESSABLE' or self.reason_codes!=['NO_ALIGNED_READS']:
            raise ValueError('empty aligned population must be unavailable')
        return self


class NucleaseObservation(Observation):
    metric_contract_version: Literal['indel-nuclease-v1']


class NucleaseStatisticsProvenance(M5Provenance):
    statistics_contract_version: Literal['indel-nuclease-stats-v1']='indel-nuclease-stats-v1'
    source_metric_contract_versions: list[Literal['indel-nuclease-v1']]


class NucleaseStatisticsResult(M5Result):
    analysis_mode: Literal['indel_nuclease']='indel_nuclease'
    statistics_contract_version: Literal['indel-nuclease-stats-v1']
    provenance: NucleaseStatisticsProvenance
    observations: list[NucleaseObservation]
    nuclease_results: list[NucleaseMetricResult]

    @model_validator(mode='after')
    def nuclease_links(self):
        sources={(r.sample_id,r.target_id):r for r in self.nuclease_results}
        if len(sources)!=len(self.nuclease_results):raise ValueError('duplicate nuclease sample/target evidence')
        seen=set()
        for row in self.observations:
            key=(row.sample_id,row.target_name)
            if key not in sources or row.metric_name not in sources[key].metrics:raise ValueError('unknown nuclease observation source')
            source=sources[key];metric=source.metrics[row.metric_name]
            expected=(metric.numerator,metric.denominator,metric.fraction) if source.status=='REPORTABLE' else (None,None,None)
            if (row.numerator,row.denominator,row.fraction)!=expected or row.status!=source.status or row.reason_codes!=source.reason_codes:
                raise ValueError('nuclease observation differs from source counts')
            if row.routing_conditioned or row.copy_name is not None or row.policy_id is not None:raise ValueError('nuclease observations must use the whole prepared single-copy population')
            identity=(*key,row.metric_name)
            if identity in seen:raise ValueError('duplicate nuclease observation')
            seen.add(identity)
        if seen!={(s,t,m) for s,t in sources for m in METRICS}:raise ValueError('incomplete nuclease observation inventory')
        return self


class NucleaseReportManifest(ReportManifest):
    report_contract_version: Literal['indel-nuclease-report-v1']
    source_statistics_contract_version: Literal['indel-nuclease-stats-v1']
