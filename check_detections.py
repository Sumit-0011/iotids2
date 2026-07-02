import pandas as pd, time
time.sleep(30)
df = pd.read_csv('data/data2.csv')
print('Total rows:', len(df))
det = int(df['detected'].sum()) if 'detected' in df.columns else 0
print('Detections:', det)
if len(df) > 0 and 'detected' in df.columns:
    rate = df['detected'].mean() * 100
    print('Detection rate: %.1f%%' % rate)
    print()
    cols = [c for c in ['temperature','humidity','sound_level','fuzz','detected','score'] if c in df.columns]
    print(df[cols].tail(20).to_string())
