import psycopg2
import json

def default(o):
    if hasattr(o, 'isoformat'):
        return o.isoformat()
    return str(o)

conn = psycopg2.connect('postgresql://finflow:finflow@localhost:5433/finflow')
cur = conn.cursor()
cur.execute("SELECT * FROM submissions WHERE id = '3c114a81-9f64-4127-a1a7-93c2cec5dea3'")
row = cur.fetchone()
if row:
    columns = [col[0] for col in cur.description]
    data = dict(zip(columns, row))
    state_summary = data.get('state_summary', {})
    
    # Check if state_summary is string or dict
    if isinstance(state_summary, str):
        state_summary = json.loads(state_summary)
        
    preview_rows = state_summary.get('schema_proposal', {}).get('preview_rows', [])
    if not preview_rows:
        preview_rows = state_summary.get('raw_records', [])

    if preview_rows:
        print("First row:", json.dumps(preview_rows[0], indent=2))
        for key in preview_rows[0].keys():
            unique_vals = list(set(str(r.get(key, '')) for r in preview_rows[:20]))
            print(f"{key}: {unique_vals[:5]}")
    else:
        print("No preview rows found in state_summary.")
