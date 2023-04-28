from dotenv import load_dotenv
import os
import logging
import requests
import sys
import time
import telegram

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
stream_handler.setFormatter(formatter)

logger.addHandler(stream_handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяем доступность переменных окружения.
    Которые необходимы для работы программы.
    """
    tokens = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for token in tokens:
        if token is None:
            logging.critical('Отсутствует обязательная переменная окружения.'
                             'программа принудительно остановлена.')
            return False
        return True


def send_message(bot, message):
    """отправляем сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.debug(f'Бот отправил сообщение: {message}')
    except Exception as error:
        logger.error(f'Ошибка отправки сообщения: {error}')


def get_api_answer(timestamp):
    """Получаем ответ от API эндпоинта."""
    logger.info('Отправляем запрос к API Практикума')
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception:
        raise ConnectionError('Проблемы с подключением к серверу')
    if response.status_code != 200:
        raise Exception(
            f'Эндпоинт {ENDPOINT} не доступен'
        )
    return response.json()


def check_response(response):
    """Проверяем ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Неверный тип ответа API.')
    if ('homeworks' not in response) or ('current_date' not in response):
        raise KeyError('Отсутствуют обязательные поля'
                       'в ответе API.')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Неверный тип значения поля "homeworks" в ответе API.')
    return homeworks


def parse_status(homework):
    """Получаем статус домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_name is None:
        raise KeyError(f'Отсутствует поле: {homework_name} в ответе API.')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неверный статус работы: {homework_status}')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    new_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if message != new_message:
                    send_message(bot, message)
                    new_message = message
            else:
                logger.debug('Отсутствует новый статус.')
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != new_message:
                send_message(bot, message)
                new_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
