import sqlite3
import pandas as pd

def get_db_connection():
    return sqlite3.connect("combined_products.db")

def fetch_top_discount_total_product():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            cp.id,
            cp.name,
            SUM(d.discount_value) AS total_discount
        FROM CombinedProduct cp
        JOIN Discount d ON cp.id = d.combined_product_id
        GROUP BY cp.id
        ORDER BY total_discount DESC
        LIMIT 1
    """)
    top = cursor.fetchone()
    if not top:
        return None, []

    cp_id, name, total_discount = top
    # 할인된 요금제들만 가져오기
    cursor.execute("""
        SELECT sp.name, sp.fee
        FROM Discount d
        JOIN ServicePlan sp ON d.plan_id = sp.id
        WHERE d.combined_product_id = ?
    """, (cp_id,))
    plans = cursor.fetchall()
    conn.close()
    return {"product_name": name, "total_discount": total_discount}, plans

def fetch_cheapest_final_price_product():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            cp.id,
            cp.name,
            SUM(sp.fee) - IFNULL(SUM(d.discount_value), 0) AS final_price
        FROM CombinedProduct cp
        JOIN CombinedProductServicePlan cpsp ON cp.id = cpsp.combined_product_id
        JOIN ServicePlan sp ON cpsp.service_plan_id = sp.id
        LEFT JOIN Discount d ON d.plan_id = sp.id AND d.combined_product_id = cp.id
        GROUP BY cp.id
        ORDER BY final_price ASC
        LIMIT 1
    """)
    top = cursor.fetchone()
    if not top:
        return None, []

    cp_id, name, final_price = top
    # 할인 적용된 요금제들만 가져오기
    cursor.execute("""
        SELECT sp.name, sp.fee
        FROM Discount d
        JOIN ServicePlan sp ON d.plan_id = sp.id
        WHERE d.combined_product_id = ?
    """, (cp_id,))
    plans = cursor.fetchall()
    conn.close()
    return {"product_name": name, "final_price": final_price}, plans

def fetch_most_expensive_original_price_product():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            cp.id,
            cp.name,
            SUM(sp.fee) AS original_price
        FROM CombinedProduct cp
        JOIN CombinedProductServicePlan cpsp ON cp.id = cpsp.combined_product_id
        JOIN ServicePlan sp ON cpsp.service_plan_id = sp.id
        GROUP BY cp.id
        ORDER BY original_price DESC
        LIMIT 1
    """)
    top = cursor.fetchone()
    if not top:
        return None, []

    cp_id, name, original_price = top
    # 전체 연결된 요금제들 가져오기
    cursor.execute("""
        SELECT sp.name, sp.fee
        FROM CombinedProductServicePlan cpsp
        JOIN ServicePlan sp ON cpsp.service_plan_id = sp.id
        WHERE cpsp.combined_product_id = ?
    """, (cp_id,))
    plans = cursor.fetchall()
    conn.close()
    return {"product_name": name, "original_price": original_price}, plans

# 실행 및 출력
discount_info, discount_plans = fetch_top_discount_total_product()
cheapest_info, cheapest_plans = fetch_cheapest_final_price_product()
expensive_info, expensive_plans = fetch_most_expensive_original_price_product()

df = pd.DataFrame([
    {
        "유형": "할인 총액 최대",
        "상품명": discount_info["product_name"],
        "금액": discount_info["total_discount"],
        "요금제 목록": ", ".join(name for name, _ in discount_plans)
    },
    {
        "유형": "할인 후 최저가",
        "상품명": cheapest_info["product_name"],
        "금액": cheapest_info["final_price"],
        "요금제 목록": ", ".join(name for name, _ in cheapest_plans)
    },
    {
        "유형": "원가 최고가",
        "상품명": expensive_info["product_name"],
        "금액": expensive_info["original_price"],
        "요금제 목록": ", ".join(name for name, _ in expensive_plans)
    },
])

print(df)
