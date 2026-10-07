import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

db_name = os.getenv("DB_NAME", "physio_db")
user = os.getenv("DB_USER", "postgres")
password = os.getenv("DB_PASSWORD", "")
host = os.getenv("DB_HOST", "localhost")
port = os.getenv("DB_PORT", "5433")

print(f"Attempting PostgreSQL connection to host={host}, port={port}, dbname={db_name}, user={user}...")

try:
    conn = psycopg.connect(
        dbname=db_name,
        user=user,
        password=password,
        host=host,
        port=port,
        connect_timeout=5,
    )
    print("SUCCESS: Connected to PostgreSQL server!")
    with conn.cursor() as cur:
        cur.execute("SELECT version();")
        ver = cur.fetchone()[0]
        print("PostgreSQL Version:", ver)
        
        cur.execute("SELECT current_database(), current_user;")
        db_info = cur.fetchone()
        print(f"Current Database: {db_info[0]}, Current User: {db_info[1]}")
        
        cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
        tbl_count = cur.fetchone()[0]
        print(f"Total tables in public schema: {tbl_count}")

        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name LIMIT 15;")
        tbls = cur.fetchall()
        print("Sample tables:", [t[0] for t in tbls])

    conn.close()
except Exception as exc:
    print(f"FAILED to connect: {type(exc).__name__}: {exc}")
