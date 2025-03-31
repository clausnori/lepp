import requests
import os
from abc import ABC, abstractmethod

class VoiceGenerator(ABC):
    @abstractmethod
    def generate(self, text: str) -> str:
        pass

class ElevenLabsVoiceGenerator(VoiceGenerator):
    def __init__(self, api_key: str, voice_id: str):
        self.api_key = api_key
        self.voice_id = voice_id
        self.chunk_size = 1024

    def generate(self, text: str) -> str:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.50,
                "similarity_boost": 0.25
            }
        }
        
        response = requests.post(url, json=data, headers=headers)
        output_file = 'a.mp3'
        
        with open(output_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if chunk:
                    f.write(chunk)
        
        return output_file