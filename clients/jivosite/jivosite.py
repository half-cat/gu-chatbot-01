from datetime import datetime, timedelta
import requests
import logging
from typing import Dict, Any, Optional

from bot.models import Bot, Message
from clients.exceptions import JivoServerError
from constants import MessageDirection, ChatType, MessageContentType, BotType
from entities import EventCommandToSend, EventCommandReceived
from clients.jivosite.jivo_entities import JivoEvent, JivoIncomingWebhook
from clients.jivosite.jivo_constants import JivoEventType, JivoMessageType, JIVO_WH_KEY, JIVO_TOKEN
from bot.apps import SingletonAPS


logger = logging.getLogger('clients')
bot_scheduler = SingletonAPS().get_aps


class JivositeClient:
    """Клиент для работы с социальной платформой JivoSite.

    Содержит методы для преобразования входящих вебхуков в формат ECR,
    формирования ECTS на основе сформированного ботом ответа
    и отправки сообщения в систему Jivo.
    """

    headers: Dict[str, Any] = {'Content-Type': 'application/json'}
    command_cache: Dict[str, Dict[str, Optional[str]]] = {}
    _send_link = 'https://bot.jivosite.com/webhooks/{}/{}'.format(
        JIVO_WH_KEY, JIVO_TOKEN
    )

    def form_jivo_event(self, payload: EventCommandToSend) -> JivoEvent:
        """Создаёт программный объект с данными исходящего сообщения, готовыми для отправки."""

        event_data: Dict[str, Any] = {
            'event': JivoEventType.BOT_MESSAGE,
            # todo think about how to work this around
            'id': str(payload.message_id),
            'client_id': payload.chat_id_in_messenger,
        }

        msg_data: Dict[str, Any] = {
            'text': payload.payload.text,
            'timestamp': datetime.now().timestamp()
        }

        if payload.inline_buttons:
            msg_data['title'] = payload.payload.text
            msg_data['type'] = JivoMessageType.BUTTONS
            msg_data['buttons'] = [
               {
                   'text': payload.inline_buttons[i].text,
                   'id': i,
               } for i in range(len(payload.inline_buttons))]
            # todo pretty much a hack, but a good solution kinda requires
            # passing more data in base commands tbh
            if payload.inline_buttons[0].action.payload.find('greeting'):
                msg_data['buttons'].append({
                    'text': 'Переключиться на оператора',
                    'id': 0,
                })
        else:
            msg_data['type'] = JivoMessageType.TEXT
        event_data['message'] = msg_data
        event = JivoEvent.Schema().load(event_data)

        logger.debug(event)

        if payload.inline_buttons:
            self.command_cache[payload.chat_id_in_messenger] = {
                btn.text: btn.action.payload for btn in payload.inline_buttons
            }

        return event

    def _invite_agent(self, wh: JivoIncomingWebhook):
        data = {
            'event': 'INVITE_AGENT',
            # todo more magic hacks
            'id': -int(wh.client_id),
            'client_id': wh.client_id,
            'chat_id': wh.chat_id,
        }
        event = JivoEvent.Schema().load(data)
        bot_scheduler.add_job(
            self._post_to_platform,
            'interval',
            seconds=5,
            next_run_time=datetime.now(),
            end_date=datetime.now() + timedelta(minutes=5),
            args=[data['id'], self._send_link, event.Schema().dumps(event)],
            id=f'jivo_{wh.client_id}',
            )

    def parse_jivo_webhook(self, wh: JivoIncomingWebhook) -> EventCommandReceived:
        """Преобразует объект входящего вебхука в формат входящей команды бота - ECR."""

        # формирование объекта с данными для ECR
        ecr_data: Dict[str, Any] = {
            'bot_id': Bot.objects.get_bot_id_by_type(BotType.TYPE_JIVOSITE.value),
            'chat_id_in_messenger': wh.client_id,  # important, do not change
            'content_type': MessageContentType.COMMAND,
            'payload': {
                'direction': MessageDirection.RECEIVED,
                'command': wh.message.button_id,  # it doesn't do anything.
                'text': wh.message.text,
            },
            'chat_type': ChatType.PRIVATE,
            # switched places
            'user_id_in_messenger': str(wh.chat_id),
            'user_name_in_messenger': 'Тест',
            'message_id_in_messenger': str(wh.sender.id),
            'reply_id_in_messenger': None,
            'ts_in_messenger': str(datetime.fromtimestamp(int(wh.message.timestamp))),
        }

        try:
            if self.command_cache[wh.client_id]:
                ecr_data['payload']['command'] = self.command_cache[wh.client_id][wh.message.text]
        except KeyError as err:
            logger.debug(f'nothing in command_cache: {err.args}')

        if wh.message.text == 'Переключиться на оператора':
            logger.info('Agent invited: {}'.format(wh.client_id))
            self._invite_agent(wh)
            # todo more hacks
            ecr_data['payload']['command'] = '{"type": "invite", "id": 0}'

        ecr = EventCommandReceived.Schema().load(ecr_data)

        logger.debug(ecr)

        return ecr

    def _post_to_platform(self, message_id: int, send_link: str, data: str,) -> None:
        print('Trying to send...')

        try:
            r = requests.post(send_link, headers=self.headers, data=data)
            logger.debug(f'JIVO answered: {r.text}')
            bot_scheduler.remove_job(f'jivo_{message_id}')
            if 'error' in r.json():
                err = r.json()['error']
                logger.error(f'OK error: {err["code"]} -> {err["message"]}')
                raise JivoServerError(err["code"], err["message"])
            if message_id > 0:
                Message.objects.set_sent(message_id)
        except (requests.Timeout, requests.ConnectionError) as e:
            logger.error(f'JIVO unreachable{e.args}')

    def send_message(self, payload: EventCommandToSend) -> None:
        """Отправляет соответствующее используемой команде формата ECTS сообщение в Jivo."""

        msg = self.form_jivo_event(payload)
        send_link = 'https://bot.jivosite.com/webhooks/{}/{}'.format(
            JIVO_WH_KEY, JIVO_TOKEN
        )
        data = msg.Schema().dumps(msg)

        logger.debug(f'Sending to JIVO: {data}')

        bot_scheduler.add_job(
            self._post_to_platform,
            'interval',
            seconds=5,
            next_run_time=datetime.now(),
            end_date=datetime.now() + timedelta(minutes=5),
            args=[payload.message_id, send_link, data],
            id=f'jivo_{payload.message_id}',
            )