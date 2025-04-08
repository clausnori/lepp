from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Настройка драйвера
service = Service(ChromeDriverManager().install())  # Автоматическая установка драйвера
driver = webdriver.Chrome(service=service)

# Открытие страницы
driver.get('https://example.com')

# Получение HTML-кода страницы
html_content = driver.page_source
print(html_content)

# Закрытие браузера
driver.quit()