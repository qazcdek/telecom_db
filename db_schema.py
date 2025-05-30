import sqlite3
import hashlib

def hash_id(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

# DB 연결
conn = sqlite3.connect("combined_products.db")
cursor = conn.cursor()

# Company(통신사) 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS Company (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
)
""")


# ServicePlan 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS ServicePlan (
    id TEXT PRIMARY KEY,
    company_id INTEGER,
    name TEXT,
    service_type TEXT CHECK(service_type IN ('mobile', 'internet', 'iptv')),
    fee INTEGER,
    FOREIGN KEY (company_id) REFERENCES Company(id)
)
""")

# CombinedProduct 테이블 (결합상품 메타 정보)
cursor.execute("""
CREATE TABLE IF NOT EXISTS CombinedProduct (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company_id INTEGER,
    join_condition TEXT,
    notice TEXT,
    applicant_scope TEXT,
    application_channel TEXT,
    url TEXT,
    summary TEXT,
    available BOOLEAN,
    FOREIGN KEY (company_id) REFERENCES Company(id)
)
""")

# Discount 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS Discount (
    id TEXT PRIMARY KEY,
    combined_product_id TEXT,
    company_id INTEGER,
    plan_id TEXT,
    discount_type TEXT CHECK(discount_type IN ('amount', 'rate')),
    discount_value INTEGER,
    note TEXT,
    FOREIGN KEY (combined_product_id) REFERENCES CombinedProduct(id),
    FOREIGN KEY (company_id) REFERENCES Company(id),
    FOREIGN KEY (plan_id) REFERENCES ServicePlan(id)
)
""")

# Benefits 테이블
cursor.execute("""
CREATE TABLE IF NOT EXISTS Benefits (
    id TEXT PRIMARY KEY,
    discount_id TEXT,
    content TEXT,
    FOREIGN KEY (discount_id) REFERENCES Discount(id)
)
""")

# 연결 테이블: CombinedProduct - ServicePlan
cursor.execute("""
CREATE TABLE IF NOT EXISTS CombinedProductServicePlan (
    combined_product_id TEXT,
    service_plan_id TEXT,
    PRIMARY KEY (combined_product_id, service_plan_id),
    FOREIGN KEY (combined_product_id) REFERENCES CombinedProduct(id),
    FOREIGN KEY (service_plan_id) REFERENCES ServicePlan(id)
)
""")

# 커밋 및 종료
conn.commit()
conn.close()

conn = sqlite3.connect("combined_products.db")
cursor = conn.cursor()

companies = ["skt", "kt", "lguplus", "others"]
for c_ in companies:
    cursor.execute("""
        INSERT INTO Company (name)
        VALUES (?)
        ON CONFLICT(name) DO NOTHING
    """, (c_,))
    
cursor.execute("SELECT * FROM Company")
rows = cursor.fetchall()

for row in rows:
    print(row)

conn.commit()
conn.close()