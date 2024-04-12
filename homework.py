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


logger = logging.getLogger(__name__)
file_handler = RotatingFileHandler(
    __file__ + '.log',
    maxBytes=50000000,
    backupCount=3)
stream_handler = logging.StreamHandler(stream=sys.stdout)
logging.basicConfig(
    handlers=(file_handler, stream_handler),
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
)

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

CHECK_TOKENS_MESSAGE = 'Отсутствуют токены: {missing_tokens}!'
SEND_MESSAGE = 'Отправлено сообщение: `{message}`'
SEND_MESSAGE_ERROR = 'Ошибка `{error}` при отправке сообщения: `{message}`'
API_ERROR_MESSAGE = ('Ошибка при обращении к API. Параметры запроса: '
                     '`{endpoint}`, '
                     '`{headers}`, '
                     '`{params}`.')
ERROR_KEY_MESSAGE = ' Найден ключ {key} со значением {homework_statuses_key}.'
STATUS_ERROR_MESSAGE = ('Получен неожиданный статус сервера: {status_code}. '
                        'Параметры запроса: '
                        '`{endpoint}`, '
                        '`{headers}`, '
                        '`{params}`.')
STATUS_MESSAGE = ('Изменился статус проверки работы "{name}". '
                  '{verdict}')
RESPONSE_MESSAGE = ('Тип ответа не соответствует ожидаемому. '
                    'Тип ответа: {response}')
RESPONSE_KEY_MESSAGE = 'В ответе отсутствует ключ `homeworks`'
RESPONSE_TYPE_MESSAGE = ('Неправильный тип поля `homeworks`. '
                         'Тип поля `homeworks`: {homeworks}')
PARSE_MESSAGE = 'Ошибка ключа при извлечении статуса домашней работы.'
PARSE_STATUS_MESSAGE = 'Неожиданный статус домашней работы: {status}.'
NO_NEW_STATUS_MESSAGE = 'Статус домашней работы не изменился.'
ERROR_MESSAGE = 'Сбой в работе программы: {new_error}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    missing_tokens = [token for token in TOKENS if globals()[token] is None]
    if missing_tokens:
        logger.critical(
            CHECK_TOKENS_MESSAGE.format(missing_tokens=missing_tokens)
        )
        return False
    return True


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(SEND_MESSAGE.format(message=message))
        return True
    except Exception as error:
        logger.error(SEND_MESSAGE_ERROR.format(error=error, message=message))
        return False


def get_api_answer(timestamp):
    """Получение ответа от API-сервиса."""
    try:
        params = {'from_date': timestamp}
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
    except requests.RequestException:
        raise RuntimeError(API_ERROR_MESSAGE.format(
            endpoint=ENDPOINT, headers=HEADERS, params=params
        ))
    status_code = homework_statuses.status_code
    if homework_statuses.status_code != requests.codes.ok:
        raise ApiError(
            STATUS_ERROR_MESSAGE.format(
                status_code=status_code, endpoint=ENDPOINT,
                headers=HEADERS, params=params
            )
        )
    homework_statuses = homework_statuses.json()
    error_message = API_ERROR_MESSAGE.format(
        endpoint=ENDPOINT, headers=HEADERS, params=params
    )
    error_keys = [key for key in ('error', 'code') if key in homework_statuses]
    if error_keys:
        for key in error_keys:
            error_message += ERROR_KEY_MESSAGE.format(
                key=key, homework_statuses_key=homework_statuses[key]
            )
        raise ApiError(error_message)
    return homework_statuses


def check_response(response):
    """Проверика ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_MESSAGE.format(response=type(response)))
    if 'homeworks' not in response:
        raise KeyError(RESPONSE_KEY_MESSAGE)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            RESPONSE_TYPE_MESSAGE.format(homeworks=type(homeworks))
        )


def parse_status(homework):
    """Извлечение статуса домашней работы работы."""
    try:
        status = homework['status']
        if status not in HOMEWORK_VERDICTS:
            raise ValueError(PARSE_STATUS_MESSAGE.format(status=status))
        return STATUS_MESSAGE.format(
            name=homework['homework_name'], verdict=HOMEWORK_VERDICTS[status]
        )
    except KeyError:
        raise KeyError(PARSE_MESSAGE)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
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
                if send_message(bot, message):
                    timestamp = response.get('current_date', timestamp)
            else:
                logger.debug(NO_NEW_STATUS_MESSAGE)
        except Exception as new_error:
            new_error_message = ERROR_MESSAGE.format(new_error=new_error)
            logger.error(new_error_message)
            if new_error_message != recent_error_message:
                if send_message(bot, new_error_message):
                    recent_error_message = new_error_message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
