"""看一眼批量跑到哪了。临时脚本，跑完删。"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
txt = Path('run-0.7.0.log').read_bytes().decode('gbk', errors='replace')
keep = []
for line in txt.splitlines():
    if 'HTTP Request' in line or 'Retrying request' in line:
        continue
    line = re.sub(r'\x1b\[[0-9;]*m', '', line)
    line = re.sub(r'^.*callHandlers:\d+ - ', '', line)
    keep.append(line.strip())
print('\n'.join(keep[-25:]))
print('--- 已出结果:', sorted(p.name for p in Path('out-0.7.0').glob('pair-*.json')))
print('--- 已缓存抽取:', len(list(Path('.srd-cache-0.7.0').glob('*.json'))), '/ 12 篇')
