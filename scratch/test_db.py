"""Script temporal para verificar conexión a BD."""
import psycopg

conn = psycopg.connect(
    host='217.216.85.110',
    port=5433,
    dbname='facturacion',
    user='admin',
    password='mysecretpassword'
)
cur = conn.cursor()
cur.execute('SELECT current_database(), version()')
print('DB:', cur.fetchone())

cur.execute(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'facturacion' ORDER BY table_name"
)
tablas = [r[0] for r in cur.fetchall()]
print(f'Tablas encontradas ({len(tablas)}):')
for t in tablas:
    print(f'  - {t}')

conn.close()
print('Conexión OK')
