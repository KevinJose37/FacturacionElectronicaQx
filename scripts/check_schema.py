import psycopg2
conn = psycopg2.connect(host='217.216.85.110', port=5433, dbname='facturacion', user='admin', password='mysecretpassword')
cur = conn.cursor()
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='facturacion' AND table_name='log_proceso' ORDER BY ordinal_position")
print("=== log_proceso ===")
for r in cur.fetchall():
    print(f"  {r[0]}")
conn.close()
