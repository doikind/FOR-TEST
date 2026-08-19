"""Generate .docx files for the two FinSignal talk scripts using only stdlib.

A .docx is a ZIP container with OOXML parts; we write the minimal set of parts
by hand so no third-party dependency (python-docx / lxml) is needed.
"""
import io
import os
import zipfile
from xml.sax.saxutils import escape

BASE = r"F:\deep\finsignal-content-agent\docs"
OUT = r"F:\deep"

FILES = [
    ("talk-agent1.md", "FinSignal-Agent1-功能介绍逐字稿.docx"),
    ("talk-agent2.md", "FinSignal-Agent2-功能介绍逐字稿.docx"),
]


def esc(text):
    return escape(text, {'"': "&quot;"})


def run(text, bold=False, size=24, color=None, italic=False):
    """Build one <w:r> run. size is half-points (24 = 12pt, 32 = 16pt)."""
    props = []
    if bold:
        props.append("<w:b/>")
    if italic:
        props.append("<w:i/>")
    if size:
        props.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    if color:
        props.append(f'<w:color w:val="{color}"/>')
    # East-Asian font so Chinese renders with a CJK font in Word
    rpr = (
        '<w:rPr>'
        '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="宋体"/>'
        + "".join(props) +
        '</w:rPr>'
    )
    return f'<w:r>{rpr}<w:t xml:space="preserve">{esc(text)}</w:t></w:r>'


def paragraph(runs, space_after=120):
    """One <w:p> with the given runs; spacing in twentieths of a point."""
    return (
        f'<w:p><w:pPr><w:spacing w:after="{space_after}" w:line="360" '
        f'w:lineRule="auto"/></w:pPr>{"".join(runs)}</w:p>'
    )


def md_to_paragraphs(md_text):
    """Convert the simple markdown into a list of paragraph XML strings."""
    paras = []
    for raw in md_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.strip() == "---":
            continue
        if line.startswith("# "):
            paras.append(paragraph([run(line[2:].strip(), bold=True, size=36)], space_after=200))
        elif line.startswith(">"):
            # blockquote note: gray, italic
            content = line.lstrip(">").strip()
            paras.append(paragraph([run(content, italic=True, size=21, color="808080")], space_after=100))
        else:
            paras.append(paragraph([run(line, size=24)], space_after=140))
    return paras


def build_docx(title, paragraphs_xml):
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(paragraphs_xml)}</w:body></w:document>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
    return buf.getvalue()


def main():
    for md_name, docx_name in FILES:
        md_path = os.path.join(BASE, md_name)
        with open(md_path, encoding="utf-8") as f:
            md_text = f.read()
        paras = md_to_paragraphs(md_text)
        data = build_docx(docx_name, paras)
        out_path = os.path.join(OUT, docx_name)
        with open(out_path, "wb") as f:
            f.write(data)
        print(f"OK: {out_path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
