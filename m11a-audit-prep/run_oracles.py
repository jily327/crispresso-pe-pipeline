"""Read-only baseline oracles; synthetic inputs/evidence stay in this audit directory.
Run with Python from the qualified 0.8.0 environment. No scientific stage runs.
"""
import csv,copy,json,os,random,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT/'backend-snapshot/src'))
from peanalyzer.schemas import Target,Sample,Config,reverse_complement
from peanalyzer.nuclease.targets import NucleaseTarget
from peanalyzer.nuclease.qualification import scientific_arguments
from peanalyzer.validation import load_samples,load_targets,load_config,metadata_warnings,SAMPLE_COLUMNS,TARGET_COLUMNS
from peanalyzer.barcodes import Catalog,Barcode,validate_catalog_matching,extraction_rules
from peanalyzer.backend.pooled import validate_targets,preflight_guides
from peanalyzer.analysis_fastq import resolve_trims,PreparationConfig
from peanalyzer.fastq import paired_fastq
from peanalyzer.workflow_models import dag
from peanalyzer.workflow_storage import digest,no_symlinks,owned
from peanalyzer.geometry import geometry
from peanalyzer import workflow
import peanalyzer
assert Path(peanalyzer.__file__).is_relative_to(ROOT/'backend-snapshot')

rng=random.Random(8011)
wt=''.join(rng.choice('ACGT') for _ in range(180))
def changed(s,pos):return s[:pos]+('A' if s[pos]!='A' else 'C')+s[pos+1:]
pe=changed(wt,87)
base=dict(target_name='T1',copy_name='copy1',wt_sequence=wt,prime_edited_sequence=pe,
          pegRNA_spacer=wt[15:35],pegRNA_extension=reverse_complement(pe[70:105]),
          nicking_guide=None,pegRNA_scaffold=None,quantification_window_coordinates='70-105')
target='ACGTTGCAAGTCGATCGA';pal='ACGTTGCAATTGCAACGT'
assert len(target)==18 and len(pal)==18 and reverse_complement(pal)==pal
nuc=dict(analysis_mode='indel_nuclease',target_name='T1',copy_name='copy1',wt_sequence='G'*20+target+'C'*22,
         nuclease_profile='tigr_tas_v1',tigr_target_sequence=target)
sample=dict(sample_name='bioA',barcode_id='bc001',forward_barcode='AAAACCCC',reverse_barcode='GGGGTTTT',
            editor='editor1',treatment='control',dpi=6,biological_replicate='1',block_id=None,paired=False)
other={**sample,'sample_name':'bioB','barcode_id':'bc002','forward_barcode':'CCCCAAAA','biological_replicate':'2'}
rows=[];literal_fixtures={};trap_calls=[]
def record(id,contract,fn,expected,fixture=None):
    if fixture is not None:literal_fixtures[id]=fixture
    try:value=fn();error=None
    except Exception as exc:value=None;error=str(exc)
    if error is not None:assert isinstance(expected,str) and expected in error,(id,error,expected)
    else:
        assert error is None,(id,error)
        if expected is not None:assert value==expected,(id,value,expected)
    rows.append(dict(id=id,contract=contract,expected=expected,observed=value,error=error,matched=True))

def model_pe(d):
    t=Target.model_validate(d);return {'mode':t.analysis_mode,'nick':t.nicking_guide,'qwc':t.quantification_window_coordinates}
def model_nuc(d):return NucleaseTarget.model_validate(d).window

def no_execution(*a,**kw):
    trap_calls.append('subprocess');raise AssertionError('NO_EXECUTION_TRAP: subprocess')
# Imported modules are already initialized; no subprocess is permitted by any oracle.
with patch('subprocess.Popen',no_execution),patch('subprocess.run',no_execution),patch('subprocess.check_output',no_execution), tempfile.TemporaryDirectory(prefix='oracles-',dir=ROOT) as scratch:
    scratch=Path(scratch)
    def write_csv(name,items,fields):
        p=scratch/name
        with p.open('w',newline='') as h:
            w=csv.DictWriter(h,fieldnames=fields);w.writeheader()
            for row in items:w.writerow({k:('' if row.get(k) is None else str(row[k]).lower() if isinstance(row[k],bool) else row[k]) for k in fields})
        return p
    for id,seq in [('PE_SNP',pe),('PE_SUBSTITUTIONS',changed(changed(wt,82),90)),('PE_INSERTION',wt[:87]+'ATG'+wt[87:]),('PE_DELETION',wt[:87]+wt[90:]),('PE_MULTIPLE',changed(wt[:87]+'ATG'+wt[87:],110))]:
        d={**base,'prime_edited_sequence':seq,'pegRNA_extension':reverse_complement(seq[70:105])}
        record(id,'Target schema only; indel routing qualification NOT run',lambda d=d:model_pe(d),{'mode':'precise_edit','nick':None,'qwc':'70-105'},d)
    for id,change,err in [
        ('PE_DNA_N',{'wt_sequence':'N'+wt[1:]},'sequence must contain'),
        ('PE_IDENTICAL',{'prime_edited_sequence':wt},'must differ'),
        ('PE_BAD_SPACER',{'pegRNA_spacer':'ACNT'},'sequence must contain'),
        ('PE_MISSING_SPACER',{'pegRNA_spacer':None},'valid string'),
        ('PE_MISSING_EXTENSION',{'pegRNA_extension':None},'valid string'),
        ('PE_RESERVED_COPY',{'copy_name':'copy__1'},'reserved'),
        ('PE_SCAFFOLD_LENGTH',{'prime_editing_pegRNA_scaffold_min_match_length':1},'requires pegRNA_scaffold')]:
        d={**base,**change};record(id,'Target rejection',lambda d=d:model_pe(d),err,d)
    record('PE_OPTIONAL_NICK','Target',lambda:model_pe(base),{'mode':'precise_edit','nick':None,'qwc':'70-105'},base)
    record('PE_SENTINEL_ZERO','legacy PE Target only',lambda:model_pe({**base,'quantification_window_coordinates':'0'}),{'mode':'precise_edit','nick':None,'qwc':'0'})
    record('PE_RNA_U','RNA normalization',lambda:Target.model_validate({**base,'pegRNA_spacer':base['pegRNA_spacer'].replace('T','U')}).pegRNA_spacer,base['pegRNA_spacer'])
    reverse={**base,'pegRNA_spacer':reverse_complement(base['pegRNA_spacer'])}
    record('PE_REVERSE_MODEL','schema accepts reverse-only spacer',lambda:model_pe(reverse),{'mode':'precise_edit','nick':None,'qwc':'70-105'},reverse)
    record('PE_REVERSE_PREFLIGHT','pure PE preflight',lambda:preflight_guides([Target.model_validate(reverse)]),'PE_GUIDE_ORIENTATION_UNSUPPORTED')
    bad={**base,'pegRNA_spacer':'A'*20}
    record('PE_ABSENT_GUIDE','pure PE preflight',lambda:preflight_guides([Target.model_validate(bad)]),'PE_GUIDE_REFERENCE_MISMATCH_UNSUPPORTED',bad)
    record('PE_EXTENSION_ABSENT','pure target validation',lambda:validate_targets([Target.model_validate({**base,'pegRNA_extension':'A'*30})]),'PE_EXTENSION_REFERENCE_INCOMPATIBLE')
    record('PE_SNP_ANNOTATION','geometry substitution-only branch',lambda:geometry([Target.model_validate(base)])['copies']['copy1']['edits'],[dict(wt_position=87,pe_position=87,old=wt[87],new=pe[87],kind='substitution')])
    for id,targets in [('PE_DUPLICATE_COPY',[base,base]),('PE_DUPLICATE_WT',[base,{**base,'copy_name':'copy2'}]),('PE_CASEFOLD_COPY',[base,{**base,'copy_name':'COPY1','wt_sequence':changed(wt,135),'prime_edited_sequence':changed(pe,135)}])]:
        p=write_csv(id+'.csv',targets,[*TARGET_COLUMNS,'quantification_window_coordinates'])
        fn=(lambda p=p:load_targets(p)) if id!='PE_CASEFOLD_COPY' else (lambda p=p:geometry(load_targets(p)))
        record(id,'CSV collection / geometry identity',fn,'duplicate',targets)
    hom=[Target.model_validate(base),Target.model_validate({**base,'copy_name':'copy2','wt_sequence':changed(wt,135),'prime_edited_sequence':changed(pe,135)})]
    record('PE_HOMELOG_TOO_FEW_DIAGNOSTICS','pure substitution geometry',lambda:geometry(hom)['status'],'BLOCKED')
    assert rows[-1]['observed']=='BLOCKED'
    # These negative canaries stop BEFORE any experimental routing or executable probe.
    def routing_trap(*a,**k):raise AssertionError('TRAPPED_EXPERIMENTAL_ROUTE_PAIR')
    with patch('peanalyzer.routing.route_pair',routing_trap):
        d=literal_fixtures['PE_INSERTION']
        record('TRAP_GEOMETRY_INDEL','geometry has hidden scientific trial',lambda:geometry([Target.model_validate(d)]),'TRAPPED_EXPERIMENTAL_ROUTE_PAIR')
    def probe_trap(*a,**k):raise AssertionError('TRAPPED_EXECUTABLE_PROBE')
    samples_path=write_csv('samples.csv',[sample,other],SAMPLE_COLUMNS)
    targets_path=write_csv('targets.csv',[base],[*TARGET_COLUMNS,'quantification_window_coordinates'])
    config_path=scratch/'config.yaml';config_path.write_text('schema_version: 1\ndemux:\n  profile: custom\n  forward_length: 8\n  reverse_length: 8\n')
    r1=scratch/'R1.fastq';r2=scratch/'R2.fastq'
    def fastq(path,mate,seq='ACGTACGT',suffix=True):path.write_text(f'@r{("/"+str(mate)) if suffix else ""}\n{seq}\n+\n'+('I'*len(seq))+'\n')
    fastq(r1,1);fastq(r2,2)
    with patch('peanalyzer.workflow.resolve_executable',probe_trap):
        record('TRAP_BUILD_PLAN','builder probes despite no output writing',lambda:workflow.build_workflow_plan(mode='run',samples=samples_path,targets=targets_path,config=config_path,output=scratch/'never-created',r1=r1,r2=r2,crispresso='CRISPResso',runtime_digest='declared-only'),'TRAPPED_EXECUTABLE_PROBE')
    assert not (scratch/'never-created').exists()
    # Sample collection rules. One shared forward or reverse end is allowed.
    def sample_count(items):return len(load_samples(write_csv('rows.csv',items,SAMPLE_COLUMNS)))
    record('SAMPLE_SHARED_REVERSE','load_samples',lambda:sample_count([sample,other]),2,[sample,other])
    record('SAMPLE_DUPLICATE_CONDITION','different biological replicates',lambda:sample_count([sample,other]),2)
    for id,d,err in [('SAMPLE_DUP_ID',{**other,'barcode_id':'bc001'},'duplicate barcode_id'),('SAMPLE_DUP_LABEL',{**other,'sample_name':'bioA'},'duplicate sample_name'),('SAMPLE_DUP_PAIR',{**other,'forward_barcode':sample['forward_barcode']},'duplicate forward/reverse barcode pair'),('SAMPLE_CASEFOLD',{**other,'barcode_id':'BC001'},'collision'),('SAMPLE_BLANK_EDITOR',{**other,'editor':''},'at least 1 character'),('SAMPLE_BLANK_DPI',{**other,'dpi':''},'dpi must be an integer'),('SAMPLE_PAIRED_BLOCK',{**other,'paired':True},'require block_id')]:
        record(id,'load_samples collection',lambda d=d:sample_count([sample,d]),err,[sample,d])
    record('SAMPLE_DUP_BIO_REP_METADATA','metadata accepts; downstream M5 rejects per condition/target',lambda:sample_count([sample,{**other,'biological_replicate':'1'}]),2)
    record('FASTQ_SYNCHRONIZED','paired_fastq read-only',lambda:len(list(paired_fastq(r1,r2))),1)
    record('FASTQ_SWAPPED_MARKED','paired_fastq',lambda:list(paired_fastq(r2,r1)),'wrong mate suffix')
    fastq(r1,1,suffix=False);fastq(r2,2,suffix=False)
    record('FASTQ_UNMARKED_IDENTICAL_INPUT','iterator alone DOES NOT reject same file; separate identity gate required',lambda:len(list(paired_fastq(r1,r1))),1)
    record('FASTQ_SWAPPED_UNMARKED','file roles cannot be proved from unmarked matching IDs',lambda:len(list(paired_fastq(r2,r1))),1)
    record('TRIM_ONE_ONLY','resolve_trims',lambda:resolve_trims({},PreparationConfig(r1_analysis_trim_5p=3)),'supply both')
    record('TRIM_EXPLICIT','resolve_trims does not inspect read length',lambda:list(resolve_trims({},PreparationConfig(r1_analysis_trim_5p=8,r2_analysis_trim_5p=8))),[8,8])
    summary={'resolved_config':{'demux':{'profile':'qi_hitom_v1','trim_barcodes':False,'trim_bridges':False}},'extraction_profile':{'rules':{'forward':{'start':2,'bridge':'AAA'},'reverse':{'start':0,'bridge':'CCCC'}}},'barcode_catalog':{'matching_safety':{'forward':{'barcode_length':8},'reverse':{'barcode_length':8}}}}
    record('TRIM_AUTOMATIC','recorded library layout only',lambda:list(resolve_trims(summary,PreparationConfig())),[13,12],summary)
    for value,expect in [('10-20',[[10,20]]),('0-0',[[0,0]]),('0-59',[[0,59]]),('59-59',[[59,59]]),('1-3_8-10',[[1,3],[8,10]]),('010-020',[[10,20]])]:
        d={k:v for k,v in nuc.items() if k not in ('nuclease_profile','tigr_target_sequence')};d['quantification_window_coordinates']=value
        record('NUC_QWC_'+value,'NucleaseTarget explicit',lambda d=d:model_nuc(d)['intervals'],expect,d)
    for value,err in [('0','NUCLEASE_WINDOW_REQUIRED'),('20-10','NUCLEASE_WINDOW_INVALID'),('59-60','NUCLEASE_WINDOW_INVALID'),('1-4_4-8','NUCLEASE_WINDOW_INVALID'),('8-10_1-3','NUCLEASE_WINDOW_INVALID'),('-1-3','NUCLEASE_WINDOW_REQUIRED'),('','NUCLEASE_WINDOW_REQUIRED')]:
        d={k:v for k,v in nuc.items() if k not in ('nuclease_profile','tigr_target_sequence')};d['quantification_window_coordinates']=value
        record('NUC_BAD_QWC_'+repr(value),'NucleaseTarget explicit',lambda d=d:model_nuc(d),err,d)
    expected_windows={'W1':[[24,25],[32,33]],'W2':[[24,33]],'W3':[[20,37]],'W4':[[10,47]]}
    for orientation,physical,q in [('forward',target,target),('reverse',reverse_complement(target),target),('palindromic',pal,pal)]:
        for window,expected in expected_windows.items():
            d={**nuc,'wt_sequence':'G'*20+physical+'C'*22,'tigr_target_sequence':q,'tigr_window':window}
            def result(d=d):
                w=model_nuc(d);return {k:w[k] for k in ('orientation','target_interval','physical_nick_boundaries','target_oriented_nick_labels','intervals','selected_window')}
            record('TIGR_'+orientation+'_'+window,'exact independent physical-locus golden',result,dict(orientation=orientation,target_interval=[20,37],physical_nick_boundaries=[[24,25],[32,33]],target_oriented_nick_labels={'forward':['5|6','13|14'],'reverse':['13|14','5|6'],'palindromic':None}[orientation],intervals=expected,selected_window=window),d)
            if orientation=='palindromic':assert model_nuc(d)['target_oriented_between_cuts'] is None
    record('TIGR_DEFAULT_W2','omitted selection',lambda:model_nuc(nuc)['intervals'],[[24,33]],nuc)
    record('TIGR_W4_LEFT_CLIP','edge fixture',lambda:model_nuc({**nuc,'wt_sequence':target+'C'*22,'tigr_window':'W4'})['intervals'],[[0,27]])
    record('TIGR_W4_RIGHT_CLIP','edge fixture',lambda:model_nuc({**nuc,'wt_sequence':'G'*42+target,'tigr_window':'W4'})['intervals'],[[32,59]])
    for id,change,err in [('MISSING',{'tigr_target_sequence':'A'*18},'TIGR_TARGET_MISSING'),('MULTIPLE',{'wt_sequence':target+'G'*20+target},'TIGR_TARGET_NOT_UNIQUE'),('SHORT',{'tigr_target_sequence':target[:-1]},'TIGR_TARGET_LENGTH'),('BAD_DNA',{'tigr_target_sequence':'N'+target[1:]},'sequence must contain'),('BOTH',{'quantification_window_coordinates':'10-20'},'not both'),('LEGACY',{'insertion_quantification_mode':'legacy'},'current'),('PE_CONTAMINATION',{'prime_edited_sequence':pe},'Extra inputs')]:
        d={**nuc,**change};record('TIGR_'+id,'NucleaseTarget rejection',lambda d=d:model_nuc(d),err,d)
    record('QUALIFIED_ARGUMENT_COUNT','expected map, not executed/verified runtime',lambda:len(scientific_arguments('ACGT','0-0')),58)
    record('DAG_RUN_2X2','two samples/two targets independent of copy count',lambda:len(dag('run',['bc001','bc002'],['T1','T2'])),14)
    record('DAG_ANALYZE_2X2','external source, no demux node',lambda:len(dag('analyze',['bc001','bc002'],['T1','T2'])),13)
    a=NucleaseTarget.model_validate(nuc);b=NucleaseTarget.model_validate({**nuc,'tigr_window':'W2'});c=NucleaseTarget.model_validate({**nuc,'tigr_window':'W3'})
    record('IDENTITY_W2_DEFAULT','backend scientific identity canonicalization',lambda:digest(a.scientific_identity)==digest(b.scientific_identity),True)
    record('IDENTITY_WINDOW_CHANGE','backend scientific identity',lambda:digest(a.scientific_identity)!=digest(c.scientific_identity),True)
    record('PATH_DOTDOT_HELPER','no_symlinks normalizes traversal; not a registration allowlist',lambda:str(no_symlinks(scratch/'a/../b'))==str(scratch/'b'),True)
    record('PATH_OWNED_REJECTS','owned relative artifact boundary',lambda:owned(scratch,'../outside'),'UNSAFE_PATH')
assert not trap_calls,trap_calls
(ROOT/'oracle-fixtures.json').write_text(json.dumps(literal_fixtures,indent=2)+'\n')
(ROOT/'oracle-observations.json').write_text(json.dumps({'authority':'40bd8ad8844fd07ce8a138b5520f7f0ec948030f','package_import':str(peanalyzer.__file__),'checks':len(rows),'matched':sum(r['matched'] for r in rows),'scientific_executions':0,'subprocess_calls':len(trap_calls),'notes':'Two intentional tripwire canaries stopped before routing/probing. No candidate verdict.', 'observations':rows},indent=2)+'\n')
print(f'{len(rows)} baseline oracle checks matched; zero science or subprocess execution')
