import re
from collections import Counter

class SentimentClassifier:
    def __init__(self):
    # Словарь позитивных слов
      self.positive_words = {
        'хорош', 'отлич', 'замечатель', 'прекрас', 'радост',
        'счаст', 'люб', 'восторг', 'удовольств', 'улыбк',
        'смех', 'восхищ', 'благодар', 'удач', 'успех',
        'побед', 'красот', 'вдохнов', 'надежд', 'довер',
        'добр', 'преимуществ', 'достиж', 'соглас', 'правиль',
        'здоров', 'благоприят', 'прият', 'доволь', 'позитив',
        'великолепн', 'ярк', 'сильн', 'тепл', 'забот',
        'друж', 'спокойн', 'гармон', 'лучш', 'вер',
        'значим', 'весел', 'жив', 'мил', 'рад', 'умиротворён',
        'энергичн', 'воодушевл', 'стабильн', 'оптимистичн', 'настроен','целую','мяу','спасибо','лучше'
    }

    # Словарь негативных слов
      self.negative_words = {
        'плох', 'ужас', 'отврат', 'груст', 'печал',
        'бол', 'страда', 'обид', 'зл', 'гнев',
        'разочаров', 'беспокой', 'страх', 'тревог', 'сожал',
        'ненавис', 'неудач', 'провал', 'проблем', 'трудн',
        'несчаст', 'недостат', 'отказ', 'пораж', 'неправиль',
        'жал', 'негатив', 'неприят', 'раздраж', 'недоволь',
        'тоск', 'одиноч', 'нелюб', 'предател', 'разруш',
        'стыд', 'сомнен', 'униз', 'холодн', 'пуст',
        'больн', 'завист', 'скандал', 'агресс', 'обвин',
        'устал', 'нехорош', 'мерз', 'гряз', 'злоб',
        'паник', 'хаос', 'истерик', 'напряж', 'критик',
        'огорчен', 'обремен', 'ошибк', 'шокир', 'запутан','лох','сука','тварь','крым','путин','трамп','война','кровь','убий','уби','самоубийство','нечтожество','секс','наркотики','геи','пидор'
    }

    # Усилители эмоций
      self.amplifiers = {
        'очень', 'крайне', 'чрезвычайно', 'невероятно', 'безумно',
        'абсолютно', 'полностью', 'совершенно', 'максимально', 'исключительно',
        'ультра', 'экстра', 'по-настоящему', 'реально', 'чрезмерно',
        'всецело', 'сильно', 'ужасно', 'страшно', 'безгранично','клево','прикольно'
    }

    # Частицы отрицания
      self.negations = {
        'не', 'нет', 'ни', 'никак', 'никогда', 'нисколько', 'отнюдь',
        'никто', 'ничто', 'нигде', 'нельзя', 'нипочём', 'никоим',
        'ничей', 'никем', 'ничего', 'некому', 'никудышн'
    }

    # Частые окончания русских слов
      self.endings = [
        'ая', 'ый', 'ой', 'ий', 'ей', 'ые', 'ие', 'ого', 'его', 'ому', 'ему',
        'ом', 'ем', 'ой', 'ей', 'ую', 'юю', 'ые', 'ии', 'ях', 'ами', 'ями',
        'ть', 'ти', 'шь', 'ет', 'ут', 'ют', 'ат', 'ят', 'ешь', 'ишь', 'ем',
        'им', 'ете', 'ите', 'ал', 'ял', 'ыл', 'ил', 'ла', 'ло', 'ли', 'ся',
        'сь', 'енн', 'нн', 'ств', 'ост', 'есть', 'ичь', 'аться', 'иться',
        'ющий', 'юща', 'ющи', 'вш', 'авш', 'ивш', 'енн', 'еннo', 'ива', 'ыва'
    ]
    
    def _preprocess_text(self, text):
        # Преобразование текста к нижнему регистру
        text = text.lower()
        
        # Удаление пунктуации (кроме пробелов)
        text = re.sub(r'[^\w\s]', '', text)
        
        # Разделение на слова
        words = text.split()
        
        return words
    
    def _stem_word(self, word):
        """
        Простой алгоритм стемминга для русского языка
        
        Args:
            word (str): Слово для стемминга
        
        Returns:
            str: Основа слова
        """
        if len(word) <= 3:  # Короткие слова оставляем без изменений
            return word
            
        # Удаляем окончания
        for ending in sorted(self.endings, key=len, reverse=True):
            if word.endswith(ending) and len(word) - len(ending) >= 3:
                return word[:-len(ending)]
                
        # Если не нашли окончаний, возвращаем оригинальное слово
        return word
    
    def _word_matches_dictionary(self, word, dictionary):
        """
        Проверяет, соответствует ли слово или его основа словарю
        
        Args:
            word (str): Слово для проверки
            dictionary (set): Словарь для поиска
            
        Returns:
            bool: True если слово или его основа есть в словаре
        """
        stemmed_word = self._stem_word(word)
        
        # Проверяем, соответствует ли основа слова какому-либо элементу в словаре
        for dict_word in dictionary:
            if stemmed_word.startswith(dict_word) or dict_word.startswith(stemmed_word):
                return True
                
        return False
    
    def classify(self, text):
        """
        Классифицирует текст по настроению и возвращает одно слово-характеристику
        
        Args:
            text (str): Текст для анализа
            
        Returns:
            str: Одно слово, описывающее настроение ('позитивное', 'негативное', 'нейтральное')
        """
        if not text:
            return "нейтральное"
        
        words = self._preprocess_text(text)
        
        # Подсчет позитивных и негативных слов с учетом отрицаний и усилителей
        pos_count = 0
        neg_count = 0
        
        i = 0
        while i < len(words):
            word = words[i]
            
            # Проверка, является ли слово отрицанием
            if i < len(words) - 1 and word in self.negations:
                next_word = words[i + 1]
                
                if self._word_matches_dictionary(next_word, self.positive_words):
                    neg_count += 1
                elif self._word_matches_dictionary(next_word, self.negative_words):
                    pos_count += 1
                
                i += 2  # Пропускаем следующее слово, так как мы его уже учли
                continue
            
            # Проверка на усилители
            multiplier = 1
            if i < len(words) - 1 and word in self.amplifiers:
                multiplier = 2
                word = words[i + 1]
                i += 1
            
            # Подсчет позитивных и негативных слов
            if self._word_matches_dictionary(word, self.positive_words):
                pos_count += multiplier
            elif self._word_matches_dictionary(word, self.negative_words):
                neg_count += multiplier
            
            i += 1
        
        # Определение преобладающего настроения
        if pos_count > neg_count:
            if pos_count >= neg_count * 2:
                return "восторженное"
            return "позитивное"
        elif neg_count > pos_count:
            if neg_count >= pos_count * 2:
                return "негативное"
            return "разочарованное"
        else:
            return "нейтральное"
    
    def get_sentiment_details(self, text):
        """
        Возвращает детальную информацию об анализе настроения текста
        
        Args:
            text (str): Текст для анализа
            
        Returns:
            dict: Словарь с деталями анализа
        """
        words = self._preprocess_text(text)
        
        positive_matches = []
        negative_matches = []
        negated_words = []
        amplified_words = []
        
        i = 0
        while i < len(words):
            word = words[i]
            
            # Обработка отрицаний
            if i < len(words) - 1 and word in self.negations:
                next_word = words[i + 1]
                if self._word_matches_dictionary(next_word, self.positive_words):
                    negated_words.append(f"{word} {next_word}")
                elif self._word_matches_dictionary(next_word, self.negative_words):
                    negated_words.append(f"{word} {next_word}")
                i += 2
                continue
            
            # Обработка усилителей
            if i < len(words) - 1 and word in self.amplifiers:
                next_word = words[i + 1]
                if self._word_matches_dictionary(next_word, self.positive_words):
                    amplified_words.append(f"{word} {next_word}")
                elif self._word_matches_dictionary(next_word, self.negative_words):
                    amplified_words.append(f"{word} {next_word}")
                i += 2
                continue
            
            # Обычные слова
            if self._word_matches_dictionary(word, self.positive_words):
                positive_matches.append(word)
            elif self._word_matches_dictionary(word, self.negative_words):
                negative_matches.append(word)
            
            i += 1
        
        sentiment = self.classify(text)
        
        return {
            'sentiment': sentiment,
            'positive_words': positive_matches,
            'negative_words': negative_matches,
            'negated_phrases': negated_words,
            'amplified_phrases': amplified_words
        }


# Пример использования
if __name__ == "__main__":
    classifier = SentimentClassifier()
    
    # Примеры текстов
    texts = [
        "Я очень счастлив сегодня, всё отлично!",
        "Это был ужасный день, всё пошло не так.",
        "Сегодня обычный день, ничего особенного.",
        "Не могу поверить, как мне повезло!",
        "Не хочу больше видеть этот ужасный фильм.",
        "Мне нравится эта прекрасная погода!",
        "Я разочарован результатами соревнований.",
        "Он радостно улыбнулся, увидев старого друга."
    ]
    
    # Классификация примеров
    for text in texts:
        sentiment = classifier.classify(text)
        details = classifier.get_sentiment_details(text)
        print(f'Текст: "{text}"')
        print(f'Настроение: {sentiment}')
        print(f'Позитивные слова: {", ".join(details["positive_words"])}')
        print(f'Негативные слова: {", ".join(details["negative_words"])}')
        print(f'Отрицания: {", ".join(details["negated_phrases"])}')
        print(f'Усиленные выражения: {", ".join(details["amplified_phrases"])}')
        print()