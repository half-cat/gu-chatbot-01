from typing import Optional, Any

from django.db import models


class BotManager(models.Manager):
    def get_bot_id_by_type(self, bot_type: int) -> int:
        return self.get(bot_type=bot_type).id


class BotUserManager(models.Manager):
    def get_or_create_user(self, bot_id: int, messenger_user_id: str, user_name: str) -> Any:
        # Todo: Any type replaced by model type
        user, created = self.get_or_create(bot_id=bot_id, messenger_user_id=messenger_user_id)
        if created:
            user.name = user_name
            user.save()
        return user


class ChatManager(models.Manager):
    def get_or_create_chat(self, bot_id: int, chat_id_in_messenger: str, chat_type: int, user: Any) -> Any:
        # Todo: Any type replaced by model type
        chat, created = self.get_or_create(
            bot_id=bot_id,
            id_in_messenger=chat_id_in_messenger,
            type=chat_type,
            bot_user=user
        )
        return chat


class MessageManager(models.Manager):
    def save_message(self,
                     bot_id: int,
                     messenger_user_id: str,
                     user_name: str,
                     chat_id_in_messenger: str,
                     chat_type: int,
                     message_direction: int,
                     message_content_type: int,
                     message_text: Optional[str] = '',
                     message_id_in_messenger: Optional[str] = '') -> None:

        from .models import BotUser, Chat
        # can't import the models at the top of the file because of a circular dependency
        user = BotUser.objects.get_or_create_user(bot_id, messenger_user_id, user_name)
        chat = Chat.objects.get_or_create_chat(bot_id, chat_id_in_messenger, chat_type, user)
        message = self.create(
            bot_id=bot_id,
            bot_user=user,
            chat=chat,
            direction=message_direction,
            content_type=message_content_type,
            id_in_messenger=message_id_in_messenger,
            text=message_text
        )
        message.save()
