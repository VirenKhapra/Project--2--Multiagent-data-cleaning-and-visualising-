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
columns = [col[0] for col in cur.description]
if row:
    data = dict(zip(columns, row))
    print(json.dumps(data, indent=2, default=default))
