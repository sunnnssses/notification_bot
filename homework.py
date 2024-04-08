from logging.handlers import RotatingFileHandler
import logging
import os
import sys
import time

from dotenv import load_dotenv
from telegram import Bot
import requests

from exceptions import ApiError


load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
)

logger = logging.getLogger(__name__)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
)
file_handler = RotatingFileHandler(
    __file__ + '.log',
    maxBytes=50000000,
    backupCount=3)
stream_handler = logging.StreamHandler(stream=sys.stdout)
file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

RESPONSE_KEY = 'homeworks'

STATUS_MESSAGE = ('Изменился статус проверки работы "{name}". '
                  '{verdict}')


def check_tokens():
    """Проверка доступности переменных окружения."""
    missing_tokens = [token for token in TOKENS if globals()[token] is None]
    if len(missing_tokens) != 0:
        logger.critical(f'Отсутствуют токены: {missing_tokens}!')
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Отправлено сообщение: `{message}`')
    except Exception as error:
        logger.error(f'Ошибка `{error}` при отправке сообщения: `{message}`')


def get_api_answer(timestamp):
    """Получение ответа от API-сервиса."""
    try:
        params = {'from_date': timestamp}
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except requests.RequestException as error:
        error.add_note('Ошибка при обращении к API. Параметры запроса: '
                       f'`{ENDPOINT}`, '
                       f'`{HEADERS}`, '
                       f'`{params}`.')
        raise error
    status_code = homework_statuses.status_code
    if homework_statuses.status_code != requests.codes.ok:
        raise ApiError(f'Получен неожиданный статус сервера: {status_code}')
    homework_statuses = homework_statuses.json()
    if any(key in homework_statuses for key in ['error', 'code']):
        error_message = 'Ошибка при обращении к API.'
        if 'error' in homework_statuses.keys():
            error_message += ' Описание ошибки: ' + homework_statuses['error']
        if 'code' in homework_statuses.keys():
            error_message += ' Код ошибки: ' + homework_statuses['code']
        raise ApiError(error_message)
    return homework_statuses


def check_response(response):
    """Проверика ответа API на соответствие документации."""
    if not isinstance(response, dict):
        error_message = (
            'Тип ответа не соответствует ожидаемому. '
            f'Тип ответа: {type(response)}'
        )
        raise TypeError(error_message)
    if RESPONSE_KEY not in response:
        raise KeyError(f'В ответе отсутствует ключ {RESPONSE_KEY}')
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        error_message = (
            'Неправильный тип поля `homeworks`. '
            f'Тип поля `homeworks`: {type(homeworks)}'
        )
        raise TypeError(error_message)


def parse_status(homework):
    """Извлечение статуса домашней работы работы."""
    try:
        name = homework['homework_name']
        status = homework['status']
    except KeyError as error:
        error.add_note('Ошибка извлечения статуса домашней работы.')
        raise error
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неожиданный статус домашней работы: {status}.')
    verdict = HOMEWORK_VERDICTS[status]
    return STATUS_MESSAGE.format(name=name, verdict=verdict)


def main():
    """Основная логика работы бота."""
    if check_tokens():
        bot = Bot(token=TELEGRAM_TOKEN)
        recent_error_message = ''
        timestamp = int(time.time())

        while True:
            try:
                response = get_api_answer(timestamp)
                check_response(response)
                homeworks = response.get('homeworks')
                if homeworks:
                    homework = homeworks[0]
                    message = parse_status(homework)
                    send_message(bot, message)
                else:
                    logger.debug('Статус домашней работы не изменился.')
                if 'current_date' in response:
                    timestamp = response.get('current_date')
            except Exception as new_error:
                logger.error(new_error)
                if new_error.__str__() != recent_error_message:
                    message = f'Сбой в работе программы: {new_error}'
                    send_message(bot, message)
                    recent_error_message = new_error.__str__()
            time.sleep(RETRY_PERIOD)
    return


if __name__ == '__main__':
    main()
