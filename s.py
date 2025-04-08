from requests_html import HTMLSession

session = HTMLSession()
r = session.get("https://google.com")
r.html.render()  # запускает JS
print(r.html.html)