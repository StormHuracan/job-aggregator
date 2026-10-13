class HHIntegrationError(Exception):
    """Базовая ошибка интеграции с HH.ru.

    Сообщения не должны содержать токены и секреты.
    """
