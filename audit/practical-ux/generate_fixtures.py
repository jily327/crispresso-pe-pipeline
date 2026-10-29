"""Deterministic, synthetic, stdlib-only audit fixtures; never parses candidate inputs."""
import argparse, copy, gzip, hashlib, json, random, zipfile
from pathlib import Path
from xml.sax.saxutils import escape
HERE=Path(__file__).resolve().parent
HEADERS=['sample_name','barcode_id','forward_barcode','reverse_barcode','editor','treatment','dpi','biological_replicate','block_id','paired']

def workbook(path, rows, *, sheet='Samples', extra=False, hidden_row=False, hidden_col=False, merged=False, formula=False, error=False, date=False):
    def cell(i,j,v):
        col=''; n=j+1
        while n: n,r=divmod(n-1,26);col=chr(65+r)+col
        ref=f'{col}{i+1}'
        if i==1 and j==6 and formula:return f'<c r="{ref}"><f>3+3</f><v>6</v></c>'
        if i==1 and j==6 and error:return f'<c r="{ref}" t="e"><v>#VALUE!</v></c>'
        if i==1 and j==6 and date:return f'<c r="{ref}" t="d"><v>2026-10-29T00:00:00</v></c>'
        return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(v))}</t></is></c>'
    data=''.join(f'<row r="{i+1}"'+(' hidden="1"' if hidden_row and i==1 else '')+'>'+''.join(cell(i,j,v) for j,v in enumerate(row))+'</row>' for i,row in enumerate(rows))
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    parts={'[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{x}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for x in range(1,3 if extra else 2))+'</Types>',
    '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
    'xl/workbook.xml':f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="{sheet}" sheetId="1" r:id="rId1"/>'+('<sheet name="OtherSamples" sheetId="2" r:id="rId2"/>' if extra else '')+'</sheets></workbook>',
    'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{x}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{x}.xml"/>' for x in range(1,3 if extra else 2))+'</Relationships>',
    'xl/worksheets/sheet1.xml':f'<worksheet xmlns="{ns}">'+('<cols><col min="7" max="7" hidden="1"/></cols>' if hidden_col else '')+'<sheetData>'+data+'</sheetData>'+('<mergeCells count="1"><mergeCell ref="A2:B2"/></mergeCells>' if merged else '')+'</worksheet>'}
    if extra:parts['xl/worksheets/sheet2.xml']=parts['xl/worksheets/sheet1.xml']
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name,value in sorted(parts.items()):
            info=zipfile.ZipInfo(name,(2020,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,value)

def generate(out, pairs=16):
    out.mkdir(parents=True,exist_ok=True)
    # Data uses the frozen main catalog, not a second hardcoded sequence lookup.
    import csv
    repo=HERE.parents[1]
    cat=list(csv.DictReader((repo/'src/peanalyzer/barcode_sets/qi_hitom_v1.csv').open()))
    ends={r['barcode_id']:r['sequence'] for r in cat}
    base=['sample1','4A',ends['F4'],ends['RA'],'editorA','control','6','01','','false']
    cases={}
    def add(name,rows=None,expect='reject',**opts):
        workbook(out/(name+'.xlsx'),rows or [HEADERS,base],**opts);cases[name]={'expectation':expect,'options':opts}
    add('valid-one',expect='accept')
    rows=[HEADERS]
    for i in range(20):
        row=base.copy();f=i//8+1;r=chr(65+i%8);row[0]=f'sample{i+1}';row[1]=f'{f}{r}';row[2]=ends[f'F{f}'];row[3]=ends['R'+r];row[7]=str(i+1);rows.append(row)
    add('valid-twenty',rows,expect='accept')
    add('whitespace',[HEADERS,[' '+v+' ' for v in base]],expect='accept-normalized')
    add('optional-blanks',expect='accept')
    row=base.copy();row[2]=row[3]='';add('catalog-4A',[HEADERS,row],expect='candidate-catalog-expansion')
    for name,col in [('missing-column',0),('missing-biological-column',7)]:add(name,[[v for i,v in enumerate(r) if i!=col] for r in [HEADERS,base]])
    h=HEADERS.copy();h[0]='sample_nam';add('misspelled-column',[h,base])
    add('unexpected-column',[HEADERS+['extra'],base+['x']])
    h=HEADERS.copy();h[1]=h[0];add('duplicate-header',[h,base])
    h=HEADERS.copy();h[0]='';add('empty-header',[h,base])
    for name,col,value in [('missing-name',0,''),('missing-replicate',7,''),('unknown-barcode',1,'9Z'),('bad-dpi',6,'six'),('bad-paired',9,'maybe'),('bad-custom-sequence',2,'ACNX')]:
        row=base.copy();row[col]=value
        if name=='unknown-barcode':row[2]=row[3]=''
        add(name,[HEADERS,row])
    row=base.copy();row[0]='sample2';add('duplicate-barcode',[HEADERS,base,row]);add('duplicate-samples',[HEADERS,base,base])
    add('blank-middle',[HEADERS,base,['']*len(HEADERS),rows[2]])
    add('data-after-blank',[HEADERS,['']*len(HEADERS),base])
    for name,opts in [('multiple-sheets',{'extra':True}),('renamed-sheet',{'sheet':'Renamed'}),('hidden-row',{'hidden_row':True}),('hidden-column',{'hidden_col':True}),('merged-cells',{'merged':True}),('formula',{'formula':True}),('formula-error',{'error':True}),('date-dpi',{'date':True})]:add(name,**opts)
    rng=random.Random(7341)
    with (out/'R1.fastq.gz').open('wb') as a,(out/'R2.fastq.gz').open('wb') as b:
        with gzip.GzipFile(fileobj=a,mode='wb',mtime=0,filename='') as ga,gzip.GzipFile(fileobj=b,mode='wb',mtime=0,filename='') as gb:
            for i in range(pairs):
                for mate,g in [(1,ga),(2,gb)]:
                    seq=''.join(rng.choices('ACGT',k=150));g.write(f'@audit{i}/{mate}\n{seq}\n+\n{"I"*150}\n'.encode())
    (out/'truncated.fastq.gz').write_bytes((out/'R1.fastq.gz').read_bytes()[:-9])
    (out/'excel-cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    hashes={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size_bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.json'}
    (out/'manifest.json').write_text(json.dumps(hashes,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--pairs',type=int,default=16);a=p.parse_args();generate(a.output,a.pairs)
