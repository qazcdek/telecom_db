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

def inform_combined_product(db_name: str, combined_product_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    # 1. 결합 상품 정보 조회
    cursor.execute("""
        SELECT 
            cp.id, 
            cp.name, 
            cp.description, 
            c.name as company_name, 
            cp.max_mobile_lines, 
            cp.max_internet_lines, 
            cp.max_iptv_lines
        FROM CombinedProduct cp
        JOIN Company c ON cp.company_id = c.id
        WHERE cp.id = ?
    """, (combined_product_id,))
    product_info = cursor.fetchone()

    if not product_info:
        conn.close()
        return None

    # 2. RequiredBaseRole 조회: 결합상품에 요구되는 base_role들
    cursor.execute("""
        SELECT base_role, required_count
        FROM RequiredBaseRole
        WHERE combined_product_id = ?
    """, (combined_product_id,))
    required_roles = cursor.fetchall()

    base_roles_required = [
        {"base_role": row["base_role"], "required_count": row["required_count"]}
        for row in required_roles
    ]

    # 3. 결합 가능한 요금제 리스트 (서비스 타입별로)
    associated_mobile_plans = []
    associated_internet_plans = []
    associated_tv_plans = []

    cursor.execute("""
        SELECT sp.name, sp.fee, sp.service_type, cpe.base_role as base_role
        FROM ServicePlan sp
        JOIN CombinedProductEligibility cpe ON sp.id = cpe.service_plan_id
        WHERE cpe.combined_product_id = ?
        ORDER BY sp.fee DESC
    """, (combined_product_id,))
    all_plans = cursor.fetchall()

    for plan in all_plans:
        plan_info = {
            "name": plan["name"],
            "fee": plan["fee"],
            "service_type": plan["service_type"],
            "base_role": plan["base_role"]
        }
        if plan["service_type"] == "Mobile":
            associated_mobile_plans.append(plan_info)
        elif plan["service_type"] == "Internet":
            associated_internet_plans.append(plan_info)
        elif plan["service_type"] == "TV":
            associated_tv_plans.append(plan_info)

    conn.close()

    return {
        "combined_product_id": product_info['id'],
        "combined_product_name": product_info['name'],
        "company_name": product_info['company_name'],
        "required_base_roles": base_roles_required,
        "associated_mobile_plans": associated_mobile_plans,
        "associated_internet_plans": associated_internet_plans,
        "associated_tv_plans": associated_tv_plans,
    }


def get_all_combined_product_pricings(db_name: str = "combined_products.db") -> List[Dict[str, Any]]:
    """모든 결합 상품에 대해 정보를 반환합니다."""
    conn = get_db_connection(db_name)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM CombinedProduct")
    product_ids = [row['id'] for row in cursor.fetchall()]
    
    all_pricings = []
    for product_id in product_ids:
        pricing_data = inform_combined_product(db_name, product_id)
        if pricing_data:
            all_pricings.append(pricing_data)
    
    conn.close()
    return all_pricings

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

    all_combined_products = get_all_combined_product_pricings(db_name)

    total_results = []

    for combined_product in all_combined_products:
        combined_product_id = combined_product["combined_product_id"]
        combined_product_name = combined_product["combined_product_name"]

        discount_type = classify_discount_type(cursor, combined_product_id)

        plans_by_type: Dict[str, List[Dict[str, Any]]] = {
            "Mobile": [], "Internet": [], "TV": []
        }
        cursor.execute("""
            SELECT sp.id, sp.name, sp.fee, sp.service_type, cpe.base_role
            FROM ServicePlan sp
            JOIN CombinedProductEligibility cpe ON sp.id = cpe.service_plan_id
            WHERE cpe.combined_product_id = ?
        """, (combined_product_id,))
        for row in cursor.fetchall():
            service_type = row["service_type"]
            if service_type in plans_by_type:
                plan_info = dict(row) # sqlite3.Row 객체를 딕셔너리로 변환
                plan_info['base_role'] = row['base_role'] # ➤ 'base_role' 컬럼 값을 딕셔너리에 추가
                plans_by_type[service_type].append(plan_info)

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
        
        #############할인액 계산 v1#############
        for combo in all_combinations:
            combo_plan_names = {plan["name"] for plan in combo}
    
            # ➤ 조합에 required_plan_names 중 적어도 하나는 포함되어야 함
            if required_plan_names and not any(name in combo_plan_names for name in required_plan_names):
                continue

            total_fee = sum(plan["fee"] for plan in combo)

            total_discount = 0
            for plan in combo:
                cursor.execute("""
                    SELECT dcbp.override_discount_value, dcbp.override_unit, sp.fee
                    FROM DiscountConditionByPlan dcbp
                    JOIN ServicePlan sp ON sp.id = dcbp.service_plan_id
                    WHERE dcbp.service_plan_id = ? AND dcbp.discount_id IN (
                        SELECT id FROM Discount WHERE combined_product_id = ?
                    )
                """, (plan["id"], combined_product_id))
                discounts = cursor.fetchall()
                total_discount += sum(
                    [row["override_discount_value"] if row["override_unit"] == "KRW" else int(row["fee"] * row["override_discount_value"] / 100) for row in discounts if row["override_discount_value"] is not None]
                )
            
        # #############할인액 계산 v2#############
        # for combo in all_combinations: # 모든 조합에 대해
        #     combo_plan_names = {plan["name"] for plan in combo} # 결합상품 이름 가져오기

        #     # ➤ 조합에 required_plan_names 중 적어도 하나는 포함되어야 함
        #     if required_plan_names and not any(name in combo_plan_names for name in required_plan_names): # 보고 싶은 결합 상품 이 있거나 
        #         continue

        #     total_fee = sum(plan["fee"] for plan in combo)
        #     total_discount = 0

        #     # 콤보 내의 각 요금제에 대해 할인을 계산
        #     for plan in combo:
        #         current_plan_base_role = plan.get("base_role") # ➤ 요금제에 base_role 정보가 포함되어 있어야 함 (이전 단계에서 추가 완료된 것으로 가정)
        #         cursor.execute("""
        #             SELECT dcbp.override_discount_value
        #             FROM DiscountConditionByPlan dcbp
        #             WHERE dcbp.service_plan_id = ? AND dcbp.base_role = ? AND dcbp.discount_id IN (
        #                 SELECT id FROM Discount WHERE combined_product_id = ?
        #             )
        #         """, (plan["id"], current_plan_base_role, combined_product_id))
        #         discounts = cursor.fetchall()
        #         total_discount += sum(
        #             [row["override_discount_value"] for row in discounts if row["override_discount_value"] is not None]
        #         )

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
    # "combined_product_id": product_info['id'],
    # "combined_product_name": product_info['name'],
    # "company_name": product_info['company_name'],
    # "required_base_roles": base_roles_required,
    # "associated_mobile_plans": associated_mobile_plans,
    # "associated_internet_plans": associated_internet_plans,
    # "associated_tv_plans": associated_tv_plans,

    all_combined_product_pricings = get_all_combined_product_pricings(db_name)
    for pricing in all_combined_product_pricings:
        print(f"상품명: {pricing['combined_product_name']} (회사: {pricing['company_name']})\n")
        print(f"  결합 가능한 모바일 요금제: {', '.join([plan['name'] for plan in pricing['associated_mobile_plans']])}")
        print(f"  결합 가능한 인터넷 요금제: {', '.join([plan['name'] for plan in pricing['associated_internet_plans']])}")
        print(f"  결합 가능한 티비 요금제: {', '.join([plan['name'] for plan in pricing['associated_tv_plans']])}")
        print(f"  필수 조건: {', '.join(role['base_role'] + ': ' + str(role['required_count']) for role in pricing['required_base_roles'])}\n")

    print("\n" + "="*50 + "\n")

    # 4. 모든 결합상품 중 할인액 상위 3개
    for sort_rule in ["max_discount_amount", "min_final_price"]:
        print("\n" + "="*50 + "\n")
        print(f"sort rule: {sort_rule}\n")
        total_results = search_combined_product_combinations(
            db_path="combined_products.db",
            max_counts={"Mobile": 1, "Internet": 1, "TV": 0},
            min_counts={"Mobile": 1, "Internet": 1, "TV": 0}, 
            required_plan_names=["5G 초이스 프리미엄"],
            sort_by=sort_rule,
            limit=20
        )

        for combo in total_results:
            print(f"  조합 ({combo['combined_product_name']}):")
            for plan in combo["plans"]:
                print(f"    - {plan['service_type']} | {plan['name']} | {plan['fee']}원")
            print(f"  총 기본 요금: {combo['total_base_fee']}원")
            print(f"  총 할인액: {combo['total_discount_amount']}원")
            print(f"  최종 가격: {combo['final_price']}원")
            print("--------")