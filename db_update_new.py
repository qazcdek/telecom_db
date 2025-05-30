import sqlite3
import hashlib
from typing import List, Tuple, Dict, Any

from db_schema_new import create_combined_product_db, create_company_table

def hash_id(text: str) -> str:
    """주어진 텍스트의 SHA256 해시 값을 반환하여 ID로 사용합니다."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

# === UPSERT 함수들 ===

def upsert_combined_product(cursor: sqlite3.Cursor, product_data: Dict[str, Any]):
    """CombinedProduct 테이블에 결합상품 정보를 UPSERT합니다."""
    # product_data 딕셔너리의 키 순서를 CREATE TABLE 문의 필드 순서에 맞춥니다.
    # 예시 데이터와 스키마 필드 불일치를 수정합니다.
    # 기존: join_condition, notice, summary
    # 변경: join_condition, description, min_mobile_lines, min_internet_lines, min_iptv_lines, max_mobile_lines, max_internet_lines, max_iptv_lines
    #       join_condition_text -> join_condition으로 스키마 통일

    cursor.execute("""
        INSERT INTO CombinedProduct (
            id, name, company_id, description, min_mobile_lines, min_internet_lines, min_iptv_lines,
            max_mobile_lines, max_internet_lines, max_iptv_lines, join_condition,
            applicant_scope, application_channel, url, available
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            company_id=excluded.company_id,
            description=excluded.description,
            min_mobile_lines=excluded.min_mobile_lines,
            min_internet_lines=excluded.min_internet_lines,
            min_iptv_lines=excluded.min_iptv_lines,
            max_mobile_lines=excluded.max_mobile_lines,
            max_internet_lines=excluded.max_internet_lines,
            max_iptv_lines=excluded.max_iptv_lines,
            join_condition=excluded.join_condition,
            applicant_scope=excluded.applicant_scope,
            application_channel=excluded.application_channel,
            url=excluded.url,
            available=excluded.available
    """, (
        product_data['id'],
        product_data['name'],
        product_data['company_id'],
        product_data.get('description'), # summary 대신 description 사용
        product_data.get('min_mobile_lines', 0),
        product_data.get('min_internet_lines', 0),
        product_data.get('min_iptv_lines', 0),
        product_data.get('max_mobile_lines'),
        product_data.get('max_internet_lines'),
        product_data.get('max_iptv_lines'),
        product_data.get('join_condition'), # join_condition_text 대신 join_condition 사용
        product_data.get('applicant_scope'),
        product_data.get('application_channel'),
        product_data.get('url'),
        product_data.get('available')
    ))

def upsert_service_plan(cursor: sqlite3.Cursor, company_id: int, service_type: str, name: str, fee: int) -> str:
    """ServicePlan 테이블에 요금제 정보를 UPSERT하고, 해당 ID를 반환합니다."""
    plan_id = hash_id(f"{company_id}-{service_type}-{name}")
    cursor.execute("""
        INSERT INTO ServicePlan (id, company_id, name, service_type, fee)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            service_type=excluded.service_type,
            fee=excluded.fee
    """, (plan_id, company_id, name, service_type, fee))
    return plan_id

def link_combined_product_eligibility(cursor: sqlite3.Cursor, combined_product_id: str,
                                      service_plan_id: str, min_lines: int = 0,
                                      max_lines: int = 1, is_base_plan_required: bool = False):
    """CombinedProductEligibility 테이블에 결합상품-요금제 자격 정보를 UPSERT합니다."""
    cursor.execute("""
        INSERT INTO CombinedProductEligibility (
            combined_product_id, service_plan_id, min_lines, max_lines, is_base_plan_required
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(combined_product_id, service_plan_id) DO UPDATE SET
            min_lines=excluded.min_lines,
            max_lines=excluded.max_lines,
            is_base_plan_required=excluded.is_base_plan_required
    """, (combined_product_id, service_plan_id, min_lines, max_lines, is_base_plan_required))

def upsert_discount(cursor: sqlite3.Cursor, discount_data: Dict[str, Any]) -> str:
    """Discount 테이블에 할인 정보를 UPSERT하고, 해당 ID를 반환합니다."""
    discount_id = discount_data['id']
    cursor.execute("""
        INSERT INTO Discount (
            id, combined_product_id, discount_name, discount_type,
            discount_value, unit, applies_to_service_type, applies_to_line_sequence, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            combined_product_id=excluded.combined_product_id,
            discount_name=excluded.discount_name,
            discount_type=excluded.discount_type,
            discount_value=excluded.discount_value,
            unit=excluded.unit,
            applies_to_service_type=excluded.applies_to_service_type,
            applies_to_line_sequence=excluded.applies_to_line_sequence,
            note=excluded.note
    """, (
        discount_id,
        discount_data['combined_product_id'],
        discount_data.get('discount_name'),
        discount_data['discount_type'],
        discount_data['discount_value'],
        discount_data['unit'],
        discount_data.get('applies_to_service_type'),
        discount_data.get('applies_to_line_sequence'),
        discount_data.get('note')
    ))
    return discount_id

def upsert_discount_condition_by_plan(cursor: sqlite3.Cursor, discount_id: str, service_plan_id: str,
                                       condition_text: str = None, override_discount_value: int = None,
                                       override_unit: str = None):
    """DiscountConditionByPlan 테이블에 요금제별 할인 조건을 UPSERT합니다."""
    cursor.execute("""
        INSERT INTO DiscountConditionByPlan (
            discount_id, service_plan_id, condition_text, override_discount_value, override_unit
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(discount_id, service_plan_id) DO UPDATE SET
            condition_text=excluded.condition_text,
            override_discount_value=excluded.override_discount_value,
            override_unit=excluded.override_unit
    """, (discount_id, service_plan_id, condition_text, override_discount_value, override_unit))

def upsert_discount_condition_by_line_count(cursor: sqlite3.Cursor, discount_id: str, min_applicable_lines: int,
                                            max_applicable_lines: int = None, override_discount_value: int = None,
                                            override_unit: str = None, applies_per_line: bool = True):
    """DiscountConditionByLineCount 테이블에 회선 수별 할인 조건을 UPSERT합니다."""
    cursor.execute("""
        INSERT INTO DiscountConditionByLineCount (
            discount_id, min_applicable_lines, max_applicable_lines,
            override_discount_value, override_unit, applies_per_line
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(discount_id, min_applicable_lines) DO UPDATE SET
            max_applicable_lines=excluded.max_applicable_lines,
            override_discount_value=excluded.override_discount_value,
            override_unit=excluded.override_unit,
            applies_per_line=excluded.applies_per_line
    """, (discount_id, min_applicable_lines, max_applicable_lines,
          override_discount_value, override_unit, applies_per_line))

def upsert_benefit(cursor: sqlite3.Cursor, combined_product_id: str, benefit_data: Dict[str, Any]):
    """Benefits 테이블에 혜택 정보를 UPSERT합니다."""
    benefit_id = benefit_data['id']
    cursor.execute("""
        INSERT INTO Benefits (
            id, combined_product_id, benefit_type, content, condition
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            combined_product_id=excluded.combined_product_id,
            benefit_type=excluded.benefit_type,
            content=excluded.content,
            condition=excluded.condition
    """, (
        benefit_id,
        combined_product_id,
        benefit_data.get('benefit_type'),
        benefit_data['content'],
        benefit_data.get('condition')
    ))

# === 예시 데이터 및 실행 ===

def insert_example_data_v2(db_name="combined_products_final.db", **kwargs):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM Company WHERE name = ?", (company_name,))
    company_id = cursor.fetchone()[0]

    product_id = None
    if 'combined_product_data' in kwargs:
        product_data = kwargs['combined_product_data']
        if 'company_id' not in product_data and company_id:
            product_data['company_id'] = company_id
        elif 'company_id' not in product_data:
            print("Error: combined_product_data provided but no company_id or default company could be determined.")
            conn.close()
            return
        
        product_id = product_data['id'] # combined_product_data가 있으면 id는 필수로 가정
        upsert_combined_product(cursor, product_data)
        print(f"CombinedProduct '{product_data['name']}' updated/inserted.")

    service_plan_map = {}
    if 'service_plan_definitions' in kwargs and company_id:
        for service_type, name, fee in kwargs['service_plan_definitions']:
            plan_id = upsert_service_plan(cursor, company_id, service_type, name, fee)
            service_plan_map[name] = plan_id
        print("ServicePlan data updated/inserted.")
    elif 'service_plan_definitions' in kwargs and not company_id:
         print("Error: service_plan_definitions provided but no company_id or default company could be determined.")


    if 'eligibility_data' in kwargs and product_id:
        # 기존 service_plan_map에 있는 요금제 ID를 활용
        # 만약 eligibility_data만 주어지고 service_plan_definitions는 주어지지 않았다면
        # 기존 DB에서 요금제 ID를 조회해야 함.
        # 여기서는 예시를 위해 service_plan_map을 먼저 채우는 흐름으로 가정
        
        # 만약 service_plan_map이 비어있다면, DB에서 요금제 정보를 로드
        if not service_plan_map:
            cursor.execute("SELECT name, id FROM ServicePlan WHERE company_id = ?", (company_id,))
            for name, plan_id in cursor.fetchall():
                service_plan_map[name] = plan_id

        for entry in kwargs['eligibility_data']:
            plan_name = entry['plan_name']
            if plan_name in service_plan_map:
                link_combined_product_eligibility(
                    cursor, product_id, service_plan_map[plan_name],
                    entry.get('min_lines', 0), entry.get('max_lines', 1), entry.get('is_base_plan_required', False)
                )
            else:
                print(f"Warning: Service plan '{plan_name}' not found for eligibility linking. Skipping.")
        print("CombinedProductEligibility data updated/inserted.")

    if 'discount_data' in kwargs and product_id:
        discount_data = kwargs['discount_data']
        if 'combined_product_id' not in discount_data:
            discount_data['combined_product_id'] = product_id
        upsert_discount(cursor, discount_data)
        discount_id = discount_data['id']
        print(f"Discount '{discount_data.get('discount_name')}' updated/inserted.")

        if 'discount_conditions_by_plan' in kwargs:
            # 만약 service_plan_map이 비어있다면, DB에서 요금제 정보를 로드
            if not service_plan_map:
                cursor.execute("SELECT name, id FROM ServicePlan WHERE company_id = ?", (company_id,))
                for name, plan_id in cursor.fetchall():
                    service_plan_map[name] = plan_id

            for entry in kwargs['discount_conditions_by_plan']:
                plan_name = entry['plan_name']
                if plan_name in service_plan_map:
                    upsert_discount_condition_by_plan(
                        cursor, discount_id, service_plan_map[plan_name],
                        condition_text=entry.get('condition_text'),
                        override_discount_value=entry.get('override_value'),
                        override_unit=entry.get('override_unit')
                    )
                else:
                    print(f"Warning: Service plan '{plan_name}' not found for discount condition by plan. Skipping.")
            print("DiscountConditionByPlan data updated/inserted.")

        if 'discount_conditions_by_line_count' in kwargs:
            upsert_discount_condition_by_line_count(
                cursor, discount_id,
                min_applicable_lines=kwargs['discount_conditions_by_line_count']['min_applicable_lines'],
                max_applicable_lines=kwargs['discount_conditions_by_line_count'].get('max_applicable_lines'),
                override_discount_value=kwargs['discount_conditions_by_line_count'].get('override_discount_value'),
                override_unit=kwargs['discount_conditions_by_line_count'].get('override_unit'),
                applies_per_line=kwargs['discount_conditions_by_line_count'].get('applies_per_line', True)
            )
            print("DiscountConditionByLineCount data updated/inserted.")

    if 'benefits_data' in kwargs and product_id:
        for benefit in kwargs['benefits_data']:
            upsert_benefit(cursor, product_id, benefit)
        print("Benefits data updated/inserted.")

    conn.commit()
    conn.close()
    print("데이터 업데이트/삽입 완료.")

# 데이터베이스 스키마 생성 및 예시 데이터 삽입 실행
if __name__ == "__main__":
    # 데이터베이스 스키마 생성
    db_name = "combined_products_final.db"
    create_combined_product_db("combined_products_final.db")
    create_company_table("combined_products_final.db")

    # 1. '따로 살아도 가족결합' 전체 데이터 삽입/업데이트 예시
    company_name = "kt"
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Company WHERE name = ?", (company_name,))
    company_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()

    combined_product_name = "따로 살아도 가족결합"
    product_id = hash_id(f"{company_name}_{combined_product_name}")
    
    # KT '따로 살아도 가족결합' PDF 기반 데이터 정의
    family_combined_product_data = {
        "id": product_id,
        "name": combined_product_name,
        "company_id": company_id, # 함수 내에서 company_id를 찾아 채워줄 예정
        "description": "따로 사는 가족끼리 뭉치면, 더 커지는 할인 혜택으로 인터넷/TV 2번째 회선 부터는 기존 결합 할인 이외 추가 할인 받을 수 있어요!",
        "min_mobile_lines": 1, # "인터넷 및 모바일 각각 1회선 이상 결합 필수" [cite: 64]
        "min_internet_lines": 1, # "인터넷 및 모바일 각각 1회선 이상 결합 필수" [cite: 64]
        "min_iptv_lines": 0,
        "max_mobile_lines": 10, # "무선 최대 10회선" [cite: 45]
        "max_internet_lines": 5, # "인터넷/TV 최대 5회선" [cite: 45]
        "max_iptv_lines": 5, # "인터넷/TV 최대 5회선" [cite: 45]
        "join_condition": """인터넷 및 모바일 각각 1회선 이상 결합 필수.
                            결합 내 인터넷 회선 중 한 회선을 '베이스 인터넷'으로 지정 필요.
                            '베이스 인터넷' 및 해당 회선에 연결된 IPTV 외 인터넷/IPTV 추가 결합은 신규 가입 시점(개통완료일 기준)부터 익월 말까지 가능.
                            법인사업자 등 일부 유형은 모바일 최대 7회선.""",
        "applicant_scope": "본인, 배우자, 본인 및 배우자의 직계 존비속/형제자매, 직계비속의 배우자(며느리/사위)",
        "application_channel": "전화상담 신청",
        "url": "https://product.kt.com/wDic/productDetail.do?ItemCode=1630",
        "available": True
    }
    
    family_service_plan_definitions = [
        # 모바일 (예시 요금제 - PDF에 구체적인 요금제 명시 안됨, 요고뭉치 PDF에서 요고30 참조)
        ("Mobile", "요고30", 30000), 
        ("Mobile", "5G 심플", 61000), # [cite: 66]
        ("Mobile", "5G 초이스", 90000), # [cite: 66]
        # 인터넷 (따로 살아도 가족결합 PDF에 언급된 이름과 매칭)
        ("Internet", "인터넷 에센스", 55000), # [cite: 4] (요고뭉치 PDF에 명시된 무약정 요금 사용)
        ("Internet", "인터넷 베이직", 46200), # [cite: 4]
        ("Internet", "인터넷 슬림", 39600), # [cite: 4]
        ("Internet", "인터넷 에센스 와이파이", 63800), # [cite: 7]
        ("Internet", "인터넷 베이직 와이파이", 55000), # [cite: 7]
        ("Internet", "인터넷 슬림 와이파이", 48400), # [cite: 7]
        # TV (따로 살아도 가족결합 PDF에 언급된 이름과 매칭)
        ("TV", "지니 TV VOD 초이스", 31020), # [cite: 7]
        ("TV", "지니 TV 에센스", 25300), # [cite: 7]
        ("TV", "지니 TV 베이직", 18150), # [cite: 7]
    ]

    family_eligibility_data = [
        # 인터넷 (베이스 인터넷 지정 필수)
        {"plan_name": "인터넷 에센스", "min_lines": 0, "max_lines": 5, "is_base_plan_required": True},
        {"plan_name": "인터넷 베이직", "min_lines": 0, "max_lines": 5, "is_base_plan_required": False},
        {"plan_name": "인터넷 슬림", "min_lines": 0, "max_lines": 5, "is_base_plan_required": False},
        {"plan_name": "인터넷 에센스 와이파이", "min_lines": 0, "max_lines": 5, "is_base_plan_required": True},
        {"plan_name": "인터넷 베이직 와이파이", "min_lines": 0, "max_lines": 5, "is_base_plan_required": False},
        {"plan_name": "인터넷 슬림 와이파이", "min_lines": 0, "max_lines": 5, "is_base_plan_required": False},
        # 모바일 (최대 10회선)
        {"plan_name": "요고30", "min_lines": 0, "max_lines": 10, "is_base_plan_required": False},
        {"plan_name": "5G 심플", "min_lines": 0, "max_lines": 10, "is_base_plan_required": False},
        {"plan_name": "5G 초이스", "min_lines": 0, "max_lines": 10, "is_base_plan_required": False},
        # TV (최대 5회선)
        {"plan_name": "지니 TV VOD 초이스", "min_lines": 0, "max_lines": 5, "is_base_plan_required": False},
        {"plan_name": "지니 TV 에센스", "min_lines": 0, "max_lines": 5, "is_base_plan_required": False},
        {"plan_name": "지니 TV 베이직", "min_lines": 0, "max_lines": 5, "is_base_plan_required": False},
    ]

    discount_name = "인터넷/TV 2번째 회선부터 추가 할인"
    discount_additional_internet_tv_lines_id = hash_id(f"{product_id}-{discount_name}")
    family_discount_data = {
        "id": discount_additional_internet_tv_lines_id,
        "combined_product_id": product_id,
        "discount_name": discount_name,
        "discount_type": "Amount",
        "discount_value": 0, # 기본값 (요금제별/회선수별로 오버라이드될 예정)
        "unit": "KRW",
        "applies_to_service_type": "Internet,TV",
        "applies_to_line_sequence": "2nd_onwards", # 2번째 회선부터 [cite: 52]
        "note": "인터넷/TV 2번째 회선부터 신규 고객 대상 추가 할인 적용. 베이스 인터넷 및 해당 회선에 연결된 IPTV 외 추가 결합된 인터넷/TV 대상 3년 약정 시 제공."
    }

    family_discount_by_plan_conditions = [
        {"plan_name": "인터넷 베이직", "condition_text": None, "override_value": 2200, "override_unit": "KRW"}, # [cite: 52]
        {"plan_name": "인터넷 베이직 와이파이", "condition_text": None, "override_value": 2200, "override_unit": "KRW"}, # PDF에 와이파이 버전 명시 없으므로 베이직과 동일하게 가정
        {"plan_name": "인터넷 에센스", "condition_text": "에센스 이상", "override_value": 3300, "override_unit": "KRW"}, # [cite: 52]
        {"plan_name": "인터넷 에센스 와이파이", "condition_text": "에센스 이상", "override_value": 3300, "override_unit": "KRW"},
        {"plan_name": "인터넷 슬림", "condition_text": None, "override_value": 0, "override_unit": "KRW"}, # PDF에 명시된 추가 할인이 없음
        {"plan_name": "인터넷 슬림 와이파이", "condition_text": None, "override_value": 0, "override_unit": "KRW"}, # PDF에 명시된 추가 할인이 없음
        {"plan_name": "지니 TV VOD 초이스", "condition_text": "슬림 이상", "override_value": 2200, "override_unit": "KRW"}, # [cite: 52]
        {"plan_name": "지니 TV 에센스", "condition_text": "슬림 이상", "override_value": 2200, "override_unit": "KRW"},
        {"plan_name": "지니 TV 베이직", "condition_text": "슬림 이상", "override_value": 2200, "override_unit": "KRW"}, # [cite: 52]
    ]

    family_discount_by_line_count_condition = {
        "min_applicable_lines": 2, # 2번째 회선부터 [cite: 52]
        "max_applicable_lines": None, # 제한 없음 (최대 5회선까지 가능하므로 논리적으로 5회선까지 적용) [cite: 45]
        "applies_per_line": True, # 각 회선에 적용
        "override_discount_value": None, # 요금제별로 오버라이드되므로 여기서는 None
        "override_unit": None
    }

    family_benefits_data = [
        {"id": hash_id(f"{product_id}-benefit-1"), "benefit_type": "Discount", "content": "가구당 최대 19,140원 할인", "condition": "인터넷 에센스, TV 베이직 결합 기준"},
        {"id": hash_id(f"{product_id}-benefit-2"), "benefit_type": "LineFlexibility", "content": "모바일 최대 10회선, 인터넷/TV 최대 5회선 결합 가능", "condition": None},
        {"id": hash_id(f"{product_id}-benefit-3"), "benefit_type": "Eligibility", "content": "본인, 배우자, 직계 존비속/형제자매, 직계비속의 배우자(며느리/사위) 결합 가능", "condition": None},
        {"id": hash_id(f"{product_id}-benefit-4"), "benefit_type": "Flexibility", "content": "따로 사는 가족끼리 뭉칠 수 있음", "condition": None},
        {"id": hash_id(f"{product_id}-benefit-5"), "benefit_type": "AdditionalDiscount", "content": "인터넷+TV 최대 5,500원 추가 할인", "condition": "추가 결합 시, 인터넷 에센스+TV 슬림 이상, 3년 약정 신규 가입시"},
    ]


    print("\n--- '따로 살아도 가족결합' 전체 데이터 업데이트 ---")
    insert_example_data_v2(
        company_data={"name": company_name},
        combined_product_data=family_combined_product_data,
        service_plan_definitions=family_service_plan_definitions,
        eligibility_data=family_eligibility_data,
        discount_data=family_discount_data,
        discount_conditions_by_plan=family_discount_by_plan_conditions,
        discount_conditions_by_line_count=family_discount_by_line_count_condition,
        benefits_data=family_benefits_data
    )

    # 2. '요고뭉치 결합' 데이터 추가/업데이트 예시
    combined_product_name_yogo = "요고뭉치 결합"
    product_id_yogo = hash_id(f"{company_name}_{combined_product_name_yogo}")

    yogo_mungchi_combined_product_data = {
        "id": product_id_yogo,
        "name": combined_product_name_yogo,
        "company_id": company_id, # 함수 내에서 company_id를 찾아 채워줄 예정
        "description": "핸드폰은 요고로 하고 인터넷/TV도 뭉치면 약정 걱정 없이 통신비 최대 32% 할인! [cite: 3]",
        "min_mobile_lines": 1, # "모바일과 인터넷은 필수상품으로 결합 내 모두 포함되어 있어야 합니다." [cite: 13]
        "min_internet_lines": 1, # "모바일과 인터넷은 필수상품으로 결합 내 모두 포함되어 있어야 합니다." [cite: 13]
        "min_iptv_lines": 0, # IPTV는 선택 상품 [cite: 12]
        "max_mobile_lines": None, # 명시된 최대 회선 없음 (요고뭉치에는 다회선 개념이 명시되지 않음)
        "max_internet_lines": 1, # "1회선" 명시 [cite: 12]
        "max_iptv_lines": 1, # TV의 경우 "인터넷 1회선당 최대 1회선의 TV까지 결합 가능" [cite: 64] (따로살아도 가족결합 PDF 참조)
        "join_condition": """5G/LTE 다이렉트 또는 요고 요금제를 가입한 모바일 고객이 가입조건을 만족하는 인터넷 또는 인터넷과 IPTV를 결합. [cite: 9]
                            KT 공식 온라인 채널(KT SHOP)을 통해 가입하여 약정 혜택을 받고 있지 않아야 가입 가능. [cite: 12]
                            STB은 Genie TV STB 3 또는 Genie TV STB A이어야 함. [cite: 12]
                            모바일, 인터넷, IPTV 모두 동일 명의이어야 합니다. [cite: 13]
                            모바일과 인터넷은 필수상품으로 결합 내 모두 포함되어 있어야 합니다. [cite: 13]
                            함께 결합된 모바일에는 결합할인이 제공되지 않습니다. [cite: 11]
                            (정지 기간 동안 결합할인은 미제공되며, 결합 필수 상품인 모바일 또는 인터넷 정지 시 결합한 상품 모두 할인 미제공됩니다.) [cite: 10]""",
        "applicant_scope": "신규 및 기존 고객 (무약정 온라인 가입고객) [cite: 2]",
        "application_channel": "전화상담 신청 [cite: 2, 6, 16]",
        "url": "https://product.kt.com/wDic/productDetail.do?ItemCode=1630", # 요고뭉치 URL은 PDF에 명시되지 않음
        "available": True
    }

    # 요고뭉치에 특화된 요금제. 이미 '따로 살아도 가족결합'에서 넣은 요금제와 겹칠 수 있으나,
    # upsert_service_plan 함수가 ON CONFLICT DO UPDATE SET을 사용하여 중복을 처리함
    yogo_mungchi_service_plan_definitions = [
        ("Mobile", "요고30", 43000),
        ("Internet", "인터넷 에센스", 55000), # [cite: 4]
        ("Internet", "인터넷 베이직", 46200), # [cite: 4]
        ("Internet", "인터넷 슬림", 39600), # [cite: 4]
        ("Internet", "인터넷 베이직 와이파이", 55000), # [cite: 7]
        ("Internet", "인터넷 슬림 와이파이", 48400), # [cite: 7]
        ("TV", "지니 TV VOD 초이스", 31020), # [cite: 7]
        ("TV", "지니 TV 에센스", 25300), # [cite: 7]
        ("TV", "지니 TV 베이직", 18150), # [cite: 7]
    ]

    yogo_mungchi_eligibility_data = [
        {"plan_name": "요고30", "min_lines": 1, "max_lines": 1, "is_base_plan_required": False}, # 모바일 1회선 필수 [cite: 12]
        {"plan_name": "인터넷 에센스", "min_lines": 1, "max_lines": 1, "is_base_plan_required": False}, # 인터넷 1회선 필수 [cite: 12]
        {"plan_name": "인터넷 베이직", "min_lines": 1, "max_lines": 1, "is_base_plan_required": False}, # 인터넷 1회선 필수 [cite: 12]
        {"plan_name": "인터넷 슬림", "min_lines": 1, "max_lines": 1, "is_base_plan_required": False}, # 인터넷 1회선 필수 [cite: 12]
        {"plan_name": "인터넷 베이직 와이파이", "min_lines": 1, "max_lines": 1, "is_base_plan_required": False}, # 인터넷 1회선 필수 [cite: 12]
        {"plan_name": "인터넷 슬림 와이파이", "min_lines": 1, "max_lines": 1, "is_base_plan_required": False}, # 인터넷 1회선 필수 [cite: 12]
        {"plan_name": "지니 TV VOD 초이스", "min_lines": 0, "max_lines": 1, "is_base_plan_required": False}, # IPTV는 선택 [cite: 12]
        {"plan_name": "지니 TV 에센스", "min_lines": 0, "max_lines": 1, "is_base_plan_required": False}, # IPTV는 선택 [cite: 12]
        {"plan_name": "지니 TV 베이직", "min_lines": 0, "max_lines": 1, "is_base_plan_required": False}, # IPTV는 선택 [cite: 12]
    ]

    discount_yogo_mungchi_id = hash_id(f"{product_id_yogo}-yogo_mungchi_discount")
    yogo_mungchi_discount_data = {
        "id": discount_yogo_mungchi_id,
        "combined_product_id": product_id_yogo,
        "discount_name": "요고뭉치 결합할인",
        "discount_type": "Amount",
        "discount_value": 0, # 요금제별로 다름
        "unit": "KRW",
        "applies_to_service_type": "Internet,TV", # 모바일은 할인 미제공 [cite: 11]
        "applies_to_line_sequence": "1st_line", # 1회선에 대한 할인
        "note": "약정 걱정 없이 통신비 최대 32% 할인 (일반 무약정 요금 대비) [cite: 3]"
    }

    yogo_mungchi_discount_by_plan_conditions = [
        {"plan_name": "인터넷 에센스", "override_value": 22000, "override_unit": "KRW"}, # [cite: 4]
        {"plan_name": "인터넷 베이직", "override_value": 18700, "override_unit": "KRW"}, # [cite: 4]
        {"plan_name": "인터넷 슬림", "override_value": 17500, "override_unit": "KRW"}, # [cite: 4]
        {"plan_name": "인터넷 베이직 와이파이", "override_value": 26400, "override_unit": "KRW"}, # [cite: 7]
        {"plan_name": "인터넷 슬림 와이파이", "override_value": 25300, "override_unit": "KRW"}, # [cite: 7]
        {"plan_name": "지니 TV VOD 초이스", "override_value": 10120, "override_unit": "KRW"}, # [cite: 7]
        {"plan_name": "지니 TV 에센스", "override_value": 8800, "override_unit": "KRW"}, # [cite: 7]
        {"plan_name": "지니 TV 베이직", "override_value": 6050, "override_unit": "KRW"}, # [cite: 7]
    ]

    yogo_mungchi_benefits_data = [
        {"id": hash_id(f"{product_id_yogo}-benefit-1"), "benefit_type": "Discount", "content": "약정 없이 최대 32% 할인 (일반 무약정 요금 대비) [cite: 2]", "condition": None},
        {"id": hash_id(f"{product_id_yogo}-benefit-2"), "benefit_type": "Eligibility", "content": "신규 및 기존고객 결합 가능 (무약정 온라인 가입고객) [cite: 2]", "condition": None},
        {"id": hash_id(f"{product_id_yogo}-benefit-3"), "benefit_type": "Service", "content": "GIGA WIFI home 제공 (GIGA WIFI home 제공 기준 요금) [cite: 8]", "condition": None},
    ]

    print("\n--- '요고뭉치 결합' 전체 데이터 업데이트 ---")
    insert_example_data_v2(
        company_data={"name": company_name},
        combined_product_data=yogo_mungchi_combined_product_data,
        service_plan_definitions=yogo_mungchi_service_plan_definitions,
        eligibility_data=yogo_mungchi_eligibility_data,
        discount_data=yogo_mungchi_discount_data,
        discount_conditions_by_plan=yogo_mungchi_discount_by_plan_conditions,
        benefits_data=yogo_mungchi_benefits_data
    )

    # 3. 특정 요금제만 업데이트하는 예시 (ServicePlan 테이블만)
    # 기존 KT 요금제 중 '인터넷 슬림'의 요금을 변경한다고 가정
    # print("\n--- '인터넷 슬림' 요금제만 업데이트하는 예시 ---")
    # insert_example_data_v2(
    #     company_data={"name": company_name},
    #     service_plan_definitions=[
    #         ("Internet", "인터넷 슬림", 40000) # 기존 39600에서 40000으로 변경 [cite: 4]
    #     ]
    # )
