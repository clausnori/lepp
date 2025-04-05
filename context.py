from dataclasses import dataclass
import pickle
from datetime import datetime, timedelta
import threading
import time
from typing import Optional, List, Dict, Any, Callable
import os
import random


@dataclass
class MessageContext:
    text: str
    user_id: int
    username: str
    first_name: str
    chat_id: int
    chat_type: str
    message_id: int
    reply_to_message: Optional[Dict] = None
    thread_id: Optional[int] = None

class ContextManager:
    """Менеджер контекста для хранения и управления контекстом диалогов"""
    
    def __init__(self, storage_file: str, ttl: int = 3600, max_contexts: int = 1000):
        self.storage_file = storage_file
        self.ttl = ttl
        self.max_contexts = max_contexts
        self.context_cache = {}
        self._lock = threading.Lock()
        self._load_contexts()
    
    def _get_context_key(self, chat_id: int, user_id: int) -> str:
        """Создает уникальный ключ для каждой пары чат-пользователь"""
        return f"{chat_id}:{user_id}"
    
    def _load_contexts(self) -> None:
        """Загружает контекст из файла при инициализации"""
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'rb') as f:
                    saved_data = pickle.load(f)
                    
                    # Фильтрация устаревших данных при загрузке
                    current_time = time.time()
                    for key, context_list in saved_data.items():
                        valid_contexts = [
                            ctx for ctx in context_list 
                            if current_time - ctx.get('timestamp', 0) < self.ttl
                        ]
                        if valid_contexts:
                            self.context_cache[key] = valid_contexts
                            
                print(f"Загружено {len(self.context_cache)} контекстов диалогов")
        except Exception as e:
            print(f"Ошибка загрузки контекстов: {e}")
            self.context_cache = {}
    
    def _save_contexts(self) -> None:
        """Сохраняет контексты в файл"""
        try:
            # Создаем директорию, если её нет
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            
            with open(self.storage_file, 'wb') as f:
                pickle.dump(self.context_cache, f)
        except Exception as e:
            print(f"Ошибка сохранения контекстов: {e}")
    
    def get_user_context(self, chat_id: int, user_id: int) -> List[Dict]:
        """Получает контекст диалога для конкретного пользователя в конкретном чате"""
        key = self._get_context_key(chat_id, user_id)
        return self.context_cache.get(key, [])
    
    def update_context(self, msg_context: MessageContext) -> None:
        """Обновляет контекст диалога для конкретного пользователя в конкретном чате"""
        key = self._get_context_key(msg_context.chat_id, msg_context.user_id)
        
        with self._lock:
            current = self.context_cache.get(key, [])
            
            # Добавление нового сообщения в контекст
            current.append({
                'text': msg_context.text,
                'timestamp': time.time()
            })
            
            # Ограничение количества сообщений в контексте для одного пользователя
            self.context_cache[key] = current[-10:]
            # Периодическое сохранение контекста (каждые 10 обновлений)
            if random.random() < 0.1:  
                self._save_contexts()
    
    def cleanup_old_contexts(self) -> None:
        """Удаляет устаревшие контексты"""
        with self._lock:
            current_time = time.time()
            keys_to_remove = []
            
            for key, context_list in self.context_cache.items():
                # Фильтрация устаревших сообщений в каждом контексте
                valid_contexts = [
                    ctx for ctx in context_list 
                    if current_time - ctx.get('timestamp', 0) < self.ttl
                ]
                
                if valid_contexts:
                    self.context_cache[key] = valid_contexts
                else:
                    keys_to_remove.append(key)
            
            # Удаление пустых контекстов
            for key in keys_to_remove:
                del self.context_cache[key]
            
            # Если слишком много контекстов, удаляем самые старые
            if len(self.context_cache) > self.max_contexts:
                # Сортировка контекстов по времени последнего сообщения
                sorted_keys = sorted(
                    self.context_cache.keys(),
                    key=lambda k: max([c.get('timestamp', 0) for c in self.context_cache[k]]) 
                    if self.context_cache[k] else 0
                )
                
                # Удаление лишних контекстов
                for key in sorted_keys[:len(self.context_cache) - self.max_contexts]:
                    del self.context_cache[key]
            
            # Сохранение изменений
            self._save_contexts()