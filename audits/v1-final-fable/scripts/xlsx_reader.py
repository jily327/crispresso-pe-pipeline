"""Independent stdlib XLSX reader (ZIP + XML); no openpyxl, no PEAnalyzer."""
import zipfile
import xml.etree.ElementTree as ET

# ECMA-376 built-in number formats relevant here (id 10 is the percentage format with two decimals).
BUILTIN = {'0': 'General', '9': '0%', '10': '0.00%'}
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_xlsx(path):
    """Independent reader: returns {sheet_name: [[(type, raw_value, style_index)...]...]} and numFmts."""
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared = []
        if 'xl/sharedStrings.xml' in names:
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS):
                shared.append(''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])))
        workbook = ET.fromstring(z.read('xl/workbook.xml'))
        rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        styles = ET.fromstring(z.read('xl/styles.xml'))
        custom = {n.attrib['numFmtId']: n.attrib['formatCode'] for n in styles.iter('{%s}numFmt' % NS['m'])}
        xfs = [x.attrib.get('numFmtId') for x in styles.find('m:cellXfs', NS)]
        sheets = {}
        for sheet in workbook.find('m:sheets', NS):
            rid = sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
            target = rels[rid]
            target = target[1:] if target.startswith('/') else 'xl/' + target
            rows = []
            for row in ET.fromstring(z.read(target)).iter('{%s}row' % NS['m']):
                cells = []
                for c in row.findall('m:c', NS):
                    kind = c.attrib.get('t', 'n')
                    v = c.find('m:v', NS)
                    f = c.find('m:f', NS)
                    if kind == 's':
                        value = shared[int(v.text)]
                    elif kind == 'inlineStr':
                        value = ''.join(t.text or '' for t in c.iter('{%s}t' % NS['m']))
                    else:
                        value = None if v is None else v.text
                    fmt = xfs[int(c.attrib.get('s', 0))]
                    kind = 'text' if kind in ('s', 'inlineStr', 'str') else kind
                    cells.append(dict(ref=c.attrib['r'], type=kind, value=value, formula=None if f is None else f.text,
                                      num_fmt=custom.get(fmt, BUILTIN.get(fmt, fmt))))
                rows.append(cells)
            sheets[sheet.attrib['name']] = rows
        return sheets, names


