from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import os

DISPLAY_TODAYS_WORD_IN_CONSOLE=False

# Suppress TensorFlow log levels (0=all, 1=INFO hidden, 2=WARNING hidden, 3=ERROR only)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

def fetch_todays_word():
    global TODAYS_WORD
    driver = None
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")  # Run without GUI
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--enable-unsafe-swiftshader")
    options.add_argument("--remote-debugging-port=9222")

    driver_path = ChromeDriverManager().install()
    driver = webdriver.Chrome(service=Service(executable_path=driver_path), options=options)
    driver.get("https://www.nytimes.com/games/wordle/index.html")

    time.sleep(10)  # Wait for page to load

    # Close initial "We've updated our Terms" popup
    try:
        button = driver.find_element(By.CLASS_NAME, "purr-blocker-card__button")
        button.click()
        time.sleep(2.5)
        print(f"[INFO] Initial popup closed")
    except Exception as e:
        first_line = str(e).split('\n', 1)[0]

        print(f"[INFO] No initial popup or skipped: {first_line}")

    # Click "Play" button
    try:
        all_buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in all_buttons:
            class_name = btn.get_attribute("class")
            data_testid = btn.get_attribute("data-testid")
            if class_name and class_name.startswith("Welcome-module_button") and data_testid == "Play":
                btn.click()
                time.sleep(2.5)
                break
        print(f"[INFO] Clicked Play button")
    except Exception as e:
        first_line = str(e).split('\n', 1)[0]
        print(f"[INFO] No popup or skipped: {first_line}")

    # Click "Skip" button for ads if present
    try:
        all_buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in all_buttons:
            class_name = btn.get_attribute("class")
            if class_name and class_name.startswith("Skip-module_skipInfo"):
                btn.click()
                print("[INFO] Clicked Skip ad button")
                time.sleep(2.5)
                break
    except Exception as e:
        first_line = str(e).split('\n', 1)[0]
        print(f"[INFO] No Skip button or skipped: {first_line}")

    # Close tutorial screen if present
    try:
        close_icon = driver.find_element(By.CSS_SELECTOR, 'svg[data-testid="icon-close"]')
        close_icon.click()
        print("[INFO] Closed tutorial screen")
        time.sleep(1)
    except Exception as e:
        first_line = str(e).split('\n', 1)[0]
        print(f"[INFO] No tutorial screen or skipped: {first_line}")

    # Enter incorrect word multiple times to get the answer
    wrong_word = "xviii"
    for i in range(6):
        print(f"[INFO] Typing incorrect word attempt ({i + 1}/6)")
        for letter in wrong_word:
            driver.find_element(By.TAG_NAME, "body").send_keys(letter)
            time.sleep(0.1)
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ENTER)
        time.sleep(3)

    # Close subscription popup if present
    try:
        subscribe_close_icon = driver.find_element(By.CSS_SELECTOR, 'svg[data-testid="icon-close"]')
        subscribe_close_icon.click()
        print("[INFO] Closed subscription popup")
        time.sleep(2.5)
    except Exception as e:
        print(f"[INFO] No subscription popup or skipped")

    # Read toast message
    try:
        toast_div = driver.find_element(By.CSS_SELECTOR, "div[class^='Toast-module_toast__']")
        toast_text = toast_div.text.strip()
        if DISPLAY_TODAYS_WORD_IN_CONSOLE :
            print(f"[INFO] Toast text: {toast_text.lower()}")
        else :
            print("[INFO] Toast text: OOOOO(Blurred)")
        return toast_text.lower()
    except Exception as e:
        print(f"[ERROR] Cannot read toast message: {e}")

    driver.quit()
