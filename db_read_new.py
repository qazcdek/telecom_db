import sqlite3
import hashlib # hash_id 함수가 다른 파일에 있다면 필요 없음
import itertools
from itertools import combinations, product, combinations_with_replacement
from typing import List, Dict, Any, Optional, Tuple

# db 연결
def get_db_connection(db_name: str = "combined_products.db"):
    """데이터베이스 연결을 반환합니다."""
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row  # 컬럼 이름으로 데이터 접근 가능하게 설정
    return conn

def classify_discount_type(cursor, discount_id: int) -> str:
    """해당 discount_id의 조건이 요금제 기반인지, 회선 수 기반인지, 혼합인지 판단"""
    cursor.execute("SELECT COUNT(*) FROM DiscountConditionByPlan WHERE discount_id = ?", (discount_id,))
    plan_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM DiscountConditionByLineCount WHERE discount_id = ?", (discount_id,))
    line_count = cursor.fetchone()[0]

    if plan_count > 0 and line_count > 0:
        return "mixed"
    elif plan_count > 0:
        return "plan_based"
    elif line_count > 0:
        return "line_based"
    else:
        return "simple"

# 
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
    
    # 'Mobile' 서비스 요금제 선택
    cursor.execute(f"""
        SELECT sp.name, sp.fee, sp.service_type
        FROM ServicePlan sp
        JOIN CombinedProductEligibility cpe ON sp.id = cpe.service_plan_id
        WHERE cpe.combined_product_id = ? AND sp.service_type = 'Mobile'
        ORDER BY sp.fee DESC
    """, (combined_product_id,))
    all_mobile_plan = cursor.fetchall()
    if all_mobile_plan:
        for mobile_plan in all_mobile_plan:
            associated_plans.append({"name": mobile_plan['name'], "fee": mobile_plan['fee'], "service_type": mobile_plan['service_type']})
            total_base_fee += mobile_plan['fee']

    # 'Internet' 서비스 요금제 중 가장 비싼 요금제 선택
    cursor.execute(f"""
        SELECT sp.name, sp.fee, sp.service_type
        FROM ServicePlan sp
        JOIN CombinedProductEligibility cpe ON sp.id = cpe.service_plan_id
        WHERE cpe.combined_product_id = ? AND sp.service_type = 'Internet'
        ORDER BY sp.fee DESC
    """, (combined_product_id,))
    all_internet_plan = cursor.fetchall()
    if all_internet_plan:
        for internet_plan in all_internet_plan:
            associated_plans.append({"name": internet_plan['name'], "fee": internet_plan['fee'], "service_type": internet_plan['service_type']})
            total_base_fee += internet_plan['fee']
            
    # 'TV' 서비스 요금제 중 가장 비싼 요금제 선택
    # TV는 선택 상품인 경우가 많으므로, min_iptv_lines가 0인 경우에도 포함 여부는 비즈니스 로직에 따라 결정
    # 여기서는 일단 있다면 포함하는 것으로 가정 (할인 계산을 위함)
    cursor.execute(f"""
        SELECT sp.name, sp.fee, sp.service_type
        FROM ServicePlan sp
        JOIN CombinedProductEligibility cpe ON sp.id = cpe.service_plan_id
        WHERE cpe.combined_product_id = ? AND sp.service_type = 'TV'
        ORDER BY sp.fee DESC
    """, (combined_product_id,))
    all_tv_plan = cursor.fetchall()
    if all_tv_plan: # TV 요금제가 있다면 포함
        for tv_plan in all_tv_plan:
            associated_plans.append({"name": tv_plan['name'], "fee": tv_plan['fee'], "service_type": tv_plan['service_type']})
            total_base_fee += tv_plan['fee']


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


def get_all_combined_product_pricings(db_name: str = "combined_products.db") -> List[Dict[str, Any]]:
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


def get_combined_product_with_largest_total_discount(db_name: str = "combined_products.db"):
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

def get_combined_product_with_lowest_final_price(db_name: str = "combined_products.db"):
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

def get_combined_product_with_highest_base_fee(db_name: str = "combined_products.db"):
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

def classify_combined_product_discount_type(cursor, combined_product_id: str) -> str:
    cursor.execute("""
        SELECT COUNT(*) FROM Discount d
        JOIN DiscountConditionByPlan p ON d.id = p.discount_id
        WHERE d.combined_product_id = ?
    """, (combined_product_id,))
    has_plan = cursor.fetchone()[0] > 0

    cursor.execute("""
        SELECT COUNT(*) FROM Discount d
        JOIN DiscountConditionByLineCount l ON d.id = l.discount_id
        WHERE d.combined_product_id = ?
    """, (combined_product_id,))
    has_line = cursor.fetchone()[0] > 0

    if has_plan and has_line:
        return "mixed"
    elif has_plan:
        return "plan_based"
    elif has_line:
        return "line_based"
    else:
        return "none"
    
def search_combined_product_combinations(
    db_path: str,
    *,
    min_counts: Dict[str, int] = {},
    max_counts: Dict[str, int] = {},
    required_plan_names: List[str] = [],
    sort_by: str = "max_discount_amount",
    limit: int = 10,
    only_products: bool = False,
    with_combinations: bool = False
) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM CombinedProduct")
    all_combined_products = cursor.fetchall()

    total_results = []

    for combined_product in all_combined_products:
        combined_product_id = combined_product["id"]
        combined_product_name = combined_product["name"]

        discount_type = classify_discount_type(cursor, combined_product_id)

        plans_by_type: Dict[str, List[Dict[str, Any]]] = {
            "Mobile": [], "Internet": [], "TV": []
        }
        cursor.execute("""
            SELECT sp.id, sp.name, sp.fee, sp.service_type
            FROM ServicePlan sp
            JOIN CombinedProductEligibility cpe ON sp.id = cpe.service_plan_id
            WHERE cpe.combined_product_id = ?
        """, (combined_product_id,))
        for row in cursor.fetchall():
            service_type = row["service_type"]
            if service_type in plans_by_type:
                plans_by_type[service_type].append(dict(row))

        # 필터: required_plan_names가 주어진 경우 해당 요금제를 포함하지 않는 상품은 건너뜀
        if required_plan_names:
            all_plan_names = [plan["name"] for plans in plans_by_type.values() for plan in plans]
            if not all(name in all_plan_names for name in required_plan_names):
                continue

        all_type_combinations = []
        for service_type, plans in plans_by_type.items():
            max_count = max_counts.get(service_type, 0)
            min_count = min_counts.get(service_type, 0)
            service_type_combos = []
            for r in range(min_count, max_count + 1):
                service_type_combos.extend(combinations_with_replacement(plans, r))
            all_type_combinations.append(service_type_combos)

        all_combinations = []
        for combo_set in product(*all_type_combinations):
            combined = []
            for sublist in combo_set:
                combined.extend(sublist)
            all_combinations.append(combined)

        for combo in all_combinations:
            combo_plan_names = {plan["name"] for plan in combo}
    
            # ➤ 조합에 required_plan_names 중 적어도 하나는 포함되어야 함
            if required_plan_names and not any(name in combo_plan_names for name in required_plan_names):
                continue
            
            total_fee = sum(plan["fee"] for plan in combo)

            total_discount = 0
            for plan in combo:
                cursor.execute("""
                    SELECT dcbp.override_discount_value
                    FROM DiscountConditionByPlan dcbp
                    WHERE dcbp.service_plan_id = ? AND dcbp.discount_id IN (
                        SELECT id FROM Discount WHERE combined_product_id = ?
                    )
                """, (plan["id"], combined_product_id))
                discounts = cursor.fetchall()
                total_discount += sum(
                    [row["override_discount_value"] for row in discounts if row["override_discount_value"] is not None]
                )

            final_price = total_fee - total_discount
            result = {
                "combined_product_name": combined_product_name,
                "plans": combo,
                "total_base_fee": total_fee,
                "total_discount_amount": total_discount,
                "final_price": final_price,
                "discount_type": discount_type,
                "combined_product_id": combined_product_id
            }
            total_results.append(result)

    conn.close()

    if sort_by == "max_discount_amount":
        total_results.sort(key=lambda x: x["total_discount_amount"], reverse=True)
    elif sort_by == "min_final_price":
        total_results.sort(key=lambda x: x["final_price"])
    elif sort_by == "max_total_base_fee":
        total_results.sort(key=lambda x: x["total_base_fee"], reverse=True)

    if only_products:
        return list({r["combined_product_id"]: r for r in total_results}.values())[:limit]

    if not with_combinations:
        return total_results[:limit]

    return total_results[:limit]

# --- 테스트 실행 (main 블록은 실제 환경에 맞게 조정 필요) ---
if __name__ == "__main__":
    db_name = "combined_products.db"
    
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

    # 4. 모든 결합상품 중 할인액 상위 3개
    for sort_rule in ["max_discount_amount", "min_final_price"]:
        print("\n" + "="*50 + "\n")
        print(f"sort rule: {sort_rule}\n")
        total_results = search_combined_product_combinations(
            db_path="combined_products.db",
            max_counts={"Mobile": 2, "Internet": 3, "TV": 1},
            min_counts={"Mobile": 2, "Internet": 3, "TV": 1}, 
            required_plan_names=["요고 30"],
            sort_by=sort_rule,
            limit=3
        )

        for combo in total_results:
            print(f"  조합 ({combo['combined_product_name']}):")
            for plan in combo["plans"]:
                print(f"    - {plan['service_type']} | {plan['name']} | {plan['fee']}원")
            print(f"  총 기본 요금: {combo['total_base_fee']}원")
            print(f"  총 할인액: {combo['total_discount_amount']}원")
            print(f"  최종 가격: {combo['final_price']}원")
            print("--------")