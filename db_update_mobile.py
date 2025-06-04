import sqlite3
import hashlib
import csv
import re

def hash_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def parse_fee(text: str) -> int:
    """ '109,000' → 109000 """
    text = text.replace(",", "").replace("원", "").strip()
    return int(re.search(r'\d+', text).group()) if re.search(r'\d+', text) else 0

def get_company_id(conn, name: str) -> int:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Company WHERE name = ?", (name.lower(),))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute("INSERT INTO Company (name) VALUES (?)", (name.lower(),))
        conn.commit()
        return cursor.lastrowid

def upsert_service_plan_from_csv(csv_path: str, db_name: str = "combined_products.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            company_name = row["통신사(SKT, KT, LGU)"].strip().lower()
            product_name = row["상품명"].strip()
            raw_fee = row["월 요금"].strip()
            fee = parse_fee(raw_fee)

            company_id = get_company_id(conn, company_name)
            service_type = "Mobile"  # 현재 CSV는 모바일 요금제만 다루고 있음

            plan_id = hash_id(f"{company_name}-{product_name}")

            cursor.execute("""
                INSERT OR REPLACE INTO ServicePlan (id, company_id, name, service_type, fee)
                VALUES (?, ?, ?, ?, ?)
            """, (plan_id, company_id, product_name, service_type, fee))

            print(f"Upserted: {product_name} ({company_name}, {service_type}) → {fee}원")

    conn.commit()
    conn.close()

def show_all_tables(db_name="combined_products.db"):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    print("📋 현재 데이터베이스에 존재하는 테이블 목록:")
    for table in tables:
        print("-", table[0])

    conn.close()

if __name__ == "__main__":
    show_all_tables()
    upsert_service_plan_from_csv(r"C:\Users\Admin\Desktop\i_bricks\code_space\telecom\combo_db\telecom_raw.csv")