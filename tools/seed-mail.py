#!/usr/bin/env python3
"""Seed the greenmail inbox with a few demo messages so the Apple Mail skin's
message list and preview have something to render.

Usage:  python3 tools/seed-mail.py [host] [port] [recipient]
Defaults: 127.0.0.1 3025 demo@localhost
"""
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formatdate

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2] if len(sys.argv) > 2 else 3025)
RCPT = sys.argv[3] if len(sys.argv) > 3 else "demo@localhost"

DEMO = [
    ("Анна Ковалёва <anna@studio.design>", "Правки по макету рассылки — финал",
     "Привет!\n\nПосмотрела последнюю версию макета — почти всё отлично. "
     "Осталось поправить отступы в футере и цвет кнопки.\n\nСпасибо!\nАнна"),
    ("GitHub <noreply@github.com>", "[roundcube/roundcubemail] Новый релиз 1.6.7",
     "A new version has been published. This is a maintenance release with "
     "several bug fixes and security improvements."),
    ("Дмитрий Соколов <d.sokolov@host.ru>", "Счёт за хостинг, июль",
     "Добрый день!\n\nПрикрепляю счёт за текущий месяц. Оплату желательно "
     "провести до 20 числа.\n\nС уважением,\nДмитрий"),
    ("Apple <no_reply@apple.com>", "Ваша квитанция от Apple",
     "Спасибо за покупку. Ниже вы найдёте детали вашего недавнего заказа "
     "в App Store."),
    ("Newsletter Design <hi@uxdaily.io>", "10 трендов интерфейсов 2026 года",
     "В этом выпуске: возвращение скевоморфизма, spatial-интерфейсы, "
     "адаптивная типографика и многое другое."),
]

with smtplib.SMTP(HOST, PORT) as s:
    for sender, subject, body in DEMO:
        m = EmailMessage()
        m["From"] = sender
        m["To"] = RCPT
        m["Subject"] = subject
        m["Date"] = formatdate(localtime=True)
        m.set_content(body)
        s.send_message(m)
        print(f"sent: {subject}")

print(f"\nDone. {len(DEMO)} messages delivered to {RCPT}.")
