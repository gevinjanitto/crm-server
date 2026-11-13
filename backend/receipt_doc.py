"""Kwitansi: satu tata letak (cm, dari kiri-atas A4) yang dirender ke DOCX (VML seperti template) dan PDF (reportlab)."""
import io
import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape
from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

TPL_DIR = Path(__file__).parent / 'templates'
TEMPLATE = TPL_DIR / 'kwitansi_template.docx'
BRAND_LOGO = TPL_DIR / 'logo_maiharta.png'
DEFAULT_SIGN = TPL_DIR / 'ttd_default.png'
BLUE, DARK, GREY, LINE, TITLE, WHITE = '2454BF', '263449', '566278', 'B8C0CC', '202631', 'FFFFFF'
GRAD = ['3C49A6', '2454BF', '1599D4']
TAB_PATH = 'm 0,0 l 690,0 c 770,0,790,45,825,235 l 1000,1000 l 0,1000 x e'
MAX_ITEMS = 6

def rp(n): return 'Rp ' + f'{int(round(n)):,}'.replace(',', '.') + ',00'

def terbilang(n):
    n = int(n)
    s = ['', 'Satu', 'Dua', 'Tiga', 'Empat', 'Lima', 'Enam', 'Tujuh', 'Delapan', 'Sembilan', 'Sepuluh', 'Sebelas']
    if n < 12: return s[n]
    if n < 20: return terbilang(n - 10) + ' Belas'
    if n < 100: return terbilang(n // 10) + ' Puluh ' + terbilang(n % 10)
    if n < 200: return 'Seratus ' + terbilang(n - 100)
    if n < 1000: return terbilang(n // 100) + ' Ratus ' + terbilang(n % 100)
    if n < 2000: return 'Seribu ' + terbilang(n - 1000)
    for unit, name in [(10**12, 'Triliun'), (10**9, 'Miliar'), (10**6, 'Juta'), (1000, 'Ribu')]:
        if n >= unit: return terbilang(n // unit) + f' {name} ' + terbilang(n % unit)

def terbilang_rupiah(n): return re.sub(r'\s+', ' ', terbilang(n) or 'Nol').strip() + ' Rupiah'

def _font(bold, italic): return 'Helvetica' + ('-BoldOblique' if bold and italic else '-Bold' if bold else '-Oblique' if italic else '')

def wrap(text, width_cm, size, bold=False, italic=False, max_lines=2):
    out = []
    for para in str(text or '').split('\n'):
        line = ''
        for w in para.split():
            cand = f'{line} {w}'.strip()
            if stringWidth(cand, _font(bold, italic), size) <= width_cm * cm or not line: line = cand
            else: out.append(line); line = w
        out.append(line)
    out = [l for l in out if l] or ['']
    if len(out) > max_lines:
        out = out[:max_lines]; out[-1] = out[-1].rstrip('.') + '…'
    return out

def T(x, y, w, h, lines, size, color, bold=False, italic=False, align='left', f=None):
    return {'t': 'text', 'x': x, 'y': y, 'w': w, 'h': h, 'lines': lines, 'size': size, 'color': color, 'bold': bold, 'italic': italic, 'align': align, 'f': f}

def R(x, y, w, h, fill=LINE): return {'t': 'rect', 'x': x, 'y': y, 'w': w, 'h': h, 'fill': fill}
def G(x, y, w, h, path=None): return {'t': 'grad', 'x': x, 'y': y, 'w': w, 'h': h, 'path': path}
def I(x, y, w, h, key, s=None): return {'t': 'img', 'x': x, 'y': y, 'w': w, 'h': h, 'key': key, 's': s}

def scale(r, key): return max(0.3, min(2.5, float(r.get(key) or 100) / 100))

def _f(v):
    try: return max(-30.0, min(30.0, float(v or 0)))
    except (TypeError, ValueError): return 0.0

def apply_boxes(els, r):
    boxes = r.get('image_boxes') if isinstance(r.get('image_boxes'), dict) else {}
    for e in els:
        b = boxes.get(e.get('key')) if e['t'] == 'img' else None
        if not isinstance(b, dict): continue
        dw, dh = _f(b.get('dw')), _f(b.get('dh'))
        e['w'], e['h'] = max(0.3, min(21, e['w'] + dw)), max(0.3, min(29.7, e['h'] + dh))
        e['x'] = max(0, min(21 - e['w'], e['x'] + _f(b.get('dx'))))
        e['y'] = max(0, min(29.7 - e['h'], e['y'] + _f(b.get('dy'))))
        if dw or dh: e['stretch'] = True
    return els

def image_dims(data):
    if not data: return None
    try: return Image.open(io.BytesIO(data)).size
    except Exception: return None

def _fit(box_w, box_h, size, max_w=None):
    iw, ih = size
    s = min(box_w / iw, box_h / ih)
    if max_w and iw * s > max_w: s = max_w / iw
    return iw * s, ih * s

def layout(r, dims=None):
    """r: dict kwitansi lengkap (number, date_label, received_from, items, tax_rows, total, terbilang, signer_*)."""
    items, taxes = r['items'][:MAX_ITEMS], r['tax_rows']
    tl = wrap(r['terbilang'], 16.8, 12, italic=True, max_lines=3)
    tax_off = (0.7 + len(taxes)) if taxes else 0.45
    gap = 2.0
    budget = 21.7 - 11.0 - tax_off - gap - 0.7 - len(tl) * 0.46 - 0.9
    if budget / len(items) < 0.75: gap = 1.3; budget += 0.7
    rowh = max(0.65, min(1.6, budget / len(items)))
    dims = dims or {}
    bs = 3.2 * scale(r, 'logo_scale')
    els = [I(1.5, 1.3, bs, bs, 'brand', 'logo_scale'), T(10, 2.05, 9.5, 1.4, ['KWITANSI'], 36, TITLE, align='right'),
           T(9, 3.55, 10.5, 0.7, [f"Nomor  {r['number']}"], 10, GREY, align='right', f='number'), R(1.5, 4.7, 18, 0.025),
           G(1.5, 5.7, 9, 3.3, TAB_PATH), T(2.25, 6.35, 6.8, 0.5, ['Diterima dari'], 10, WHITE)]
    nx, nw = 2.25, 6.7
    if dims.get('client'):
        b = 1.5 * scale(r, 'client_logo_scale')
        lw, lh = _fit(b, b, dims['client'], 4.2)
        els.append(I(2.25, max(5.9, 6.95 + (1.5 - lh) / 2), lw, lh, 'client', 'client_logo_scale'))
        nx, nw = 2.25 + lw + 0.3, 6.7 - lw - 0.3
    nsize, name = 15, wrap(r['received_from'], nw, 15, bold=True, max_lines=9)
    if len(name) > 2: nsize, name = 12, wrap(r['received_from'], nw, 12, bold=True, max_lines=3)
    els.append(T(nx, 6.95, nw, 1.6, name, nsize, WHITE, bold=True, f='received_from'))
    els += [T(14.1, 6.25, 5.4, 0.5, ['Total Jumlah'], 11, BLUE, bold=True), T(14.1, 6.85, 5.4, 0.7, [rp(r['total'])], 16, DARK, bold=True),
            R(14.1, 7.65, 5.4, 0.025), T(14.1, 7.85, 5.4, 0.45, ['Tanggal'], 10, BLUE, bold=True), T(14.1, 8.35, 5.4, 0.45, [r['date_label']], 10, DARK, f='date'),
            G(1.5, 9.35, 18, 1.05), T(1.85, 9.64, 0.75, 0.55, ['No'], 10, WHITE, bold=True), T(2.9, 9.64, 6.2, 0.55, ['Deskripsi'], 11, WHITE, bold=True),
            T(9.45, 9.64, 1, 0.55, ['Qty'], 10, WHITE, bold=True, align='center'), T(10.7, 9.64, 4.1, 0.55, ['Harga Satuan'], 10, WHITE, bold=True, align='center'),
            T(15.1, 9.64, 4.05, 0.55, ['Jumlah'], 10, WHITE, bold=True, align='right')]
    dsize, dlines = (12, 3) if rowh >= 1.4 else (10, 2) if rowh >= 1.05 else (9, 1)
    for i, it in enumerate(items):
        top = 11.0 + i * rowh
        center = top + min(0.46, rowh / 2 - 0.02)
        desc = wrap(it['description'], 6.1, dsize, bold=True, max_lines=dlines)
        dh = len(desc) * dsize * 1.083 / 72 * 2.54
        els += [T(1.85, center - 0.23, 0.75, 0.6, [str(i + 1)], 11, DARK), T(2.9, center - dh / 2, 6.1, 1.5, desc, dsize, DARK, bold=True, f=f'items.{i}.description'),
                T(9.45, center - 0.23, 1, 0.6, [f"{it['qty']:g}"], 10, DARK, align='center', f=f'items.{i}.qty'), T(10.7, center - 0.23, 4.1, 0.6, [rp(it['price'])], 10, DARK, align='center', f=f'items.{i}.price'),
                T(15.1, center - 0.23, 4.05, 0.6, [rp(it['qty'] * it['price'])], 10, DARK, align='right')]
        if i < len(items) - 1: els.append(R(1.5, top + rowh, 18, 0.012, 'DDE2EA'))
    sep = 11.0 + len(items) * rowh
    els.append(R(1.5, sep, 18, 0.025))
    y = sep + 0.45
    for label, amount in taxes:
        els += [T(12.15, y, 3, 0.6, [label], 11, DARK), T(15.2, y, 3.95, 0.6, [rp(amount)], 11, DARK, align='right'), R(11.8, y + 0.75, 7.7, 0.025)]
        y += 1.0
    gy = sep + tax_off
    els += [G(11.8, gy, 7.7, 1.0), T(12.15, gy + 0.25, 2.8, 0.6, ['Total Jumlah'], 11, WHITE, bold=True), T(15.1, gy + 0.25, 4.05, 0.6, [rp(r['total'])], 11, WHITE, bold=True, align='right')]
    ty = gy + gap
    els += [T(1.5, ty, 4, 0.6, ['Terbilang'], 12, BLUE, bold=True), T(1.5, ty + 0.7, 16.8, 1.3, tl, 12, DARK, italic=True)]
    sy = min(21.7, max(20.65, ty + 0.7 + len(tl) * 0.46 + 0.9))
    if r.get('show_signature') and dims.get('sign'):
        b = 2.6 * scale(r, 'sign_scale')
        sw, sh = _fit(b, b, dims['sign'])
        els.append(I(15.75 - sw / 2, sy + 3.55 - sh, sw, sh, 'sign', 'sign_scale'))
    els += [T(12.0, sy, 7.5, 0.5, ['Hormat kami,'], 11, DARK, align='center'), T(12.0, sy + 0.53, 7.5, 0.5, [r['company_name']], 11, DARK, bold=True, align='center', f='company_name'),
            R(12.8, sy + 3.0, 5.9, 0.025), T(11.8, sy + 3.25, 7.9, 0.5, [r['signer_name']], 11, DARK, bold=True, align='center', f='signer_name'),
            T(12, sy + 3.8, 7.5, 0.5, [r['signer_title']], 10, GREY, align='center', f='signer_title')]
    els += [R(1.5, 26.3, 18, 0.025), T(1.5, 26.65, 4, 0.5, ['CV. MAI HARTA'], 10, BLUE, bold=True), T(1.5, 27.2, 4.1, 0.5, ['+6281236300562'], 9, GREY),
            T(6.0, 26.65, 5, 0.5, ['EMAIL'], 9, BLUE, bold=True), T(6.0, 27.2, 5, 0.5, ['cvmaiharta@gmail.com'], 9, GREY),
            T(11.7, 26.65, 7.8, 1.2, ['Jl. Tukad Ayung No. 5, Panjer,', 'Kec. Denpasar Selatan, Kota Denpasar,', 'Bali 14085'], 9, GREY),
            G(1.5, 28.35, 18, 0.75)]
    return apply_boxes(els, r)

def _png(img):
    b = io.BytesIO()
    (img if img.mode in ('RGB', 'RGBA', 'L', 'LA', 'P') else img.convert('RGBA')).save(b, 'PNG')
    return b.getvalue()

# ---------- DOCX ----------
def _style(e, z):
    return (f"position:absolute;margin-left:{e['x']:.3f}cm;margin-top:{e['y']:.3f}cm;width:{e['w']:.3f}cm;height:{e['h']:.3f}cm;"
            f"z-index:{z};mso-position-horizontal-relative:page;mso-position-vertical-relative:page")

def _vml(e, i):
    sid = f'Shape{i}'
    grad = f'<v:fill type="gradient" color="#{GRAD[0]}" color2="#{GRAD[2]}" angle="90" colors="0 #{GRAD[0]};0.5 #{GRAD[1]};1 #{GRAD[2]}"/>'
    if e['t'] == 'rect': return f'<v:rect id="{sid}" style="{_style(e, 1)}" stroked="f" fillcolor="#{e["fill"]}"/>'
    if e['t'] == 'grad':
        if e['path']: return f'<v:shape id="{sid}" style="{_style(e, 1)}" stroked="f" coordsize="1000,1000" path="{e["path"]}">{grad}</v:shape>'
        return f'<v:rect id="{sid}" style="{_style(e, 1)}" stroked="f">{grad}</v:rect>'
    if e['t'] == 'img':
        rid = f"rIdImg_{e['key']}"
        return f'<v:rect id="{sid}" style="{_style(e, 5)}" stroked="f" filled="f"><v:imagedata r:id="{rid}" o:title="Logo"/></v:rect>'
    e = {**e, 'h': max(e['h'], len(e['lines']) * e['size'] * 1.45 / 72 * 2.54 + 0.15)}
    rpr = (f'<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="{int(e["size"] * 2)}"/><w:color w:val="{e["color"]}"/>'
           + ('<w:b/>' if e['bold'] else '') + ('<w:i/>' if e['italic'] else ''))
    paras = ''.join(f'<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="260" w:lineRule="auto"/><w:jc w:val="{e["align"]}"/></w:pPr>'
                    f'<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space="preserve">{escape(l)}</w:t></w:r></w:p>' for l in e['lines'])
    return f'<v:rect id="{sid}" style="{_style(e, 10)}" stroked="f" filled="f"><v:textbox inset="0,0,0,0"><w:txbxContent>{paras}</w:txbxContent></v:textbox></v:rect>'

def render_docx_els(template, els, images):
    with zipfile.ZipFile(template) as src:
        files = {n: src.read(n) for n in src.namelist()}
    doc = files['word/document.xml'].decode()
    head, tail = doc[:doc.index('<w:body>') + 8], doc[doc.index('<w:sectPr'):]
    body = '<w:p>' + ''.join(f'<w:r><w:pict>{_vml(e, i + 1)}</w:pict></w:r>' for i, e in enumerate(els)) + '</w:p>'
    files['word/document.xml'] = (head + body + tail).encode()
    rels = files['word/_rels/document.xml.rels'].decode()
    present = set(files)
    for rel in re.findall(r'<Relationship [^>]*/>', rels):
        target = re.search(r'Target="([^"]+)"', rel).group(1)
        if 'customXml' not in target and f'word/{target}' not in present: rels = rels.replace(rel, '')
    ct = files['[Content_Types].xml'].decode()
    for part in re.findall(r'<Override PartName="/([^"]+)"[^>]*/>', ct):
        if part not in present: ct = re.sub(rf'<Override PartName="/{re.escape(part)}"[^>]*/>', '', ct)
    if 'Extension="png"' not in ct: ct = ct.replace('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="png" ContentType="image/png"/>')
    for key in dict.fromkeys(e['key'] for e in els if e['t'] == 'img'):
        files[f'word/media/img_{key}.png'] = _png(Image.open(io.BytesIO(images[key])))
        rels = rels.replace('</Relationships>', f'<Relationship Id="rIdImg_{key}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/img_{key}.png"/></Relationships>')
    files['word/_rels/document.xml.rels'] = rels.encode()
    files['[Content_Types].xml'] = ct.encode()
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, data in files.items(): z.writestr(n, data)
    return out.getvalue()

def doc_images(logo_bytes=None, sign_bytes=None, show_signature=False):
    imgs = {'brand': BRAND_LOGO.read_bytes()}
    if logo_bytes: imgs['client'] = logo_bytes
    if show_signature: imgs['sign'] = sign_bytes or DEFAULT_SIGN.read_bytes()
    return imgs

def dims_of(images): return {k: image_dims(v) for k, v in images.items()}

def render_docx(r, images): return render_docx_els(TEMPLATE, layout(r, dims_of(images)), images)

# ---------- PDF ----------
def _path(c, e):
    x, top, w, h = e['x'] * cm, (29.7 - e['y']) * cm, e['w'] * cm, e['h'] * cm
    p = c.beginPath()
    if not e['path']:
        p.rect(x, top - h, w, h); return p
    P = lambda px, py: (x + px / 1000 * w, top - py / 1000 * h)
    p.moveTo(*P(0, 0)); p.lineTo(*P(690, 0)); p.curveTo(*P(770, 0), *P(790, 45), *P(825, 235)); p.lineTo(*P(1000, 1000)); p.lineTo(*P(0, 1000)); p.close()
    return p

def render_pdf_els(title, els, images):
    imgs = {k: ImageReader(io.BytesIO(_png(Image.open(io.BytesIO(v))))) for k, v in images.items()}
    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)
    c.setTitle(title)
    for e in els:
        x, y = e['x'] * cm, (29.7 - e['y']) * cm
        if e['t'] == 'rect':
            c.setFillColor(HexColor('#' + e['fill'])); c.rect(x, y - e['h'] * cm, e['w'] * cm, e['h'] * cm, stroke=0, fill=1)
        elif e['t'] == 'grad':
            c.saveState(); c.clipPath(_path(c, e), stroke=0, fill=0)
            c.linearGradient(x, y, x + e['w'] * cm, y, [HexColor('#' + g) for g in GRAD], [0, 0.5, 1], extend=True)
            c.restoreState()
        elif e['t'] == 'img':
            c.drawImage(imgs[e['key']], x, y - e['h'] * cm, e['w'] * cm, e['h'] * cm, mask='auto', preserveAspectRatio=not e.get('stretch'), anchor='c')
        else:
            f, s = _font(e['bold'], e['italic']), e['size']
            c.setFont(f, s); c.setFillColor(HexColor('#' + e['color']))
            lh = s * 1.083 * 1.22
            for i, line in enumerate(e['lines']):
                by = y - s * 0.95 - i * lh
                if e['align'] == 'right': c.drawRightString(x + e['w'] * cm, by, line)
                elif e['align'] == 'center': c.drawCentredString(x + e['w'] * cm / 2, by, line)
                else: c.drawString(x, by, line)
    c.showPage(); c.save()
    return out.getvalue()

def render_pdf(r, images): return render_pdf_els(f"Kwitansi {r['number']}", layout(r, dims_of(images)), images)
