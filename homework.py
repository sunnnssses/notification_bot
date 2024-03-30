import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
from telegram import Bot

from exceptions import ApiException, HomeworkException

load_dotenv()

logger = logging.getLogger(__name__)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
handler.setLevel(logging.DEBUG)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
OK_STATUS = 200
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

RESPONSE_KEYS = set([
    'homeworks', 'current_date',
])

HOMEWORK_KEYS = set([
    'id', 'status', 'homework_name',
    'reviewer_comment', 'date_updated', 'lesson_name',
])


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for token_name, token in tokens.items():
        if token is None:
            logger.critical(f'{token_name} отсутсвует!')
            raise SystemExit


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено.')
    except Exception as error:
        logger.error(f'Ошибка отправки сообщения: {error}.')


def get_api_answer(timestamp):
    """Получение ответа от API-сервиса."""
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=timestamp
        )
        homework_statuses.raise_for_status()
        if homework_statuses.status_code != OK_STATUS:
            raise requests.exceptions.HTTPError
        return homework_statuses.json()
    except Exception as error:
        error_message = f'Ошибка при запросе к API: {error}.'
        logger.error(error_message)
        raise ApiException(error_message)


def check_response(response):
    """Проверика ответа API на соответствие документации."""
    if not isinstance(response, dict):
        error_message = (
            'Тип ответа не соответствует ожидаемому. '
            f'Тип ответа: {type(response)}'
        )
        logger.error(error_message)
        raise TypeError(error_message)
    if RESPONSE_KEYS != set(response.keys()):
        error_message = 'Поля ответа не соответствуют ожидаемым.'
        logger.error(error_message)
        raise TypeError(error_message)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        error_message = (
            'Неправильный тип поля `homeworks`. '
            f'Тип поля `homeworks`: {type(homeworks)}'
        )
        logger.error(error_message)
        raise TypeError(error_message)


def parse_status(homework):
    """Извлечение статуса домашней работы работы."""
    try:
        homework_name = homework['homework_name']
        status = homework['status']
    except Exception as error:
        error_message = f'Ошибка чтения статуса: {error}.'
        logger.error(error_message)
        raise HomeworkException(error_message)
    if status not in HOMEWORK_VERDICTS:
        error_message = f'Неожиданный статус домашней работы: {status}.'
        logger.error(error_message)
        raise HomeworkException(error_message)
    verdict = HOMEWORK_VERDICTS[status]
    return (f'Изменился статус проверки работы "{homework_name}". '
            f'{verdict}')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    recent_homework = {}
    error = None
    timestamp = int(time.time()) - RETRY_PERIOD

    while True:
        try:
            response = get_api_answer({'from_date': timestamp})
            check_response(response)
            homeworks = response.get('homeworks')
            if (len(homeworks) != 0):
                homework = homeworks[-1]
                if recent_homework != homework:
                    recent_homework = homework
                    message = parse_status(homework)
                    send_message(bot, message)
                else:
                    logger.debug('Статус домашней работы не изменился.')
        except Exception as new_error:
            if new_error != error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
        timestamp = int(time.time())
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
