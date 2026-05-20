import sqlite3
import os
import psycopg2

# Check SQLite backup
db_path = 'db.sqlite3.backup'
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        
        print("=== SQLite Database (db.sqlite3.backup) ===")
        print(f"Total tables: {len(tables)}\n")
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            count = cursor.fetchone()[0]
            print(f"{table_name}: {count} rows")
        
        conn.close()
    except Exception as e:
        print(f"Error reading SQLite: {e}")
else:
    print("db.sqlite3.backup not found")

print("\n" + "="*50 + "\n")

# Check PostgreSQL
try:
    conn = psycopg2.connect(
        dbname='blacphics',
        user='postgres',
        password='Machel1704',
        host='localhost',
        port='5432'
    )
    cursor = conn.cursor()
    
    # Get all tables from public schema
    cursor.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    tables = cursor.fetchall()
    
    print("=== PostgreSQL Database (blacphics) ===")
    print(f"Total tables: {len(tables)}\n")
    
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"{table_name}: {count} rows")
    
    conn.close()
except Exception as e:
    print(f"Error reading PostgreSQL: {e}")
