import json

with open('/tmp/dailydata.json') as f:
    data = json.load(f)

with open('/tmp/metrics.json') as f:
    metrics = json.load(f)

target_date = metrics['target_date']

rows = data['values']
header = rows[0]
col_map = {name: idx for idx, name in enumerate(header)}

# NOTE: Keeping Chinese characters here as they strict-match the raw Google Sheet headers for HK audience.
core_brand_cols = ['美素', '美素金裝', '美素皇家', '美素有機', '美素Kids', '美素Signature']

alerts = []
for i, row in enumerate(rows[1:], start=2):
    while len(row) < len(header):
        row.append('')

    # Skip rows that don't match the target date
    if row[col_map.get('Date', 2)] != target_date:
        continue

    # Identify if any core brand column contains 'N' (Negative Sentiment)
    has_n = any(col_name in col_map and row[col_map[col_name]] == 'N' for col_name in core_brand_cols)
    if not has_n:
        continue

    alerts.append({
        'group': row[col_map.get('Group', 0)],
        'date': target_date,
        'time': row[col_map.get('Time', 3)],
        'userPhone': row[col_map.get('userPhone', 4)],
        'messageBody': row[col_map.get('messageBody', 7)],
        'quotedMessage': row[col_map.get('quotedMessage', 6)],
        'n_brands': [c for c in core_brand_cols if c in col_map and row[col_map[c]] == 'N']
    })

print(f"Target date: {target_date}, Negative Alerts found: {len(alerts)}")
for idx, a in enumerate(alerts, 1):
    print(f"  Alert {idx}: {a['group']} | {a['time']} | {a['userPhone']}")

with open('/tmp/alerts.json', 'w', encoding='utf-8') as f:
    json.dump({'target_date': target_date, 'alerts': alerts}, f, ensure_ascii=False, indent=2)
print("Saved to /tmp/alerts.json")
