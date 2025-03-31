import requests
from bs4 import BeautifulSoup
import re
from config import Config
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional


class GoogleScraper:
    def __init__(self, api_key: Optional[str] = None, cx: Optional[str] = None):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        self.api_base_url = "https://www.googleapis.com/customsearch/v1"
        self.api_key = api_key
        self.cx = cx
        self.google_search_url = "https://www.google.com/search"
        self.filtered_domains = ['.ru']
        self.stop_words = {"cookie", "права", "reserved", "copyright", "политика", "конфиденциальности"}

    def is_filtered_domain(self, url: str) -> bool:
        domain = urlparse(url).netloc
        return any(domain.endswith(fd) for fd in self.filtered_domains)

    def clean_text(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'[\n\r\t]+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\S+@\S+', '', text)
        text = re.sub(r'http\S+', '', text)
        return text.strip()

    def is_valid_content(self, text: str) -> bool:
        if len(text) < 50 or any(word in text.lower() for word in self.stop_words):
            return False
        return len(re.findall(r'[a-zA-Zа-яА-Я]', text)) / len(text) > 0.5

    def search_google_api(self, query: str, num: int = 10) -> List[str]:
        if not self.api_key or not self.cx:
            return []
        params = {"q": query, "key": self.api_key, "cx": self.cx, "num": num}
        try:
            response = requests.get(self.api_base_url, params=params, timeout=10)
            response.raise_for_status()
            results = response.json().get("items", [])
            return [item["link"] for item in results if "link" in item and not self.is_filtered_domain(item["link"])]
        except Exception as e:
            print(f"Google API error: {e}")
            return []

    def search_google_scrape(self, query: str) -> List[str]:
        params = {"q": query, "hl": "ru", "num": 10}
        try:
            response = requests.get(self.google_search_url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return [a['href'] for a in soup.select(".yuRUbf a") if 'href' in a.attrs and not self.is_filtered_domain(a['href'])]
        except Exception as e:
            print(f"Google scraping error: {e}")
            return []

    def get_first_two_links(self, query: str) -> List[str]:
        links = self.search_google_api(query) or self.search_google_scrape(query)
        return links[:2] if links else []

    def extract_content(self, url: str) -> Dict[str, str]:
        try:
            if self.is_filtered_domain(url):
                return {"url": url, "title": "", "content": "Blocked domain", "domain": urlparse(url).netloc}
            
            response = requests.get(url, headers=self.headers, timeout=10, allow_redirects=True)
            response.raise_for_status()
            final_url = response.url
            soup = BeautifulSoup(response.text, "html.parser")
            
            for element in soup.select('script, style, footer, header, nav, aside, .cookie-notice, .advertisement'):
                element.decompose()
            
            title = soup.title.string if soup.title else ""
            main_content = soup.find(['article', 'main', 'section', 'div'], class_=re.compile(r'content|article|post|text|entry', re.I)) or soup
            
            content_elements = main_content.find_all(['p', 'h1', 'h2', 'h3', 'li'])
            content = " ".join(self.clean_text(el.get_text()) for el in content_elements if self.is_valid_content(el.get_text()))
            
            if len(content) < 50:
                return {"url": final_url, "title": "", "content": "Insufficient content", "domain": urlparse(final_url).netloc}
            
            return {"url": final_url, "title": self.clean_text(title), "content": content, "domain": urlparse(final_url).netloc}
        except Exception as e:
            return {"url": url, "title": "", "content": f"Error extracting content: {e}", "domain": urlparse(url).netloc}

    def get_content_with_fallback(self, query: str) -> str:
        links = self.get_first_two_links(query)
        if not links:
            return "No valid links found."
        
        for link in links:
            content = self.extract_content(link)
            if content["content"] and "Error" not in content["content"] and content["content"] != "Insufficient content":
                return f"\n=== {content['title']} ===\nSource: {content['domain']}\n{content['content']}"
        
        return "Failed to extract content."

    def search_images(self, query: str, num: int = 5) -> List[str]:
        params = {"q": query, "searchType": "image", "num": num, "key": self.api_key, "cx": self.cx}
        try:
            response = requests.get(self.api_base_url, params=params, timeout=10)
            response.raise_for_status()
            return [item["link"] for item in response.json().get("items", []) if "link" in item]
        except Exception as e:
            print(f"Image search error: {e}")
            return []


if __name__ == "__main__":
    API_KEY = Config.API_KEY_SEARCH
    CX = Config.CX
    scraper = GoogleScraper(api_key=API_KEY, cx=CX)
    print(scraper.get_content_with_fallback("Что такое Марс"))
    print(scraper.search_images("годжо сатору", num=3))