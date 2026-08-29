from playwright.sync_api import sync_playwright

URL = "https://hillbilly-camping.com/reserve/"


def main():
    print("===== Network Test =====")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def log_response(response):
            url = response.url.lower()

            if (
                "reserve" in url
                or "calendar" in url
                or "room" in url
                or "availability" in url
                or "d-reserve" in url
                or "api" in url
            ):
                print(
                    "RESPONSE",
                    response.status,
                    response.request.resource_type,
                    response.url
                )

        page.on("response", log_response)

        print("ヒルビリー予約ページを開きます")

        page.goto(
            URL,
            wait_until="networkidle",
            timeout=60000
        )

        page.wait_for_timeout(10000)

        print("ページタイトル:", page.title())
        print("===== Network Test END =====")

        browser.close()


if __name__ == "__main__":
    main()
