import telebot
import os
import time
import random
import threading
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from cachetools import TTLCache
from concurrent.futures import ThreadPoolExecutor

# Предполагаем наличие этих модулей
from config import Config
from ai_client import AIClient
from find_data import GoogleScraper
from voice_generator import ElevenLabsVoiceGenerator, VoiceGenerator
from context import ContextManager,MessageContext
from sentimental import SentimentClassifier

class ResponseTriggerManager:
    """Класс для централизованного управления условиями ответа бота"""
    
    def __init__(self):
        # Словарь ключевых слов для различных действий
        self.action_keywords = {
            "voice_generation": ["расскажи", "озвучь", "прочитай"],
            "image_search": ["картинка", "картинку", "изображение", "фото"],
            "internet_search": ["аоинмаусппмпкууап"],
            "bot_mention": ["ami", "ами", "@ami"]
        }
        
        # Словарь действий, которые может выполнять бот
        self.actions = {}
        
        # Вероятность случайного ответа (по умолчанию 3%)
        self.random_reply_chance = 0.03
    
    def register_action(self, action_name: str, action_function: Callable) -> None:
        """Регистрирует новое действие бота по имени"""
        self.actions[action_name] = action_function
    
    def add_keywords(self, action_type: str, new_keywords: List[str]) -> None:
        """Добавляет новые ключевые слова для существующего типа действия"""
        if action_type in self.action_keywords:
            # Добавляем только уникальные ключевые слова
            self.action_keywords[action_type].extend([kw for kw in new_keywords if kw not in self.action_keywords[action_type]])
        else:
            # Создаем новый тип действия с ключевыми словами
            self.action_keywords[action_type] = new_keywords
    
    def set_random_reply_chance(self, chance: float) -> None:
        """Устанавливает вероятность случайного ответа"""
        if 0 <= chance <= 1:
            self.random_reply_chance = chance
    
    def should_reply(self, message: telebot.types.Message) -> bool:
        """Проверяет, должен ли бот ответить на сообщение"""
        # Если это личный чат - всегда отвечаем
        if message.chat.type == "private":
            return True
        
        # Если это ответ на сообщение бота - всегда отвечаем
        if message.reply_to_message and message.reply_to_message.from_user.id == 6403705955:
            return True
        
        # Проверка на упоминание бота по ключевым словам
        text = message.text.lower() if message.text else ""
        if any(keyword in text for keyword in self.action_keywords["bot_mention"]):
            return True
            
        # Случайный ответ с заданной вероятностью
        if random.random() < self.random_reply_chance:
            return True
            
        return False
    
    def get_action_type(self, message: telebot.types.Message) -> Optional[str]:
        """Определяет тип действия, которое должен выполнить бот, по ключевым словам"""
        if not message.text:
            return None
            
        text = message.text.lower()
        
        # Проверяем все типы действий
        for action_type, keywords in self.action_keywords.items():
            if any(keyword in text for keyword in keywords):
                return action_type
                
        return None

class ResponseGenerator:
    def __init__(self, ai_client: AIClient, google_scraper: GoogleScraper, context_manager: ContextManager,sentimental_user:SentimentClassifier):
        self.ai_client = ai_client
        self.google_scraper = google_scraper
        self.sentimental_user = sentimental_user
        self.context_manager = context_manager
        self.response_cache = TTLCache(maxsize=100, ttl=300)
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._lock = threading.Lock()

    def get_cached_response(self, query_hash: str) -> Optional[str]:
        return self.response_cache.get(query_hash)

    def cache_response(self, query_hash: str, response: str) -> None:
        self.response_cache[query_hash] = response

    def generate_response(self, msg_context: MessageContext) -> str:
        # Обновление контекста пользователя
        self.context_manager.update_context(msg_context)
        
        # Получение контекста пользователя
        context = self.context_manager.get_user_context(msg_context.chat_id, msg_context.user_id)
        mood = self.sentimental_user.classify(msg_context.text)
        print(mood)
        prompt_parts = []
        if context:
            prompt_parts.append("Previous messages:")
            for msg in context[-5:]:  # Последние 5 сообщений для контекста
                prompt_parts.append(f"- {msg['text']}")
        
        prompt_parts.append(f"\nCurrent message: {msg_context.text}")
        prompt_parts.append(f"[From user: {msg_context.first_name} (@{msg_context.username})]")
        prompt_parts.append(f"[Your Mood: {mood}]")
        
        if msg_context.reply_to_message:
            prompt_parts.append(f"[Replying to: {msg_context.reply_to_message.get('text', '')}]")
        
        prompt = "\n".join(prompt_parts)
        
        # Безопасная обработка поиска
        try:
            if 'найди' in msg_context.text.lower():
                print("Поиск:", msg_context.text.lower())
                search_data = self.google_scraper.get_content_with_fallback(msg_context.text.lower())
                print(search_data)
                if search_data:
                    prompt += f"\n[Search context: {search_data[:1000]}]"
        except Exception as e:
            print(f"Ошибка при поиске: {e}")
        
        try:
            send = self.ai_client.get_response(prompt)
            return send
        except Exception as e:
            print(f"Ошибка при генерации ответа: {e}")
            print(prompt)

class TelegramBot:
    def __init__(self, token: str, ai_client: AIClient, 
                 voice_generator: VoiceGenerator, google_scraper: GoogleScraper,sentimental_user:SentimentClassifier):
        try:
            self.bot = telebot.TeleBot(token)
            
            # Создание менеджера контекста с указанием файла для хранения
            context_storage_path = os.path.join(os.path.dirname(__file__), "data", "context_storage.pkl")
            self.context_manager = ContextManager(context_storage_path)
            
            # Создание генератора ответов с передачей менеджера контекста
            self.response_generator = ResponseGenerator(ai_client, google_scraper, self.context_manager,sentimental_user)
            self.voice_generator = voice_generator
            self.start_time = time.time()
            self.google_scraper = google_scraper
            # Создаем менеджер триггеров ответов
            self.trigger_manager = ResponseTriggerManager()
            
            # Флаг активности бота - по умолчанию активен
            self.is_active = True
            
            # Хранение отключенных чатов
            self.inactive_chats = set()
            self.user_message_counts = {}  # Format: {user_id: {"count": int, "reset_time": datetime}}
            self.chat_message_counts = {}  # Format: {chat_id: {"count": int, "reset_time": datetime}}
            self.USER_DAILY_LIMIT = 100
            self.CHAT_DAILY_LIMIT = 300
            
            # Запуск фонового потока для периодической очистки старых контекстов
            self._start_cleanup_thread()
            
            # Регистрация действий бота
            self._register_bot_actions()
            
            # Установка обработчиков команд
            self.bot.message_handler(commands=['start_ami'])(self.handle_start_command)
            self.bot.message_handler(commands=['stop_ami'])(self.handle_stop_command)
            self.bot.message_handler(commands=['send_message'])(self.handle_send_message_command)
            
            # Установка обработчиков сообщений
            self.bot.message_handler(func=self._message_filter)(self.handle_message)
        except Exception as e:
            print(f"Ошибка инициализации бота: {e}")
            raise
    def handle_send_message_command(self, message: telebot.types.Message) -> None:
      """Handler for /send_message command to broadcast messages"""
      user_id = message.from_user.id
      # Check if the sender is an admin
      if user_id != Config.ADMIN_ID:
          self.bot.reply_to(message, "Только администраторы могут использовать эту команду.")
          return
          
      # Extract the message to send
      command_parts = message.text.split(' ', 1)
      if len(command_parts) < 2:
          self.bot.reply_to(message, "Использование: /send_message <текст сообщения>")
          return
          
      broadcast_text = command_parts[1].strip()
      
      # Get a list of all active chats (could be stored separately)
      active_chats = set()
      for chat_id in self.chat_message_counts.keys():
          if chat_id not in self.inactive_chats:
              active_chats.add(chat_id)
      
      # Add private chats from user message counts
      for user_id in self.user_message_counts.keys():
          # Assuming user_id is the chat_id for private chats
          if user_id not in self.inactive_chats:
              active_chats.add(user_id)
      
      # Send the message to all active chats
      success_count = 0
      failed_count = 0
      
      for chat_id in active_chats:
          try:
              self.bot.send_message(chat_id, f"📢 Объявление:\n\n{broadcast_text}")
              success_count += 1
          except Exception as e:
              print(f"Failed to send message to chat {chat_id}: {e}")
              failed_count += 1
      
      # Notify the admin about the broadcast results
      self.bot.reply_to(
          message, 
          f"Сообщение отправлено в {success_count} чатов.\n"
          f"Не удалось отправить в {failed_count} чатов."
      )
    def _register_bot_actions(self):
        """Регистрирует все действия бота в менеджере триггеров"""
        # Регистрация действий
        self.trigger_manager.register_action("voice_generation", self._handle_voice_request)
        self.trigger_manager.register_action("image_search", self._handle_image_request)
        self.trigger_manager.register_action("internet_search", self._handle_search_request)
        
        
        self.trigger_manager.add_keywords("voice_generation", ["скажи голосом", "озвучь текст","скажи","голосом"])
        self.trigger_manager.add_keywords("image_search", ["найди картинку", "покажи фото","фото","картинка","картинку"])
        
        # Здесь можно добавить новые ключевые слова для существующих действий
    def _check_message_limits(self, user_id, chat_id):
      """Check if the user or chat has exceeded their daily message limit"""
      current_time = datetime.now()
      
      # Check user limit
      if user_id not in self.user_message_counts or current_time > self.user_message_counts[user_id]["reset_time"]:
          self.user_message_counts[user_id] = {
              "count": 0,
              "reset_time": current_time + timedelta(days=1)
          }
      
      self.user_message_counts[user_id]["count"] += 1
      user_count = self.user_message_counts[user_id]["count"]
      
      # Check chat limit
      if chat_id not in self.chat_message_counts or current_time > self.chat_message_counts[chat_id]["reset_time"]:
          self.chat_message_counts[chat_id] = {
              "count": 0,
              "reset_time": current_time + timedelta(days=1)
          }
      
      self.chat_message_counts[chat_id]["count"] += 1
      chat_count = self.chat_message_counts[chat_id]["count"]
      
      # Return True if within limits, False otherwise
      user_ok = user_count <= self.USER_DAILY_LIMIT
      chat_ok = chat_count <= self.CHAT_DAILY_LIMIT
      
      return user_ok and chat_ok

    def handle_start_command(self, message: telebot.types.Message) -> None:
        """Обработчик команды /start_ami для включения бота в чате"""
        # Проверка прав администратора
        if not self._is_admin(message):
            self.bot.reply_to(message, "Только администраторы могут включать бота.")
            return
            
        chat_id = message.chat.id
        if chat_id in self.inactive_chats:
            self.inactive_chats.remove(chat_id)
            self.bot.reply_to(message, "Ами активирована в этом чате.")
        else:
            self.bot.reply_to(message, "Ами уже активна в этом чате.")

    def handle_stop_command(self, message: telebot.types.Message) -> None:
        """Обработчик команды /stop_ami для отключения бота в чате"""
        # Проверка прав администратора
        if not self._is_admin(message):
            self.bot.reply_to(message, "Только администраторы могут отключать Ами.")
            return
            
        chat_id = message.chat.id
        if chat_id not in self.inactive_chats:
            self.inactive_chats.add(chat_id)
            self.bot.reply_to(message, "Ами деактивирована в этом чате.")
        else:
            self.bot.reply_to(message, "Ами уже неактивена в этом чате.")

    def _start_cleanup_thread(self):
        """Запускает фоновый поток для периодической очистки устаревших контекстов"""
        def cleanup_task():
            while True:
                try:
                    time.sleep(3600)  # Очистка каждый час
                    self.context_manager.cleanup_old_contexts()
                except Exception as e:
                    print(f"Ошибка в потоке очистки: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
        cleanup_thread.start()

    def _message_filter(self, message: telebot.types.Message) -> bool:
        # Фильтр сообщений с учетом состояния активности в чате
        is_recent = message.date >= int(self.start_time)
        chat_active = message.chat.id not in self.inactive_chats
        return is_recent and chat_active

    def handle_message(self, message: telebot.types.Message) -> None:
        try:
            # Проверка чата
            if not self._validate_chat(message):
                self.bot.reply_to(message, "К сожелению Ами не доступна в чатах если меньше 5 учасников")
                return
  
            # Пропускаем сообщения без текста
            if not hasattr(message, 'text') or not message.text:
              return
                
            # Check message limits
            user_id = message.from_user.id
            chat_id = message.chat.id
            
            # Skip limit check for admin commands
  
            # Подготовка контекста сообщения
            reply_data = None
            if message.reply_to_message:
                  reply_data = {
                      'text': message.reply_to_message.text or '',
                      'from_user': {
                          'id': message.reply_to_message.from_user.id,
                          'username': message.reply_to_message.from_user.username or "",
                          'first_name': message.reply_to_message.from_user.first_name or ""
                      } if message.reply_to_message.from_user else None
                  }
  
            msg_context = MessageContext(
                  text=message.text,
                  user_id=message.from_user.id,
                  username=message.from_user.username or "",
                  first_name=message.from_user.first_name or "",
                  chat_id=message.chat.id,
                  chat_type=message.chat.type,
                  message_id=message.message_id,
                  reply_to_message=reply_data,
                  thread_id=getattr(message, 'message_thread_id', None)
              )
  
              # Проверяем, должен ли бот ответить на сообщение
            if self.trigger_manager.should_reply(message):
                  # Получаем тип действия из сообщения
                  action_type = self.trigger_manager.get_action_type(message)
                  if not (message.text.startswith('/send_message') and self._is_admin(message)):
                    if not self._check_message_limits(user_id, chat_id):
                        remaining_time = self.user_message_counts[user_id]["reset_time"] - datetime.now()
                        hours, remainder = divmod(remaining_time.seconds, 3600)
                        minutes, _ = divmod(remainder, 60)
                        self.bot.reply_to(
                            message, 
                            f"Лимит сообщений превышен. Лимиты обновятся через {hours} ч. {minutes} мин.Ваш лимит {self.USER_DAILY_LIMIT} в сутки"
                        )
                        return
                    if action_type and action_type in self.trigger_manager.actions:
                            # Вызываем соответствующее действие
                        self.trigger_manager.actions[action_type](message, msg_context)
                    else:
                        # Стандартный ответ текстом
                        self._handle_text_response(message, msg_context)
        except Exception as e:
            print(f"Критическая ошибка обработки сообщения: {e}")
            try:
                self.bot.send_message(message.chat.id, "Произошла ошибка при обработке сообщения")
            except:
                pass

    def _validate_chat(self, message: telebot.types.Message) -> bool:
      
      return (
          message.chat.type == "private" or 
          (message.chat.type == "supergroup" and self.bot.get_chat_members_count(message.chat.id) > 5))
          
    def _handle_text_response(self, message: telebot.types.Message, msg_context: MessageContext) -> None:
        """Обработка стандартного текстового ответа"""
        try:
          print("MessageContext",msg_context)
          response = self.response_generator.generate_response(msg_context)
          
          print("Response",response)
            
          if response:
            self.bot.reply_to(message, response, parse_mode='Markdown')
            print(response)
            print(f"Сообщение: {message.text}")
        except Exception as e:
            print(f"Ошибка при подготовке текстового ответа: {e}")
            print(e)
            self.bot.reply_to(message, "Извините, произошла ошибка при формировании ответа")

    def _handle_voice_request(self, message: telebot.types.Message, msg_context: MessageContext) -> None:
        """Обработка запроса на голосовое сообщение"""
        try:
            response = self.response_generator.generate_response(msg_context)
            if response:
                try:
                    voice_file = self.voice_generator.generate(response)
                    with open(voice_file, "rb") as voice:
                        self.bot.send_voice(message.chat.id, voice)
                    os.remove(voice_file)
                    print(f"Голосовое сообщение: {message.text}")
                except Exception as e:
                    print(f"Ошибка генерации голоса: {e}")
                    # Если не удалось сгенерировать голос, отправляем текстовый ответ
                    self.bot.reply_to(message, response, parse_mode='Markdown')
        except Exception as e:
            print(f"Ошибка при подготовке голосового ответа: {e}")
            self.bot.reply_to(message, "Извините, произошла ошибка при формировании голосового ответа")

    def _handle_image_request(self, message: telebot.types.Message, msg_context: MessageContext) -> None:
        """Обработка запроса на изображение"""
        try:
            response = self.response_generator.generate_response(msg_context)
            links = self.google_scraper.search_images(msg_context.text, num=5)
            if links and len(links) > 0:
                # Отправляем найденное изображение
                self.send_image_from_url(message.chat.id, links[0], caption=response)
            else:
                self.bot.reply_to(message, "Извините, не удалось найти подходящее изображение. " + response)
        except Exception as e:
            print(f"Ошибка при поиске изображения: {e}")
            self.bot.reply_to(message, "Извините, произошла ошибка при поиске изображения")

    def _handle_search_request(self, message: telebot.types.Message, msg_context: MessageContext) -> None:
        """Обработка запроса на поиск информации"""
        self._handle_text_response(message, msg_context)

    def send_image_from_url(self, chat_id, image_url, caption=None):
        """Отправка изображения по URL"""
        try:
            self.bot.send_photo(chat_id, image_url, caption=caption)
            print(f"Image sent successfully: {image_url}")
        except Exception as e:
            print(f"Error sending image: {e}")
            # Fallback message if image sending fails
            self.bot.send_message(chat_id, f"Не удалось отправить изображение: {e}")

    def _is_admin(self, message: telebot.types.Message) -> bool:
        try:
            # Для личных чатов считаем пользователя "админом"
            if message.chat.type == "private":
                return True
                
            chat_member = self.bot.get_chat_member(message.chat.id, message.from_user.id)
            return chat_member.status in ['creator', 'administrator']
        except Exception as e:
            print(f"Ошибка проверки администратора: {e}")
            return False

    def run(self) -> None:
        try:
            print("Бот запущен...")
            self.bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"Критическая ошибка при запуске бота: {e}")

def main():
    try:
        # Создание директории для данных
        os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
        
        # Инициализация компонентов
        ai_client = AIClient("Qwen/Qwen2.5-Coder-demo")
        ai_client.call_in_start()
        sentimental_user = SentimentClassifier()
        
        voice_generator = ElevenLabsVoiceGenerator(Config.ELEVEN_LABS_KEY, Config.VOICE_ID)
        API_KEY = Config.API_KEY_SEARCH
        CX = Config.CX
        google_scraper = GoogleScraper(api_key=API_KEY, cx=CX)
        
        # Создание и запуск бота
        bot = TelegramBot(
            token=Config.TOKEN,
            ai_client=ai_client,
            voice_generator=voice_generator,
            google_scraper=google_scraper,
            sentimental_user= sentimental_user
        )
        
        bot.run()
    except Exception as e:
        print(f"Фатальная ошибка при запуске: {e}")

if __name__ == '__main__':
    main()