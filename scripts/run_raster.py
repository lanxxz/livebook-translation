#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量执行栅格图的中文化：擦英文 → 写中文 → 出报告（替代 bash heredoc 片段）。

用法：
  python run_raster.py <figtexts.json> <figtrans_dir> <cache_dir> <out_dir>

  python run_raster.py work/book_figtexts.json work work/ocr_cache figs

参数：
  figtexts.json   ocr_figs.py 的产物：{key: {page, blocks, scale, bbox}}
  figtrans_dir    每张图的译文目录，文件名 <key>_figtrans.json（内容 {"0": "中文"}）
  cache_dir       OCR 裁好的原图目录，文件名 <key>.png
  out_dir         输出目录，写出 <key>.png（覆盖）

闸门：MISSING（有原文无译文）与 OVERFLOW（溢出方框）必须为 0，
      否则退出码 1；SMALL（字号过小）与 kept（保留英文）只报告。
"""
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fig_raster import process_figure  # noqa: E402


def main():
    args = sys.argv[1:]
    if len(args) != 4 or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0 if args and args[0] in ('-h', '--help') else 1
    ft_p, tr_dir, cache_dir, out_dir = args

    ft = json.load(open(ft_p, encoding='utf-8-sig'))
    os.makedirs(out_dir, exist_ok=True)
    rep = {k: [] for k in ('rendered', 'kept', 'MISSING', 'OVERFLOW', 'SMALL')}
    no_tr = []

    for key in sorted(ft, key=lambda k: (ft[k].get('page', 0), k)):
        v = ft[key]
        png = os.path.join(cache_dir, key + '.png')
        if not os.path.exists(png):
            print(f'!! 缺原图 {png}（先跑 ocr_figs.py 生成裁图缓存）')
            return 1
        trp = os.path.join(tr_dir, key + '_figtrans.json')
        if os.path.exists(trp):
            tr = json.load(open(trp, encoding='utf-8-sig'))
        else:
            tr = {}
            no_tr.append(key)
        process_figure(png, v['blocks'], tr, rep, scale=v.get('scale'),
                       out_path=os.path.join(out_dir, key + '.png'))

    print(f"合计 图 {len(ft)} 张  rendered={len(rep['rendered'])}  "
          f"kept={len(rep['kept'])}  MISSING={len(rep['MISSING'])}  "
          f"OVERFLOW={len(rep['OVERFLOW'])}  SMALL={len(rep['SMALL'])}")
    if no_tr:
        print(f'!! {len(no_tr)} 张图没有译文文件（按全缺处理）: {no_tr[:10]}')
    for name in ('MISSING', 'OVERFLOW', 'SMALL'):
        items = rep[name]
        if not items:
            continue
        print(f'\n{name}（{len(items)}）:')
        for d in items[:20]:
            extra = ''
            if name == 'OVERFLOW' and d.get('over_h') is not None:
                extra = f"  over={d['over_h']}"
            print(f"  {d.get('id')}  {str(d.get('en', ''))[:40]}{extra}")
        if len(items) > 20:
            print(f'  … 其余 {len(items) - 20} 条略')

    ok = not rep['MISSING'] and not rep['OVERFLOW']
    print('\n结论：' + ('✓ 通过（MISSING/OVERFLOW 均为 0）' if ok
                       else '✗ 未通过，先清 MISSING / OVERFLOW'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
