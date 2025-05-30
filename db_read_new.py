import sqlite3
import hashlib # hash_id 함수가 다른 파일에 있다면 필요 없음
from typing import List, Dict, Any, Optional, Tuple

def get_db_connection(db_name: str = "combined_products_final.db"):
    """데이터베이스 연결을 반환합니다."""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row  # 컬럼 이름으로 데이터 접근 가능하게 설정
    return conn

def calculate_combined_product_pricing(db_name: str, combined_product_id: str) -> Optional[Dict[str, Any]]:
    """
    특정 결합상품의 총 할인액, 할인 전 가격, 할인 후 가격 및 관련 요금제를 계산합니다.
    주의: 현재 이 함수는 단순한 결합 (1회선 모바일 + 1회선 인터넷 + 1회선 IPTV)을 가정합니다.
          '따로 살아도 가족결합'의 2번째 회선부터 적용되는 추가 할인 등 복잡한 로직은
          이 함수 내에서 완전히 구현하기 어렵습니다. 이는 비즈니스 로직에 따라
          더 복잡한 시뮬레이션이 필요합니다.
          여기서는 '요고뭉치 결합'처럼 각 상품의 특정 요금제에 대한 고정 할인액이 있는 경우를
          우선적으로 고려하여 구현합니다.
    """
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    # 1. 결합 상품 정보 조회
    # min_mobile_lines, min_internet_lines, min_iptv_lines를 추가하여 IndexError 해결
    cursor.execute("""
        SELECT
            cp.id, cp.name, cp.description, cp.min_mobile_lines, cp.min_internet_lines, cp.min_iptv_lines,
            c.name as company_name
        FROM CombinedProduct cp
        JOIN Company c ON cp.company_id = c.id
        WHERE cp.id = ?
    """, (combined_product_id,))
    product_info = cursor.fetchone()

    if not product_info:
        conn.close()
        return None

    # 2. 결합 상품에 포함될 수 있는 요금제 조회 및 기본 요금 합산
    associated_plans = []
    total_base_fee = 0

    required_service_types = []
    if product_info['min_mobile_lines'] > 0:
        required_service_types.append('Mobile')
    if product_info['min_internet_lines'] > 0:
        required_service_types.append('Internet')
    if product_info['min_iptv_lines'] > 0: # min_iptv_lines가 0 초과인 경우에도 추가
        required_service_types.append('TV')

    # 각 서비스 타입별 대표 요금제 (가장 높은 요금제) 선택
    # 주의: 이 로직은 실제 결합 시나리오와 다를 수 있으며,
    # 복잡한 다회선/다중 서비스 결합 시뮬레이션에는 추가적인 로직이 필요합니다.
    # 여기서는 필수 서비스는 가장 높은 요금제를, TV는 선택 사항으로 추가될 수 있도록 처리합니다.
    
    # 먼저, CombinedProductEligibility에 연결된 모든 요금제 정보를 가져와서
    # 각 서비스 타입별로 가장 요금이 높은 요금제를 선정합니다.
    # 이렇게 하면 결합 상품에 '해당되는' 요금제 중 가장 비싼 요금제를 선택하는 것이 됩니다.
    
    # 'Mobile' 서비스 요금제 중 가장 비싼 요금제 선택
    cursor.execute(f"""
        SELECT sp.name, sp.fee, sp.service_type
        FROM ServicePlan sp
        JOIN CombinedProductEligibility cpe ON sp.id = cpe.service_plan_id
        WHERE cpe.combined_product_id = ? AND sp.service_type = 'Mobile'
        ORDER BY sp.fee DESC
        LIMIT 1
    """, (combined_product_id,))
    top_mobile_plan = cursor.fetchone()
    if top_mobile_plan:
        associated_plans.append({"name": top_mobile_plan['name'], "fee": top_mobile_plan['fee'], "service_type": top_mobile_plan['service_type']})
        total_base_fee += top_mobile_plan['fee']

    # 'Internet' 서비스 요금제 중 가장 비싼 요금제 선택
    cursor.execute(f"""
        SELECT sp.name, sp.fee, sp.service_type
        FROM ServicePlan sp
        JOIN CombinedProductEligibility cpe ON sp.id = cpe.service_plan_id
        WHERE cpe.combined_product_id = ? AND sp.service_type = 'Internet'
        ORDER BY sp.fee DESC
        LIMIT 1
    """, (combined_product_id,))
    top_internet_plan = cursor.fetchone()
    if top_internet_plan:
        associated_plans.append({"name": top_internet_plan['name'], "fee": top_internet_plan['fee'], "service_type": top_internet_plan['service_type']})
        total_base_fee += top_internet_plan['fee']
        
    # 'TV' 서비스 요금제 중 가장 비싼 요금제 선택
    # TV는 선택 상품인 경우가 많으므로, min_iptv_lines가 0인 경우에도 포함 여부는 비즈니스 로직에 따라 결정
    # 여기서는 일단 있다면 포함하는 것으로 가정 (할인 계산을 위함)
    cursor.execute(f"""
        SELECT sp.name, sp.fee, sp.service_type
        FROM ServicePlan sp
        JOIN CombinedProductEligibility cpe ON sp.id = cpe.service_plan_id
        WHERE cpe.combined_product_id = ? AND sp.service_type = 'TV'
        ORDER BY sp.fee DESC
        LIMIT 1
    """, (combined_product_id,))
    top_tv_plan = cursor.fetchone()
    if top_tv_plan: # TV 요금제가 있다면 포함
        associated_plans.append({"name": top_tv_plan['name'], "fee": top_tv_plan['fee'], "service_type": top_tv_plan['service_type']})
        total_base_fee += top_tv_plan['fee']


    # 3. 할인 정보 조회 및 적용
    total_discount_amount = 0

    # 해당 결합 상품에 대한 모든 할인 조회
    cursor.execute("""
        SELECT
            d.id as discount_id, d.discount_name, d.discount_type, d.discount_value, d.unit,
            d.applies_to_service_type, d.applies_to_line_sequence, d.note
        FROM Discount d
        WHERE d.combined_product_id = ?
    """, (combined_product_id,))
    discounts = cursor.fetchall()

    for discount in discounts:
        current_discount_value = discount['discount_value'] # Discount 테이블의 기본 할인 값

        # 3.1. 요금제별 할인 조건 (DiscountConditionByPlan) 적용
        # 현재 `associated_plans`에 있는 요금제들에 대해 할인을 적용
        for ap in associated_plans:
            cursor.execute("""
                SELECT
                    dcbp.override_discount_value, dcbp.override_unit, sp.name as plan_name
                FROM DiscountConditionByPlan dcbp
                JOIN ServicePlan sp ON dcbp.service_plan_id = sp.id
                WHERE dcbp.discount_id = ? AND sp.id = (SELECT id FROM ServicePlan WHERE name = ? LIMIT 1)
            """, (discount['discount_id'], ap['name']))
            plan_cond = cursor.fetchone()

            if plan_cond:
                override_value = plan_cond['override_discount_value'] if plan_cond['override_discount_value'] is not None else current_discount_value
                total_discount_amount += override_value
                # 이 할인 로직은 각 요금제에 대한 할인이 한번만 적용되는 경우를 가정합니다.
                # 복수 회선, 조건부 중복 할인은 더 복잡한 로직이 필요합니다.
        
        # 3.2. 회선 수별 할인 조건 (DiscountConditionByLineCount) 적용
        # '따로 살아도 가족결합'의 2번째 회선부터 할인과 같은 로직 처리는 여기에서.
        # 현재 코드에서는 Benefits에 명시된 "가구당 최대 19,140원"이 총 할인액에
        # 직접적으로 반영되지는 않으므로, 이 부분을 어떻게 반영할지 추가적인 비즈니스 규칙이 필요합니다.
        # 예를 들어, 해당 혜택이 특정 조건 하의 '최대 할인액'이라면, 이 값을 총 할인액으로 사용하거나,
        # 다른 할인들과 합산되는 규칙을 명확히 해야 합니다.
        
        # 현재는 DiscountConditionByPlan에서 계산된 값만 총 할인액에 더해지도록 합니다.
        # 만약 '따로 살아도 가족결합'의 "가구당 최대 19,140원"이 전체 할인액을 의미한다면,
        # 해당 상품에 대해 `total_discount_amount`를 그 값으로 직접 설정하는 로직을 추가할 수 있습니다.
        # (예: if product_info['name'] == '따로 살아도 가족결합': total_discount_amount = 19140)
        # 하지만 이는 다른 요금제별 할인을 무시할 수 있으므로, 비즈니스 규칙에 대한 명확한 정의가 중요합니다.


    final_price = total_base_fee - total_discount_amount
    
    conn.close()

    return {
        "combined_product_id": product_info['id'],
        "combined_product_name": product_info['name'],
        "company_name": product_info['company_name'],
        "associated_plans": associated_plans,
        "total_base_fee": total_base_fee,
        "total_discount_amount": total_discount_amount,
        "final_price": final_price
    }


def get_all_combined_product_pricings(db_name: str = "combined_products_final.db") -> List[Dict[str, Any]]:
    """모든 결합 상품에 대해 가격 정보를 계산하여 반환합니다."""
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM CombinedProduct")
    product_ids = [row['id'] for row in cursor.fetchall()]
    
    all_pricings = []
    for product_id in product_ids:
        pricing_data = calculate_combined_product_pricing(db_name, product_id)
        if pricing_data:
            all_pricings.append(pricing_data)
    
    conn.close()
    return all_pricings


def get_combined_product_with_largest_total_discount(db_name: str = "combined_products_final.db"):
    """할인 총액이 가장 큰 결합상품과 그 각각의 개별 요금제 이름을 조회합니다."""
    all_pricings = get_all_combined_product_pricings(db_name)

    if not all_pricings:
        return "데이터베이스에 결합 상품 정보가 없습니다."

    # 할인 총액이 가장 큰 상품 찾기
    largest_discount_product = max(all_pricings, key=lambda x: x['total_discount_amount'])

    result = {
        "message": "할인 총액이 가장 큰 결합 상품",
        "combined_product_name": largest_discount_product['combined_product_name'],
        "company_name": largest_discount_product['company_name'],
        "total_discount_amount": largest_discount_product['total_discount_amount'],
        "associated_plans": [plan['name'] for plan in largest_discount_product['associated_plans']],
        "calculated_pricing_details": largest_discount_product # 전체 계산 결과 포함
    }
    return result

def get_combined_product_with_lowest_final_price(db_name: str = "combined_products_final.db"):
    """할인 후 가격이 가장 저렴한 결합상품과 그 각각의 개별 요금제 이름을 조회합니다."""
    all_pricings = get_all_combined_product_pricings(db_name)

    if not all_pricings:
        return "데이터베이스에 결합 상품 정보가 없습니다."

    # 할인 후 가격이 가장 저렴한 상품 찾기
    # 최종 가격이 0원 이하인 경우는 제외하고, 유효한 가격 중에서 가장 저렴한 것을 찾음
    valid_pricings = [p for p in all_pricings if p['final_price'] > 0]
    if not valid_pricings:
        return "할인 후 가격이 유효한 결합 상품이 없습니다."

    lowest_price_product = min(valid_pricings, key=lambda x: x['final_price'])

    result = {
        "message": "할인 후 가격이 가장 저렴한 결합 상품",
        "combined_product_name": lowest_price_product['combined_product_name'],
        "company_name": lowest_price_product['company_name'],
        "final_price": lowest_price_product['final_price'],
        "total_base_fee": lowest_price_product['total_base_fee'],
        "total_discount_amount": lowest_price_product['total_discount_amount'],
        "associated_plans": [plan['name'] for plan in lowest_price_product['associated_plans']],
        "calculated_pricing_details": lowest_price_product
    }
    return result

def get_combined_product_with_highest_base_fee(db_name: str = "combined_products_final.db"):
    """할인 전 가격이 가장 비싼 결합상품과 각각의 개별 요금제 이름을 조회합니다."""
    all_pricings = get_all_combined_product_pricings(db_name)

    if not all_pricings:
        return "데이터베이스에 결합 상품 정보가 없습니다."

    # 할인 전 가격이 가장 비싼 상품 찾기
    highest_base_fee_product = max(all_pricings, key=lambda x: x['total_base_fee'])

    result = {
        "message": "할인 전 가격이 가장 비싼 결합 상품",
        "combined_product_name": highest_base_fee_product['combined_product_name'],
        "company_name": highest_base_fee_product['company_name'],
        "total_base_fee": highest_base_fee_product['total_base_fee'],
        "associated_plans": [plan['name'] for plan in highest_base_fee_product['associated_plans']],
        "calculated_pricing_details": highest_base_fee_product
    }
    return result


# --- 테스트 실행 (main 블록은 실제 환경에 맞게 조정 필요) ---
if __name__ == "__main__":
    db_name = "combined_products_final.db"
    
    # 이전에 실행한 insert_example_data_v2 함수가 이미 db를 채웠다고 가정
    # 필요하다면 여기에 데이터 삽입 로직을 다시 호출할 수 있음

    print("--- 모든 결합 상품 가격 정보 계산 ---")
    all_combined_product_pricings = get_all_combined_product_pricings(db_name)
    for pricing in all_combined_product_pricings:
        print(f"상품명: {pricing['combined_product_name']} (회사: {pricing['company_name']})")
        print(f"  총 기본 요금: {pricing['total_base_fee']}원")
        print(f"  총 할인액: {pricing['total_discount_amount']}원")
        print(f"  최종 가격: {pricing['final_price']}원")
        print(f"  포함된 요금제: {', '.join([plan['name'] for plan in pricing['associated_plans']])}\n")

    print("\n" + "="*50 + "\n")

    # 1. 할인 총액이 가장 큰 결합상품 조회
    result_largest_discount = get_combined_product_with_largest_total_discount(db_name)
    print(result_largest_discount)
    print("\n" + "="*50 + "\n")

    # 2. 할인 후 가격이 가장 저렴한 결합상품 조회
    result_lowest_price = get_combined_product_with_lowest_final_price(db_name)
    print(result_lowest_price)
    print("\n" + "="*50 + "\n")

    # 3. 할인 전 가격이 가장 비싼 결합상품 조회
    result_highest_base_fee = get_combined_product_with_highest_base_fee(db_name)
    print(result_highest_base_fee)