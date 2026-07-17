#!/usr/bin/env python3
"""Create extra IMAP mailboxes in greenmail (besides Inbox) and drop a couple
of sample messages in Sent/Junk so the folder list looks realistic.

Roundcube localises the special folders: Sent→Отправленные, Drafts→Черновики,
Junk→Спам, Trash→Корзина, Archive→Архив.

Usage:  python3 tools/make-folders.py [host] [imap_port] [user]
Defaults: 127.0.0.1 3143 demo@localhost
"""
import imaplib
import sys
from email.message import EmailMessage
from email.utils import formatdate

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2] if len(sys.argv) > 2 else 3143)
USER = sys.argv[3] if len(sys.argv) > 3 else "demo@localhost"

imap = imaplib.IMAP4(HOST, PORT)
imap.login(USER, "pass")  # greenmail runs with auth disabled

for f in ["Sent", "Drafts", "Junk", "Trash", "Archive"]:
    try:
        imap.create(f)
        print("created:", f)
    except Exception as e:  # already exists
        print("skip create:", f, e)
    try:
        imap.subscribe(f)     # Roundcube only lists SUBSCRIBED folders
        print("subscribed:", f)
    except Exception as e:
        print("skip subscribe:", f, e)


def append(folder, sender, to, subject, body):
    m = EmailMessage()
    m["From"] = sender
    m["To"] = to
    m["Subject"] = subject
    m["Date"] = formatdate(localtime=True)
    m.set_content(body)
    imap.append(folder, "", None, m.as_bytes())
    print("appended to", folder + ":", subject)


append("Sent", "demo@localhost", "Анна Ковалёва <anna@studio.design>",
       "Re: Правки по макету рассылки — финал",
       "Привет! Внёс правки — отступы в футере и цвет кнопки. "
       "Посмотри обновлённую версию.\n\nСпасибо!")
append("Sent", "demo@localhost", "Дмитрий Соколов <d.sokolov@host.ru>",
       "Re: Счёт за хостинг, июль",
       "Добрый день! Оплатил счёт, чек прикреплю отдельно.")
append("Junk", "Розыгрыш призов <promo@lucky-draw.example>",
       "demo@localhost", "🎁 Вы выиграли iPhone 17 Pro!",
       "Поздравляем! Вы стали победителем. Перейдите по ссылке, чтобы забрать приз.")
append("Archive", "Бухгалтерия <buh@host.ru>", "demo@localhost",
       "Акт выполненных работ за июнь",
       "Направляю акт за прошлый период. Подписанный экземпляр во вложении.")

imap.logout()
print("\nDone.")
