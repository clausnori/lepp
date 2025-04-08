import re
import sys
import os
import json
import time
from requests_html import HTMLSession
from urllib.parse import urljoin, urlparse, quote_plus


class AIBrowser:
    """
    Веб-браузер для ИИ, управляемый через текстовые запросы с псевдокодом
    """
    def __init__(self):
        self.session = HTMLSession()
        self.current_url = None
        self.history = []
        self.response = None
        self.memory = {}  # "Память" браузера для хранения переменных
        self.js_enabled = False  # По умолчанию JS выключен для производительности
        
    def navigate(self, url):
        """Переход по URL"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        try:
            self.response = self.session.get(url, timeout=10)
            
            # Рендеринг JavaScript при необходимости
            if self.js_enabled:
                try:
                    self.response.html.render(timeout=20)
                except Exception as js_error:
                    return {
                        'status': 'warning',
                        'message': f'Страница загружена, но возникла ошибка при выполнении JavaScript: {str(js_error)}',
                        'url': url
                    }
            
            self.current_url = self.response.url
            self.history.append(self.current_url)
            
            title = self.response.html.find('title', first=True)
            title_text = title.text if title else "[Без заголовка]"
            
            return {
                'status': 'success',
                'title': title_text,
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
        if not self.response:
            return "Сначала нужно перейти на страницу"
        
        # Если указан селектор, используем его
        if selector:
            elements = self.response.html.find(selector)
            result = "\n".join([elem.text for elem in elements])
            return result if result else f"Элементы по селектору '{selector}' не найдены"
        
        # Пытаемся определить основной контент
        main_content = ""
        
        # Приоритетные контейнеры для основного содержимого
        main_selectors = [
            'article', 'main', '[role="main"]', '#content', '.content', 
            '#main', '.main', '.post', '.article', '.entry', 
            '.entry-content', '.post-content', '.article-content',
            '[itemprop="articleBody"]', '.story', '.story-body'
        ]
        
        for selector in main_selectors:
            main_elements = self.response.html.find(selector)
            if main_elements:
                main_content = "\n\n".join([elem.text for elem in main_elements])
                break
        
        # Если основной контент не найден, собираем текст из абзацев и заголовков
        if not main_content:
            paragraphs = self.response.html.find('p')
            headings = self.response.html.find('h1, h2, h3, h4, h5, h6')
            
            content_elements = []
            content_elements.extend(headings)
            content_elements.extend(paragraphs)
            
            if content_elements:
                main_content = "\n\n".join([elem.text for elem in content_elements if len(elem.text.strip()) > 20])
        
        # Если всё ещё нет контента, берем весь текст страницы
        if not main_content:
            main_content = self.response.html.text
        
        # Очистка текста
        if main_content:
            # Удаляем лишние пробелы и переносы строк
            main_content = re.sub(r'\n{3,}', '\n\n', main_content)
            main_content = re.sub(r' {2,}', ' ', main_content)
            
            # Удаляем HTML-символы
            main_content = re.sub(r'&[a-zA-Z]+;', ' ', main_content)
        
        return main_content if main_content else "Не удалось извлечь основной текст страницы"
    
    def extract_links(self, limit=10):
        """Извлечение ссылок со страницы"""
        if not self.response:
            return "Сначала нужно перейти на страницу"
            
        links = []
        for i, link in enumerate(self.response.html.links):
            if i >= limit:
                break
                
            # Получаем элемент с этой ссылкой
            elements = self.response.html.find(f'a[href="{link}"]')
            text = elements[0].text if elements and elements[0].text.strip() else '[Без текста]'
            
            # Преобразуем относительные ссылки в абсолютные
            if link.startswith(('http://', 'https://')):
                full_url = link
            else:
                full_url = urljoin(self.current_url, link)
                
            links.append({
                'id': i,
                'text': text,
                'url': full_url
            })
            
        return links
        
    def back(self):
        """Переход на предыдущую страницу"""
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
        if not self.response:
            return "Сначала нужно перейти на страницу"
        
        # Ищем элементы с текстом, содержащим запрос
        query = query.lower()
        results = []
        
        # Проверяем абзацы и заголовки
        elements = self.response.html.find('p, h1, h2, h3, h4, h5, h6, li')
        
        for elem in elements:
            text = elem.text.strip()
            if query in text.lower():
                # Определяем тип элемента
                element_type = 'paragraph'
                if elem.tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    element_type = elem.tag
                elif elem.tag == 'li':
                    element_type = 'list item'
                
                results.append({
                    'type': element_type,
                    'text': text
                })
        
        return results if results else f"Информация по запросу '{query}' не найдена"

    def click_link(self, link_id):
        """Переход по ссылке по ее ID"""
        links = self.extract_links(limit=100)
        
        if isinstance(links, str):  # Обработка ошибки
            return {"status": "error", "message": links}
            
        try:
            link_id = int(link_id)
            if 0 <= link_id < len(links):
                return self.navigate(links[link_id]['url'])
            else:
                return {"status": "error", "message": f"Ссылка с ID {link_id} не найдена"}
        except ValueError:
            # Если указан не числовой ID, попробуем найти ссылку по тексту
            for link in links:
                if link_id.lower() in link['text'].lower():
                    return self.navigate(link['url'])
            return {"status": "error", "message": f"Ссылка с текстом '{link_id}' не найдена"}

    def fill_form(self, form_data):
        """Заполнение формы (имитация)"""
        if not self.response:
            return {"status": "error", "message": "Сначала нужно перейти на страницу"}
            
        forms = self.response.html.find('form')
        if not forms:
            return {"status": "error", "message": "На странице не найдено форм"}
            
        # Простая имитация заполнения формы
        return {
            "status": "success", 
            "message": f"Форма заполнена данными: {form_data}"
        }

    def submit_form(self, form_id=0):
        """Отправка формы (имитация)"""
        if not self.response:
            return {"status": "error", "message": "Сначала нужно перейти на страницу"}
            
        forms = self.response.html.find('form')
        if not forms:
            return {"status": "error", "message": "На странице не найдено форм"}
            
        try:
            form_id = int(form_id)
            if 0 <= form_id < len(forms):
                action = forms[form_id].attrs.get('action', '')
                method = forms[form_id].attrs.get('method', 'get')
                
                # Имитация отправки формы
                return {
                    "status": "success",
                    "message": f"Форма отправлена с методом {method.upper()} по адресу {action}"
                }
            else:
                return {"status": "error", "message": f"Форма с ID {form_id} не найдена"}
        except ValueError:
            return {"status": "error", "message": "Неверный ID формы"}

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
            
    def toggle_javascript(self, enabled=None):
        """Включение или выключение JavaScript"""
        if enabled is not None:
            self.js_enabled = bool(enabled)
        else:
            self.js_enabled = not self.js_enabled
            
        status = "включен" if self.js_enabled else "выключен"
        return {"status": "success", "message": f"JavaScript {status}"}

    def get_html(self):
        """Получение исходного HTML текущей страницы"""
        if not self.response:
            return {"status": "error", "message": "Сначала нужно перейти на страницу"}
            
        return {"status": "success", "html": self.response.html.html}


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
            
        elif action == "javascript":
            enabled = None
            if params:
                if params[0].lower() in ["true", "1", "on", "yes"]:
                    enabled = True
                elif params[0].lower() in ["false", "0", "off", "no"]:
                    enabled = False
            return self.browser.toggle_javascript(enabled)
            
        elif action == "get_html":
            return self.browser.get_html()
            
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
                  return f"Извлеченный текст (первые 500 символов):\n{result['text']}..."
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
          
          elif "html" in result:
              if len(result["html"]) > 500:
                  return f"HTML код (первые 500 символов):\n{result['html'][:500]}..."
              else:
                  return f"HTML код:\n{result['html']}"
          
          elif "message" in result:
              return result["message"]
          
          else:
              return "Операция успешно выполнена"
      
      elif result.get("status") == "warning":
          return f"Предупреждение: {result.get('message', 'Неизвестное предупреждение')}"
      
      elif result.get("status") == "error":
          return f"Ошибка: {result.get('message', 'Неизвестная ошибка')}"
      
      else:
          return str(result)


def main():
    """Основная функция программы"""
    browser = AIBrowser()
    parser = PseudoCodeParser(browser)
    
    print("AI Браузер с управлением через псевдокод")
    print("Введите команды между тегами <browser>...</browser>")
    
    if len(sys.argv) > 1:
        # Если переданы аргументы командной строки, используем их как команды
        text = " ".join(sys.argv[1:])
    else:
        # Иначе используем пример
        text = """
                  <browser>
                  javascript("yes")
                  search("Топ телефон", "duckduckgo")
                  extract_links(20)
                  extract_text()
                  </browser>"""
    
    # Извлекаем команды браузера
    browser_commands = parser.extract_browser_commands(text)
    if browser_commands:
      print("\nВыполнение команд браузера:")
      results = parser.parse_commands(browser_commands)
      print("\nРезультаты:")
      for i, result in enumerate(results):
        print(f"Команда {i+1}: {parser.format_result(result)}")
    else:
      print("Команды браузера не найдены. Используйте формат: <browser>команды</browser>")


if __name__ == "__main__":
    main()
