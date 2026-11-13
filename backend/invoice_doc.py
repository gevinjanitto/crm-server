from pathlib import Path
from receipt_doc import T, R, I, wrap, rp, scale, _fit, MAX_ITEMS, TPL_DIR, render_docx_els, render_pdf_els, dims_of, apply_boxes

TEMPLATE = TPL_DIR / 'invoice_template.docx'
NAVY, BLUE, DARK, GREY, LINE = '20469B', '2454BF', '263449', '566278', 'D0D9E7'

def layout(r, dims=None):
    dims = dims or {}
    items, taxes = r['items'][:MAX_ITEMS], r['tax_rows']
    bs = 3.25 * scale(r, 'logo_scale')
    hx = max(4.7, 1.25 + bs + 0.2)
    els = [I(1.25, 1.05, bs, bs, 'brand', 'logo_scale'),
           T(hx, 1.9, 6.5, 0.7, ['CV. MAI HARTA'], 19, NAVY, bold=True), T(hx, 2.75, 6.5, 0.6, ['+6281236300562'], 11, GREY),
           T(hx, 3.3, 6.5, 0.6, ['cvmaiharta@gmail.com'], 11, GREY), T(11.5, 1.8, 8.0, 1.5, ['INVOICE'], 38, NAVY, align='right'),
           T(11.5, 3.35, 8.0, 0.6, [r['number']], 11, GREY, align='right', f='number'),
           T(1.5, 4.65, 17.5, 0.9, ['Jl. Tukad Ayung No. 5, Panjer, Kec. Denpasar Selatan,', 'Kota Denpasar, Bali 14085'], 11, GREY),
           R(1.5, 6.0, 18, 0.025, LINE), R(1.5, 6.0, 2.6, 0.065, BLUE), T(1.95, 6.55, 8.9, 0.5, ['KEPADA'], 9, BLUE, bold=True),
           T(13.0, 6.55, 6.5, 0.5, ['TANGGAL INVOICE'], 9, BLUE, bold=True, align='right'),
           T(13.0, 7.15, 6.5, 0.7, [r['date_label']], 16, DARK, bold=True, align='right', f='date')]
    kx, kw = 1.95, 9.8
    if dims.get('client'):
        b = 1.6 * scale(r, 'client_logo_scale')
        lw, lh = _fit(b, b, dims['client'], 4.5)
        els.append(I(1.95, 7.15, lw, lh, 'client', 'client_logo_scale'))
        kx, kw = 1.95 + lw + 0.35, 9.8 - lw - 0.35
    y = 7.15
    name = wrap(r['to_name'] or ' ', kw, 12, bold=True, max_lines=2)
    els.append(T(kx, y, kw, 0.55 * len(name), name, 12, DARK, bold=True, f='to_name')); y += 0.52 * len(name) + 0.23
    title = wrap(r['to_title'] or ' ', kw, 11, max_lines=2)
    els.append(T(kx, y, kw, 0.5 * len(title), title, 11, DARK, f='to_title')); y += 0.48 * len(title) + 0.17
    addr = wrap(r['to_address'] or ' ', kw, 11, max_lines=3)
    els.append(T(kx, y, kw, 0.5 * len(addr), addr, 11, GREY, f='to_address'))
    els += [R(1.5, 10.2, 18, 1.1, 'F2F5F9'), T(1.85, 10.52, 0.75, 0.55, ['No'], 11, NAVY, bold=True),
            T(2.9, 10.52, 6.2, 0.55, ['Deskripsi'], 11, NAVY, bold=True), T(9.45, 10.52, 1, 0.55, ['Qty'], 11, NAVY, bold=True, align='center'),
            T(10.7, 10.52, 4.1, 0.55, ['Harga Satuan'], 11, NAVY, bold=True, align='center'),
            T(15.1, 10.52, 4.05, 0.55, ['Jumlah'], 11, NAVY, bold=True, align='right')]
    start = 11.3
    rowh = max(0.7, min(2.5, (15.6 - start + (2 - len(taxes)) * 1.0) / len(items)))
    dsize, dlines = (12, 3) if rowh >= 1.4 else (10, 2) if rowh >= 1.05 else (9, 1)
    for i, it in enumerate(items):
        top = start + i * rowh
        center = top + rowh / 2
        desc = wrap(it['description'], 6.1, dsize, bold=True, max_lines=dlines)
        dh = len(desc) * dsize * 1.083 / 72 * 2.54
        els += [T(1.85, center - 0.23, 0.75, 0.6, [str(i + 1)], 11, DARK), T(2.9, center - dh / 2, 6.1, 1.5, desc, dsize, DARK, bold=True, f=f'items.{i}.description'),
                T(9.45, center - 0.23, 1, 0.6, [f"{it['qty']:g}"], 11, DARK, align='center', f=f'items.{i}.qty'),
                T(10.7, center - 0.23, 4.1, 0.6, [rp(it['price'])], 11, DARK, align='center', f=f'items.{i}.price'),
                T(15.1, center - 0.23, 4.05, 0.6, [rp(it['qty'] * it['price'])], 11, DARK, align='right')]
        if i < len(items) - 1: els.append(R(1.5, top + rowh, 18, 0.012, 'E3E8F0'))
    sep = start + len(items) * rowh
    els.append(R(1.5, sep, 18, 0.025, 'CBD6E8'))
    y = sep + 0.5
    for label, amount in taxes:
        els += [T(11.7, y, 3.3, 0.6, [label], 11, DARK), T(15.2, y, 3.95, 0.6, [rp(amount)], 11, DARK, align='right'), R(11.4, y + 0.75, 8.1, 0.025, LINE)]
        y += 1.0
    ty = y + 0.3
    els += [T(11.7, ty, 7.8, 0.5, ['TOTAL JUMLAH'], 9, GREY, bold=True, align='right'),
            T(11.7, ty + 0.6, 7.8, 1.1, [rp(r['total'])], 22, BLUE, bold=True, align='right')]
    by = max(19.0, ty + 2.2)
    els += [T(1.5, by, 9, 0.6, ['Syarat dan Ketentuan'], 14, NAVY, bold=True),
            T(1.5, by + 0.9, 10, 1.1, ['1. Mohon melakukan pembayaran', '    ke nomor rekening:'], 11, DARK),
            T(2.0, by + 2.25, 8, 0.6, [r['bank_name'] or ' '], 13, NAVY, bold=True, f='bank_name'),
            T(2.0, by + 2.95, 8, 0.6, [r['bank_branch'] or ' '], 11, DARK, f='bank_branch'),
            T(2.0, by + 3.65, 8, 0.6, [f"No. Rek: {r['account_number']}" if r['account_number'] else ' '], 12, DARK, bold=True, f='account_number'),
            T(2.0, by + 4.4, 8, 0.6, [f"A/N: {r['account_holder']}" if r['account_holder'] else ' '], 11, DARK, f='account_holder')]
    hy = by + 1.0
    if r.get('show_signature') and dims.get('sign'):
        b = 4.3 * scale(r, 'sign_scale')
        sw, sh = _fit(b, b, dims['sign'])
        els.append(I(15.4 - sw / 2, hy + 5.4 - sh, sw, sh, 'sign', 'sign_scale'))
    els += [T(11.5, hy, 8, 0.5, ['Hormat kami,'], 11, DARK, align='center'),
            T(11.5, hy + 0.55, 8, 0.6, [r['company_name']], 11, DARK, bold=True, align='center', f='company_name'),
            T(11.5, hy + 5.0, 8, 0.6, [r['signer_name']], 11, DARK, bold=True, align='center', f='signer_name'),
            T(11.5, hy + 5.6, 8, 0.5, [r['signer_title']], 10, GREY, align='center', f='signer_title'),
            R(1.5, 27.6, 18, 0.025, LINE), T(1.5, 27.95, 8, 0.5, ['CV. MAI HARTA'], 9, NAVY, bold=True),
            T(11.0, 27.95, 8.5, 0.5, [r['number']], 9, GREY, align='right'), R(1.5, 28.7, 2.6, 0.065, BLUE)]
    return apply_boxes(els, r)

def render_docx(r, images): return render_docx_els(TEMPLATE, layout(r, dims_of(images)), images)
def render_pdf(r, images): return render_pdf_els(f"Invoice {r['number']}", layout(r, dims_of(images)), images)
