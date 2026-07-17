#!/usr/bin/env python3
"""Seed the greenmail inbox with a few demo messages so the Apple Mail skin's
message list and preview have something to render.

Usage:  python3 tools/seed-mail.py [host] [port] [recipient]
Defaults: 127.0.0.1 3025 demo@localhost
"""
import io
import smtplib
import sys
import zipfile
from email.message import EmailMessage
from email.utils import formatdate


def make_pdf(title):
    """A tiny but valid single-page PDF."""
    text = title.encode("latin-1", "replace")
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]"
        b"/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
        b"<</Length 60>>\nstream\nBT /F1 24 Tf 72 760 Td (" + text + b") Tj ET\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return bytes(out)


def make_docx(title):
    """A minimal but valid .docx (OOXML zip)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>')
        z.writestr("_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
        z.writestr("word/document.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>' + title + '</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()

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

    # one message with real PDF + DOCX attachments
    m = EmailMessage()
    m["From"] = "Дмитрий Соколов <d.sokolov@host.ru>"
    m["To"] = RCPT
    m["Subject"] = "Договор и смета по проекту"
    m["Date"] = formatdate(localtime=True)
    m.set_content("Добрый день!\n\nПрикладываю договор и смету по проекту — "
                  "посмотрите, пожалуйста, и подтвердите.\n\nС уважением,\nДмитрий")
    m.add_attachment(make_pdf("Dogovor"), maintype="application", subtype="pdf",
                     filename="Договор.pdf")
    m.add_attachment(make_docx("Смета проекта"),
                     maintype="application",
                     subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                     filename="Смета.docx")
    s.send_message(m)
    print("sent: Договор и смета по проекту (2 attachments)")

print(f"\nDone. {len(DEMO) + 1} messages delivered to {RCPT}.")
