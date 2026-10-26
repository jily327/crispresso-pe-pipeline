"""Independent report hash, SVG XML and local HTML resource checks."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import xml.etree.ElementTree as ET
from common import read,sha,write
class Resources(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('src','data') and value:self.paths.append(value)

def check(root):
    root=Path(root);manifest=read(root/'report_manifest.json');html=root/'report.html'
    for a in manifest['artifacts']:assert sha(root/a['path'])==a['sha256']
    svgs=sorted(root.glob('figures/*.svg'))
    for p in svgs:assert ET.parse(p).getroot().tag=='{http://www.w3.org/2000/svg}svg'
    parser=Resources();parser.feed(html.read_text());parser.close()
    for name in parser.paths:
        assert not name.startswith(('http:','https:','//','/'))
        assert (root/name).resolve().is_relative_to(root.resolve()) and (root/name).is_file()
    assert all(p.read_text() in html.read_text() for p in svgs)
    return dict(svg_xml_count=len(svgs),html_local_resources=parser.paths,artifact_hashes_valid=True,html_includes_all_figures=True,limitation='Structural/resource checks, not browser rendering or full HTML conformance')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('roots',nargs='+');p.add_argument('--out',required=True);a=p.parse_args();write(a.out,{root:check(root) for root in a.roots})
