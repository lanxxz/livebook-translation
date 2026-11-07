# -*- coding: utf-8 -*-
"""按「唯一英文短语映射表」批量生成各分册的图内译文 `_figzh.txt`。

用于骨架文本流水线（W11 / X9）。一次处理全书，避免每章各写一份生成脚本。

用法：
    python gen_figzh_map.py [--root 项目根] [--map map.json] [--keep keep.json]

映射表 JSON：`{"prompt template": "提示词模板", ...}`（键大小写不敏感、NFKC 归一）。
KEEP 规则 JSON：`["^click ", "sql_db_", ...]`（正则，命中即保留英文）。
未命中映射的长句、界面文字、数据表与标识符**写英文原文**——`render_figs.py`
判 KEEP 的条件是「译文 == 原文」，写纯空白会被判 MISSING，写 `SAME` 只有
`fig_raster.py` 认。

输入：<root>/work/<doc>__figtexts.json 或 <root>/work/book_figtexts.json
输出：<root>/work/<doc>_figzh.txt
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter

# 流程标签的通用译法；具体项目用 --map 覆盖/扩充
DEFAULT_MAP = {
    'data': '数据', 'input': '输入', 'output': '输出', 'model': '模型',
    'query': '查询', 'query result': '查询结果', 'result': '结果',
    'prompt': '提示词', 'prompt template': '提示词模板',
    'generate prompt': '生成提示词', 'generate answer': '生成答案',
    'substitute placeholders': '替换占位符', 'question': '问题',
    'answer': '答案', 'task': '任务', 'tools': '工具',
    'language model': '语言模型', 'llm agent': 'LLM 智能体',
    'data structure': '数据结构', 'data-processing tool': '数据处理工具',
    'natural language query interface': '自然语言查询界面',
    'input text': '输入文本', 'examples': '示例', 'attributes': '属性',
    'classification result': '分类结果', 'structured output': '结构化输出',
    'postprocessing': '后处理', 'output parser': '输出解析器',
    'create embedding': '生成嵌入向量', 'index data': '建立索引',
    'load data': '加载数据', 'retrieve data': '检索数据',
    'relational db': '关系数据库', 'sql code': 'SQL 代码',
    'sql query': 'SQL 查询', 'review': '评论', 'email': '邮件',
    'speech transcription': '语音转录', 'speech generator': '语音生成器',
    'translate text': '翻译文本', 'raw result': '原始结果',
    'spoken question': '口头问题', 'text question': '文本问题',
    'descriptions': '描述', 'model list': '模型列表',
    'model description': '模型描述', 'web text': '网页文本',
    'upload pictures': '上传图片', 'trying it out': '上手试一试',
}

DEFAULT_KEEP = [
    r'^(click|enter|submit|copy|select the|create database|execute query)\b',
    r'^(settings|history|continue|run|regenerate|new chat|start chat)\b',
    r'^(show analysis|web connector|upload button|google login|microsoft login|search)\b',
    r'^(table \d|sql_db_|name:|name |gpa |year |category |class |genre |platform |reviewid |satisfied |degree )',
    r'^(is this a banana|do the images show|rdbms|\.\.\.)',
    r'https?://', r'^www\.', r'^[A-Za-z_][A-Za-z0-9_.]{0,24}$',
]


def norm(s):
    return unicodedata.normalize('NFKC', s).strip().lower()


def find_root(p):
    if p:
        return os.path.abspath(p)
    d = os.getcwd()
    for _ in range(4):
        if os.path.exists(os.path.join(d, 'docs.json')):
            return d
        d = os.path.dirname(d)
    return os.getcwd()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', help='项目根（含 docs.json）')
    ap.add_argument('--map', dest='map_path', help='映射表 JSON')
    ap.add_argument('--keep', dest='keep_path', help='KEEP 正则列表 JSON')
    a = ap.parse_args()
    root = find_root(a.root)
    work = os.path.join(root, 'work')

    table = dict(DEFAULT_MAP)
    if a.map_path:
        table.update(json.load(open(a.map_path, encoding='utf-8')))
    nmap = {norm(k): v for k, v in table.items()}

    keep_pats = list(DEFAULT_KEEP)
    if a.keep_path:
        keep_pats += json.load(open(a.keep_path, encoding='utf-8'))
    keep_re = re.compile('|'.join(f'(?:{p})' for p in keep_pats), re.I)

    docs = json.load(open(os.path.join(root, 'docs.json'), encoding='utf-8'))
    ids = [d['id'] for d in docs]

    # 优先逐份 figtexts；缺失时从全书按页范围切
    all_figs = None
    bookp = os.path.join(work, 'book_figtexts.json')
    if os.path.exists(bookp):
        all_figs = json.load(open(bookp, encoding='utf-8'))

    total_ok = total_keep = handled = 0
    for doc in ids:
        p = os.path.join(work, doc + '_figtexts.json')
        if os.path.exists(p):
            figs = json.load(open(p, encoding='utf-8'))
        elif all_figs is not None:
            d = next(x for x in docs if x['id'] == doc)
            lo, hi = d['from'], d['to']
            figs = {k: v for k, v in all_figs.items()
                    if lo <= v.get('page', 0) <= hi}
        else:
            continue          # 该份暂无图内文字，静默跳过（部分章节推进时常见）

        handled += 1
        lines, ok, kept = [], 0, 0
        for key in sorted(figs, key=lambda k: (figs[k].get('page', 0), k)):
            lines.append(f'@@FIG {key}')
            for b in figs[key].get('blocks') or []:
                en = b['en']
                cn = nmap.get(norm(en))
                if cn is None:
                    if len(en) > 60 or keep_re.search(norm(en)):
                        cn = en                    # KEEP
                    else:
                        cn = en                    # 短未知短语也保留，避免误译专名
                    kept += 1
                else:
                    ok += 1
                lines.append(f"@@T {b['id']}")
                lines.append(f'ZH {cn}')
            lines.append('')
        open(os.path.join(work, doc + '_figzh.txt'), 'w',
             encoding='utf-8').write('\n'.join(lines))
        print(f'{doc:8s} 图 {len(figs):3d}  中文化 {ok:3d}  KEEP {kept:3d}')
        total_ok += ok
        total_keep += kept
    if not handled:
        sys.exit('未找到任何 <doc>_figtexts.json / book_figtexts.json，'
                 '请先跑 extract_fig_texts.py 与 slice_layout.py')
    print(f'处理 {handled}/{len(ids)} 份；中文化 {total_ok} 条，'
          f'KEEP 保留英文 {total_keep} 条')


if __name__ == '__main__':
    main()
