from gradio_client import Client
from typing import List, Tuple
from config import Config
class AIClient:
    def __init__(self, model_name: str):
        self.client = Client(model_name)
        self.history: List[List[str]] = []
        self.system_prompt = Config.SYSTEM_PROMPT
        self.max_history = 10

    def get_response(self, query: str) -> str:
        result = self.client.predict(
            query=query,
            history=self.history,
            system=self.system_prompt,
            radio="32B",
            api_name="/model_chat"
        )
        
        reply = result[1][-1][1]
        self.update_history(query, reply)
        return reply
        
    def escape_markdown(self,text):
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def update_history(self, query: str, reply: str) -> None:
        self.history.append([query, reply])
        if len(self.history) >= self.max_history:
            self.history = []
    def get_history(self):
      return self.history
            
    def call_in_start(self) -> None:
      result = self.client.predict(
      		system = Config.SYSTEM_PROMPT,
      		api_name="/modify_system_session"
      )