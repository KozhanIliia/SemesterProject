import csv
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Замініть на ваше посилання на Google Форму
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSei5b0q6xOYRMJpM_QkIZ2p1B8vaqWf-RHA1aEocZrEjn4wMQ/viewform?usp=dialog"
CSV_FILE = "answers.csv"


class GoogleFormFiller:
    def __init__(self, form_url):
        self.form_url = form_url
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service)
        self.wait = WebDriverWait(self.driver, 10)

    def fill_form(self, answers_dict):
        try:
            self.driver.get(self.form_url)
            print(f"Початок заповнення. Кількість відповідей: {len(answers_dict)}")

            for question, answer in answers_dict.items():
                if not answer:
                    continue

                print(f"Обробка питання: '{question}'")

                # Спроба заповнити текстове поле
                if self._try_fill_text(question, answer):
                    continue

                # Спроба обрати радіо-кнопку або чекбокс
                if self._try_select_radio(question, answer):
                    continue

                print(f"Поле не знайдено для питання: {question}")

            # Відправка форми
            self._submit_form()

        except Exception as e:
            print(f"Помилка виконання: {e}")

    def _try_fill_text(self, question_text, answer_text):
        """Шукає input або textarea, пов'язані з текстом питання."""
        try:
            # Змінено стратегію: шукаємо блок питання (listitem), який має заголовок (heading) з нашим текстом
            # Це працює краще для кирилиці, ніж пошук в data-params
            container_xpath = f"//div[@role='listitem'][.//div[@role='heading'][contains(., '{question_text}')]]"

            xpath = f"{container_xpath}//input | {container_xpath}//textarea"
            elements = self.driver.find_elements(By.XPATH, xpath)
            if elements and elements[0].is_displayed():
                elements[0].clear()
                elements[0].send_keys(answer_text)
                return True
            return False
        except:
            return False

    def _try_select_radio(self, question_text, option_text):
        """Шукає варіант відповіді (radio/checkbox) за текстом."""
        try:
            # Змінено стратегію: шукаємо контейнер за видимим заголовком
            container_xpath = f"//div[@role='listitem'][.//div[@role='heading'][contains(., '{question_text}')]]"

            # Шукаємо option за aria-label або текстом всередині span у знайденому контейнері
            option_xpath = f"{container_xpath}//div[@role='radio' and @aria-label='{option_text}'] | {container_xpath}//span[text()='{option_text}']"

            elements = self.driver.find_elements(By.XPATH, option_xpath)
            if elements:
                self.driver.execute_script("arguments[0].scrollIntoView(true);", elements[0])
                time.sleep(0.5)
                elements[0].click()
                return True
            return False
        except:
            return False

    def _submit_form(self):
        """Шукає кнопку відправки та натискає її."""
        try:
            submit_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH,
                 "//span[text()='Надіслати' or text()='Submit' or text()='Отправить']/ancestor::div[@role='button']")
            ))
            submit_btn.click()
            print("Форма відправлена успішно.")
            time.sleep(2)
        except Exception as e:
            print(f"Помилка відправки: {e}")

    def close(self):
        self.driver.quit()


# --- ГОЛОВНИЙ БЛОК ---
if __name__ == "__main__":
    single_submission_data = {}

    # Зчитування відповідей з CSV
    try:
        with open(CSV_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None)  # Пропускаємо рядок заголовків

            for row in reader:
                if len(row) >= 2:
                    q_text = row[0].strip()
                    a_text = row[1].strip()
                    if q_text:
                        single_submission_data[q_text] = a_text
    except FileNotFoundError:
        print(f"Файл {CSV_FILE} не знайдено.")
        exit()

    print(f"Завантажено записів: {len(single_submission_data)}")

    # Запуск автоматизації
    filler = GoogleFormFiller(FORM_URL)
    filler.fill_form(single_submission_data)
    time.sleep(2)
    filler.close()