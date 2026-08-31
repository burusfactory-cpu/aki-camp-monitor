import os
import json
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ==========================================
# 設定
# ==========================================

HOTEL_CODE = "0000003596"

API_URL = (
    "https://search-api.d-reserve.jp/"
    f"v1/search/hotels/{HOTEL_CODE}/calendar"
)

NTFY_TOPIC = os.getenv("NTFY_TOPIC")

STATE_FILE = "last_state.txt"

# 今月 + 次の2か月を監視
MONITOR_MONTHS = 3

TIMEOUT = 15


# ==========================================
# 月計算
# ==========================================

def get_target_months():
    now = datetime.now(ZoneInfo("Asia/Tokyo"))

    year = now.year
    month = now.month

    result = []

    for i in range(MONITOR_MONTHS):
        m = month + i
        y = year

        while m > 12:
            m -= 12
            y += 1

        result.append(f"{y}{m:02d}")

    return result


# ==========================================
# API取得
# ==========================================

def get_calendar(month):
    params = {
        "fromYM": month,
        "toYM": month,
        "lodgerCode": "0",
        "lodgerNum": "1",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) "
            "Version/18.0 Mobile/15E148 Safari/604.1"
        )
    }

    for attempt in range(1, 4):
        try:
            print(
                f"{month} の空室APIを確認します "
                f"({attempt}/3)"
            )

            response = requests.get(
                API_URL,
                params=params,
                headers=headers,
                timeout=TIMEOUT,
            )

            response.raise_for_status()

            print(
                f"{month} API取得成功 "
                f"HTTP {response.status_code}"
            )

            return response.json()

        except requests.exceptions.RequestException as e:
            print(
                f"{month} API取得失敗 "
                f"({attempt}/3): {e}"
            )

            if attempt < 3:
                time.sleep(3)

        except ValueError as e:
            print(f"JSON解析失敗: {e}")
            return None

    return None


# ==========================================
# 空室データ解析
# ==========================================

def extract_availability(data):
    availability = {}

    if not data:
        return availability

    rooms = data.get("data", [])

    today = datetime.now(
        ZoneInfo("Asia/Tokyo")
    ).date()

    for room in rooms:
        room_code = room.get("code", "")
        room_name = room.get(
            "name",
            room_code or "名称不明"
        )

        daily_list = room.get(
            "dailySalesStatusList",
            []
        )

        for day in daily_list:
            sales_date = day.get("salesDate")

            if not sales_date:
                continue

            try:
                date_obj = datetime.strptime(
                    sales_date,
                    "%Y-%m-%d"
                ).date()
            except ValueError:
                continue

            # 過去の日付は監視しない
            if date_obj < today:
                continue

            stock_num = day.get("stockNum", 0) or 0
            sales_available = day.get(
                "salesAvailable",
                False
            )

            # どちらかが空室を示せば空きと判定
            is_available = (
                sales_available is True
                or stock_num > 0
            )

            key = f"{room_code}|{sales_date}"

            availability[key] = {
                "room_code": room_code,
                "room_name": room_name,
                "date": sales_date,
                "available": is_available,
                "stock_num": stock_num,
                "stock_status": day.get(
                    "stockStatus",
                    ""
                ),
            }

    return availability


# ==========================================
# 前回状態
# ==========================================

def load_previous_state():
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception as e:
        print(f"前回状態の読込失敗: {e}")
        return None


def save_state(state):
    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            state,
            f,
            ensure_ascii=False,
            indent=2
        )


# ==========================================
# 新しい空室を検出
# ==========================================

def find_new_availability(
    previous,
    current
):
    new_slots = []

    if previous is None:
        return new_slots

    for key, current_info in current.items():
        if not current_info.get("available"):
            continue

        old_info = previous.get(key)

        # 前回存在しなかった空き
        if old_info is None:
            new_slots.append(current_info)
            continue

        # 前回は満室 → 今回は空室
        if not old_info.get(
            "available",
            False
        ):
            new_slots.append(current_info)

    return new_slots


# ==========================================
# ntfy通知
# ==========================================

def send_notification(slots):
    if not NTFY_TOPIC:
        print(
            "NTFY_TOPICが設定されていません。"
        )
        return

    if not slots:
        return

    lines = [
        "ヒルビリーキャンピングに"
        "空きが出ました！",
        ""
    ]

    for slot in slots[:20]:
        date_text = slot["date"]

        try:
            d = datetime.strptime(
                date_text,
                "%Y-%m-%d"
            )

            date_text = (
                f"{d.month}/{d.day}"
            )
        except ValueError:
            pass

        stock_num = slot.get(
            "stock_num",
            0
        )

        lines.append(
            f"○ {date_text} "
            f"{slot['room_name']} "
            f"空き{stock_num}"
        )

    if len(slots) > 20:
        lines.append(
            f"ほか {len(slots) - 20}件"
        )

    lines.extend([
        "",
        "予約ページ",
        "https://hillbilly-camping.com/reserve/"
    ])

    message = "\n".join(lines)

    try:
        response = requests.post(
            "https://ntfy.sh/",
            json={
                "topic": NTFY_TOPIC,
                "message": message,
                "title": "ヒルビリーキャンピング 空き発生",
                "priority": 4,
                "tags": ["camping"],
                "click": "https://hillbilly-camping.com/reserve/"
            },
            timeout=15
        )

        response.raise_for_status()

        print("ntfy通知成功")

    except requests.exceptions.RequestException as e:
        print(f"ntfy通知失敗: {e}")


# ==========================================
# メイン
# ==========================================

def main():
    print(
        "===== Hillbilly Availability Monitor ====="
    )

    months = get_target_months()

    print(
        "監視対象月:",
        ", ".join(months)
    )

    current_state = {}

    successful_months = 0

    for month in months:
        data = get_calendar(month)

        if data is None:
            continue

        successful_months += 1

        month_state = extract_availability(
            data
        )

        current_state.update(
            month_state
        )

    if successful_months == 0:
        print(
            "全ての月でAPI取得に失敗しました。"
        )
        print(
            "前回状態は変更せず終了します。"
        )
        return

    print(
        f"監視枠数: "
        f"{len(current_state)}"
    )

    available_now = [
        info
        for info in current_state.values()
        if info.get("available")
    ]

    print(
        f"現在の空室数: "
        f"{len(available_now)}"
    )

    previous_state = load_previous_state()

    # 初回は通知しない
    if previous_state is None:
        print(
            "初回監視です。"
            "現在の空室状態を保存します。"
        )

        save_state(current_state)

        print(
            "===== 初回チェック終了 ====="
        )
        return

    new_slots = find_new_availability(
        previous_state,
        current_state
    )

    if new_slots:
        print(
            f"新しい空室を "
            f"{len(new_slots)}件 検出しました！"
        )

        for slot in new_slots:
            print(
                "空室:",
                slot["date"],
                slot["room_name"],
                "stock:",
                slot["stock_num"]
            )

        send_notification(
            new_slots
        )

    else:
        print(
            "新しい空室はありません"
        )

    save_state(
        current_state
    )

    print(
        "状態を保存しました"
    )

    print(
        "===== チェック終了 ====="
    )


if __name__ == "__main__":
    main()
