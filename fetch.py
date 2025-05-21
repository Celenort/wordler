from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"  # 0=모두 출력, 1=INFO 숨김, 2=WARNING 숨김, 3=ERROR만 표시


def fetch_todays_word():
    global TODAYS_WORD
    driver = None
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # 창 없이 실행
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--enable-unsafe-swiftshader")
    options.add_argument("--remote-debugging-port=9222")



    #driver = webdriver.Chrome('/usr/local/bin/chromedriver')
    driver_path = ChromeDriverManager().install()
    #correct_driver_path = os.path.join(os.path.dirname(driver_path), "chromedriver.exe")
    driver = webdriver.Chrome(service=Service(executable_path=driver_path), options=options)
    driver.get("https://www.nytimes.com/games/wordle/index.html")

    time.sleep(10)  # 페이지 로드 대기

    # 맨 처음 뜨는 "We've updated our Terms" 팝업 닫기
    try:
        button = driver.find_element(By.CLASS_NAME, "purr-blocker-card__button")
        button.click()
        time.sleep(2.5)
        print(f"[INFO] 초기 팝업 제거")
    except Exception as e:
        print(f"[INFO] 초기 팝업이 없거나 무시함: {e}")

    # "Play" 버튼 클릭
        # Play 버튼 클릭 (Welcome-module_button + data-testid=Play)
    try:
        all_buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in all_buttons:
            class_name = btn.get_attribute("class")
            data_testid = btn.get_attribute("data-testid")
            if class_name and class_name.startswith("Welcome-module_button") and data_testid == "Play":
                btn.click()
                time.sleep(2.5)
                break
        print(f"[INFO] Play 버튼 클릭")
    except Exception as e:
        print(f"[INFO] Play 버튼 무시 또는 없음: {e}")

    # 광고 Skip 버튼 클릭 (있을 경우)
    try:
        all_buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in all_buttons:
            class_name = btn.get_attribute("class")
            if class_name and class_name.startswith("Skip-module_skipInfo"):
                btn.click()
                print("[INFO] 광고 Skip 버튼 클릭 완료")
                time.sleep(2.5)
                break
    except Exception as e:
        print(f"[INFO] 광고 Skip 버튼 없음 또는 무시: {e}")

    # 튜토리얼 창 닫기 (있을 경우)
    try:
        close_icon = driver.find_element(By.CSS_SELECTOR, 'svg[data-testid=\"icon-close\"]')
        close_icon.click()
        print("[INFO] 튜토리얼 창 닫기 완료")
        time.sleep(1)
    except Exception as e:
        print(f"[INFO] 튜토리얼 창 없음 또는 무시: {e}")
    
    wrong_word = "xviii"
    for _ in range(6):
        for letter in wrong_word:
            driver.find_element(By.TAG_NAME, "body").send_keys(letter)
            time.sleep(0.1)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ENTER)
        time.sleep(3)

    # 6번 입력 후, 구독(subscribe) 팝업 닫기 (있을 경우)
    try:
        subscribe_close_icon = driver.find_element(By.CSS_SELECTOR, 'svg[data-testid=\"icon-close\"]')
        subscribe_close_icon.click()
        print("[INFO] 구독 창 닫기 완료")
        time.sleep(2.5)
    except Exception as e:
        print(f"[INFO] 구독 창 없음 또는 무시")# : {e}")

    try:
        toast_div = driver.find_element(By.CSS_SELECTOR, "div[class^='Toast-module_toast__']")
        toast_text = toast_div.text.strip()
        print(f"[INFO] Toast 텍스트: {toast_text.lower()}")
        return toast_text.lower()
    except Exception as e:
        print(f"[ERROR] Toast 메시지를 읽을 수 없습니다: {e}")
    driver.quit()
