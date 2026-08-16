import json, sys
sys.stdout.reconfigure(encoding='utf-8')
for f in ['accuracy.json', 'accuracy_morning.json', 'accuracy_rp5.json', 'accuracy_rp5_morning.json']:
    d = json.load(open(f, encoding='utf-8'))
    print("{} 模型={} 样本={} MAE={} 偏差={} ±1={}% ±2={}%".format(
        f.ljust(28), d.get('model'), d.get('n'), d.get('mae'), d.get('bias'), d.get('hit1'), d.get('hit2')))