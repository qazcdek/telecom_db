import sqlite3
import hashlib

# 테이블별 SQL 문 정의 (create_combined_product_db의 일부 발췌)
table_sql_map = {
    "Company": """
        CREATE TABLE IF NOT EXISTS Company (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(32) UNIQUE NOT NULL
        )
    """,
    "ServicePlan": """
        CREATE TABLE IF NOT EXISTS ServicePlan (
            id VARCHAR(64) PRIMARY KEY,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            service_type TEXT NOT NULL,
            fee INTEGER NOT NULL,
            FOREIGN KEY (company_id) REFERENCES Company(id)
        )
    """,
    "CombinedProduct": """
        CREATE TABLE IF NOT EXISTS CombinedProduct (
            id VARCHAR(64) PRIMARY KEY,
            name TEXT NOT NULL,
            company_id INTEGER NOT NULL,
            description TEXT,
            min_mobile_lines INTEGER DEFAULT 0,
            min_internet_lines INTEGER DEFAULT 0,
            min_iptv_lines INTEGER DEFAULT 0,
            max_mobile_lines INTEGER,
            max_internet_lines INTEGER,
            max_iptv_lines INTEGER,
            join_condition TEXT,
            applicant_scope TEXT,
            application_channel TEXT,
            url TEXT,
            available BOOLEAN,
            FOREIGN KEY (company_id) REFERENCES Company(id)
        )
    """,
    "CombinedProductEligibility": """
        CREATE TABLE IF NOT EXISTS CombinedProductEligibility (
            combined_product_id VARCHAR(64) NOT NULL,
            service_plan_id VARCHAR(64) NOT NULL,
            min_lines INTEGER DEFAULT 0,
            max_lines INTEGER DEFAULT 1,
            is_base_plan_required BOOLEAN DEFAULT FALSE,
            PRIMARY KEY (combined_product_id, service_plan_id),
            FOREIGN KEY (combined_product_id) REFERENCES CombinedProduct(id),
            FOREIGN KEY (service_plan_id) REFERENCES ServicePlan(id)
        )
    """,
    "Discount": """
        CREATE TABLE IF NOT EXISTS Discount (
            id VARCHAR(64) PRIMARY KEY,
            combined_product_id VARCHAR(64) NOT NULL,
            discount_name VARCHAR(128),
            discount_type VARCHAR(64) NOT NULL,
            discount_value INTEGER NOT NULL,
            unit VARCHAR(10) NOT NULL,
            applies_to_service_type VARCHAR(124),
            applies_to_line_sequence VARCHAR(64),
            note VARCHAR(256),
            FOREIGN KEY (combined_product_id) REFERENCES CombinedProduct(id)
        )
    """,
    "DiscountConditionByPlan": """
        CREATE TABLE IF NOT EXISTS DiscountConditionByPlan (
            discount_id VARCHAR(64) NOT NULL,
            service_plan_id VARCHAR(64) NOT NULL,
            condition_text VARCHAR(256),
            override_discount_value INTEGER,
            override_unit VARCHAR(10),
            PRIMARY KEY (discount_id, service_plan_id),
            FOREIGN KEY (discount_id) REFERENCES Discount(id),
            FOREIGN KEY (service_plan_id) REFERENCES ServicePlan(id)
        )
    """,
    "DiscountConditionByLineCount": """
        CREATE TABLE IF NOT EXISTS DiscountConditionByLineCount (
            discount_id VARCHAR(64) NOT NULL,
            min_applicable_lines INTEGER NOT NULL,
            max_applicable_lines INTEGER,
            override_discount_value INTEGER,
            override_unit VARCHAR(10),
            applies_per_line BOOLEAN DEFAULT TRUE,
            PRIMARY KEY (discount_id, min_applicable_lines),
            FOREIGN KEY (discount_id) REFERENCES Discount(id)
        )
    """,
    "Benefits": """
        CREATE TABLE IF NOT EXISTS Benefits (
            id VARCHAR(64) PRIMARY KEY,
            combined_product_id VARCHAR(64) NOT NULL,
            benefit_type VARCHAR(64),
            content VARCHAR(256),
            condition VARCHAR(256),
            FOREIGN KEY (combined_product_id) REFERENCES CombinedProduct(id)
        )
    """
}

def hash_id(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def create_combined_product_db(db_name="combined_products.db", table_sql_map=table_sql_map):
    """
    최종 업데이트된 스키마에 따라 SQLite 데이터베이스를 생성하고 테이블을 정의합니다.
    (할인 관련 테이블 세분화 반영)
    """
    conn = None
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        # Company 테이블 생성
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS Company (
        #         id INTEGER PRIMARY KEY AUTOINCREMENT,
        #         name VARCHAR(32) UNIQUE NOT NULL
        #     )
        # """)
        cursor.execute(table_sql_map["Company"])

        # ServicePlan 테이블 생성
        # VARCHAR 대신 TEXT 타입 유지
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS ServicePlan (
        #         id VARCHAR(64) PRIMARY KEY,
        #         company_id INTEGER NOT NULL,
        #         name TEXT NOT NULL,
        #         service_type TEXT NOT NULL,
        #         fee INTEGER NOT NULL,
        #         FOREIGN KEY (company_id) REFERENCES Company(id)
        #     )
        # """)
        cursor.execute(table_sql_map["ServicePlan"])

        # CombinedProduct 테이블 생성
        # VARCHAR 대신 TEXT 타입 유지 및 필드명/타입 반영
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS CombinedProduct (
        #         id VARCHAR(64) PRIMARY KEY,
        #         name TEXT NOT NULL,
        #         company_id INTEGER NOT NULL,
        #         description TEXT,
        #         min_mobile_lines INTEGER DEFAULT 0,
        #         min_internet_lines INTEGER DEFAULT 0,
        #         min_iptv_lines INTEGER DEFAULT 0,
        #         max_mobile_lines INTEGER,
        #         max_internet_lines INTEGER,
        #         max_iptv_lines INTEGER,
        #         join_condition TEXT, -- 텍스트 기반의 기타 조건
        #         applicant_scope TEXT,
        #         application_channel TEXT,
        #         url TEXT,
        #         available BOOLEAN,
        #         FOREIGN KEY (company_id) REFERENCES Company(id)
        #     )
        # """)
        cursor.execute(table_sql_map["CombinedProduct"])

        # CombinedProductEligibility 테이블 생성 (동일)
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS CombinedProductEligibility (
        #         combined_product_id VARCHAR(64) NOT NULL,
        #         service_plan_id VARCHAR(64) NOT NULL,
        #         min_lines INTEGER DEFAULT 0,
        #         max_lines INTEGER DEFAULT 1,
        #         is_base_plan_required BOOLEAN DEFAULT FALSE,
        #         PRIMARY KEY (combined_product_id, service_plan_id),
        #         FOREIGN KEY (combined_product_id) REFERENCES CombinedProduct(id),
        #         FOREIGN KEY (service_plan_id) REFERENCES ServicePlan(id)
        #     )
        # """)
        cursor.execute(table_sql_map["CombinedProductEligibility"])

        # Discount 테이블 생성 (업데이트: discount_name, applies_to_line_sequence 추가, condition 제거)
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS Discount (
        #         id VARCHAR(64) PRIMARY KEY,
        #         combined_product_id VARCHAR(64) NOT NULL,
        #         discount_name VARCHAR(128), -- 할인의 구체적인 이름
        #         discount_type VARCHAR(64) NOT NULL, -- 할인 유형 (Amount, Percentage)
        #         discount_value INTEGER NOT NULL, -- 기본 할인 금액 또는 비율
        #         unit VARCHAR(10) NOT NULL, -- 'KRW', '%'
        #         applies_to_service_type VARCHAR(124), -- 적용 서비스 타입 (Mobile, Internet, TV)
        #         applies_to_line_sequence VARCHAR(64), -- 적용 회선 순서 (All, 1st, 2nd_onwards, Nth_line)
        #         note VARCHAR(256), -- 기타 참고사항
        #         FOREIGN KEY (combined_product_id) REFERENCES CombinedProduct(id)
        #     )
        # """)
        cursor.execute(table_sql_map["Discount"])

        # DiscountConditionByPlan 테이블 생성 (요금제별 할인 조건)
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS DiscountConditionByPlan (
        #         discount_id VARCHAR(64) NOT NULL,
        #         service_plan_id VARCHAR(64) NOT NULL,
        #         condition_text VARCHAR(256), -- 요금제 관련 추가 텍스트 조건 (예: "에센스 이상")
        #         override_discount_value INTEGER, -- 특정 요금제 시 할인 값 재정의
        #         override_unit VARCHAR(10), -- 재정의된 단위
        #         PRIMARY KEY (discount_id, service_plan_id),
        #         FOREIGN KEY (discount_id) REFERENCES Discount(id),
        #         FOREIGN KEY (service_plan_id) REFERENCES ServicePlan(id)
        #     )
        # """)
        cursor.execute(table_sql_map["DiscountConditionByPlan"])

        # DiscountConditionByLineCount 테이블 생성 (회선 수별 할인 조건)
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS DiscountConditionByLineCount (
        #         discount_id VARCHAR(64) NOT NULL,
        #         min_applicable_lines INTEGER NOT NULL, -- 할인이 적용되는 최소 회선 번호 (예: 2)
        #         max_applicable_lines INTEGER, -- 할인이 적용되는 최대 회선 번호 (NULL 가능)
        #         override_discount_value INTEGER, -- 특정 회선 수 범위 시 할인 값 재정의
        #         override_unit VARCHAR(10), -- 재정의된 단위
        #         applies_per_line BOOLEAN DEFAULT TRUE, -- 각 회선에 개별 적용 여부 (TRUE/FALSE)
        #         PRIMARY KEY (discount_id, min_applicable_lines),
        #         FOREIGN KEY (discount_id) REFERENCES Discount(id)
        #     )
        # """)
        cursor.execute(table_sql_map["DiscountConditionByLineCount"])

        # Benefits 테이블 생성 (동일)
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS Benefits (
        #         id VARCHAR(64) PRIMARY KEY,
        #         combined_product_id VARCHAR(64) NOT NULL,
        #         benefit_type VARCHAR(64),
        #         content VARCHAR(256),
        #         condition VARCHAR(256),
        #         FOREIGN KEY (combined_product_id) REFERENCES CombinedProduct(id)
        #     )
        # """)
        cursor.execute(table_sql_map["Benefits"])

        conn.commit()
        print(f"데이터베이스 '{db_name}'와 테이블이 성공적으로 생성되었습니다.")

    except sqlite3.Error as e:
        print(f"데이터베이스 오류 발생: {e}")
    finally:
        if conn:
            conn.close()

def create_company_table(db_name="combined_products.db"):
    conn = None
    try:
        conn = sqlite3.connect(db_name)
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
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.commit()
        conn.close()

def reset_selected_tables(table_names: list[str], db_name="combined_products.db", table_sql_map=table_sql_map):
    """
    전달된 테이블 이름 리스트에 해당하는 테이블만 삭제하고 다시 생성합니다.
    주의: 데이터가 완전히 삭제되므로 신중히 사용하세요.
    """
    conn = None
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()

        print("선택한 테이블 삭제 중...")

        # 외래 키 제약 순서 고려 (삭제 순서는 역방향, 생성은 정방향)
        drop_order = [
            "DiscountConditionByLineCount",
            "DiscountConditionByPlan",
            "Discount",
            "CombinedProductEligibility",
            "Benefits",
            "CombinedProduct",
            "ServicePlan",
            "Company"
        ]

        # 삭제
        for table in drop_order:
            if table in table_names:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                print(f"테이블 {table} 삭제 완료.")

        conn.commit()

        print("선택한 테이블 재생성 중...")

        # 다시 생성 (create_combined_product_db 내부의 테이블 생성 순서를 그대로 사용)
        def create_table_if_selected(table_sql_map, table_name):
            if table_name in table_names:
                cursor.execute(table_sql_map[table_name])
                print(f"테이블 {table_name} 재생성 완료.")

        # 생성
        for table in drop_order:
            create_table_if_selected(table_sql_map, table)

        conn.commit()

    except sqlite3.Error as e:
        print(f"테이블 리셋 중 오류 발생: {e}")
    finally:
        if conn:
            conn.close()


# 데이터베이스 생성 함수 호출
if __name__ == "__main__":
    create_combined_product_db()
    create_company_table()
