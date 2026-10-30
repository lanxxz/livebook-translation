# -*- coding: utf-8 -*-
"""生成与 Word 同版式的 HTML 预览（仅供自查排版，不作为交付物）。"""
import json, sys, os, re, html as H

PT = 96 / 72.0
TEXT_W_CM = 16.2
ORIG_TEXT_W_PT = 423.0


def esc(s):
    return H.escape(s).replace('\n', '<br>')


def rich(s):
    s = esc(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    return s


def main(trans_p, figtexts_p, figtrans_p, figdir, out_html):
    blocks = json.load(open(trans_p, encoding='utf-8'))
    figtexts = json.load(open(figtexts_p, encoding='utf-8'))
    figtrans = json.load(open(figtrans_p, encoding='utf-8'))
    body = []
    for b in blocks:
        t = b['type']
        if t == 'chapter_open':
            body.append(f'<div class="chnum">第 {b["num"]} 章</div>')
            body.append(f'<h1>{esc(b["title"])}</h1>')
            if b.get('orig_title'):
                body.append(f'<div class="orig">{esc(b["orig_title"])}</div>')
            body.append('<hr class="rule">')
            body.append('<div class="tochead">本章内容</div><ul class="toc">')
            for it in b['toc']:
                body.append(f'<li>{rich(it)}</li>')
            body.append('</ul>')
            body.append(f'<div class="quote">“{esc(b["quote"])}”</div>')
            if b.get('quote_by'):
                body.append(f'<div class="qby">{esc(b["quote_by"])}</div>')
            if b.get('intro'):
                body.append(f'<p>{rich(b["intro"])}</p>')
        elif t == 'h2':
            body.append(f'<h2>{esc(b["text"])}</h2>')
        elif t == 'h3':
            body.append(f'<h3>{esc(b["text"])}</h3>')
        elif t == 'p':
            body.append(f'<p>{rich(b["text"])}</p>')
        elif t == 'list':
            body.append('<ul>' + ''.join(f'<li>{rich(i)}</li>' for i in b['items']) + '</ul>')
        elif t == 'numlist':
            body.append('<ol>' + ''.join(f'<li>{rich(i)}</li>' for i in b['items']) + '</ol>')
        elif t == 'figure':
            key = b['key']
            bb = figtexts.get(key, {}).get('bbox')
            wpt = (bb[2] - bb[0]) if bb else None
            wcm = min(TEXT_W_CM, max(7.0, wpt / ORIG_TEXT_W_PT * TEXT_W_CM)) if wpt else TEXT_W_CM * 0.8
            body.append(f'<div class="fig"><img src="../figs/ch07/{key}.png" style="width:{wcm}cm"></div>')
            pairs = []
            seen = set()
            CJK = re.compile(r'[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]')
            for x in figtexts[key]['blocks']:
                cn = figtrans.get(key, {}).get(str(x['id']))
                if not cn:
                    continue
                en = re.sub(r'\s+', ' ', x['en']).strip()
                parts = [p.strip() for p in cn.split('\n') if p.strip()]
                o = ''
                for i, p in enumerate(parts):
                    if i == 0:
                        o = p
                    elif o and CJK.match(o[-1]) and CJK.match(p[0]):
                        o += p
                    else:
                        o += ' ' + p
                if en == o or (en.lower(), o) in seen:
                    continue
                seen.add((en.lower(), o))
                pairs.append(f'{en} → {o}')
            if pairs:
                body.append('<div class="fignote"><b>图内文字对照</b>　' + esc('；'.join(pairs)) + '</div>')
        elif t == 'table':
            rows = ''.join('<tr>' + ''.join(f'<td>{rich(c)}</td>' for c in r) + '</tr>' for r in b['rows'])
            head = ''.join(f'<th>{rich(c)}</th>' for c in b['head'])
            body.append(f'<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>')

    css = f'''
    @page {{ size: 21cm 29.7cm; margin: 0; }}
    body {{ margin:0; background:#e9e9e9; }}
    .page {{ width:21cm; min-height:29.7cm; background:#fff; margin:0 auto; padding:2.2cm 2.4cm; box-sizing:border-box;
             font-family:"宋体",SimSun,serif; font-size:10.5pt; line-height:1.6; color:#1a1a1a; }}
    p {{ margin:0 0 8pt 0; text-indent:2em; text-align:justify; }}
    h1 {{ font-family:"微软雅黑","Microsoft YaHei",sans-serif; font-size:28pt; color:#9E1B32; margin:0 0 4pt 0; line-height:1.15; }}
    h2 {{ font-family:"微软雅黑",sans-serif; font-size:16pt; color:#9E1B32; margin:18pt 0 8pt 0; line-height:1.25; }}
    h3 {{ font-family:"微软雅黑",sans-serif; font-size:12.5pt; color:#404040; margin:12pt 0 6pt 0; }}
    .chnum {{ font-family:"微软雅黑",sans-serif; font-size:11pt; font-weight:bold; color:#9E1B32; margin-top:6pt; }}
    .orig {{ font-family:"微软雅黑",sans-serif; font-size:11pt; color:#808080; font-style:italic; margin-bottom:10pt; }}
    hr.rule {{ border:0; border-top:6px solid #9E1B32; margin:0 0 10pt 0; }}
    .tochead {{ font-family:"微软雅黑",sans-serif; font-size:11pt; font-weight:bold; color:#9E1B32; margin:2pt 0 4pt 0; }}
    ul.toc {{ margin:0 0 0 1.2em; padding:0; }}
    ul.toc li {{ margin-bottom:2pt; }}
    .quote {{ text-align:center; font-family:"楷体",KaiTi,serif; font-size:11.5pt; font-style:italic; color:#595959; margin:16pt 0 2pt 0; }}
    .qby {{ text-align:right; font-family:"楷体",serif; font-size:10pt; color:#808080; margin-bottom:14pt; }}
    ul, ol {{ margin:0 0 8pt 1.6em; padding:0; }}
    li {{ margin-bottom:4pt; line-height:1.55; }}
    .fig {{ text-align:center; margin:6pt 0 2pt 0; }}
    .fig img {{ max-width:100%; }}
    .fignote {{ font-family:"微软雅黑",sans-serif; font-size:8pt; color:#808080; line-height:1.3; margin:0 0 10pt 0; text-indent:0; }}
    table {{ border-collapse:collapse; width:100%; margin:6pt 0 12pt 0; font-size:9pt; }}
    th, td {{ border:1px solid #999; padding:4pt; vertical-align:top; text-align:left; line-height:1.3; }}
    th {{ background:#F5EDEF; color:#9E1B32; text-align:center; font-family:"微软雅黑",sans-serif; }}
    '''
    doc = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body><div class="page">{"".join(body)}</div></body></html>'
    open(out_html, 'w', encoding='utf-8').write(doc)
    print('saved', out_html, len(doc))


if __name__ == '__main__':
    main(*sys.argv[1:6])
