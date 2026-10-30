# -*- coding: utf-8 -*-
"""检查某包译文覆盖情况，并合并分片译文源。

为什么要它：长书必须分片翻译（每片几十~上百项），而分片最容易出的错是
「键号写错」。这个脚本把「分片 tx 源」+「已有 fill」合并，然后和骨架模板
逐键比对，一眼看出 缺多少 / 多余多少。

判读规则（重要）：
  - **多余必须为 0** —— 大于 0 说明键号写错了（写到了骨架里不存在的键）。
  - **缺可以为非 0** —— 说明这一片还没写完，继续写就行。
  - 两个都为 0 = 这个包翻译完成。

用法：
  python cov.py <包名>                       # 只看现状
  python cov.py <包名> work/tx_a.py work/tx_b.py   # 合并分片后再看

分片源文件格式（任意文件名，只要能被 import）：
  # -*- coding: utf-8 -*-
  FILL_A = {"0|title": "中文章名", "3|text": "……"}
也可以叫 FILL、FILL_B、FILL_C …… 脚本会收集所有 FILL* 字典。
"""
import importlib.util
import json
import os
import sys

from bookconf import cfg

PACK = os.path.join(cfg('root'), 'work', 'pack')


def load(p):
    spec = importlib.util.spec_from_file_location('m', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    name = sys.argv[1]
    tpl_path = os.path.join(PACK, name + '_fill.json')
    tpl = json.load(open(tpl_path, encoding='utf-8'))
    merged = {}
    # 先读现有 fill（可能已被别的脚本补过）
    for k, v in tpl.items():
        if str(v).strip():
            merged[k] = v
    # 再叠加分片 tx 源（同名键以分片为准）
    for p in sys.argv[2:]:
        full = p if os.path.isabs(p) else os.path.join(cfg('root'), p)
        m = load(full)
        for attr in dir(m):
            if attr == 'FILL' or attr.startswith('FILL_'):
                d = getattr(m, attr)
                if isinstance(d, dict):
                    for k, v in d.items():
                        if str(v).strip():
                            merged[k] = v
    extra = [k for k in merged if k not in tpl]
    missing = [k for k in tpl if k not in merged]
    print('模板 %d 键，已填 %d，缺 %d，多余 %d'
          % (len(tpl), len(merged), len(missing), len(extra)))
    if extra:
        print('多余键（键号写错了！）:', extra[:12])
    if missing:
        print('缺失（前 30）:', missing[:30])
    # 写出合并结果，便于 apply_fill 直接使用
    out = os.path.join(PACK, name + '_fill.json')
    json.dump({k: merged.get(k, '') for k in tpl},
              open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('已写出', out)


if __name__ == '__main__':
    main()
