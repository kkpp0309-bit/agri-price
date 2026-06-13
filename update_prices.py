#!/usr/bin/env python3
"""
อัพเดทราคาสินค้าเกษตรใน index.html
ดึงข้อมูลจาก MOC Open Data API (กระทรวงพาณิชย์)
"""

import requests
import json
import re
from datetime import date, timedelta

TODAY = date.today()
FROM_DATE = (TODAY - timedelta(days=14)).isoformat()
TO_DATE = TODAY.isoformat()

# ชื่อที่แสดงในเว็บ → keyword ค้นหาใน MOC API
PRODUCT_MAP = {
    "ข้าวเปลือกเจ้า":        "ข้าวเจ้า",
    "ยางพาราแผ่นดิบ":        "ยางพารา",
    "มันสำปะหลัง":           "มันสำปะหลัง",
    "อ้อย":                   "อ้อย",
    "ปาล์มน้ำมัน":           "ปาล์ม",
    "หอมใหญ่":               "หอมใหญ่",
    "พริกชี้ฟ้า":             "พริกชี้ฟ้า",
    "กะหล่ำปลี":             "กะหล่ำปลี",
    "กล้วยหอม":              "กล้วยหอม",
    "มะม่วงน้ำดอกไม้":       "มะม่วง",
    "สุกรมีชีวิต":            "สุกร",
    "ไก่เนื้อมีชีวิต":        "ไก่",
    "โคมีชีวิต":              "โค",
    "ไข่ไก่ เบอร์ 2":        "ไข่ไก่",
    "น้ำนมดิบ":              "นม",
    "กุ้งขาวแวนนาไม":        "กุ้ง",
    "ปลานิลสด":              "ปลานิล",
    "ปลาทู":                 "ปลาทู",
    "ปลาหมึกกล้วย":          "ปลาหมึก",
    "ปูม้า":                  "ปูม้า",
}

API_BASE = "https://dataapi.moc.go.th"


def get_product_id(keyword: str) -> str | None:
    try:
        r = requests.get(
            f"{API_BASE}/gis-products",
            params={"keyword": keyword},
            timeout=15,
        )
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            if isinstance(data, list) and data:
                return data[0].get("product_id")
    except Exception as e:
        print(f"  [!] get_product_id({keyword}): {e}")
    return None


def get_price(product_id: str) -> float | None:
    try:
        r = requests.get(
            f"{API_BASE}/gis-product-price",
            params={
                "product_id": product_id,
                "from_date": FROM_DATE,
                "to_date": TO_DATE,
            },
            timeout=15,
        )
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            if isinstance(data, dict):
                lo = data.get("price_min_avg") or 0
                hi = data.get("price_max_avg") or 0
                if hi > 0:
                    return (lo + hi) / 2
    except Exception as e:
        print(f"  [!] get_price({product_id}): {e}")
    return None


def format_price(value: float, display_name: str) -> str:
    """จัดรูปแบบราคาให้เหมาะสมกับสินค้า"""
    # สินค้าที่นับเป็น ตัน/ตัน (คูณ 1000)
    if display_name in ("ข้าวเปลือกเจ้า", "อ้อย") and value < 100:
        value *= 1000
    if value >= 1000:
        return f"{value:,.0f}"
    if value < 1:
        return f"{value:.2f}"
    return f"{value:.2f}"


def update_html(prices: dict) -> int:
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    updated = 0
    for display_name, new_price in prices.items():
        if new_price is None:
            continue

        price_str = format_price(new_price, display_name)

        # จับ: ชื่อสินค้า → ภายใน <tr> เดียวกัน → <td><strong>???</strong>
        pattern = (
            rf"({re.escape(display_name)}"
            rf"(?:(?!<\/tr>).)*?<td><strong>)"
            rf"[^<]+"
            rf"(<\/strong>)"
        )
        new_html, n = re.subn(pattern, rf"\g<1>{price_str}\g<2>", html, flags=re.DOTALL)
        if n > 0:
            html = new_html
            updated += 1
            print(f"  ✓ {display_name}: {price_str}")
        else:
            print(f"  ✗ ไม่พบ pattern: {display_name}")

    # อัพเดทวันที่อัพเดทในหน้าเว็บ (ถ้ามี)
    html = re.sub(
        r"(อัพเดท:\s*)\d{4}-\d{2}-\d{2}",
        rf"\g<1>{TODAY.isoformat()}",
        html,
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    return updated


def load_previous_prices() -> dict:
    try:
        with open("prices.json", "r", encoding="utf-8") as f:
            return json.load(f).get("products", {})
    except Exception:
        return {}


def save_prices_json(prices: dict):
    data = {
        "updated": TODAY.isoformat(),
        "source": "MOC Open Data — dataapi.moc.go.th",
        "products": {k: v for k, v in prices.items() if v is not None},
    }
    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"บันทึก prices.json ({len(data['products'])} สินค้า)")


def main():
    print(f"=== อัพเดทราคาสินค้าเกษตร {TODAY} ===")
    prev = load_previous_prices()
    prices = {}

    for display_name, keyword in PRODUCT_MAP.items():
        print(f"[{display_name}] ค้นหา: {keyword}")
        pid = get_product_id(keyword)
        if pid:
            price = get_price(pid)
            prices[display_name] = price
        else:
            # ใช้ราคาเดิมถ้าดึงใหม่ไม่ได้
            prices[display_name] = prev.get(display_name)
            print(f"  → ใช้ราคาเดิม: {prices[display_name]}")

    n = update_html(prices)
    print(f"\nอัพเดทใน HTML: {n}/{len(prices)} สินค้า")
    save_prices_json(prices)
    print("เสร็จสิ้น ✓")


if __name__ == "__main__":
    main()
