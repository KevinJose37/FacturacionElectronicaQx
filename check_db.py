import asyncio
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

async def check_db():
    conninfo = f"host={os.getenv('POSTGRES_HOST')} port={os.getenv('POSTGRES_PORT')} dbname={os.getenv('POSTGRES_DB')} user={os.getenv('POSTGRES_USER')} password={os.getenv('POSTGRES_PASSWORD')}"
    try:
        conn = await psycopg.AsyncConnection.connect(conninfo)
        async with conn.cursor() as cur:
            await cur.execute('SELECT COUNT(*) FROM facturacion.factura_control')
            count_control = (await cur.fetchone())[0]
            print(f'Total registros en factura_control: {count_control}')
            
            await cur.execute('''
                SELECT MIN(f.fecha_generacion), MAX(f.fecha_generacion) 
                FROM facturacion.factura f
                JOIN facturacion.factura_control fc ON f.id_factura = fc.id_factura
            ''')
            min_date, max_date = await cur.fetchone()
            print(f'Rango de fechas disponibles (fecha_generacion): {min_date} a {max_date}')
            
            await cur.execute('''
                SELECT f.fecha_generacion::date, COUNT(*) 
                FROM facturacion.factura f
                JOIN facturacion.factura_control fc ON f.id_factura = fc.id_factura
                GROUP BY f.fecha_generacion::date
                ORDER BY f.fecha_generacion::date DESC
                LIMIT 5
            ''')
            print('Últimas fechas registradas:')
            for r in await cur.fetchall():
                print(f' - {r[0]}: {r[1]} registros')
            
        await conn.close()
    except Exception as e:
        print(f'Error conectando a la BD: {e}')

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_db())
