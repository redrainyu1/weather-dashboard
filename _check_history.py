import json, glob, os, sys
sys.stdout.reconfigure(encoding='utf-8')
for f in sorted(glob.glob('history/*.json')):
    d = json.load(open(f, encoding='utf-8'))
    rows = d.get('rows', [])
    dates = {}
    for r in rows:
        dates[r.get('date_display')] = dates.get(r.get('date_display'), 0) + 1
    print("{:28s} updated={} rows={} dates={}".format(os.path.basename(f), d.get('updated_at', '?'), len(rows), dates))