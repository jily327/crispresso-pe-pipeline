"""Archive only the small inputs needed to replay the strict Core result parser."""
import json
from pathlib import Path
import shutil
import sys
import zipfile

from peanalyzer.nuclease.window_comparison import compare


def collect(root, dest):
    metrics = {}
    with zipfile.ZipFile(dest/'core-evidence.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for window in ('W2','W3','explicit_distinct'):
            case = root/window
            metric, = (case/'workflow/metrics').rglob('result.json')
            metrics[window] = metric
            shutil.copyfile(case/'oracle.json',dest/(window+'-oracle.json'))
            archive.write(metric,window+'/result.json')
            for copy in ('chr03g','chr13g'):
                child = metric.parent/'references'/copy/'output/CRISPResso_on_nuclease'
                for name in ('CRISPResso2_info.json','CRISPResso_mapping_statistics.txt',
                             'CRISPResso_quantification_of_editing_frequency.txt','Alleles_frequency_table.zip',
                             'out.extendedFrags.fastq.gz'):
                    archive.write(child/name,window+'/'+copy+'/'+name)
    (dest/'window-comparison.json').write_text(json.dumps(compare(metrics['W2'],metrics['W3']),indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    collect(Path(sys.argv[1]),Path(__file__).parent)
