# -*- coding: utf-8 -*-
"""历史快照清理：保留最近 KEEP_DAYS 天的全部快照；更早的每天只保留
最后一个（当日最后时刻）快照，用于长期准确度统计。"""
import os, glob, collections
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KEEP_DAYS = 14

def main():
    cutoff = datetime.now().date() - timedelta(days=KEEP_DAYS)
    files = sorted(glob.glob(os.path.join(SCRIPT_DIR, "history", "*.json")))
    keep = set()
    old = collections.defaultdict(list)
    for f in files:
        name = os.path.basename(f)
        try:
            day = datetime.strptime(name[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if day >= cutoff:
            keep.add(f)
        else:
            old[day].append(f)
    removed = 0
    for day, lst in sorted(old.items()):
        lst = sorted(lst)
        for f in lst[:-1]:
            os.remove(f)
            removed += 1
    print(f"保留 {len(keep) + len(old)} 个，删除 {removed} 个旧快照")

if __name__ == "__main__":
    main()