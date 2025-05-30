import os
from typing import List, Tuple, Dict, Any
import csv

from db_update import hash_id as generate_id

company_id_dictionary = dict.fromkeys(["skt", "kt", "lguplus", "others"])
for _idx, _k in enumerate(company_id_dictionary.keys):
    company_id_dictionary[_k] = _idx + 1 
# --- CSV 파일 저장 함수들 ---
def save_data_to_csv(data: List[Dict[str, Any]], file_path: str, fieldnames: List[str]):
    """주어진 데이터를 CSV 파일로 저장합니다."""
    # 디렉토리가 없으면 생성
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Data saved to {file_path}")

def save_combined_product_data_to_csv(data: List[Dict[str, Any]], file_path: str):
    fieldnames = [
        "id", "name", "company_id", "description",
        "min_mobile_lines", "max_mobile_lines",
        "min_internet_lines", "max_internet_lines",
        "min_iptv_lines", "max_iptv_lines",
        "join_condition", "applicant_scope", "application_channel", "url", "available"
    ]
    save_data_to_csv(data, file_path, fieldnames)

def save_service_plan_data_to_csv(data: List[Dict[str, Any]], file_path: str):
    fieldnames = [
        "id", "company_id", "service_type", "name", "fee", "description",
        "contract_period_months", "is_unlimited", "data_allowance_gb",
        "voice_allowance_min", "sms_allowance"
    ]
    save_data_to_csv(data, file_path, fieldnames)

def save_eligibility_data_to_csv(data: List[Dict[str, Any]], file_path: str):
    fieldnames = ["combined_product_id", "service_plan_id", "min_lines", "max_lines", "is_base_plan_required"]
    save_data_to_csv(data, file_path, fieldnames)

def save_discount_data_to_csv(data: List[Dict[str, Any]], file_path: str):
    fieldnames = [
        "id", "combined_product_id", "discount_name", "discount_type", "discount_value", "unit",
        "applies_to_service_type", "applies_to_line_sequence", "note"
    ]
    save_data_to_csv(data, file_path, fieldnames)

def save_discount_conditions_by_plan_to_csv(data: List[Dict[str, Any]], file_path: str):
    fieldnames = ["discount_id", "service_plan_id", "condition_text", "override_discount_value", "override_unit"]
    save_data_to_csv(data, file_path, fieldnames)

def save_discount_conditions_by_line_count_to_csv(data: List[Dict[str, Any]], file_path: str):
    fieldnames = [
        "discount_id", "min_applicable_lines", "max_applicable_lines",
        "override_discount_value", "override_unit", "applies_per_line"
    ]
    save_data_to_csv(data, file_path, fieldnames)

def save_benefits_data_to_csv(data: List[Dict[str, Any]], file_path: str):
    fieldnames = ["id", "combined_product_id", "benefit_type", "content", "condition"]
    save_data_to_csv(data, file_path, fieldnames)

# if __name__ == "__main__":
#     data_to_save_combined_product_data = [{}]
#     data_to_save_service_plan_data = [{}]
#     data_to_save_eligibility_data = [{}]
#     data_to_save_discount_data = [{}]
#     data_to_save_discount_conditions_by_plan = [{}]
#     data_to_save_discount_conditions_by_line_count = [{}]
#     data_to_save_benefits = [{}]


if __name__ == "__main__":
    # 회사 ID (KT 가정)
    company_name = "kt"
    company_kt_id = company_id_dictionary[company_name]
    
    # '신혼미리결합' 상품 ID
    combined_product_name = "신혼미리결합"
    combined_product_shinhohn_id = generate_id(f"{company_name}_{combined_product_name}")

    # 가상의 ServicePlan ID (실제로는 요금제별로 고유 ID가 필요)
    # 현재 텍스트에는 구체적인 요금제 이름과 요금이 없으므로 임의로 생성합니다.
    # 5G/LTE 77,000원 이상 요금제를 가정합니다.
    plan_5g_lte_77000_plus_id = generate_id("5G/LTE 77000원 이상 요금제")
    plan_internet_slim_id = generate_id("인터넷 슬림")


    # 1. CombinedProduct 데이터
    data_to_save_combined_product_data: List[Dict[str, Any]] = [
        {
            "id": combined_product_shinhohn_id,
            "name": "신혼미리결합",
            "company_id": company_kt_id, # 가정: KT의 ID
            "description": "예비/신혼 부부를 위한 결합 상품",
            "min_mobile_lines": 1, # '모바일만 2회선 결합' 언급으로 미니멈 1로 추정, 최소 2회선은 Mobile만 2회선 부분에서 고려
            "max_mobile_lines": None, # 정보 없음
            "min_internet_lines": 0, # '인터넷 상품 없이 모바일만 2회선 결합' 가능 언급
            "max_internet_lines": None, # 정보 없음
            "min_iptv_lines": 0, # 정보 없음
            "max_iptv_lines": None, # 정보 없음
            "join_condition": "예비/신혼 부부 (혼인신고 후 3년 이내), 명의당 1회 제한, 결합약정 기간 경과 시 할인 미제공",
            "applicant_scope": "예비/신혼 부부 명의의 인터넷, 집전화, 인터넷전화, TV, 모바일 상품",
            "application_channel": "신규/기변 고객 및 기존 고객 신청 가능",
            "url": None, # 텍스트에 URL 정보 없음
            "available": True
        }
    ]

    # 2. ServicePlan 데이터 (텍스트에서 직접적인 요금제 정보는 없지만, 언급된 요금제 기준으로 가정하여 생성)
    # 실제 요금제는 "5G/LTE 77,000원 이상 요금제"와 "인터넷 슬림"만 언급
    data_to_save_service_plan_data: List[Dict[str, Any]] = [
        {
            "id": plan_5g_lte_77000_plus_id,
            "company_id": company_kt_id,
            "service_type": "Mobile",
            "name": "5G/LTE 77,000원 이상 요금제",
            "fee": 77000, # 최소 금액으로 가정
            "description": "배우자 모바일 최대 반값 혜택을 위한 요금제",
            "contract_period_months": None,
            "is_unlimited": None,
            "data_allowance_gb": None,
            "voice_allowance_min": None,
            "sms_allowance": None
        },
        {
            "id": plan_internet_slim_id,
            "company_id": company_kt_id,
            "service_type": "Internet",
            "name": "인터넷 슬림",
            "fee": None, # 텍스트에 요금 정보 없음 (별도 조회 필요)
            "description": "모바일 2회선 결합 시 총액결합 할인 기준 상품",
            "contract_period_months": None,
            "is_unlimited": None,
            "data_allowance_gb": None,
            "voice_allowance_min": None,
            "sms_allowance": None
        }
    ]

    # 3. CombinedProductEligibility 데이터 (어떤 요금제가 결합될 수 있는지 명확하지 않으므로, 언급된 요금제 기반으로 추정)
    data_to_save_eligibility_data: List[Dict[str, Any]] = [
        {
            "combined_product_id": combined_product_shinhohn_id,
            "service_plan_id": plan_5g_lte_77000_plus_id,
            "min_lines": 1, # 배우자 포함 2회선이므로 각 1회선씩 가능
            "max_lines": 2, # 본인+배우자
            "is_base_plan_required": False # 특정 요금제 필수 여부 불확실
        },
        {
            "combined_product_id": combined_product_shinhohn_id,
            "service_plan_id": plan_internet_slim_id,
            "min_lines": 0, # 인터넷 없이 모바일만 결합 가능
            "max_lines": 1,
            "is_base_plan_required": False
        }
        # 인터넷, 집전화, 인터넷전화, TV 상품도 명시적으로 결합 가능하다고 되어 있으나,
        # 구체적인 요금제 정보가 없으므로 여기서는 포함하지 않음.
        # 필요하다면 추가적인 가상 요금제 ID를 생성하여 추가해야 함.
    ]

    # 4. Discount 데이터
    # 텍스트에 언급된 할인은 크게 두 가지: "배우자 모바일 최대 반값" (50%), "25% 결합할인" (본인), "총액결합할인" (배우자)
    # 그리고 "인터넷 슬림'상품 기준에 해당하는 총액결합 할인 금액 적용"
    
    discount_spouse_50_percent_id = generate_id("배우자 모바일 50% 할인")
    discount_self_25_percent_id = generate_id("본인 모바일 25% 할인")
    discount_mobile_only_6months_id = generate_id("모바일만 2회선 6개월 할인")

    data_to_save_discount_data: List[Dict[str, Any]] = [
        {
            "id": discount_spouse_50_percent_id,
            "combined_product_id": combined_product_shinhohn_id,
            "discount_name": "배우자 모바일 최대 반값 할인",
            "discount_type": "Percentage",
            "discount_value": 50,
            "unit": "%",
            "applies_to_service_type": "Mobile",
            "applies_to_line_sequence": "Spouse", # 배우자에게 적용
            "note": "5G/LTE 77,000원 이상 요금제 결합 시"
        },
        {
            "id": discount_self_25_percent_id,
            "combined_product_id": combined_product_shinhohn_id,
            "discount_name": "본인 모바일 25% 결합 할인",
            "discount_type": "Percentage",
            "discount_value": 25,
            "unit": "%",
            "applies_to_service_type": "Mobile",
            "applies_to_line_sequence": "Self", # 본인에게 적용
            "note": "본인 명의 모바일에 적용 가능"
        },
        {
            "id": discount_mobile_only_6months_id,
            "combined_product_id": combined_product_shinhohn_id,
            "discount_name": "모바일 2회선 6개월 한정 할인 (인터넷 미결합)",
            "discount_type": "Amount", # '총액결합 할인 금액'은 실제 금액이 필요하지만, 여기서는 타입만 지정
            "discount_value": 0, # 실제 금액 정보 없음 (DiscountConditionByPlan에서 오버라이드될 수 있음)
            "unit": "KRW",
            "applies_to_service_type": "Mobile",
            "applies_to_line_sequence": "All",
            "note": "인터넷 상품 없이 모바일만 2회선 결합 시 최대 6개월 제공, 인터넷 슬림 기준 총액결합 할인 적용"
        }
    ]

    # 5. DiscountConditionByPlan (요금제별 할인 조건)
    # "5G/LTE 77,000원 이상 요금제"에 대한 배우자 할인 조건
    data_to_save_discount_conditions_by_plan: List[Dict[str, Any]] = [
        {
            "discount_id": discount_spouse_50_percent_id,
            "service_plan_id": plan_5g_lte_77000_plus_id,
            "condition_text": "5G/LTE 77,000원 이상 요금제",
            "override_discount_value": 50, # 비율이므로 동일 값
            "override_unit": "%"
        },
        {
            "discount_id": discount_mobile_only_6months_id,
            "service_plan_id": plan_internet_slim_id, # '인터넷 슬림' 기준 총액결합 할인 금액을 적용함
            "condition_text": "인터넷 슬림 상품 기준",
            "override_discount_value": None, # 실제 할인 금액이 텍스트에 없음. 이 값은 외부 데이터나 다른 로직으로 채워져야 함.
            "override_unit": "KRW"
        }
    ]

    # 6. DiscountConditionByLineCount (회선 수별 할인 조건)
    # 현재 텍스트에서는 직접적인 회선 수에 따른 "추가 할인"이 명시되어 있지 않음.
    # '모바일만 2회선 결합' 조건은 Discount 테이블의 `note`에 포함.
    data_to_save_discount_conditions_by_line_count: List[Dict[str, Any]] = []

    # 7. Benefits (혜택)
    benefit_join_condition_doc_id = generate_id("예비/신혼 부부 증빙서류")
    benefit_spouse_50_percent_summary_id = generate_id("배우자 모바일 최대 50% 할인 요약")
    benefit_internet_mobile_only_6months_id = generate_id("인터넷 없이 모바일만 6개월 할인")

    data_to_save_benefits: List[Dict[str, Any]] = [
        {
            "id": benefit_join_condition_doc_id,
            "combined_product_id": combined_product_shinhohn_id,
            "benefit_type": "ApplicationCondition",
            "content": "예비/신혼 부부의 경우 가족관계증빙서류 대신, 종이 청첩장, 예식장 계약서, 웨딩플래너 계약서, 주민등록등본(동거인표기 필수)으로 신혼미리결합(무선/유무선)에 가입 가능",
            "condition": "예비/신혼 부부 대상"
        },
        {
            "id": benefit_spouse_50_percent_summary_id,
            "combined_product_id": combined_product_shinhohn_id,
            "benefit_type": "Discount",
            "content": "5G/LTE 77,000원 이상 요금제를 함께 가입하시면, 배우자는 최대 반값에 이용하실 수 있습니다.",
            "condition": "5G/LTE 77,000원 이상 요금제 가입 시"
        },
        {
            "id": benefit_internet_mobile_only_6months_id,
            "combined_product_id": combined_product_shinhohn_id,
            "benefit_type": "Discount",
            "content": "인터넷 상품 없이 모바일만 2회선 결합할 경우 모바일 할인 혜택은 최대 6개월 간 제공받을 수 있습니다. (단, 예비/신혼부부 명의의 모바일 회선만 가입 가능하며, ‘인터넷 슬림‘상품 기준에 해당하는 총액결합 할인 금액을 적용하며 6개월 내 인터넷 상품을 가입하지 않으면 할인이 중단됩니다.)",
            "condition": "인터넷 미결합 모바일 2회선 시, 6개월 한정"
        }
    ]

    print("데이터 변수들이 성공적으로 생성되었습니다.")
    print("\n--- 생성된 데이터 미리보기 ---")
    print(f"data_to_save_combined_product_data: {data_to_save_combined_product_data}")
    print(f"data_to_save_service_plan_data: {data_to_save_service_plan_data}")
    print(f"data_to_save_eligibility_data: {data_to_save_eligibility_data}")
    print(f"data_to_save_discount_data: {data_to_save_discount_data}")
    print(f"data_to_save_discount_conditions_by_plan: {data_to_save_discount_conditions_by_plan}")
    print(f"data_to_save_discount_conditions_by_line_count: {data_to_save_discount_conditions_by_line_count}")
    print(f"data_to_save_benefits: {data_to_save_benefits}")

    # CSV 파일로 저장 (원하는 경우 주석 해제하여 실행)
    # save_combined_product_data_to_csv(data_to_save_combined_product_data, "data/combined_product.csv")
    # save_service_plan_data_to_csv(data_to_save_service_plan_data, "data/service_plan.csv")
    # save_eligibility_data_to_csv(data_to_save_eligibility_data, "data/eligibility.csv")
    # save_discount_data_to_csv(data_to_save_discount_data, "data/discount.csv")
    # save_discount_conditions_by_plan_to_csv(data_to_save_discount_conditions_by_plan, "data/discount_conditions_by_plan.csv")
    # save_discount_conditions_by_line_count_to_csv(data_to_save_discount_conditions_by_line_count, "data/discount_conditions_by_line_count.csv")
    # save_benefits_data_to_csv(data_to_save_benefits, "data/benefits.csv")
