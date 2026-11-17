"""无需额外软件，将工作台正文导出为标准Word文档。"""
import io
import re
import zipfile
from xml.sax.saxutils import escape


def word_document(markdown):
    def para(text, style='Normal'):
        return '<w:p><w:pPr><w:pStyle w:val="' + style + '"/></w:pPr><w:r><w:t xml:space="preserve">' + escape(text) + '</w:t></w:r></w:p>'
    content = [para('知研 · 文献综述', 'Title')]
    for line in markdown.splitlines():
        match = re.match(r'^(#{1,3})\s+(.+)', line)
        if match:
            content.append(para(match[2], 'Heading' + str(len(match[1]))))
        elif line.startswith('|'):
            if not re.fullmatch(r'[|\s:\-]+', line):
                content.append(para('　｜　'.join(x.strip() for x in line.strip('|').split('|'))))
        elif line.startswith('!['):
            # Markdown 图像以标题占位。
            m = re.match(r'!\[(.*?)\]', line)
            content.append(para('图示：' + (m[1] if m else '操作截图')))
        elif line.strip():
            content.append(para(line))
    document = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + ''.join(content) + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1304" w:right="1440" w:bottom="1304" w:left="1440"/></w:sectPr></w:body></w:document>'
    styles = '''<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="宋体"/><w:sz w:val="24"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="360" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults><w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'''
    for name, size in [('Title', 36), ('Heading1', 32), ('Heading2', 28), ('Heading3', 24)]:
        styles += '<w:style w:type="paragraph" w:styleId="' + name + '"><w:name w:val="' + name + '"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="200" w:after="140"/></w:pPr><w:rPr><w:b/><w:sz w:val="' + str(size) + '"/></w:rPr></w:style>'
    styles += '</w:styles>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
        z.writestr('_rels/.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml', document)
        z.writestr('word/styles.xml', styles)
        z.writestr('word/_rels/document.xml.rels', '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    return output.getvalue()
