import sqlite3
import hashlib
from typing import List, Tuple

def hash_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# === UPSERT 함수들 ===

def upsert_combined_product(cursor, product: dict):
    cursor.execute("""
        INSERT INTO CombinedProduct (
            id, name, company_id, join_condition, notice,
            applicant_scope, application_channel, url, summary, available
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            company_id=excluded.company_id,
            join_condition=excluded.join_condition,
            notice=excluded.notice,
            applicant_scope=excluded.applicant_scope,
            application_channel=excluded.application_channel,
            url=excluded.url,
            summary=excluded.summary,
            available=excluded.available
    """, tuple(product.values()))

def upsert_service_plans(cursor, company_id: int, plans: List[Tuple[str, str, int]]) -> List[str]:
    plan_ids = []
    for service_type, name, fee in plans:
        plan_id = hash_id(f"{service_type}-{name}")
        plan_ids.append((plan_id, service_type, name))
        cursor.execute("""
            INSERT INTO ServicePlan (id, company_id, name, service_type, fee)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                fee=excluded.fee
        """, (plan_id, company_id, name, service_type, fee))
    return plan_ids

def link_combined_product_service_plans(cursor, combined_product_id: str, plan_ids: List[str]):
    for plan_id, _, _ in plan_ids:
        cursor.execute("""
            INSERT OR IGNORE INTO CombinedProductServicePlan (combined_product_id, service_plan_id)
            VALUES (?, ?)
        """, (combined_product_id, plan_id))

def insert_discounts(cursor, combined_product_id: str, company_id: int, discount_data: List[Tuple[str, str, int]]):
    for service_type, plan_name, discount_value in discount_data:
        plan_id = hash_id(f"{service_type}-{plan_name}")
        discount_id = hash_id(f"{combined_product_id}-{plan_name}")
        cursor.execute("""
            INSERT INTO Discount (
                id, combined_product_id, company_id,
                plan_id, discount_type, discount_value, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                discount_value=excluded.discount_value,
                note=excluded.note
        """, (
            discount_id, combined_product_id, company_id,
            plan_id, "amount", discount_value, f"{plan_name} 요금제의 요고뭉치 결합 할인"
        ))

def insert_benefits(cursor, combined_product_id: str, benefits: List[str]):
    cursor.execute("SELECT id FROM Discount WHERE combined_product_id = ? LIMIT 1", (combined_product_id,))
    row = cursor.fetchone()
    if not row:
        return
    first_discount_id = row[0]
    for content in benefits:
        benefit_id = hash_id(f"{combined_product_id}-{content}")
        cursor.execute("""
            INSERT OR IGNORE INTO Benefits (id, discount_id, content)
            VALUES (?, ?, ?)
        """, (benefit_id, first_discount_id, content))

# === 예시 데이터 및 실행 ===

def insert_example_data():
    conn = sqlite3.connect("combined_products.db")
    cursor = conn.cursor()

    ## 문서를 보고 수집할 데이터 목록
    # 통신사 이름([skt, kt, lguplus] 중 하나, 아예 다른 회사면 others)
    company_name = "kt"
    cursor.execute("SELECT id FROM Company WHERE name = ?", (company_name,))
    company_id = cursor.fetchone()[0]

    # 결합상품 이름
    combined_product_name = "요고뭉치 결합"
    product_id = hash_id(f"{company_name}_{combined_product_name}")

    # 가입 조건
    join_condition = "5G/LTE 요고 요금제 + 인터넷 필수, IPTV 선택 가능. 동일 명의 필요"
    # 유의사항 등
    notice = """모바일, 인터넷, IPTV 모두 동일 명의이어야 합니다.
모바일과 인터넷은 필수상품으로 결합 내 모두 포함되어 있어야 합니다.
일부 상품 해지/대상 외 요금제로 변경/약정 혜택 적용 등 상기 조건 미충족 상태로 변경 시 결합은 해지됩니다.
(결합 해지 시 이용 중인 상품은 더 이상 결합할인이 제공되지 않아 무약정 요금이 적용됩니다)"""
    # 신청인 범위
    applicant_scope = "신규 및 기존 고객"
    # 가입 채널
    application_channel = "KT닷컴(KT SHOP) 온라인 전용"
    # 상품 상세 페이지 url: 잘 모르면 빈 문자열("")
    detail_url = "https://product.kt.com/wDic/productDetail.do?ItemCode=1571&CateCode=6027&filter_code=114&option_code=166&pageSize=10"
    # 상품 설명 또는 캐치프레이즈 또는 간략한 설명
    summary = "약정 없이 최대 32% 할인! KT 요고 요금제와 인터넷/TV 결합 상품"

    ############################################

    product_data = {
        "id": product_id,
        "name": combined_product_name,
        "company_id": company_id,
        "join_condition": join_condition,
        "notice": notice,
        "applicant_scope": applicant_scope,
        "application_channel": application_channel,
        "url": detail_url,
        "summary": summary,
        "available": True
    }

    service_plans = [
        ("mobile", "요고30", 43000),
        ("internet", "인터넷 에센스", 33000),
        ("internet", "인터넷 베이직", 27500),
        ("internet", "인터넷 슬림", 22000),
        ("internet", "인터넷 에센스 와이파이", 33000),
        ("internet", "인터넷 베이직 와이파이", 28600),
        ("internet", "인터넷 슬림 와이파이", 23100),
        ("iptv", "지니 TV VOD 초이스", 20900),
        ("iptv", "지니 TV 에센스", 16500),
        ("iptv", "지니 TV 베이직", 12100),
    ]

    discounts = [
        ("internet", "인터넷 에센스", 11000),
        ("internet", "인터넷 베이직", 8800),
        ("internet", "인터넷 슬림", 6600),
        ("internet", "인터넷 에센스 와이파이", 11000),
        ("internet", "인터넷 베이직 와이파이", 8800),
        ("internet", "인터넷 슬림 와이파이", 7700),
        ("iptv", "지니 TV VOD 초이스", 10120),
        ("iptv", "지니 TV 에센스", 8800),
        ("iptv", "지니 TV 베이직", 6050),
    ]

    benefits = [
        "약정 없이 최대 32% 할인",
        "모바일 + 인터넷 필수, IPTV 선택 가능",
        "모든 서비스는 동일 명의 필요",
        "신규 및 기존 고객 모두 신청 가능",
    ]

    upsert_combined_product(cursor, product_data)
    plan_ids = upsert_service_plans(cursor, company_id, service_plans)
    link_combined_product_service_plans(cursor, product_id, plan_ids)
    insert_discounts(cursor, product_id, company_id, discounts)
    insert_benefits(cursor, product_id, benefits)

    conn.commit()
    conn.close()

insert_example_data()
