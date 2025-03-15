# Notification bot

## Описание проекта
Notification bot - это Telegram-бот, который предназначен для уведомления об изменении статуса проверки домашнего задания. 
Этот бот опрашивает API сервиса и проверяет статус задачи. При обновлении статуса проводится анализ ответа API и отправляется соответствующее уведомление в Telegram.

## Стек
- Python
- Библиотека 'python-telegram-bot'
- Библиотека 'requests'

## Как развернуть проект
Клонировать репозиторий и перейти в него в командной строке:
```
git clone git@github.com:sunnnssses/notification_bot.git
cd notification_bot
```
Создать и активировать виртуальное окружение:
```
python -m venv venv
. venv/bin/activate (или . venv/Scripts/activate)
```
Установить зависимости:
```
pip install -r requirements.txt
```

## Заполнение .env
Далее необходимо подготовить .env файл со следующими параметрами:
PRACTICUM_TOKEN = 'PRACTICUM_TOKEN'
TELEGRAM_TOKEN = 'TELEGRAM_TOKEN'
TELEGRAM_CHAT_ID = 'TELEGRAM_CHAT_ID'

## Запуск бота
Запустите программу через терминал или из редактора кода:
`python homework.py`

##### Автор:  [Щеткина Елизавета](https://github.com/sunnnssses)