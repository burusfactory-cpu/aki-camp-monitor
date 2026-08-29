from playwright.sync_api import sync_playwright
import json

URL = "https://hillbilly-camping.com/reserve/"


def main():
    print("===== Calendar API Test =====")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def check_response(response):
            if "/calendar" not in response.url:
                return

            print("===== CALENDAR API FOUND =====")
            print("STATUS:", response.status)
            print("URL:", response.url)

            try:
                data = response.json()

                print("===== JSON START =====")
                print(
                    json.dumps(
                        data,
                        ensure_ascii=False,
                        indent=2
                    )[:15000]
                )
                print("===== JSON END =====")

            except Exception as e:
                print("JSON取得失敗:", e)

                try:
                    print(
                        "本文:",
                        response.text()[:5000]
                    )
                except Exception as e2:
                    print("本文取得失敗:", e2)

        page.on("response", check_response)

        print("ヒルビリー予約ページを開きます")

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=60000
        )

        page.wait_for_timeout(5000)

        browser.close()

    print("===== TEST END =====")


if __name__ == "__main__":
    main()
