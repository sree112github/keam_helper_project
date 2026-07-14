import json
import psycopg2
import os
import sys
from dotenv import load_dotenv

def main():
    if len(sys.argv) < 2:
        print("Usage: python insert_data.py <path_to_json_file>")
        return

    json_file = sys.argv[1]

    # Load environment variables
    load_dotenv('.env')

    db_host = os.getenv('DB_HOST')
    db_port = os.getenv('DB_PORT')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_name = os.getenv('DB_NAME')

    if not db_host:
        print("Database credentials not found in .env")
        return

    # Connect to the database
    conn_str = f"host={db_host} port={db_port} user={db_user} password={db_password} dbname={db_name} sslmode=require"
    try:
        conn = psycopg2.connect(conn_str)
        conn.autocommit = True
        cursor = conn.cursor()
    except Exception as e:
        print(f"Error connecting to DB: {e}")
        return

    # Load data from json
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Loaded {len(data)} records from {json_file}.")

    # Insert data
    insert_query = """
    INSERT INTO public.keam_cutoff_ranks (year, round, course, college_code, college_name, college_type, ranks)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (year, round, course, college_code) 
    DO UPDATE SET 
        college_name = EXCLUDED.college_name,
        college_type = EXCLUDED.college_type,
        ranks = EXCLUDED.ranks;
    """

    inserted = 0
    for row in data:
        try:
            # Handle potential differences in key names based on different JSON files
            year = row.get('year')
            round_val = row.get('round')
            course = row.get('course')
            college_code = row.get('college_code', row.get('college_code'))
            name = row.get('name', row.get('college_name'))
            ctype = row.get('type', row.get('college_type'))
            ranks = row.get('ranks', {})

            cursor.execute(insert_query, (
                year,
                round_val,
                course,
                college_code,
                name,
                ctype,
                json.dumps(ranks)
            ))
            inserted += 1
        except Exception as e:
            print(f"Error inserting row: {e}")

    print(f"Successfully inserted/updated {inserted} records from {json_file}.")
    cursor.close()
    conn.close()

if __name__ == '__main__':
    main()
