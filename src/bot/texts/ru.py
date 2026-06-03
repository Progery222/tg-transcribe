# ruff: noqa: RUF001 — legitimate Russian text contains Cyrillic letters that look like Latin.

_STRINGS: dict[str, str] = {
    # /start, /help
    "start_super_admin": (
        "Привет! Вы владелец этого бота.\n\n"
        "<b>Команды</b>\n"
        "/invite — одноразовая ссылка для подписчика\n"
        "/grant &lt;user_id&gt; — добавить подписчика напрямую\n"
        "/revoke &lt;user_id&gt; — отозвать доступ\n"
        "/subscribers — список активных подписчиков\n"
        "/chats — группы, в которых работает бот\n"
        "/digest_now — собрать сводку прямо сейчас\n"
        "/model — выбрать модель распознавания\n"
        "/enable, /disable — переключить мониторинг группы\n"
    ),
    "start_subscriber": (
        "Привет! Вы подписаны на транскрипции этого бота.\n"
        "Сюда будут приходить расшифровки голосовых и видеокружков из всех групп, "
        "в которых работает бот, и ежедневная сводка в 10:00 по Москве."
    ),
    "start_outsider": ("Привет! Этот бот работает по приглашениям. Попросите ссылку у владельца."),
    "start_group": (
        "Я готов транскрибировать. Расшифровки приходят владельцу и подписчикам в ЛС. "
        "Чтобы это работало: добавьте меня админом и отключите Group Privacy в @BotFather."
    ),
    "help": (
        "Этот бот пересылает текстовые расшифровки голосовых и видеокружков подписчикам в ЛС.\n"
        "Доступ выдаёт владелец бота. Получить инвайт можно у него."
    ),
    "help_super_admin": (
        "<b>Команды владельца</b>\n"
        "/invite — одноразовая ссылка\n"
        "/grant &lt;user_id&gt;\n"
        "/revoke &lt;user_id&gt;\n"
        "/subscribers\n"
        "/chats\n"
        "/digest_now\n"
        "/model, /enable, /disable — здесь или в группе"
    ),
    # Transcript fanout (DM to subscribers)
    "transcript_dm": "🎙 <b>[{group_title}]</b> {speaker} · {time_msk}\n«{text}»",
    "transcript_failed_admin": (
        "⚠️ Не удалось транскрибировать сообщение\nГруппа: {chat_title}\nОшибка: {error}"
    ),
    # Access control
    "super_admin_only": "Эта команда доступна только владельцу бота.",
    "group_only": "Эта команда работает только в группе.",
    "grant_need_id": (
        "Укажите числовой user_id: <code>/grant 123456789</code>.\n"
        "Для незнакомых пользователей используйте /invite."
    ),
    "grant_ok": "✅ Подписчик добавлен: <code>{user_id}</code>",
    "grant_already": "Уже подписан: <code>{user_id}</code>",
    "revoke_ok": "✅ Подписчик удалён: <code>{user_id}</code>",
    "revoke_not_found": "Не найден или уже неактивен: <code>{user_id}</code>",
    "subscribers_empty": "Подписчиков пока нет.",
    "subscribers_list_template": "<b>Активные подписчики</b>\n{lines}",
    "subscribers_line": "• <code>{uid}</code> · @{username} · {display}",
    # Chats
    "chats_empty": "Бот ещё не добавлен ни в одну группу.",
    "chats_list_template": "<b>Группы под мониторингом</b>\n{lines}",
    "chats_line": "• {title} (<code>{chat_id}</code>)",
    # Invite
    "invite_created": ("🔗 Одноразовая ссылка для подписчика:\n{url}\nИстекает: {expires}"),
    "invite_used": (
        "✅ Доступ выдан. Транскрипции из групп будут приходить сюда, "
        "плюс ежедневная сводка в 10:00 по Москве."
    ),
    "invite_invalid_or_expired": "Эта ссылка недействительна или уже использована.",
    # Model picker (super-admin only now)
    "model_picker_title": "Выберите модель для этого чата:",
    "model_picker_title_global": "Выберите модель — она применится ко всем группам бота:",
    "model_picker_cancel": "Отмена",
    "model_set": "Модель установлена: <b>{label}</b>",
    "model_set_global": "Модель <b>{label}</b> установлена для всех групп ({count}).",
    "model_cancelled": "Отменено.",
    # Group monitoring toggle
    "enabled": "Мониторинг этой группы включён.",
    "disabled": "Мониторинг этой группы выключен.",
    "toggle_group_only": "Команды /enable и /disable работают только в группе с ботом.",
    # Daily digest
    "digest_caption": "Сводка: {group} · {date}",
    "digest_header": "Группа: {group}\nПериод: {start} — {end} ({tz})",
    "digest_line": "[{time}] {speaker}: {text}",
    "digest_now_running": "Запускаю сводку…",
    "digest_now_done": "Готово. Отправлено документов: {files}",
    "digest_now_failed": "⚠️ Ошибка при сборке сводки. Проверьте логи.",
    "digest_pick_group": "Выберите группу для сводки:",
    "digest_picker_all": "📋 Все группы",
    "digest_cancelled": "Отменено.",
}


def t(key: str, **kwargs: object) -> str:
    template = _STRINGS[key]
    return template.format(**kwargs) if kwargs else template
