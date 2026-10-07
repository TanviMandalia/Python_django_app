import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

db_name = os.getenv("DB_NAME", "physio_db")
user = os.getenv("DB_USER", "postgres")
password = os.getenv("DB_PASSWORD", "")
host = os.getenv("DB_HOST", "localhost")
port = os.getenv("DB_PORT", "5433")

conn = psycopg.connect(
    dbname=db_name,
    user=user,
    password=password,
    host=host,
    port=port,
)

with conn.cursor() as cur:
    # 1. Extensions
    cur.execute("SELECT extname, extversion FROM pg_extension;")
    extensions = cur.fetchall()
    print("--- Extensions ---")
    for ext in extensions:
        print(f"  {ext[0]} (v{ext[1]})")

    # 2. Table count and list
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = [row[0] for row in cur.fetchall()]
    print(f"\n--- Total Public Tables: {len(tables)} ---")

    # 3. Foreign key constraints count
    cur.execute("""
        SELECT count(*) 
        FROM information_schema.table_constraints 
        WHERE constraint_type = 'FOREIGN KEY' AND table_schema = 'public';
    """)
    fk_count = cur.fetchone()[0]
    print(f"Foreign Key Constraints: {fk_count}")

    # 4. Indexes count
    cur.execute("""
        SELECT count(*) 
        FROM pg_indexes 
        WHERE schemaname = 'public';
    """)
    idx_count = cur.fetchone()[0]
    print(f"Total Indexes: {idx_count}")

    # 5. Check constraints count
    cur.execute("""
        SELECT count(*) 
        FROM information_schema.table_constraints 
        WHERE constraint_type = 'CHECK' AND table_schema = 'public';
    """)
    chk_count = cur.fetchone()[0]
    print(f"Check Constraints: {chk_count}")

    # 6. Unique constraints count
    cur.execute("""
        SELECT count(*) 
        FROM information_schema.table_constraints 
        WHERE constraint_type = 'UNIQUE' AND table_schema = 'public';
    """)
    uniq_count = cur.fetchone()[0]
    print(f"Unique Constraints: {uniq_count}")

    # 7. Check for orphaned records in key tables (e.g. Appointment without Hospital, PatientProfile without User)
    print("\n--- Integrity Invariant Checks ---")
    cur.execute("""
        SELECT count(*) FROM core_appointment a
        LEFT JOIN core_hospital h ON a.hospital_id = h.id
        WHERE a.hospital_id IS NOT NULL AND h.id IS NULL;
    """)
    orphan_appt_hosp = cur.fetchone()[0]
    print(f"Orphan Appointments (invalid hospital_id): {orphan_appt_hosp}")

    cur.execute("""
        SELECT count(*) FROM core_patientprofile p
        LEFT JOIN auth_user u ON p.user_id = u.id
        WHERE u.id IS NULL;
    """)
    orphan_patients = cur.fetchone()[0]
    print(f"Orphan Patient Profiles (invalid user_id): {orphan_patients}")

    cur.execute("""
        SELECT count(*) FROM core_hospitalsubscription s
        LEFT JOIN core_hospital h ON s.hospital_id = h.id
        WHERE h.id IS NULL;
    """)
    orphan_subs = cur.fetchone()[0]
    print(f"Orphan Subscriptions (invalid hospital_id): {orphan_subs}")

conn.close()
print("\nSchema Audit Completed Successfully.")
