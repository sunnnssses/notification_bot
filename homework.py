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
API_ERROR_MESSAGE = ('Ошибка при обращении к API: {error}. Параметры запроса: '
                     '`{url}`, '
                     '`{headers}`, '
                     '`{params}`.')
ERROR_KEY_MESSAGE = (' Найден ключ {key} со значением {homework_statuses_key}.'
                     ' Параметры запроса: '
                     '`{url}`, '
                     '`{headers}`, '
                     '`{params}`.')
STATUS_ERROR_MESSAGE = ('Получен неожиданный статус сервера: {status_code}. '
                        'Параметры запроса: '
                        '`{url}`, '
                        '`{headers}`, '
                        '`{params}`.')
STATUS_MESSAGE = ('Изменился статус проверки работы "{name}". '
                  '{verdict}')
RESPONSE_MESSAGE = ('Тип ответа не соответствует ожидаемому. '
                    'Тип ответа: {response}')
HOMEWORKS_MISSING_MESSAGE = 'В ответе отсутствует ключ `homeworks`'
HOMEWORKS_WRONG_TYPE_MESSAGE = ('Неправильный тип поля `homeworks`. '
                                'Тип поля `homeworks`: {homeworks}')
PARSE_MESSAGE = 'В домашней работе отстутсвует ключ {key}.'
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
        rq_pars = {
            'url': ENDPOINT,
            'headers': HEADERS,
            'params': {'from_date': timestamp}
        }
        homework_statuses = requests.get(**rq_pars)
    except requests.RequestException as error:
        raise requests.ConnectionError(API_ERROR_MESSAGE.format(
            error, **rq_pars
        ))
    status_code = homework_statuses.status_code
    if homework_statuses.status_code != requests.codes.ok:
        raise ApiError(
            STATUS_ERROR_MESSAGE.format(status_code=status_code, **rq_pars)
        )
    homework_statuses = homework_statuses.json()
    for key in ('error', 'code'):
        if key in homework_statuses:
            raise ApiError(
                ERROR_KEY_MESSAGE.format(
                    key,
                    homework_statuses[key],
                    **rq_pars
                )
            )
    return homework_statuses


def check_response(response):
    """Проверика ответа API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(RESPONSE_MESSAGE.format(response=type(response)))
    if 'homeworks' not in response:
        raise KeyError(HOMEWORKS_MISSING_MESSAGE)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            HOMEWORKS_WRONG_TYPE_MESSAGE.format(homeworks=type(homeworks))
        )


def parse_status(homework):
    """Извлечение статуса домашней работы работы."""
    for key in ('status', 'homework_name'):
        if key not in homework:
            raise KeyError(PARSE_MESSAGE.format(key=key))
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(PARSE_STATUS_MESSAGE.format(status=status))
    return STATUS_MESSAGE.format(
        name=homework['homework_name'], verdict=HOMEWORK_VERDICTS[status]
    )


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
            if not homeworks:
                logger.debug(NO_NEW_STATUS_MESSAGE)
                continue
            if send_message(bot, parse_status(homeworks[0])):
                timestamp = response.get('current_date', timestamp)
        except Exception as new_error:
            error_message = ERROR_MESSAGE.format(new_error=new_error)
            logger.error(error_message)
            if error_message != recent_error_message and send_message(
                bot, error_message
            ):
                recent_error_message = error_message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        handlers=(
            RotatingFileHandler(
                __file__ + '.log',
                maxBytes=50000000,
                backupCount=3
            ),
            logging.StreamHandler(stream=sys.stdout)
        ),
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
    )
    main()
