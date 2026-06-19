import psycopg2
import json

conn = psycopg2.connect('postgresql://finflow:finflow@localhost:5433/finflow')
cur = conn.cursor()
cur.execute("SELECT state_summary FROM submissions WHERE id = '3c114a81-9f64-4127-a1a7-93c2cec5dea3'")
row = cur.fetchone()
if row:
    with open('state_summary.json', 'w') as f:
        f.write(json.dumps(row[0], indent=2) if not isinstance(row[0], str) else row[0])
