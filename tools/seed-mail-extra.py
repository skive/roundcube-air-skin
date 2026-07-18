#!/usr/bin/env python3
"""Add 20 more demo messages to the greenmail inbox — longer bodies, a few with
document attachments (PDF/DOCX), a few HTML newsletters with inline images.

Usage:  python3 tools/seed-mail-extra.py [host] [port] [recipient]
Defaults: 127.0.0.1 3025 demo@localhost
"""
import io
import struct
import sys
import zlib
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


# --- tiny valid file generators (no third-party deps) -----------------------
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
    buf = io.BytesIO()
    with zipfile_ctx(buf) as z:
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


def zipfile_ctx(buf):
    import zipfile
    return zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)


def make_png(w, h, ca, cb):
    """A W×H PNG with a smooth horizontal gradient from colour ca to cb."""
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter: none
        for x in range(w):
            t = x / max(1, w - 1)
            raw += bytes(int(ca[i] + (cb[i] - ca[i]) * t) for i in range(3))

    def chunk(typ, data):
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8-bit truecolour
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


HOST = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
PORT = int(sys.argv[2] if len(sys.argv) > 2 else 3025)
RCPT = sys.argv[3] if len(sys.argv) > 3 else "demo@localhost"


# --- 20 messages ------------------------------------------------------------
# type: "plain" | "docs" | "html"
MESSAGES = [
    ("Мария Лебедева <m.lebedeva@studio.design>",
     "Итоги встречи по редизайну личного кабинета",
     "plain",
     "Привет!\n\nСпасибо всем, кто был сегодня на встрече — получилось живо и по делу. "
     "Собрала краткое резюме, чтобы ничего не потерялось.\n\n"
     "1. Договорились переносить навигацию в левую колонку и оставить в шапке только поиск и профиль. "
     "Это разгрузит верх экрана и даст больше места основному контенту.\n"
     "2. Карточки заказов делаем крупнее, со статусом-бейджем и датой доставки прямо на превью.\n"
     "3. Тёмную тему берём в работу сразу — не откладываем на второй этап, иначе потом переделывать дороже.\n\n"
     "Дизайн первых экранов пришлю в четверг, чтобы к планёрке в пятницу успели посмотреть. "
     "Если есть замечания по пунктам выше — пишите до среды, внесу в макет.\n\nХорошего вечера!\nМария"),

    ("UX Weekly <digest@uxweekly.io>",
     "Дайджест недели: 7 приёмов микроанимации, которые не раздражают",
     "html",
     "В свежем выпуске разбираем, как анимация помогает пользователю, а не отвлекает его."),

    ("Дмитрий Соколов <d.sokolov@host.ru>",
     "Договор на сопровождение и смета на III квартал",
     "docs",
     "Добрый день!\n\nВысылаю на согласование два документа: обновлённый договор на сопровождение "
     "и смету на третий квартал. По смете основные изменения — добавили резерв часов на доработки "
     "и вынесли хостинг отдельной строкой, как вы просили в прошлый раз.\n\n"
     "Прошу посмотреть до конца недели: если по составу работ всё устраивает, подпишем и начнём "
     "уже с понедельника. По любым вопросам звоните, всё обсудим.\n\nС уважением,\nДмитрий"),

    ("Анна Ковалёва <anna@studio.design>",
     "Правки по макету рассылки — второй круг",
     "plain",
     "Привет!\n\nПосмотрела вторую версию — стало заметно лучше, спасибо. Осталось несколько мелочей:\n\n"
     "• В шапке логотип чуть великоват, уменьши процентов на десять.\n"
     "• Кнопка «Читать дальше» теряется на светлом фоне — давай сделаем её нашим системным синим.\n"
     "• В футере разъехались иконки соцсетей на мобильной ширине, нужно поправить отступы.\n\n"
     "В остальном можно готовить к отправке. Как внесёшь — скинь финальную версию, и я запущу тест "
     "на небольшой сегмент, прежде чем слать всей базе.\n\nСпасибо!\nАнна"),

    ("GitHub <noreply@github.com>",
     "[roundcube/roundcubemail] Дайджест активности репозитория",
     "plain",
     "За последнюю неделю в репозитории заметная активность:\n\n"
     "— слито 12 pull request'ов, из них 4 связаны с исправлениями в скинах;\n"
     "— открыто 7 новых issue, большинство про совместимость с мобильными браузерами;\n"
     "— вышел релиз-кандидат с улучшениями доступности и правками вёрстки писем.\n\n"
     "Полный список изменений доступен на странице релизов. Если планируете обновляться, "
     "обратите внимание на заметки о миграции конфигурации."),

    ("Бухгалтерия <buh@host.ru>",
     "Акт выполненных работ и счёт-фактура за июнь",
     "docs",
     "Здравствуйте!\n\nНаправляю закрывающие документы за июнь: акт выполненных работ и счёт-фактуру. "
     "Пожалуйста, проверьте реквизиты и суммы. Если всё верно, подписанный скан акта пришлите "
     "в ответ до 25 числа — иначе не успеем закрыть период.\n\n"
     "Оригиналы отправим почтой на юридический адрес. По взаиморасчётам вопросов нет, всё сходится.\n\n"
     "С уважением,\nОтдел бухгалтерии"),

    ("Newsletter Design <hi@uxdaily.io>",
     "Тренды интерфейсов: возвращение объёма и мягких теней",
     "html",
     "Скевоморфизм 2.0, живые градиенты и spatial-интерфейсы — что из этого доживёт до продакшена."),

    ("Илья Романов <i.romanov@partner.co>",
     "Предложение о партнёрстве и совместном вебинаре",
     "plain",
     "Добрый день!\n\nМы давно следим за вашими проектами и хотели бы предложить сотрудничество. "
     "Идея простая: провести совместный вебинар про дизайн-системы для продуктовых команд. "
     "Вы делитесь практикой внедрения, мы берём на себя площадку, промо и регистрацию.\n\n"
     "По нашей статистике такие эфиры собирают 400–600 участников, а запись потом ещё долго "
     "приносит лиды обеим сторонам. Готовы обсудить формат, даты и деление аудитории.\n\n"
     "Если тема интересна, предложите пару удобных слотов на следующей неделе для короткого созвона.\n\n"
     "С уважением,\nИлья Романов"),

    ("Apple <no_reply@apple.com>",
     "Ваша квитанция от Apple",
     "plain",
     "Благодарим за покупку.\n\nНиже — детали вашего недавнего заказа в App Store. "
     "Подписка продлится автоматически, если не отменить её не менее чем за 24 часа до окончания периода. "
     "Управлять подписками можно в настройках вашей учётной записи.\n\n"
     "Если вы не совершали эту покупку, немедленно проверьте безопасность своего Apple ID."),

    ("Сергей Николаев <s.nikolaev@dev.team>",
     "Ретро спринта: что заберём в следующий",
     "plain",
     "Коллеги, спасибо за спринт — закрыли почти всё, что планировали.\n\n"
     "Что было хорошо: наконец разгребли техдолг по формам, ускорили сборку почти вдвое, "
     "подключили автоматические скриншот-тесты для писем.\n\n"
     "Что стоит улучшить: задачи заходили в спринт без оценок, из-за этого в середине пришлось "
     "перекраивать план. Предлагаю на груминге договориться не брать в работу тикеты без оценки "
     "и описанных критериев приёмки.\n\n"
     "Действия на следующий спринт я вынес в доску, посмотрите свои карточки.\n\nСергей"),

    ("Хостинг-провайдер <support@hosting.example>",
     "Плановые технические работы в ночь на субботу",
     "plain",
     "Уважаемый клиент!\n\nСообщаем о плановых работах по обновлению сетевого оборудования "
     "в ночь с пятницы на субботу, с 02:00 до 04:00 по московскому времени. "
     "В этот промежуток возможны кратковременные перерывы в доступности сайтов, "
     "суммарно не более 15 минут.\n\n"
     "Данные в безопасности, действий с вашей стороны не требуется. "
     "Приносим извинения за возможные неудобства и благодарим за понимание."),

    ("Магазин «Скрепка» <news@skrepka.shop>",
     "Летняя распродажа: канцелярия и техника со скидкой до 40%",
     "html",
     "Готовимся к новому сезону: подборка для дома и офиса с ощутимыми скидками."),

    ("Екатерина Волкова <e.volkova@hr.company>",
     "Приглашение на собеседование — Senior Product Designer",
     "plain",
     "Здравствуйте!\n\nБлагодарим за отклик на вакансию Senior Product Designer. "
     "Ваше портфолио нам понравилось, особенно кейс про перестройку онбординга.\n\n"
     "Предлагаем встретиться онлайн для знакомства и обсуждения задач. "
     "Встреча займёт около часа: полчаса — про ваш опыт, полчаса — про то, чем живёт команда. "
     "Тестовое задание на этом этапе не требуется.\n\n"
     "Подскажите, пожалуйста, когда вам удобно на следующей неделе, и я пришлю ссылку на созвон.\n\n"
     "Хорошего дня!\nЕкатерина, отдел подбора"),

    ("Павел Тихонов <p.tihonov@client.biz>",
     "Замечания по демо и список вопросов",
     "plain",
     "Добрый день!\n\nПосмотрели демо всей командой — в целом впечатление отличное, спасибо. "
     "Собрал вопросы и замечания в одном письме, чтобы вам было удобнее отвечать.\n\n"
     "1. Экспорт отчёта: нужен ли интернет, или можно выгружать офлайн?\n"
     "2. Права доступа: получится ли ограничить редактирование на уровне отдельных полей?\n"
     "3. Уведомления: можно ли настроить дайджест раз в день вместо письма на каждое событие?\n\n"
     "Если по чему-то ответ «пока нет, но в планах» — тоже напишите, нам важно понимать вектор. "
     "Ждём обратной связи и ориентировочные сроки.\n\nС уважением,\nПавел"),

    ("Смета проекта <pm@studio.design>",
     "Финальная смета и план-график по этапам",
     "docs",
     "Привет!\n\nПрикладываю финальную смету и план-график с разбивкой по этапам. "
     "Разнесла бюджет по трём фазам: аналитика и прототип, дизайн, вёрстка и передача в разработку. "
     "К каждой фазе — контрольная точка и результат, который вы принимаете.\n\n"
     "Резерв заложен в размере 10% от общего объёма, как договаривались, на непредвиденные правки. "
     "Если по этапам и суммам всё ок — согласуем и стартуем аналитику уже на этой неделе.\n\n"
     "Спасибо!\nПроектный офис"),

    ("Конференция DesignConf <hello@designconf.ru>",
     "Программа опубликована — ранние билеты заканчиваются",
     "html",
     "Три дня, пять сцен и воркшопы: смотрите программу и успевайте по раннему тарифу."),

    ("Ольга Морозова <o.morozova@editor.media>",
     "Правки к статье и согласование иллюстраций",
     "plain",
     "Здравствуйте!\n\nОтредактировала вашу статью — читается хорошо, тема раскрыта. "
     "Внесла стилистические правки и сократила пару абзацев во вступлении, там была вода. "
     "Смысл нигде не потерялся, но всё равно пробегитесь глазами перед публикацией.\n\n"
     "Отдельно нужно согласовать иллюстрации: две схемы стоит перерисовать под наш стиль, "
     "а обложку предлагаю сделать более контрастной. Черновики пришлю отдельным письмом.\n\n"
     "Публикацию наметила на следующий вторник — успеваем, если правки вернёте до пятницы.\n\nОльга"),

    ("Команда продукта <product@saas.tools>",
     "Что нового: массовые действия, фильтры и тёмная тема",
     "html",
     "Большое обновление: рассказываем про массовые операции, сохранённые фильтры и новую тему."),

    ("Андрей Гусев <a.gusev@legal.partners>",
     "Комментарии юриста к договору",
     "plain",
     "Добрый день!\n\nПосмотрел договор, в целом он рабочий, но есть несколько мест, которые "
     "стоит уточнить до подписания.\n\n"
     "Пункт 4.2: формулировка про сроки приёмки размыта — предлагаю зафиксировать конкретное "
     "число рабочих дней, иначе спорные ситуации не в нашу пользу.\n"
     "Пункт 7.1: ответственность сторон стоит сделать симметричной.\n"
     "Приложение №2: не хватает порядка передачи исключительных прав на результаты работ.\n\n"
     "Правки внёс в режиме рецензирования, файл верну отдельно. Ничего критичного, "
     "но эти детали лучше закрыть сразу.\n\nС уважением,\nАндрей"),

    ("Служба доставки <track@delivery.example>",
     "Ваш заказ в пути — ожидайте курьера завтра",
     "plain",
     "Здравствуйте!\n\nВаш заказ отправлен и прибудет завтра в интервале с 10:00 до 18:00. "
     "Курьер позвонит примерно за час до приезда. Если время неудобно, его можно перенести "
     "в личном кабинете не позднее 22:00 сегодня.\n\n"
     "При получении проверьте комплектность и целостность упаковки. "
     "Спасибо, что выбираете нас!"),
]


def html_newsletter(preview, banner_cid, chip_cid):
    return f"""\
<!doctype html>
<html><body style="margin:0;padding:0;background:#f4f4f7;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;color:#1d1d1f;">
  <div style="max-width:600px;margin:0 auto;background:#ffffff;">
    <img src="cid:{banner_cid}" width="600" alt="" style="display:block;width:100%;height:auto;border:0;">
    <div style="padding:28px 32px;">
      <p style="font-size:13px;color:#8a8a8e;margin:0 0 8px;text-transform:uppercase;letter-spacing:.04em;">Рассылка</p>
      <h1 style="font-size:24px;line-height:1.25;margin:0 0 14px;">{preview}</h1>
      <p style="font-size:15px;line-height:1.6;margin:0 0 16px;">
        В этом выпуске мы собрали самое важное за неделю. Ниже — короткие разборы,
        ссылки на материалы и пара наблюдений от редакции. Читается за пять минут
        с чашкой кофе.
      </p>
      <img src="cid:{chip_cid}" width="536" alt="" style="display:block;width:100%;height:auto;border-radius:10px;margin:6px 0 18px;">
      <p style="font-size:15px;line-height:1.6;margin:0 0 22px;">
        Если материал был полезен — перешлите его коллеге. А если что-то хотите
        увидеть в следующих выпусках, просто ответьте на это письмо, мы читаем всё.
      </p>
      <a href="#" style="display:inline-block;background:#007aff;color:#ffffff;text-decoration:none;
         font-weight:600;font-size:15px;padding:11px 22px;border-radius:8px;">Читать выпуск</a>
    </div>
    <div style="padding:18px 32px;border-top:1px solid #ececef;font-size:12px;color:#8a8a8e;">
      Вы получили это письмо, потому что подписаны на рассылку. Отписаться можно в один клик.
    </div>
  </div>
</body></html>"""


BANNERS = [
    ((94, 155, 255), (10, 99, 214)),    # blue
    ((255, 106, 136), (255, 59, 48)),   # red/pink
    ((94, 224, 138), (26, 158, 75)),    # green
    ((255, 177, 94), (255, 138, 0)),    # orange
    ((197, 139, 255), (138, 63, 252)),  # purple
]


def build(sender, subject, kind, body, idx):
    m = EmailMessage()
    m["From"] = sender
    m["To"] = RCPT
    m["Subject"] = subject
    m["Date"] = formatdate(localtime=True)

    if kind == "html":
        m.set_content(body + "\n\n(Это HTML-письмо — откройте в почтовом клиенте "
                             "с поддержкой картинок.)")
        banner_cid = make_msgid(domain="demo.local")[1:-1]
        chip_cid = make_msgid(domain="demo.local")[1:-1]
        m.add_alternative(html_newsletter(subject, banner_cid, chip_cid), subtype="html")
        html_part = m.get_payload()[1]
        ca, cb = BANNERS[idx % len(BANNERS)]
        html_part.add_related(make_png(600, 200, ca, cb), maintype="image",
                              subtype="png", cid="<%s>" % banner_cid)
        html_part.add_related(make_png(536, 120, cb, ca), maintype="image",
                              subtype="png", cid="<%s>" % chip_cid)
    else:
        m.set_content(body)
        if kind == "docs":
            m.add_attachment(make_pdf(subject), maintype="application", subtype="pdf",
                             filename="Договор.pdf")
            m.add_attachment(make_docx(subject), maintype="application",
                             subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                             filename="Смета.docx")
    return m


def main():
    with smtplib.SMTP(HOST, PORT) as s:
        for i, (sender, subject, kind, body) in enumerate(MESSAGES):
            s.send_message(build(sender, subject, kind, body, i))
            tag = {"html": "HTML+img", "docs": "PDF+DOCX", "plain": "text"}[kind]
            print(f"sent [{tag:9}]: {subject}")
    print(f"\nDone. {len(MESSAGES)} messages delivered to {RCPT}.")


if __name__ == "__main__":
    main()
