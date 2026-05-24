import asyncio
import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

async def inspect():
    conninfo = f"host={os.getenv('POSTGRES_HOST')} port={os.getenv('POSTGRES_PORT')} dbname={os.getenv('POSTGRES_DB')} user={os.getenv('POSTGRES_USER')} password={os.getenv('POSTGRES_PASSWORD')}"
    try:
        conn = await psycopg.AsyncConnection.connect(conninfo)
        async with conn.cursor() as cur:
            # check columns of facturacion.factura
            await cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'facturacion' AND table_name = 'factura'")
            rows = await cur.fetchall()
            print("Columns in factura:")
            for r in rows:
                print(f" - {r[0]} ({r[1]})")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(inspect())
