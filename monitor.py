from playwright.sync_api import sync_playwright

URL = "https://hillbilly-camping.com/reserve/"


def main():
    print("===== Playwright Calendar Test =====")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page(
            viewport={"width": 1280, "height": 2000}
        )

        print("ページを開きます")

        page.goto(
            URL,
            wait_until="domcontentloaded",
            timeout=30000
        )

        page.wait_for_timeout(5000)

        print("ページ表示完了")
        print("フレーム数:", len(page.frames))

        all_text = ""

        for i, frame in enumerate(page.frames):
            try:
                text = frame.locator("body").inner_text(timeout=5000)
                all_text += "\n" + text

                print(
                    f"FRAME {i}:",
                    frame.url,
                    "文字数:",
                    len(text)
                )

            except Exception as e:
                print(f"FRAME {i} 読み取り失敗:", e)

        print("9/1取得 =", "9/1" in all_text)
        print("9/2取得 =", "9/2" in all_text)
        print("空室取得 =", "空室" in all_text)

        print("----- カレンダー確認用 -----")

        for line in all_text.splitlines():
            if (
                "9/" in line
                or "区画" in line
                or "空室" in line
                or "満室" in line
            ):
                print(line[:200])

        browser.close()

    print("===== TEST END =====")


if __name__ == "__main__":
    main()
