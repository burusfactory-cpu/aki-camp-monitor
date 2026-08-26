import requests
from bs4 import BeautifulSoup
import hashlib
import os

# 監視する予約ページ
URL = "https://hillbilly-camping.com/reserve/?ym=202609"

# ntfyのトピック名
NTFY_TOPIC = os.getenv("NTFY_TOPIC")
if not NTFY_TOPIC:
    raise ValueError("NTFY_TOPIC is not set")

requests.post(
    f"https://ntfy.sh/{NTFY_TOPIC}",
    data="空きキャン通知テスト成功！".encode("utf-8")
)
# 前回のページ状態を保存するファイル
STATE_FILE = "last_state.txt"


def get_page_text():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(URL, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # ページ内の文字情報だけ取得
    text = soup.get_text(" ", strip=True)

    return text


def send_notification():
    message = (
        "ヒルビリーキャンピングの予約ページに変化がありました。\n"
        "キャンセルによる空きが出た可能性があります。\n"
        f"{URL}"
    )

    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={
            "Title": "キャンプ場 空き状況通知",
            "Priority": "high",
            "Tags": "camping"
        },
        timeout=30
    )


def main():
    page_text = get_page_text()

    # ページ内容からハッシュ値を作る
    current_hash = hashlib.sha256(
        page_text.encode("utf-8")
    ).hexdigest()

    # 初回実行
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f:
            f.write(current_hash)

        print("初回チェック完了")
        return

    # 前回の状態を読む
    with open(STATE_FILE, "r") as f:
        old_hash = f.read().strip()

    # ページに変化があった場合
    if current_hash != old_hash:
        print("予約ページに変化を検知しました")

        send_notification()

        with open(STATE_FILE, "w") as f:
            f.write(current_hash)

    else:
        print("変化なし")


if __name__ == "__main__":
    main()
