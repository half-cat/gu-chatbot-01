from enum import Enum


class JivoResponseType:
    OK = '200 OK'
    BAD_REQUEST = '400 Bad Request'
    UNAUTHORIZED = '401 Unauthorized'
    FORBIDDEN = '403 Forbidden'
    NOT_FOUND = '404 Not Found'
    METHOD_NOT_ALLOWED = '405 Method Not Allowed'
    TOO_MANY_REQUESTS = '429 Too Many Request'
    INTERNAL_SERVER_ERROR = '500 Internal Server Error'
    BAD_GATEWAY = '502 Bad Gateway'
    SERVICE_UNAVAILABLE = '503 Service Unavailable'
    GATEWAY_TIMEOUT = '504 Gateway Timeout'


class JivoEventType(Enum):
    CLIENT_MESSAGE = 'CLIENT_MESSAGE'
    BOT_MESSAGE = 'BOT_MESSAGE'
    INVITE_AGENT = 'INVITE_AGENT'
    AGENT_JOINED = 'AGENT_JOINED'
    AGENT_UNAVAILABLE = 'AGENT_UNAVAILABLE'


class JivoMessageType(Enum):
    TEXT = 'TEXT'
    MARKDOWN = 'MARKDOWN'
    BUTTONS = 'BUTTONS'