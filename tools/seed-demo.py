#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fill the greenmail demo account: 132 inbox messages (newest has 10 attachments)
and 30 subscribed work folders (lightly populated). Idempotent — purges INBOX and
the work folders before seeding. Uses IMAP APPEND so dates/flags are deterministic.

Usage:  python3 tools/seed-demo.py [host] [imap_port] [user]
Defaults: 127.0.0.1 3143 demo@localhost   (greenmail runs with auth disabled)
"""
import base64
import imaplib
import io
import json
import random
import struct
import sys
import time
import zipfile
import zlib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
IMAP_PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 3143
USER = sys.argv[3] if len(sys.argv) > 3 else "demo@localhost"
RCPT = USER

random.seed(20260720)  # deterministic run-to-run

# --------------------------------------------------------------------------- #
# file generators (no third-party deps)
# --------------------------------------------------------------------------- #
def make_pdf(title):
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
    offs = []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, o)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offs:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return bytes(out)


def _ooxml(parts):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
    return buf.getvalue()


def make_docx(title):
    return _ooxml({
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>',
        "word/document.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>' + title + '</w:t></w:r></w:p></w:body></w:document>',
    })


def make_xlsx(title):
    return _ooxml({
        "[Content_Types].xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '</Types>',
        "_rels/.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        "xl/_rels/workbook.xml.rels":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '</Relationships>',
        "xl/workbook.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Смета" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/worksheets/sheet1.xml":
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>' + title + '</t></is></c></row></sheetData></worksheet>',
    })


def make_png(w, h, ca, cb):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            t = x / max(1, w - 1)
            raw += bytes(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))

    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def make_zip(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def make_ics(summary):
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//demo//RU\r\nBEGIN:VEVENT\r\n"
            "UID:" + make_msgid(domain="demo.local")[1:-1] + "\r\n"
            "DTSTAMP:20260720T090000Z\r\nDTSTART:20260722T110000Z\r\nDTEND:20260722T120000Z\r\n"
            "SUMMARY:" + summary + "\r\nLOCATION:Zoom\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")


# --------------------------------------------------------------------------- #
# IMAP modified UTF-7 (RFC 3501 5.1.3) for Cyrillic folder names
# --------------------------------------------------------------------------- #
def imap_utf7(s):
    res, i, n = [], 0, len(s)
    while i < n:
        if 0x20 <= ord(s[i]) <= 0x7e:
            res.append("&-" if s[i] == "&" else s[i])
            i += 1
        else:
            j = i
            while j < n and not (0x20 <= ord(s[j]) <= 0x7e):
                j += 1
            b = base64.b64encode(s[i:j].encode("utf-16-be")).decode("ascii").rstrip("=")
            res.append("&" + b.replace("/", ",") + "-")
            i = j
    return "".join(res)


# --------------------------------------------------------------------------- #
# HTML newsletter (inline images)
# --------------------------------------------------------------------------- #
def html_newsletter(title, banner_cid, chip_cid):
    return f"""\
<!doctype html><html><body style="margin:0;padding:0;background:#f4f4f7;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;color:#1d1d1f;">
  <div style="max-width:600px;margin:0 auto;background:#fff;">
    <img src="cid:{banner_cid}" width="600" alt="" style="display:block;width:100%;height:auto;border:0;">
    <div style="padding:28px 32px;">
      <p style="font-size:13px;color:#8a8a8e;margin:0 0 8px;text-transform:uppercase;letter-spacing:.04em;">Рассылка</p>
      <h1 style="font-size:24px;line-height:1.25;margin:0 0 14px;">{title}</h1>
      <p style="font-size:15px;line-height:1.6;margin:0 0 16px;">В этом выпуске — самое важное за неделю: короткие разборы, ссылки и пара наблюдений от редакции.</p>
      <img src="cid:{chip_cid}" width="536" alt="" style="display:block;width:100%;height:auto;border-radius:10px;margin:6px 0 18px;">
      <a href="#" style="display:inline-block;background:#007aff;color:#fff;text-decoration:none;font-weight:600;font-size:15px;padding:11px 22px;border-radius:8px;">Читать выпуск</a>
    </div>
    <div style="padding:18px 32px;border-top:1px solid #ececef;font-size:12px;color:#8a8a8e;">Вы получили это письмо, потому что подписаны на рассылку.</div>
  </div></body></html>"""


BANNERS = [((94, 155, 255), (10, 99, 214)), ((255, 106, 136), (255, 59, 48)),
           ((94, 224, 138), (26, 158, 75)), ((255, 177, 94), (255, 138, 0)),
           ((197, 139, 255), (138, 63, 252))]

# --------------------------------------------------------------------------- #
# content pool: (sender, subject, kind, body)  kind: plain | html | docs
# --------------------------------------------------------------------------- #
BODY = ("Добрый день!\n\n{L}\n\nЕсли по этому вопросу есть замечания или предложения — "
        "напишите в ответ, обсудим до конца недели.\n\nС уважением,\n{N}")
LINES = [
    "Посмотрел последнюю версию — в целом всё хорошо, осталось поправить пару мелочей в футере.",
    "Собрал краткое резюме встречи, чтобы ничего не потерялось: договорились переносить навигацию влево.",
    "Высылаю на согласование обновлённые документы, основные изменения — резерв часов и хостинг отдельной строкой.",
    "Направляю закрывающие документы за период. Проверьте, пожалуйста, реквизиты и суммы.",
    "Предлагаем встретиться онлайн для знакомства и обсуждения задач. Тестовое задание не требуется.",
    "Посмотрели демо всей командой — впечатление отличное. Собрал вопросы одним письмом.",
    "Отредактировала статью — читается хорошо. Отдельно нужно согласовать иллюстрации.",
    "Плановые технические работы в ночь на субботу с 02:00 до 04:00. Действий с вашей стороны не требуется.",
    "Ваш заказ отправлен и прибудет завтра в интервале с 10:00 до 18:00. Курьер позвонит заранее.",
    "Спасибо за спринт — закрыли почти всё. На ретро предлагаю не брать задачи без оценок.",
    "Комментарии по договору: пункт 4.2 стоит уточнить по срокам приёмки, 7.1 сделать симметричным.",
    "Готовим новый сезон рассылки: подборка материалов и пара анонсов внутри.",
    "Обновление продукта: массовые операции, сохранённые фильтры и новая тёмная тема.",
    "Напоминаю про планёрку в пятницу. Прикреплю повестку и ссылку на созвон ближе к дате.",
    "По бюджету на квартал всё сходится, отправляю смету с разбивкой по этапам на согласование.",
]
NAMES = [
    ("Мария Лебедева", "m.lebedeva@studio.design"), ("Анна Ковалёва", "anna@studio.design"),
    ("Дмитрий Соколов", "d.sokolov@host.ru"), ("Сергей Николаев", "s.nikolaev@dev.team"),
    ("Илья Романов", "i.romanov@partner.co"), ("Екатерина Волкова", "e.volkova@hr.company"),
    ("Павел Тихонов", "p.tihonov@client.biz"), ("Ольга Морозова", "o.morozova@editor.media"),
    ("Андрей Гусев", "a.gusev@legal.partners"), ("Бухгалтерия", "buh@host.ru"),
    ("Команда продукта", "product@saas.tools"), ("GitHub", "noreply@github.com"),
    ("Apple", "no_reply@apple.com"), ("Хостинг-провайдер", "support@hosting.example"),
    ("Служба доставки", "track@delivery.example"),
]
SERVICES = [
    ("UX Weekly", "digest@uxweekly.io", "Дайджест недели: 7 приёмов микроанимации"),
    ("Newsletter Design", "hi@uxdaily.io", "Тренды интерфейсов: объём и мягкие тени"),
    ("Магазин «Скрепка»", "news@skrepka.shop", "Летняя распродажа: техника со скидкой до 40%"),
    ("Конференция DesignConf", "hello@designconf.ru", "Программа опубликована — ранние билеты"),
    ("Команда продукта", "product@saas.tools", "Что нового: массовые действия и фильтры"),
]
SUBJECTS = [
    "Правки по макету рассылки", "Итоги встречи по редизайну", "Договор на сопровождение",
    "Акт и счёт-фактура за период", "Приглашение на собеседование", "Замечания по демо",
    "Правки к статье", "Плановые технические работы", "Ваш заказ в пути",
    "Ретро спринта", "Комментарии юриста к договору", "Финальная смета и план-график",
    "Отчёт по проекту за неделю", "Согласование бюджета на квартал", "Повестка планёрки",
]

BASE = []
for i in range(len(SUBJECTS)):
    n = NAMES[i % len(NAMES)]
    line = LINES[i % len(LINES)]
    kind = "docs" if i % 5 == 2 else "plain"
    BASE.append((f"{n[0]} <{n[1]}>", SUBJECTS[i], kind,
                 BODY.format(L=line, N=n[0])))
for s in SERVICES:
    BASE.append((f"{s[0]} <{s[1]}>", s[2], "html",
                 "В свежем выпуске разбираем самое важное за неделю."))


def to_bytes(m):
    # keep each header on one line: folding a non-ASCII filename into RFC2231
    # continuations (filename*0*/filename*1*) makes Roundcube drop the name and
    # show "Часть N" instead. 998 = RFC 5322 hard line limit.
    return m.as_bytes(policy=m.policy.clone(max_line_length=998))


def build(sender, subject, kind, body, i):
    m = EmailMessage()
    m["From"] = sender
    m["To"] = RCPT
    m["Subject"] = subject
    if kind == "html":
        m.set_content(body + "\n\n(HTML-письмо — откройте с поддержкой картинок.)")
        bc = make_msgid(domain="demo.local")[1:-1]
        cc = make_msgid(domain="demo.local")[1:-1]
        m.add_alternative(html_newsletter(subject, bc, cc), subtype="html")
        part = m.get_payload()[1]
        ca, cb = BANNERS[i % len(BANNERS)]
        part.add_related(make_png(600, 200, ca, cb), maintype="image", subtype="png", cid="<%s>" % bc)
        part.add_related(make_png(536, 120, cb, ca), maintype="image", subtype="png", cid="<%s>" % cc)
    else:
        m.set_content(body)
        if kind == "docs":
            m.add_attachment(make_pdf(subject), maintype="application", subtype="pdf", filename="Договор.pdf")
            m.add_attachment(make_xlsx(subject), maintype="application",
                             subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="Смета.xlsx")
    return m


def build_mega():
    """The newest inbox message — 10 attachments of varied types."""
    m = EmailMessage()
    m["From"] = "Проектный офис <pm@studio.design>"
    m["To"] = RCPT
    m["Subject"] = "Пакет документов по проекту «Атлас» — 10 файлов"
    m.set_content(
        "Добрый день!\n\nСобрал в одном письме весь пакет по проекту «Атлас»: договор, смету, "
        "техзадание, макет главной, выгрузку данных, бриф, конфигурацию, архив материалов, "
        "приглашение на встречу и краткое README.\n\nПосмотрите, пожалуйста, и подтвердите — "
        "если всё ок, стартуем в понедельник.\n\nС уважением,\nПроектный офис")
    atts = [
        ("Договор №2026-07.pdf", make_pdf("Dogovor Atlas 2026-07"), "application", "pdf"),
        ("Смета.xlsx", make_xlsx("Смета проекта Атлас"), "application",
         "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("Техническое задание.docx", make_docx("Техническое задание — Атлас"), "application",
         "vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("Макет главной.png", make_png(600, 360, (94, 155, 255), (10, 99, 214)), "image", "png"),
        ("Выгрузка.csv", "id;этап;часы;сумма\n1;Аналитика;40;120000\n2;Дизайн;80;240000\n3;Вёрстка;60;180000\n".encode("utf-8"),
         "text", "csv"),
        ("Бриф.txt", "Бриф проекта «Атлас»\n\nЦель: перезапуск личного кабинета.\nСроки: 8 недель.\nКоманда: 4 человека.\n".encode("utf-8"),
         "text", "plain"),
        ("Конфигурация.json", json.dumps({"project": "Атлас", "phase": "kickoff", "budget": 540000,
         "team": ["pm", "design", "dev"]}, ensure_ascii=False, indent=2).encode("utf-8"),
         "application", "json"),
        ("Материалы.zip", make_zip({"readme.txt": "Материалы проекта Атлас",
         "palette.txt": "#007aff / #0a84ff"}), "application", "zip"),
        ("Встреча.ics", make_ics("Кик-офф проекта «Атлас»").encode("utf-8"), "text", "calendar"),
        ("README.md", "# Проект «Атлас»\n\n- Договор\n- Смета\n- ТЗ\n- Макет\n\nСтарт в понедельник.\n".encode("utf-8"),
         "text", "markdown"),
    ]
    for fn, data, mt, st in atts:
        m.add_attachment(data, maintype=mt, subtype=st, filename=fn)
    return m


FOLDERS = [
    "Клиенты", "Проект «Атлас»", "Проект «Орион»", "Проект «Меркурий»", "Договоры",
    "Счета и оплаты", "Бухгалтерия", "Отчёты", "Аналитика", "Маркетинг",
    "Рассылки", "SMM", "Дизайн-система", "Макеты", "Разработка",
    "Релизы", "Баг-репорты", "Поддержка", "Инфраструктура", "Безопасность",
    "Юристы", "Закупки", "Партнёры", "HR и найм", "Командировки",
    "Планёрки", "Ретроспективы", "Идеи", "Архив 2025", "Разное",
]


def main():
    im = imaplib.IMAP4(HOST, IMAP_PORT)
    im.login(USER, "pass")  # greenmail: auth disabled

    def purge(mbox_enc):
        try:
            im.select(mbox_enc)
            typ, d = im.search(None, "ALL")
            ids = d[0].split() if d and d[0] else []
            if ids:
                im.store(",".join(x.decode() for x in ids), "+FLAGS", "\\Deleted")
                im.expunge()
        except Exception as e:
            print("purge skip", mbox_enc, e)

    now = time.time()

    # --- 30 work folders, purge + light fill ------------------------------- #
    folder_msgs = 0
    for fi, name in enumerate(FOLDERS):
        q = '"' + imap_utf7(name) + '"'  # quoted: names may contain spaces
        try:
            im.create(q)
        except Exception:
            pass
        try:
            im.subscribe(q)
        except Exception as e:
            print("subscribe skip", name, e)
        purge(q)
        k = 2 + (fi % 4)  # 2..5 messages
        for j in range(k):
            sender, subject, kind, body = BASE[(fi * 3 + j) % len(BASE)]
            m = build(sender, f"[{name}] {subject}", kind, body, fi + j)
            ts = now - (fi * 5 + j) * 3600 * 8 - 3600
            fl = None if j == 0 else "(\\Seen)"  # 1 unread per folder
            im.append(q, fl, imaplib.Time2Internaldate(ts), to_bytes(m))
            folder_msgs += 1
        print(f"folder ok: {name} (+{k})")

    # --- INBOX: purge then 132 messages ------------------------------------ #
    purge("INBOX")

    # 131 regular, dated oldest..newest; then the mega message as the newest
    total = 132
    gaps = [random.uniform(1.5, 26.0) for _ in range(total)]  # hours between msgs
    # assign timestamps descending from "just before now" for the 131 regulars
    dates = []
    acc = 2.0  # start 2h before the mega message
    for g in gaps:
        dates.append(now - acc * 3600)
        acc += g
    # dates[0] newest regular ... dates[130] oldest

    prefixes = ["", "Re: ", "Re: ", "Fwd: ", ""]
    for k in range(total - 1):  # 131 regular messages
        sender, subject, kind, body = BASE[k % len(BASE)]
        subj = prefixes[k % len(prefixes)] + subject
        m = build(sender, subj, kind, body, k)
        ts = dates[k]
        m["Date"] = formatdate(ts, localtime=True)
        flags = []
        if random.random() < 0.55:
            flags.append("\\Seen")
        if random.random() < 0.12:
            flags.append("\\Flagged")
        fl = "(%s)" % " ".join(flags) if flags else None
        im.append("INBOX", fl, imaplib.Time2Internaldate(ts), to_bytes(m))
        if (k + 1) % 25 == 0:
            print(f"  inbox {k + 1}/131 regular")

    # the newest message = 10 attachments, unread + flagged so it stands out
    mega = build_mega()
    mega["Date"] = formatdate(now, localtime=True)
    im.append("INBOX", "(\\Flagged)", imaplib.Time2Internaldate(now), to_bytes(mega))
    print("  inbox: mega message with 10 attachments (newest)")

    # --- verify ------------------------------------------------------------ #
    im.select("INBOX")
    typ, d = im.search(None, "ALL")
    inbox_n = len(d[0].split()) if d and d[0] else 0
    typ, du = im.search(None, "UNSEEN")
    unseen = len(du[0].split()) if du and du[0] else 0
    typ, data = im.list()
    nfolders = sum(1 for x in data if b'"INBOX"' not in x)
    im.logout()
    print("\n==== SUMMARY ====")
    print(f"INBOX: {inbox_n} messages ({unseen} unread)")
    print(f"work folders created: {len(FOLDERS)} (+{folder_msgs} messages in folders)")
    print(f"IMAP LIST entries (incl. INBOX): {len(data)}")


if __name__ == "__main__":
    main()
