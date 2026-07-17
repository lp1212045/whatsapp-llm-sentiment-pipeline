import json

# Load raw dashboard data fetched by Manus AI connector
with open('/tmp/dashboard_data.json') as f:
    data = json.load(f)

rows = data['values']
header = rows[0]

# Auto-detect: find last non-empty, non-zero column from Total Reach row (row index 1)
reach_row = rows[1]
col = None
for i in range(len(reach_row)-1, 1, -1):
    if reach_row[i] and reach_row[i] not in ('0', ''):
        col = i
        break

target_date = header[col]
print(f"Target date: {target_date} (col {col})")

def get_val(row_idx, col_idx):
    if row_idx >= len(rows): return '0'
    row = rows[row_idx]
    if col_idx >= len(row): return '0'
    return row[col_idx] if row[col_idx] else '0'

# Extract predefined metrics based on known row indices
metrics = {
    'target_date': target_date,
    'reach': get_val(1, col),
    'unique_reach': get_val(2, col),
    'total_group': get_val(4, col),
    'stages': get_val(5, col),
    'hospitals': get_val(6, col),
    'ift_topics': get_val(7, col),
    'education': get_val(8, col),
    'shopping': get_val(9, col),
    'location': get_val(10, col),
    'others': get_val(11, col),
    'null_group': get_val(12, col),
    'only_image': get_val(13, col),
    
    # Sentiment Data (P: Positive, I: Neutral, N: Negative)
    'core_brand_total': get_val(16, col),
    'core_p': get_val(17, col),
    'core_i': get_val(18, col),
    'core_n': get_val(19, col),
    
    # Competitors
    'competitor_a': get_val(42, col),
    'competitor_b': get_val(43, col),
    'competitor_c': get_val(44, col)
}

print("=== Metrics Extracted ===")
for k, v in metrics.items():
    print(f"  {k}: {v}")

with open('/tmp/metrics.json', 'w') as f:
    json.dump(metrics, f, ensure_ascii=False, indent=2)
print("Saved to /tmp/metrics.json")
