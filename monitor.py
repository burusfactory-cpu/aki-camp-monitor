import os
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ==============================
# 設定
# ==============================

# ヒルビリーキャンピング監視ページ
URL = "https://hillbilly-camping.com/reserve/"

# ntfyトピック
NTFY_TOPIC = os.getenv("NTFY_TOPIC")

# 前回状態保存ファイル
STATE_FILE = "last_state.txt"

# 通信タイムアウト
TIMEOUT = 10


# ==============================
# 通信用セッション
# ==============================

def create_session():

    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=3,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504
        ],
        allowed_methods=["GET", "POST"]
    )

    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()

    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


session = create_session()


# ==============================
# 予約ページ取得
# ==============================

def get_page_text():

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(iPhone; CPU iPhone OS 18_0 like Mac OS X) "
            "AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) "
            "Version/18.0 Mobile/15E148 Safari/604.1"
        ),
        "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8",
        "Cache-Control": "no-cache"
    }

    print("ヒルビリーキャンピングへ接続します")

    try:

        response = requests.get(
            URL,
            headers=headers,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        print(
            f"ページ取得成功 HTTP {response.status_code}"
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # script/style等を除外
        for tag in soup(
            ["script", "style", "noscript"]
        ):
            tag.decompose()

        text = soup.get_text(
            " ",
            strip=True
        )

        if len(text) < 100:
            raise RuntimeError(
                "取得したページ内容が短すぎます"
            )

                print("TEST カレンダー9/1取得 =", "9/1" in text)

        return text

    except requests.exceptions.Timeout:

        print(
            "接続がタイムアウトしました。"
            "今回は監視を終了します。"
        )

        return None

    except requests.exceptions.RequestException as e:

        print(
            f"ページ取得エラー: {e}"
        )

        return None

    except Exception as e:

        print(
            f"解析エラー: {e}"
        )

        return None


# ==============================
# ntfy通知
# ==============================

def send_notification():

    if not NTFY_TOPIC:

        print(
            "NTFY_TOPICが設定されていません"
        )

        return

    message = (
        "ヒルビリーキャンピングの予約ページに"
        "変化がありました。\n\n"
        "キャンセルによる空きが出た可能性があります。\n\n"
        f"{URL}"
    )

    try:

        response = session.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title":
                    "ヒルビリーキャンピング 空き状況通知",
                "Priority":
                    "high",
                "Tags":
                    "camping"
            },
            timeout=20
        )

        response.raise_for_status()

        print("ntfy通知成功")

    except requests.exceptions.RequestException as e:

        print(
            f"ntfy通知失敗: {e}"
        )


# ==============================
# メイン処理
# ==============================

def main():

    print(
        "===== Camp Availability Monitor ====="
    )

    page_text = get_page_text()

    # サイト取得に失敗した場合
    # Actionsをエラー終了させず次回へ
    if page_text is None:

        print(
            "今回はページを取得できなかったため"
            "比較処理をスキップします。"
        )

        return

    # ページ内容をハッシュ化
    current_hash = hashlib.sha256(
        page_text.encode("utf-8")
    ).hexdigest()

    print(
        f"現在のハッシュ: {current_hash[:12]}"
    )

    # 初回
    if not os.path.exists(STATE_FILE):

        with open(
            STATE_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(current_hash)

        print(
            "初回チェック完了。"
            "現在の状態を保存しました。"
        )

        return

    # 前回状態
    with open(
        STATE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        old_hash = f.read().strip()

    print(
        f"前回のハッシュ: {old_hash[:12]}"
    )

    # ページ変化あり
    if current_hash != old_hash:

        print(
            "予約ページに変化を検出しました！"
        )

        send_notification()

        with open(
            STATE_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(current_hash)

    else:

        print(
            "変化なし"
        )

    print(
        "===== チェック終了 ====="
    )


if __name__ == "__main__":

    main()
