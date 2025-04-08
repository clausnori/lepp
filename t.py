import re
import sys
import os
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


class AIBrowser:
    """
    Веб-браузер для ИИ, управляемый через текстовые запросы с псевдокодом,
    использующий Selenium для поддержки JavaScript
    """
    def __init__(self):
        # Настройка опций Chrome
        self.options = Options()
        self.options.add_argument('--headless')  # Запуск в фоновом режиме
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        self.options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Инициализация драйвера
        try:
            self.driver = webdriver.Chrome(options=self.options)
        except Exception as e:
            print(f"Ошибка при инициализации драйвера: {str(e)}")
            self.driver = None
            
        self.current_url = None
        self.history = []
        self.page_content = None
        self.soup = None
        self.memory = {}  # "Память" браузера для хранения переменных
        
    def __del__(self):
        """Деструктор для закрытия драйвера"""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass
        
    def navigate(self, url):
        """Переход по URL"""
        if not self.driver:
            return {
                'status': 'error',
                'message': 'Драйвер браузера не инициализирован',
                'url': url
            }
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        try:
            self.driver.get(url)
            
            # Ждем загрузки страницы
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            self.current_url = self.driver.current_url
            self.page_content = self.driver.page_source
            self.soup = BeautifulSoup(self.page_content, 'html.parser')
            self.history.append(self.current_url)
            
            title = self.driver.title or "[Без заголовка]"
            return {
                'status': 'success',
                'title': title,
                'url': self.current_url
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
                'url': url
            }
    
    def search(self, query, engine="google"):
        """Поиск информации"""
        search_urls = {
            "google": f"https://www.google.com/search?q={quote_plus(query)}",
            "bing": f"https://www.bing.com/search?q={quote_plus(query)}",
            "duckduckgo": f"https://duckduckgo.com/?q={quote_plus(query)}"
        }
        
        if engine.lower() not in search_urls:
            engine = "google"
            
        return self.navigate(search_urls[engine.lower()])
    
    def extract_text(self, selector=None):
        """Извлечение основного текстового содержимого со страницы"""
        if not self.soup:
            return "Сначала нужно перейти на страницу"
        
        # Если указан селектор, используем его через Selenium
        if selector:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                result = "\n".join([elem.text for elem in elements if elem.text.strip()])
                return result if result else f"Элементы по селектору '{selector}' не найдены"
            except Exception as e:
                return f"Ошибка при извлечении текста по селектору: {str(e)}"
      
        # Создаем копию soup для работы
        content_soup = BeautifulSoup(str(self.soup), 'html.parser')
        
        # Удаляем ненужные элементы
        for element in content_soup.select(
            'script, style, meta, noscript, header, footer, nav, ' +
            'aside, [class*="menu"], [class*="nav"], [class*="header"], ' +
            '[class*="footer"], [class*="sidebar"], [class*="ad"], ' + 
            '[id*="menu"], [id*="nav"], [id*="header"], ' +
            '[id*="footer"], [id*="sidebar"], [id*="ad"], ' +
            'button, .button, [role="button"], [type="button"], ' + 
            '[class*="cookie"], [id*="cookie"], [class*="banner"], ' +
            '[class*="popup"], [id*="popup"], [class*="modal"], ' +
            '[id*="modal"], form'):
            element.extract()
        
        # Приоритетные контейнеры для основного содержимого
        main_content = ""
        main_selectors = [
            'article', 'main', '[role="main"]', '#content', '.content', 
            '#main', '.main', '.post', '.article', '.entry', 
            '.entry-content', '.post-content', '.article-content',
            '[itemprop="articleBody"]', '.story', '.story-body'
        ]
        
        for selector in main_selectors:
            main_element = content_soup.select_one(selector)
            if main_element:
                # Дополнительно удаляем ненужные элементы из основного контента
                for element in main_element.select('.social, .share, .comments, .related, .recommendations'):
                    element.extract()
                main_content = main_element.get_text(separator='\n', strip=True)
                break
        
        # Если основной контент не найден, собираем все абзацы и заголовки
        if not main_content:
            content_elements = content_soup.select('h1, h2, h3, h4, h5, h6, p, li, blockquote, .text')
            if content_elements:
                main_content = '\n\n'.join([elem.get_text(strip=True) for elem in content_elements 
                                        if len(elem.get_text(strip=True)) > 20])  # Игнорируем короткие элементы
        
        # Если всё ещё нет контента, берем текст body
        if not main_content and content_soup.body:
            main_content = content_soup.body.get_text(separator='\n', strip=True)
        
        # Очистка текста
        if main_content:
            # Удаляем лишние пробелы и переносы строк
            main_content = re.sub(r'\n{3,}', '\n\n', main_content)
            main_content = re.sub(r' {2,}', ' ', main_content)
            
            # Удаляем HTML-символы
            main_content = re.sub(r'&[a-zA-Z]+;', ' ', main_content)
            
            # Разделяем параграфы двойным переносом строки для лучшей читабельности
            main_content = re.sub(r'\n', '\n\n', main_content)
            main_content = re.sub(r'\n{3,}', '\n\n', main_content)
        
        return main_content if main_content else "Не удалось извлечь основной текст страницы"
    
    def extract_links(self, limit=10):
        """Извлечение ссылок со страницы"""
        if not self.driver:
            return "Драйвер браузера не инициализирован"
            
        if not self.soup:
            return "Сначала нужно перейти на страницу"
            
        links = []
        try:
            # Получаем все ссылки через Selenium для доступа к динамическому контенту
            link_elements = self.driver.find_elements(By.TAG_NAME, "a")
            
            for i, elem in enumerate(link_elements):
                if i >= limit:
                    break
                    
                try:
                    href = elem.get_attribute('href')
                    if not href:
                        continue
                        
                    text = elem.text.strip() or '[Без текста]'
                    links.append({
                        'id': i,
                        'text': text,
                        'url': href
                    })
                except Exception:
                    continue  # Пропускаем ссылки, вызывающие ошибки
            
            return links
        except Exception as e:
            return f"Ошибка при извлечении ссылок: {str(e)}"
        
    def back(self):
        """Переход на предыдущую страницу"""
        if not self.driver:
            return {"status": "error", "message": "Драйвер браузера не инициализирован"}
            
        if len(self.history) > 1:
            self.history.pop()  # Удаляем текущую страницу
            previous_url = self.history.pop()  # Получаем предыдущую страницу
            return self.navigate(previous_url)
        else:
            return {
                'status': 'error',
                'message': 'История пуста'
            }
    
    def find_information(self, query):
        """Поиск информации на текущей странице"""
        if not self.driver:
            return "Драйвер браузера не инициализирован"
            
        if not self.soup:
            return "Сначала нужно перейти на страницу"
        
        # Поиск элементов, содержащих запрос
        try:
            # Создаем XPath запрос для поиска текста
            xpath_query = (
                f"//p[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), " +
                f"'{query.lower()}')] | " +
                f"//h1[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), " +
                f"'{query.lower()}')] | " +
                f"//h2[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), " +
                f"'{query.lower()}')] | " +
                f"//h3[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), " +
                f"'{query.lower()}')] | " +
                f"//h4[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), " +
                f"'{query.lower()}')] | " +
                f"//h5[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), " +
                f"'{query.lower()}')] | " +
                f"//h6[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), " +
                f"'{query.lower()}')] | " +
                f"//li[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), " +
                f"'{query.lower()}')]"
            )
            
            elements = self.driver.find_elements(By.XPATH, xpath_query)
            results = []
            
            for elem in elements:
                results.append({
                    'type': elem.tag_name,
                    'text': elem.text.strip()
                })
            
            return results if results else f"Информация по запросу '{query}' не найдена"
        except Exception as e:
            return f"Ошибка при поиске информации: {str(e)}"

    def click_link(self, link_id):
        """Переход по ссылке по ее ID"""
        if not self.driver:
            return {"status": "error", "message": "Драйвер браузера не инициализирован"}
            
        links = self.extract_links(limit=100)
        
        if isinstance(links, str):  # Обработка ошибки
            return {"status": "error", "message": links}
            
        try:
            if str(link_id).isdigit():
                link_id = int(link_id)
                if 0 <= link_id < len(links):
                    return self.navigate(links[link_id]['url'])
                else:
                    return {"status": "error", "message": f"Ссылка с ID {link_id} не найдена"}
            else:
                # Если указан не числовой ID, попробуем найти ссылку по тексту
                for link in links:
                    if link_id.lower() in link['text'].lower():
                        return self.navigate(link['url'])
                
                # Также пробуем найти элемент по тексту через Selenium
                try:
                    xpath = f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{link_id.lower()}')]"
                    element = self.driver.find_element(By.XPATH, xpath)
                    element.click()
                    # Ждем загрузки новой страницы
                    time.sleep(2)
                    # Обновляем данные
                    self.current_url = self.driver.current_url
                    self.page_content = self.driver.page_source
                    self.soup = BeautifulSoup(self.page_content, 'html.parser')
                    self.history.append(self.current_url)
                    return {
                        'status': 'success',
                        'title': self.driver.title or "[Без заголовка]",
                        'url': self.current_url
                    }
                except Exception:
                    return {"status": "error", "message": f"Ссылка с текстом '{link_id}' не найдена"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка при переходе по ссылке: {str(e)}"}

    def fill_form(self, form_data):
        """Заполнение формы"""
        if not self.driver:
            return {"status": "error", "message": "Драйвер браузера не инициализирован"}
            
        if not self.soup:
            return {"status": "error", "message": "Сначала нужно перейти на страницу"}
            
        try:
            # Пытаемся найти поле ввода по его имени, id или типу
            for field_name, value in form_data.items():
                # Поиск по различным атрибутам
                selectors = [
                    f"input[name='{field_name}']",
                    f"input[id='{field_name}']",
                    f"textarea[name='{field_name}']",
                    f"textarea[id='{field_name}']",
                    f"select[name='{field_name}']",
                    f"select[id='{field_name}']"
                ]
                
                found = False
                for selector in selectors:
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        element.clear()
                        element.send_keys(value)
                        found = True
                        break
                    except Exception:
                        continue
                
                if not found:
                    return {"status": "error", "message": f"Поле '{field_name}' не найдено на странице"}
            
            return {
                "status": "success", 
                "message": f"Форма заполнена данными: {form_data}"
            }
        except Exception as e:
            return {"status": "error", "message": f"Ошибка при заполнении формы: {str(e)}"}

    def submit_form(self, form_id=0):
        """Отправка формы"""
        if not self.driver:
            return {"status": "error", "message": "Драйвер браузера не инициализирован"}
            
        if not self.soup:
            return {"status": "error", "message": "Сначала нужно перейти на страницу"}
            
        try:
            forms = self.driver.find_elements(By.TAG_NAME, "form")
            if not forms:
                return {"status": "error", "message": "На странице не найдено форм"}
                
            if isinstance(form_id, str) and not form_id.isdigit():
                # Ищем форму по атрибутам id или name
                for form in forms:
                    form_attr_id = form.get_attribute('id')
                    form_attr_name = form.get_attribute('name')
                    if (form_attr_id and form_id.lower() in form_attr_id.lower()) or \
                       (form_attr_name and form_id.lower() in form_attr_name.lower()):
                        form.submit()
                        return {
                            "status": "success",
                            "message": f"Форма отправлена"
                        }
                return {"status": "error", "message": f"Форма с ID или именем '{form_id}' не найдена"}
            else:
                # Используем числовой индекс
                form_id = int(form_id)
                if 0 <= form_id < len(forms):
                    forms[form_id].submit()
                    
                    # Ждем завершения навигации
                    current_url = self.driver.current_url
                    time.sleep(2)  # Даем странице время на загрузку
                    
                    # Обновляем данные если URL изменился
                    if current_url != self.driver.current_url:
                        self.current_url = self.driver.current_url
                        self.page_content = self.driver.page_source
                        self.soup = BeautifulSoup(self.page_content, 'html.parser')
                        self.history.append(self.current_url)
                    
                    return {
                        "status": "success",
                        "message": "Форма отправлена"
                    }
                else:
                    return {"status": "error", "message": f"Форма с индексом {form_id} не найдена"}
        except Exception as e:
            return {"status": "error", "message": f"Ошибка при отправке формы: {str(e)}"}

    def wait(self, seconds):
        """Пауза в выполнении"""
        try:
            seconds = float(seconds)
            time.sleep(seconds)
            return {"status": "success", "message": f"Выполнена пауза {seconds} секунд"}
        except ValueError:
            return {"status": "error", "message": "Неверное значение времени паузы"}

    def store_value(self, name, value):
        """Сохранение значения в 'памяти' браузера"""
        self.memory[name] = value
        return {"status": "success", "message": f"Значение '{value}' сохранено как '{name}'"}

    def get_value(self, name):
        """Получение значения из 'памяти' браузера"""
        if name in self.memory:
            return {"status": "success", "value": self.memory[name]}
        else:
            return {"status": "error", "message": f"Значение '{name}' не найдено в памяти"}


class PseudoCodeParser:
    """
    Парсер псевдокода для управления браузером
    """
    def __init__(self, browser):
        self.browser = browser
        
    def parse_commands(self, pseudo_code):
        """Разбор и выполнение псевдокода"""
        lines = pseudo_code.strip().split('\n')
        results = []
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue  # Пропускаем пустые строки и комментарии
                
            result = self.execute_command(line)
            results.append(result)
            
            # Прекращаем выполнение при ошибке
            if result.get("status") == "error":
                break
        
        return results
    
    def execute_command(self, command):
          """Выполнение отдельной команды"""
          # Разбор команды вида: действие(параметр1, параметр2, ...)
          match = re.match(r'(\w+)\((.*)\)$', command)
          if not match:
              return {"status": "error", "message": f"Неверный формат команды: {command}"}
              
          action = match.group(1).lower()
          params_str = match.group(2)
          
          # Разбор параметров, учитывая кавычки
          params = []
          if params_str:
              in_quotes = False
              current_param = ""
              quote_char = None
              
              for char in params_str:
                  if char in ['"', "'"]:
                      if not in_quotes:
                          in_quotes = True
                          quote_char = char
                      elif char == quote_char:
                          in_quotes = False
                      else:
                          current_param += char
                  elif char == ',' and not in_quotes:
                      params.append(current_param.strip())
                      current_param = ""
                  else:
                      current_param += char
                      
              params.append(current_param.strip())
              
              # Удаляем кавычки из параметров
              for i in range(len(params)):
                  param = params[i]
                  if (param.startswith('"') and param.endswith('"')) or \
                     (param.startswith("'") and param.endswith("'")):
                      params[i] = param[1:-1]
          
          # Выполнение команды на основе действия
          if action == "go":
              if not params:
                  return {"status": "error", "message": "Не указан URL для перехода"}
              return self.browser.navigate(params[0])
              
          elif action == "search":
              if not params:
                  return {"status": "error", "message": "Не указан поисковый запрос"}
              engine = params[1] if len(params) > 1 else "google"
              return self.browser.search(params[0], engine)
              
          elif action == "extract_text":
              selector = params[0] if params else None
              result = self.browser.extract_text(selector)
              return {"status": "success", "text": result}
              
          elif action == "extract_links":
              limit = int(params[0]) if params and params[0].isdigit() else 10
              links = self.browser.extract_links(limit)
              return {"status": "success", "links": links}
              
          elif action == "back":
              return self.browser.back()
              
          elif action == "find":
              if not params:
                  return {"status": "error", "message": "Не указан поисковый запрос"}
              results = self.browser.find_information(params[0])
              return {"status": "success", "results": results}
              
          elif action == "click":
              if not params:
                  return {"status": "error", "message": "Не указан ID ссылки"}
              return self.browser.click_link(params[0])
              
          elif action == "fill":
              if len(params) < 2:
                  return {"status": "error", "message": "Не указаны необходимые параметры для заполнения формы"}
              return self.browser.fill_form({params[0]: params[1]})
              
          elif action == "submit":
              form_id = params[0] if params else 0
              return self.browser.submit_form(form_id)
              
          elif action == "wait":
              if not params:
                  return {"status": "error", "message": "Не указано время ожидания"}
              return self.browser.wait(params[0])
              
          elif action == "store":
              if len(params) < 2:
                  return {"status": "error", "message": "Не указаны имя и значение для сохранения"}
              return self.browser.store_value(params[0], params[1])
              
          elif action == "get":
              if not params:
                  return {"status": "error", "message": "Не указано имя значения для получения"}
              return self.browser.get_value(params[0])
              
          else:
              return {"status": "error", "message": f"Неизвестная команда: {action}"}


    def extract_browser_commands(self, text):
        """Извлечение команд браузера из текста"""
        pattern = r'<browser>(.*?)</browser>'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None


    def format_result(self, result):
        """Форматирование результата для вывода"""
        if result.get("status") == "success":
            if "title" in result:
                return f"Загружена страница: {result['title']}\nURL: {result['url']}"
            
            elif "text" in result:
                if len(result["text"]) > 500:
                    return f"Извлеченный текст (первые 500 символов):\n{result['text'][:500]}..."
                else:
                    return f"Извлеченный текст:\n{result['text']}"
            
            elif "links" in result:
                output = "Извлеченные ссылки:\n"
                for link in result["links"]:
                    output += f"[{link['id']}] {link['text']} - {link['url']}\n"
                return output
            
            elif "results" in result:
                if isinstance(result["results"], list):
                    output = "Результаты поиска:\n"
                    for i, res in enumerate(result["results"][:5]):  # Показываем только первые 5 результатов
                        output += f"[{i+1}] [{res['type']}] {res['text'][:100]}...\n"
                    if len(result["results"]) > 5:
                        output += f"... и еще {len(result['results']) - 5} результатов"
                    return output
                else:
                    return str(result["results"])
            
            elif "value" in result:
                return f"Значение: {result['value']}"
            
            elif "message" in result:
                return result["message"]
            
            else:
                return "Операция успешно выполнена"
        
        elif result.get("status") == "error":
            return f"Ошибка: {result.get('message', 'Неизвестная ошибка')}"
        
        else:
            return str(result)

def main():
    """Основная функция программы"""
    browser = AIBrowser()
    parser = PseudoCodeParser(browser)
    
    print("AI Браузер с управлением через псевдокод (Selenium)")
    print("Введите команды между тегами <browser>...</browser>")
    text = """
<browser>
search("актуальные новости украина", "google")
extract_links(5)
</browser>"""
    # Извлекаем команды браузера
    browser_commands = parser.extract_browser_commands(text)
            
    if browser_commands:
        print("\nВыполнение команд браузера:")
        results = parser.parse_commands(browser_commands)
        print(results)
        print("\nРезультаты:")
        for i, result in enumerate(results):
            print(f"Команда {i+1}: {parser.format_result(result)}")
    else:
        print("Команды браузера не найдены. Используйте формат: <browser>команды</browser>")


if __name__ == "__main__":
    main()
      