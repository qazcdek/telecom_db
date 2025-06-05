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
    # 변경: join_condition, description, max_mobile_lines, max_internet_lines, max_iptv_lines
    #       join_condition_text -> join_condition으로 스키마 통일
    # 변경2: min_mobile_lines, min_internet_lines, min_iptv_lines 삭제

    cursor.execute("""
        INSERT INTO CombinedProduct (
            id, name, company_id, description,
            max_mobile_lines, max_internet_lines, max_iptv_lines, join_condition,
            applicant_scope, application_channel, url, available
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            company_id=excluded.company_id,
            description=excluded.description,
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
    plan_id = hash_id(f"{company_id}_{service_type}_{name}")
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
                                      max_lines: int = 1, base_role: str = ""):
    """CombinedProductEligibility 테이블에 결합상품-요금제 자격 정보를 UPSERT합니다."""
    cursor.execute("""
        INSERT INTO CombinedProductEligibility (
            combined_product_id, service_plan_id, min_lines, max_lines, base_role
        ) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(combined_product_id, service_plan_id) DO UPDATE SET
            min_lines=excluded.min_lines,
            max_lines=excluded.max_lines,
            base_role=excluded.base_role
    """, (combined_product_id, service_plan_id, min_lines, max_lines, base_role))

def upsert_required_base_roles(cursor, combined_product_id: str, base_role_requirements: Dict[str, int]):
    """
    RequiredBaseRole 테이블을 업데이트합니다.
    
    Parameters:
    - cursor: SQLite cursor
    - combined_product_id: 결합 상품 ID
    - base_role_requirements: {"role명": 최소개수} 형태의 딕셔너리
    """
    for base_role, required_count in base_role_requirements.items():
        cursor.execute("""
            INSERT INTO RequiredBaseRole (combined_product_id, base_role, required_count)
            VALUES (?, ?, ?)
            ON CONFLICT(combined_product_id, base_role) DO UPDATE SET
                required_count = excluded.required_count
        """, (combined_product_id, base_role, required_count))
    print("RequiredBaseRole data updated/inserted.")

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
                                      base_role: str = "", condition_text: str = None, 
                                      override_discount_value: int = None, override_unit: str = None):
    """DiscountConditionByPlan 테이블에 요금제별 할인 조건을 UPSERT합니다."""
    cursor.execute("""
        INSERT INTO DiscountConditionByPlan (
            discount_id, service_plan_id, base_role, condition_text, override_discount_value, override_unit
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(discount_id, service_plan_id, base_role) DO UPDATE SET -- ON CONFLICT 조건에 base_role 추가
            condition_text=excluded.condition_text,
            override_discount_value=excluded.override_discount_value,
            override_unit=excluded.override_unit
    """, (discount_id, service_plan_id, base_role, condition_text, override_discount_value, override_unit))

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

def insert_example_data_v2(db_name="combined_products.db", **kwargs):
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
        if not service_plan_map:
            cursor.execute("SELECT name, id FROM ServicePlan WHERE company_id = ?", (company_id,))
            for name, plan_id in cursor.fetchall():
                service_plan_map[name] = plan_id

        for entry in kwargs['eligibility_data']:
            plan_name = entry['plan_name']
            plan_id = service_plan_map.get(plan_name)

            # service_plan_map에 없으면 DB에서 직접 조회 시도
            if not plan_id:
                cursor.execute("SELECT id FROM ServicePlan WHERE name = ? AND company_id = ?", (plan_name, company_id))
                result = cursor.fetchone()
                if result:
                    plan_id = result[0]
                    service_plan_map[plan_name] = plan_id  # 캐시에 저장
                else:
                    print(f"Warning: Service plan '{plan_name}' not found in DB. Skipping.")
                    continue

            link_combined_product_eligibility(
                cursor, product_id, plan_id,
                entry.get('min_lines', 0),
                entry.get('max_lines', 1),
                entry.get('base_role', "")  # 수정: is_base_plan_required → base_role
            )
        print("CombinedProductEligibility data updated/inserted.")

    if 'required_base_roles' in kwargs and product_id:
        upsert_required_base_roles(cursor, product_id, kwargs['required_base_roles'])
        print("RequiredBaseRole data updated/inserted.")

    if 'discount_data' in kwargs and product_id:
        discount_data = kwargs['discount_data']
        if 'combined_product_id' not in discount_data:
            discount_data['combined_product_id'] = product_id
        upsert_discount(cursor, discount_data)
        discount_id = discount_data['id']
        print(f"Discount '{discount_data.get('discount_name')}' updated/inserted.")

        if 'discount_conditions_by_plan' in kwargs:
            # service_plan_map 비어 있으면 DB에서 먼저 채우기
            if not service_plan_map:
                cursor.execute("SELECT name, id FROM ServicePlan WHERE company_id = ?", (company_id,))
                for name, plan_id in cursor.fetchall():
                    service_plan_map[name] = plan_id
            
            for entry in kwargs['discount_conditions_by_plan']:
                plan_name = entry['plan_name']
                plan_id = service_plan_map.get(plan_name)
                base_role = entry.get("base_role", "")

                # 캐시에 없다면 DB에서 직접 조회
                if not plan_id:
                    cursor.execute("SELECT id FROM ServicePlan WHERE name = ? AND company_id = ?", (plan_name, company_id))
                    result = cursor.fetchone()
                    if result:
                        plan_id = result[0]
                        service_plan_map[plan_name] = plan_id  # 캐시 갱신
                    else:
                        print(f"Warning: Service plan '{plan_name}' not found for discount condition by plan. Skipping.")
                        continue

                upsert_discount_condition_by_plan(
                    cursor,
                    discount_id,
                    plan_id,
                    base_role,
                    condition_text=entry.get('condition_text'),
                    override_discount_value=entry.get('override_value'),
                    override_unit=entry.get('override_unit')
                )

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
    db_name = "combined_products.db"
    create_combined_product_db("combined_products.db")
    create_company_table("combined_products.db")

    # # 1. '따로 살아도 가족결합' 전체 데이터 삽입/업데이트 예시
    # company_name = "kt"
    # conn = sqlite3.connect(db_name)
    # cursor = conn.cursor()
    # cursor.execute("SELECT id FROM Company WHERE name = ?", (company_name,))
    # company_id = cursor.fetchone()[0]
    # conn.commit()
    # conn.close()

    # combined_product_name = "따로 살아도 가족결합"
    # product_id = hash_id(f"{company_name}_{combined_product_name}")

    # # KT '따로 살아도 가족결합' PDF 기반 데이터 정의
    # family_combined_product_data = {
    #     "id": product_id,
    #     "name": combined_product_name,
    #     "company_id": company_id, # 함수 내에서 company_id를 찾아 채워줄 예정
    #     "description": "따로 사는 가족끼리 뭉치면, 더 커지는 할인 혜택으로 인터넷/TV 2번째 회선 부터는 기존 결합 할인 이외 추가 할인 받을 수 있어요!",
    #     "max_mobile_lines": 10, # "무선 최대 10회선" [cite: 45]
    #     "max_internet_lines": 5, # "인터넷/TV 최대 5회선" [cite: 45]
    #     "max_iptv_lines": 5, # "인터넷/TV 최대 5회선" [cite: 45]
    #     "join_condition": """인터넷 및 모바일 각각 1회선 이상 결합 필수.
    #                         결합 내 인터넷 회선 중 한 회선을 '베이스 인터넷'으로 지정 필요.
    #                         '베이스 인터넷' 및 해당 회선에 연결된 IPTV 외 인터넷/IPTV 추가 결합은 신규 가입 시점(개통완료일 기준)부터 익월 말까지 가능.
    #                         법인사업자 등 일부 유형은 모바일 최대 7회선.""",
    #     "applicant_scope": "본인, 배우자, 본인 및 배우자의 직계 존비속/형제자매, 직계비속의 배우자(며느리/사위)",
    #     "application_channel": "전화상담 신청",
    #     "url": "https://product.kt.com/wDic/productDetail.do?ItemCode=1630",
    #     "available": True
    # }

    # db_name="combined_products.db"
    # conn = sqlite3.connect(db_name)
    # cursor = conn.cursor()

    # cursor.execute("SELECT sp.service_type, sp.name, sp.fee FROM ServicePlan sp WHERE company_id = ?", (company_id,))
    # mobile_all = cursor.fetchall()

    # family_service_plan_definitions = [
    #     # 모바일 (예시 요금제 - PDF에 구체적인 요금제 명시 안됨, 요고뭉치 PDF에서 요고30 참조)
    #     # db_update_mobile.py에서 5G 요금제 전부 업데이트

    #     # 인터넷 (따로 살아도 가족결합 PDF에 언급된 이름과 매칭)
    #     ("Internet", "인터넷 에센스", 55000), # [cite: 4] (요고뭉치 PDF에 명시된 무약정 요금 사용)
    #     ("Internet", "인터넷 베이직", 46200), # [cite: 4]
    #     ("Internet", "인터넷 슬림", 39600), # [cite: 4]
    #     ("Internet", "인터넷 에센스 와이파이", 63800), # [cite: 7]
    #     ("Internet", "인터넷 베이직 와이파이", 55000), # [cite: 7]
    #     ("Internet", "인터넷 슬림 와이파이", 48400), # [cite: 7]
    #     # TV (따로 살아도 가족결합 PDF에 언급된 이름과 매칭)
    #     ("TV", "지니 TV VOD 초이스", 31020), # [cite: 7]
    #     ("TV", "지니 TV 에센스", 25300), # [cite: 7]
    #     ("TV", "지니 TV 베이직", 18150), # [cite: 7]
    # ] + mobile_all

    # mobile_eligibility_data = []
    # for mobile_plan in mobile_all:
    #     mobile_eligibility_data.append({
    #         "plan_name": mobile_plan[1],
    #         "min_lines": 0, 
    #         "max_lines": 10, 
    #         "base_role": "main_mobile"
    #     })
    # family_eligibility_data = [
    #     # 인터넷 (베이스 인터넷 지정 필수)
    #     {"plan_name": "인터넷 에센스", "min_lines": 0, "max_lines": 5, "base_role": "main_internet"},
    #     {"plan_name": "인터넷 베이직", "min_lines": 0, "max_lines": 5, "base_role": "main_internet"},
    #     {"plan_name": "인터넷 슬림", "min_lines": 0, "max_lines": 5, "base_role": "main_internet"},
    #     {"plan_name": "인터넷 에센스 와이파이", "min_lines": 0, "max_lines": 5, "base_role": "main_internet"},
    #     {"plan_name": "인터넷 베이직 와이파이", "min_lines": 0, "max_lines": 5, "base_role": "main_internet"},
    #     {"plan_name": "인터넷 슬림 와이파이", "min_lines": 0, "max_lines": 5, "base_role": "main_internet"},
    #     # 모바일 (최대 10회선)
    #     # TV (최대 5회선)
    #     {"plan_name": "지니 TV VOD 초이스", "min_lines": 0, "max_lines": 5},
    #     {"plan_name": "지니 TV 에센스", "min_lines": 0, "max_lines": 5},
    #     {"plan_name": "지니 TV 베이직", "min_lines": 0, "max_lines": 5},
    # ] + mobile_eligibility_data

    # family_required_base_roles = {
    #     "main_mobile": 1,  # 모바일 요금제 1개 필요
    #     "main_internet": 1 # 베이스 인터넷은 반드시 1개 필요
    # }

    # discount_name = "인터넷/TV 2번째 회선부터 추가 할인"
    # discount_additional_internet_tv_lines_id = hash_id(f"{product_id}_{discount_name}")
    # family_discount_data = {
    #     "id": discount_additional_internet_tv_lines_id,
    #     "combined_product_id": product_id,
    #     "discount_name": discount_name,
    #     "discount_type": "Amount",
    #     "discount_value": 0, # 기본값 (요금제별/회선수별로 오버라이드될 예정)
    #     "unit": "KRW",
    #     "applies_to_service_type": "Internet,TV",
    #     "applies_to_line_sequence": "2nd_onwards", # 2번째 회선부터 [cite: 52]
    #     "note": "인터넷/TV 2번째 회선부터 신규 고객 대상 추가 할인 적용. 베이스 인터넷 및 해당 회선에 연결된 IPTV 외 추가 결합된 인터넷/TV 대상 3년 약정 시 제공."
    # }

    # family_discount_by_plan_conditions = [
    #     {"plan_name": "인터넷 베이직", "base_role": "", "condition_text": None, "override_value": 2200, "override_unit": "KRW"}, # [cite: 17] (base_role이 없는 일반적인 경우)
    #     {"plan_name": "인터넷 베이직 와이파이", "base_role": "", "condition_text": None, "override_value": 2200, "override_unit": "KRW"}, 
    #     {"plan_name": "인터넷 에센스", "base_role": "", "condition_text": "에센스 이상", "override_value": 3300, "override_unit": "KRW"}, # [cite: 17]
    #     {"plan_name": "인터넷 에센스 와이파이", "base_role": "", "condition_text": "에센스 이상", "override_value": 3300, "override_unit": "KRW"},
    #     {"plan_name": "인터넷 슬림", "base_role": "", "condition_text": None, "override_value": 0, "override_unit": "KRW"}, 
    #     {"plan_name": "인터넷 슬림 와이파이", "base_role": "", "condition_text": None, "override_value": 0, "override_unit": "KRW"}, 
    #     {"plan_name": "지니 TV VOD 초이스", "base_role": "", "condition_text": "슬림 이상", "override_value": 2200, "override_unit": "KRW"}, # [cite: 17]
    #     {"plan_name": "지니 TV 에센스", "base_role": "", "condition_text": "슬림 이상", "override_value": 2200, "override_unit": "KRW"},
    #     {"plan_name": "지니 TV 베이직", "base_role": "", "condition_text": "슬림 이상", "override_value": 2200, "override_unit": "KRW"}, # [cite: 17]
    # ]

    # family_discount_by_line_count_condition = {
    #     "min_applicable_lines": 2, # 2번째 회선부터 [cite: 52]
    #     "max_applicable_lines": None, # 제한 없음 (최대 5회선까지 가능하므로 논리적으로 5회선까지 적용) [cite: 45]
    #     "applies_per_line": True, # 각 회선에 적용
    #     "override_discount_value": None, # 요금제별로 오버라이드되므로 여기서는 None
    #     "override_unit": None
    # }

    # family_benefits_data = [
    #     {"id": hash_id(f"{product_id}_benefit-1"), "benefit_type": "Discount", "content": "가구당 최대 19,140원 할인", "condition": "인터넷 에센스, TV 베이직 결합 기준"},
    #     {"id": hash_id(f"{product_id}_benefit-2"), "benefit_type": "LineFlexibility", "content": "모바일 최대 10회선, 인터넷/TV 최대 5회선 결합 가능", "condition": None},
    #     {"id": hash_id(f"{product_id}_benefit-3"), "benefit_type": "Eligibility", "content": "본인, 배우자, 직계 존비속/형제자매, 직계비속의 배우자(며느리/사위) 결합 가능", "condition": None},
    #     {"id": hash_id(f"{product_id}_benefit-4"), "benefit_type": "Flexibility", "content": "따로 사는 가족끼리 뭉칠 수 있음", "condition": None},
    #     {"id": hash_id(f"{product_id}_benefit-5"), "benefit_type": "AdditionalDiscount", "content": "인터넷+TV 최대 5,500원 추가 할인", "condition": "추가 결합 시, 인터넷 에센스+TV 슬림 이상, 3년 약정 신규 가입시"},
    # ]


    # print("\n--- '따로 살아도 가족결합' 전체 데이터 업데이트 ---")
    # insert_example_data_v2(
    #     company_data={"name": company_name},
    #     combined_product_data=family_combined_product_data,
    #     service_plan_definitions=family_service_plan_definitions,
    #     eligibility_data=family_eligibility_data,
    #     discount_data=family_discount_data,
    #     discount_conditions_by_plan=family_discount_by_plan_conditions,
    #     discount_conditions_by_line_count=family_discount_by_line_count_condition,
    #     benefits_data=family_benefits_data,
    #     required_base_roles=family_required_base_roles,
    # )

    # # 2. '요고뭉치 결합' 데이터 추가/업데이트 예시
    # combined_product_name_yogo = "요고뭉치 결합"
    # product_id_yogo = hash_id(f"{company_name}_{combined_product_name_yogo}")

    # yogo_mungchi_combined_product_data = {
    #     "id": product_id_yogo,
    #     "name": combined_product_name_yogo,
    #     "company_id": company_id, # 함수 내에서 company_id를 찾아 채워줄 예정
    #     "description": "핸드폰은 요고로 하고 인터넷/TV도 뭉치면 약정 걱정 없이 통신비 최대 32% 할인!",
    #     "max_mobile_lines": None, # 명시된 최대 회선 없음 (요고뭉치에는 다회선 개념이 명시되지 않음)
    #     "max_internet_lines": 1, # "1회선" 명시 [cite: 12]
    #     "max_iptv_lines": 1, # TV의 경우 "인터넷 1회선당 최대 1회선의 TV까지 결합 가능" [cite: 64] (따로살아도 가족결합 PDF 참조)
    #     "join_condition": """5G/LTE 다이렉트 또는 요고 요금제를 가입한 모바일 고객이 가입조건을 만족하는 인터넷 또는 인터넷과 IPTV를 결합.
    #                         KT 공식 온라인 채널(KT SHOP)을 통해 가입하여 약정 혜택을 받고 있지 않아야 가입 가능.
    #                         STB은 Genie TV STB 3 또는 Genie TV STB A이어야 함.
    #                         모바일, 인터넷, IPTV 모두 동일 명의이어야 합니다.
    #                         모바일과 인터넷은 필수상품으로 결합 내 모두 포함되어 있어야 합니다.
    #                         함께 결합된 모바일에는 결합할인이 제공되지 않습니다.
    #                         (정지 기간 동안 결합할인은 미제공되며, 결합 필수 상품인 모바일 또는 인터넷 정지 시 결합한 상품 모두 할인 미제공됩니다.)""",
    #     "applicant_scope": "신규 및 기존 고객 (무약정 온라인 가입고객)",
    #     "application_channel": "전화상담 신청",
    #     "url": "https://product.kt.com/wDic/productDetail.do?ItemCode=1630", # 요고뭉치 URL은 PDF에 명시되지 않음
    #     "available": True
    # }

    # # 요고뭉치에 특화된 요금제. 이미 '따로 살아도 가족결합'에서 넣은 요금제와 겹칠 수 있으나,
    # # upsert_service_plan 함수가 ON CONFLICT DO UPDATE SET을 사용하여 중복을 처리함
    # yogo_mobile = [mobile_plan for mobile_plan in mobile_all if "요고" in mobile_plan[1]]
    # yogo_mungchi_service_plan_definitions = [
    #     ("Internet", "인터넷 에센스", 55000), # [cite: 4]
    #     ("Internet", "인터넷 베이직", 46200), # [cite: 4]
    #     ("Internet", "인터넷 슬림", 39600), # [cite: 4]
    #     ("Internet", "인터넷 에센스 와이파이", 63800), # [cite: 7]
    #     ("Internet", "인터넷 베이직 와이파이", 55000), # [cite: 7]
    #     ("Internet", "인터넷 슬림 와이파이", 48400), # [cite: 7]
    #     ("TV", "지니 TV VOD 초이스", 31020), # [cite: 7]
    #     ("TV", "지니 TV 에센스", 25300), # [cite: 7]
    #     ("TV", "지니 TV 베이직", 18150), # [cite: 7]
    # ] + yogo_mobile

    # yogo_mobile_eligibility_data = []
    # for mobile_plan in mobile_all:
    #     if "요고" in mobile_plan[1]:
    #         yogo_mobile_eligibility_data.append({
    #             "plan_name": mobile_plan[1],
    #             "min_lines": 0, 
    #             "max_lines": 1, 
    #             "base_role": "main_mobile"
    #         })
    # yogo_mungchi_eligibility_data = [
    #     {"plan_name": "인터넷 에센스", "min_lines": 0, "max_lines": 1, "base_role": "main_internet"}, # 인터넷 1회선 필수 [cite: 12]
    #     {"plan_name": "인터넷 베이직", "min_lines": 0, "max_lines": 1, "base_role": "main_internet"}, # 인터넷 1회선 필수 [cite: 12]
    #     {"plan_name": "인터넷 슬림", "min_lines": 0, "max_lines": 1, "base_role": "main_internet"}, # 인터넷 1회선 필수 [cite: 12]
    #     {"plan_name": "인터넷 에센스 와이파이", "min_lines": 0, "max_lines": 1, "base_role": "main_internet"}, # 인터넷 1회선 필수 [cite: 12]
    #     {"plan_name": "인터넷 베이직 와이파이", "min_lines": 0, "max_lines": 1, "base_role": "main_internet"}, # 인터넷 1회선 필수 [cite: 12]
    #     {"plan_name": "인터넷 슬림 와이파이", "min_lines": 0, "max_lines": 1, "base_role": "main_internet"}, # 인터넷 1회선 필수 [cite: 12]
    #     {"plan_name": "지니 TV VOD 초이스", "min_lines": 0, "max_lines": 1}, # IPTV는 선택 [cite: 12]
    #     {"plan_name": "지니 TV 에센스", "min_lines": 0, "max_lines": 1}, # IPTV는 선택 [cite: 12]
    #     {"plan_name": "지니 TV 베이직", "min_lines": 0, "max_lines": 1}, # IPTV는 선택 [cite: 12]
    # ] + yogo_mobile_eligibility_data

    # yogo_required_base_roles = {
    #     "main_mobile": 1,    # 필수 모바일 요금제 1개 (별도로 지정)
    #     "main_internet": 1   # 필수 인터넷 요금제 1개
    # }

    # discount_yogo_mungchi_id = hash_id(f"{product_id_yogo}_yogo_mungchi_discount")
    # yogo_mungchi_discount_data = {
    #     "id": discount_yogo_mungchi_id,
    #     "combined_product_id": product_id_yogo,
    #     "discount_name": "요고뭉치 결합할인",
    #     "discount_type": "Amount",
    #     "discount_value": 0, # 요금제별로 다름
    #     "unit": "KRW",
    #     "applies_to_service_type": "Internet,TV", # 모바일은 할인 미제공 [cite: 11]
    #     "applies_to_line_sequence": "1st_line", # 1회선에 대한 할인
    #     "note": "약정 걱정 없이 통신비 최대 32% 할인 (일반 무약정 요금 대비)"
    # }

    # yogo_mungchi_discount_by_plan_conditions = [
    #     {"plan_name": "인터넷 에센스", "base_role": "", "override_value": 22000, "override_unit": "KRW"}, # [cite: 4]
    #     {"plan_name": "인터넷 베이직", "base_role": "", "override_value": 18700, "override_unit": "KRW"}, # [cite: 4]
    #     {"plan_name": "인터넷 슬림", "base_role": "", "override_value": 17600, "override_unit": "KRW"}, # [cite: 4]
    #     {"plan_name": "인터넷 에센스 와이파이", "base_role": "", "override_value": 30800, "override_unit": "KRW"}, # [cite: 7]
    #     {"plan_name": "인터넷 베이직 와이파이", "base_role": "", "override_value": 26400, "override_unit": "KRW"}, # [cite: 7]
    #     {"plan_name": "인터넷 슬림 와이파이", "base_role": "", "override_value": 25300, "override_unit": "KRW"}, # [cite: 7]
    #     {"plan_name": "지니 TV VOD 초이스", "base_role": "", "override_value": 10120, "override_unit": "KRW"}, # [cite: 7]
    #     {"plan_name": "지니 TV 에센스", "base_role": "", "override_value": 8800, "override_unit": "KRW"}, # [cite: 7]
    #     {"plan_name": "지니 TV 베이직", "base_role": "", "override_value": 6050, "override_unit": "KRW"}, # [cite: 7]
    # ]

    # yogo_mungchi_benefits_data = [
    #     {"id": hash_id(f"{product_id_yogo}_benefit-1"), "benefit_type": "Discount", "content": "약정 없이 최대 32% 할인 (일반 무약정 요금 대비)", "condition": None},
    #     {"id": hash_id(f"{product_id_yogo}_benefit-2"), "benefit_type": "Eligibility", "content": "신규 및 기존고객 결합 가능 (무약정 온라인 가입고객)", "condition": None},
    #     {"id": hash_id(f"{product_id_yogo}_benefit-3"), "benefit_type": "Service", "content": "GIGA WIFI home 제공 (GIGA WIFI home 제공 기준 요금)", "condition": None},
    # ]

    # print("\n--- '요고뭉치 결합' 전체 데이터 업데이트 ---")
    # insert_example_data_v2(
    #     company_data={"name": company_name},
    #     combined_product_data=yogo_mungchi_combined_product_data,
    #     service_plan_definitions=yogo_mungchi_service_plan_definitions,
    #     eligibility_data=yogo_mungchi_eligibility_data,
    #     discount_data=yogo_mungchi_discount_data,
    #     discount_conditions_by_plan=yogo_mungchi_discount_by_plan_conditions,
    #     benefits_data=yogo_mungchi_benefits_data,
    #     required_base_roles=yogo_required_base_roles
    # )

    # # 3. '신혼미리결합' 데이터 추가/업데이트 예시
    # combined_product_name_newly_married = "신혼미리결합"
    # product_id_newly_married = hash_id(f"{company_name}_{combined_product_name_newly_married}")

    # newly_married_combined_product_data = {
    #     "id": product_id_newly_married,
    #     "name": combined_product_name_newly_married,
    #     "company_id": company_id,
    #     "description": "예비/신혼부부라면! 종이 청첩장/웨딩 계약서로 배우자 모바일 최대 50% 할인 받으세요.",
    #     "max_mobile_lines": 2, # 본인 1회선, 배우자 1회선으로 총 2회선 결합 가능
    #     "max_internet_lines": 1,
    #     "max_iptv_lines": 1,
    #     "join_condition": """예비 부부 및 혼인신고 후 3년 이내 신혼 부부 요건을 만족하는 개인 고객(외국인 포함)만 가입 가능 (단, 개인/법인 사업자는 가입 불가).
    #                         월 77,000원 이상 5G/LTE 요금제를 함께 가입하면 배우자는 최대 반값에 이용 가능.
    #                         가족관계증명서 대신 종이 청첩장, 예식장 계약서, 웨딩플래너 계약서, 주민등록등본(동거인표기 필수)으로 신혼 증빙 가능.
    #                         예비/신혼 부부 명의의 인터넷, 집전화, 인터넷전화, TV, 모바일 상품끼리만 결합 가능 (명의당 1회 제한).
    #                         인터넷 상품 없이 모바일만 2회선 결합 시 모바일 할인 혜택은 최대 6개월간 제공.
    #                         (단, 예비/신혼부부 명의의 모바일 회선만 가입 가능하며, '인터넷 슬림' 상품 기준에 해당하는 총액결합 할인 금액을 적용하며 6개월 내 인터넷 미가입 시 할인이 중단됩니다.)""",
    #     "applicant_scope": "예비 부부 및 혼인신고 후 3년 이내 신혼 부부 요건을 만족하는 개인 고객 (외국인 포함)",
    #     "application_channel": "전화상담 신청",
    #     "url": "https://product.kt.com/wDic/productDetail.do?ItemCode=1441&CateCode=6027&filter_code=114&option_code=166&pageSize=10",
    #     "available": True
    # }

    # conn = sqlite3.connect(db_name)
    # cursor = conn.cursor()
    # cursor.execute("SELECT sp.service_type, sp.name, sp.fee FROM ServicePlan sp WHERE company_id = ?", (company_id,))
    # mobile_all = cursor.fetchall()
    # conn.close()

    # # 신혼미리결합에서 언급된 모바일 요금제 및 인터넷/TV 요금제
    # # Note: Specific internet/TV plans are not explicitly listed in the PDF for 신혼미리결합,
    # # but the example shows a mobile-only discount or "신혼집 인터넷, TV" implying these services can be combined.
    # # Based on the discount examples, only mobile plans are detailed for discounts.
    # newly_married_service_plan_definitions = []
    # for mobile_plan in mobile_all:
    #     if mobile_plan[1] in ["5G 초이스 프리미엄", "5G 초이스 스페셜", "5G 스페셜", "5G Y 스페셜", "5G 초이스 베이직", "5G 베이직", "5G Y 베이직"]:
    #         newly_married_service_plan_definitions.append(mobile_plan)

    # # Eligibility data for 신혼미리결합
    # newly_married_eligibility_data = []
    # for mobile_plan in newly_married_service_plan_definitions:
    #     # Main mobile line (본인)
    #     newly_married_eligibility_data.append({
    #         "plan_name": mobile_plan[1],
    #         "min_lines": 0,
    #         "max_lines": 1,
    #         "base_role": "main_mobile"
    #     })
    #     # Spouse mobile line (배우자)
    #     newly_married_eligibility_data.append({
    #         "plan_name": mobile_plan[1],
    #         "min_lines": 0,
    #         "max_lines": 1,
    #         "base_role": "spouse_mobile"
    #     })

    # # Add placeholder for internet and TV, as they are mentioned but specific plans for eligibility are not detailed for this product.
    # # Assuming standard internet/TV plans would be eligible if combined.
    # newly_married_eligibility_data.extend([
    #     {"plan_name": "인터넷 에센스", "min_lines": 0, "max_lines": 1, "base_role": "main_internet"},
    #     {"plan_name": "인터넷 베이직", "min_lines": 0, "max_lines": 1, "base_role": "main_internet"},
    #     {"plan_name": "인터넷 슬림", "min_lines": 0, "max_lines": 1, "base_role": "main_internet"},
    #     {"plan_name": "지니 TV VOD 초이스", "min_lines": 0, "max_lines": 1},
    #     {"plan_name": "지니 TV 에센스", "min_lines": 0, "max_lines": 1},
    #     {"plan_name": "지니 TV 베이직", "min_lines": 0, "max_lines": 1},
    # ])


    # newly_married_required_base_roles = {
    #     "main_mobile": 1,
    #     "spouse_mobile": 1, # 배우자 모바일 필수
    # }

    # discount_name_newly_married = "배우자 모바일 최대 50% 할인"
    # discount_id_newly_married = hash_id(f"{product_id_newly_married}_{discount_name_newly_married}")
    # newly_married_discount_data = {
    #     "id": discount_id_newly_married,
    #     "combined_product_id": product_id_newly_married,
    #     "discount_name": discount_name_newly_married,
    #     "discount_type": "Percentage",
    #     "discount_value": 0, # Will be overridden by plan conditions
    #     "unit": "%",
    #     "applies_to_service_type": "Mobile",
    #     "applies_to_line_sequence": "spouse_line", # Applies to the spouse's mobile line
    #     "note": "결합할인 25% + 요금할인 25% = 최대 50% 할인. 5G 초이스 스페셜 기준 월 41,800원 할인. 인터넷 없이 모바일만 2회선 결합 시 '인터넷 슬림' 상품 기준에 해당하는 총액결합 할인 금액 적용."
    # }

    # # Discount conditions by plan for '신혼미리결합'
    # # Based on the table in the PDF, '신혼미리결합 (프리미엄)' discount.
    # newly_married_discount_by_plan_conditions = [
    #     # spouse_mobile 역할의 요금제에만 할인이 적용되는 경우
    #     {"plan_name": "5G 초이스 프리미엄", "base_role": "spouse_mobile", "condition_text": None, "override_value": 25, "override_unit": "%"},
    #     {"plan_name": "5G 초이스 스페셜", "base_role": "spouse_mobile", "condition_text": None, "override_value": 25, "override_unit": "%"},
    #     {"plan_name": "5G Y 스페셜", "base_role": "spouse_mobile", "condition_text": None, "override_value": 25, "override_unit": "%"},
    #     {"plan_name": "5G 초이스 베이직", "base_role": "spouse_mobile", "condition_text": None, "override_value": 25, "override_unit": "%"},
    #     {"plan_name": "5G 베이직", "base_role": "spouse_mobile", "condition_text": None, "override_value": 25, "override_unit": "%"},
    #     {"plan_name": "5G Y 베이직", "base_role": "spouse_mobile", "condition_text": None, "override_value": 25, "override_unit": "%"},
    #     {"plan_name": "5G 스페셜", "base_role": "spouse_mobile", "condition_text": None, "override_value": 25, "override_unit": "%"},
    # ]

    # newly_married_benefits_data = [
    #     {"id": hash_id(f"{product_id_newly_married}_benefit-1"), "benefit_type": "Discount", "content": "배우자 모바일 최대 50% 할인 (결합할인 25%+요금할인 25%)", "condition": None}, #[cite: 2]
    #     {"id": hash_id(f"{product_id_newly_married}_benefit-2"), "benefit_type": "Discount", "content": "월 41,800원 할인 (5G 초이스 스페셜 기준)", "condition": "5G 초이스 스페셜 기준"}, #[cite: 2]
    #     {"id": hash_id(f"{product_id_newly_married}_benefit-3"), "benefit_type": "Eligibility", "content": "종이 청첩장, 웨딩 계약서로도 결합 가능", "condition": None}, #[cite: 2, 3]
    #     {"id": hash_id(f"{product_id_newly_married}_benefit-4"), "benefit_type": "Eligibility", "content": "예비 / 신혼부부 가입 가능", "condition": "혼인신고 전 예비 부부 및 혼인신고 후 3년 이내 신혼 부부"}, #[cite: 14]
    #     {"id": hash_id(f"{product_id_newly_married}_benefit-5"), "benefit_type": "Flexibility", "content": "인터넷 없이도 결합 상품 이용 가능 (결합 후 6개월 내 인터넷 신청 가능)", "condition": None}, #[cite: 2, 6, 7]
    #     {"id": hash_id(f"{product_id_newly_married}_benefit-6"), "benefit_type": "Eligibility", "content": "간단한 신혼 증빙만으로 미리 결합 가능 (가족 관계 증명서 없이)", "condition": None}, #[cite: 6]
    # ]


    # print("\n--- '신혼미리결합' 전체 데이터 업데이트 ---")
    # # Assuming insert_example_data_v2 function is defined and handles the database operations.
    # # For this example, I'm just printing the data structure.
    # insert_example_data_v2(
    #     company_data={"name": company_name},
    #     combined_product_data=newly_married_combined_product_data,
    #     service_plan_definitions=newly_married_service_plan_definitions,
    #     eligibility_data=newly_married_eligibility_data,
    #     discount_data=newly_married_discount_data,
    #     discount_conditions_by_plan=newly_married_discount_by_plan_conditions,
    #     benefits_data=newly_married_benefits_data,
    #     required_base_roles=newly_married_required_base_roles,
    # )

    # print(f"combined_product_data: {newly_married_combined_product_data}")
    # print(f"service_plan_definitions: {newly_married_service_plan_definitions}")
    # print(f"eligibility_data: {newly_married_eligibility_data}")
    # print(f"discount_data: {newly_married_discount_data}")
    # print(f"discount_conditions_by_plan: {newly_married_discount_by_plan_conditions}")
    # print(f"benefits_data: {newly_married_benefits_data}")
    # print(f"required_base_roles: {newly_married_required_base_roles}")

    # # conn = sqlite3.connect(db_name)
    # # cursor = conn.cursor()
    # # cursor.execute("UPDATE DiscountConditionByPlan SET base_role = '' WHERE base_role IS NULL;")

    # 4. '우리가족 무선결합' 데이터 파싱
    company_name = "kt"
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM Company WHERE name = ?", (company_name,))
    company_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    combined_product_name_family_wireless = "우리가족 무선결합"
    product_id_family_wireless = hash_id(f"{company_name}_{combined_product_name_family_wireless}")

    family_wireless_combined_product_data = {
        "id": product_id_family_wireless,
        "name": combined_product_name_family_wireless,
        "company_id": company_id,
        "description": "가족끼리 KT 휴대폰을 2회선부터 최대 5회선까지 결합하면, 각 회선의 월 요금제 금액에 따라 매월 회선별로 1,100원에서 최대 11,000원까지 할인을 받을 수 있는 모바일 결합 상품입니다. 할인은 신규, 우수기변, 재약정 고객을 대상으로 24개월 동안 제공되며, 기존 고객도 가입 가능합니다. 예를 들어, 2대 결합 시에는 월 최대 22,000원의 통신비 절감 효과가 있습니다.",
        "max_mobile_lines": 5, # "최대 5회선까지 결합 가능합니다." [cite: 3]
        "max_internet_lines": 0, # 이 상품은 모바일 전용 결합으로 인터넷 회선 조건은 명시되지 않음
        "max_iptv_lines": 0, # 이 상품은 모바일 전용 결합으로 IPTV 회선 조건은 명시되지 않음
        "join_condition": """가족 구성원 중 최소 2회선부터 최대 5회선까지 결합 가능합니다. 1회선이 되면 결합은 해지됩니다.
                            모바일 신규 가입, 우수 기기변경 또는 재약정 가입일 기준 다음 달 말일까지 결합해야 하며, 이 경우 사용 중인 요금제에 따라 24개월간 할인 혜택을 받을 수 있습니다.
                            우수기변이란 사용 중인 휴대폰을 반납하고 새로운 기기로 변경하는 것을 의미합니다.""",
        "applicant_scope": "본인 및 배우자와 직계존비속, 형제자매, 며느리 및 사위", # [cite: 3]
        "application_channel": "전화상담 신청", # [cite: 1]
        "url": "https://product.kt.com/wDic/productDetail.do?ItemCode=977&CateCode=6027&filter_code=114&option_code=166&pageSize=10", # [cite: 1]
        "available": True
    }

    # Simulate fetching mobile_all from a database as in the example
    # These are hypothetical plans for demonstration, with the one example plan included.
    # ("Service Type", "Plan Name", Monthly Fee)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    cursor.execute("SELECT sp.service_type, sp.name, sp.fee FROM ServicePlan sp WHERE company_id = ?", (company_id,))
    mobile_all = cursor.fetchall()
    conn.close()

    family_wireless_service_plan_definitions = []
    for service_type, name, fee in mobile_all:
        family_wireless_service_plan_definitions.append((service_type, name, fee))

    family_wireless_eligibility_data = []
    for _, plan_name, _ in mobile_all:
        family_wireless_eligibility_data.append({
            "plan_name": plan_name,
            "min_lines": 0, # A specific plan is not individually required min_lines, but contributes to the bundle's 2-5 lines
            "max_lines": 5, # A plan can be one of up to 5 mobile lines in the bundle [cite: 3]
            "base_role": "main_mobile" # All lines in this bundle are mobile lines
        })

    family_wireless_required_base_roles = {
        "main_mobile": 2 # "최소 2회선부터" [cite: 3]
    }

    discount_name_family_wireless = "우리가족 무선결합 모바일 할인"
    discount_id_family_wireless = hash_id(f"{product_id_family_wireless}_{discount_name_family_wireless}")
    family_wireless_discount_data = {
        "id": discount_id_family_wireless,
        "combined_product_id": product_id_family_wireless,
        "discount_name": discount_name_family_wireless,
        "discount_type": "Amount",
        "discount_value": 0, # To be overridden by plan conditions based on fee tiers [cite: 5]
        "unit": "KRW",
        "applies_to_service_type": "Mobile",
        "applies_to_line_sequence": "per_line", # "회선별 최대 11,000원 할인" [cite: 1]
        "note": "모바일 회선별 월정액 요금에 따라 할인 금액이 차등 적용됩니다. 할인은 최대 5회선까지, 24개월간 제공됩니다."
    }

    family_wireless_discount_by_plan_conditions = []
    for _, plan_name, fee in mobile_all:
        discount_value = 0
        condition_text = ""
        if fee < 29700:
            discount_value = 1100 # [cite: 5]
            condition_text = "월정액 29,700원 미만" # [cite: 5]
        elif fee < 54890: # 29,700원 이상 54,890원 미만
            discount_value = 3300 # [cite: 5]
            condition_text = "월정액 29,700원 이상 54,890원 미만" # [cite: 5]
        elif fee < 73700: # 54,890원 이상 73,700원 미만
            discount_value = 5500 # [cite: 5]
            condition_text = "월정액 54,890원 이상 73,700원 미만" # [cite: 5]
        elif fee < 84700: # 73,700원 이상 84,700원 미만
            discount_value = 7700 # [cite: 5]
            condition_text = "월정액 73,700원 이상 84,700원 미만" # [cite: 5]
        else: # 84,700원 이상
            discount_value = 11000 # [cite: 5]
            condition_text = "월정액 84,700원 이상" # [cite: 5]

        family_wireless_discount_by_plan_conditions.append({
            "plan_name": plan_name,
            "base_role": "", # Discount applies to any mobile line based on its fee
            "condition_text": condition_text, # Describes the fee tier for clarity
            "override_value": discount_value,
            "override_unit": "KRW"
        })

    family_wireless_discount_by_line_count_condition = {
        "min_applicable_lines": 2, # "최소 2회선부터" [cite: 3]
        "max_applicable_lines": 5, # "최대 5회선까지" [cite: 3]
        "applies_per_line": True, # Discount is per line [cite: 1]
        "override_discount_value": None, # Handled by plan conditions
        "override_unit": None
    }

    family_wireless_benefits_data = [
        {"id": hash_id(f"{product_id_family_wireless}_benefit-1"), "benefit_type": "Discount", "content": "휴대폰 2대 결합 시 매월 최대 22,000원 할인 (1대당 11,000원)", "condition": "2회선 모두 월정액 84,700원 이상 요금제 사용 시"}, # [cite: 1, 5]
        {"id": hash_id(f"{product_id_family_wireless}_benefit-2"), "benefit_type": "Discount", "content": "회선별 요금제에 따라 월 1,100원 ~ 11,000원 할인", "condition": "모바일 요금제 월정액 기준"}, # [cite: 5]
        {"id": hash_id(f"{product_id_family_wireless}_benefit-3"), "benefit_type": "LineFlexibility", "content": "최소 2회선부터 최대 5회선까지 모바일 회선 결합 가능", "condition": None}, # [cite: 3]
        {"id": hash_id(f"{product_id_family_wireless}_benefit-4"), "benefit_type": "Eligibility", "content": "본인, 배우자, 직계존비속, 형제자매, 며느리/사위 간 결합 가능", "condition": None}, # [cite: 3]
        {"id": hash_id(f"{product_id_family_wireless}_benefit-5"), "benefit_type": "Duration", "content": "신규/우수기변/재약정 고객 대상 24개월간 할인 제공", "condition": "결합 조건 충족 시"}, # [cite: 1, 4]
        {"id": hash_id(f"{product_id_family_wireless}_benefit-6"), "benefit_type": "Eligibility", "content": "기존 KT 모바일 고객도 결합 가능", "condition": None} # [cite: 1]
    ]

    # This is where you would call a function like insert_example_data_v2 from the example
    # For now, printing the main data structures:

    print("\n--- '우리가족 무선결합' Parsed Data ---")
    print("\nfamily_wireless_combined_product_data:")
    print(family_wireless_combined_product_data)
    print("\nfamily_wireless_service_plan_definitions (simulated):")
    print(family_wireless_service_plan_definitions)
    print("\nfamily_wireless_eligibility_data (first item example):")
    if family_wireless_eligibility_data:
        print(family_wireless_eligibility_data[0])
    print("\nfamily_wireless_required_base_roles:")
    print(family_wireless_required_base_roles)
    print("\nfamily_wireless_discount_data:")
    print(family_wireless_discount_data)
    print("\nfamily_wireless_discount_by_plan_conditions (first item example):")
    if family_wireless_discount_by_plan_conditions:
        print(family_wireless_discount_by_plan_conditions[0])
    print("\nfamily_wireless_discount_by_line_count_condition:")
    print(family_wireless_discount_by_line_count_condition)
    print("\nfamily_wireless_benefits_data (first item example):")
    if family_wireless_benefits_data:
        print(family_wireless_benefits_data[0])
    
    
    insert_example_data_v2(
        company_data={"name": company_name, "id": company_id}, # Assuming company_id is also needed
        combined_product_data=family_wireless_combined_product_data,
        service_plan_definitions=family_wireless_service_plan_definitions,
        eligibility_data=family_wireless_eligibility_data,
        discount_data=family_wireless_discount_data,
        discount_conditions_by_plan=family_wireless_discount_by_plan_conditions,
        discount_conditions_by_line_count=family_wireless_discount_by_line_count_condition,
        benefits_data=family_wireless_benefits_data,
        required_base_roles=family_wireless_required_base_roles
    )