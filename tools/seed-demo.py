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
            '<sheets><sheet name="Estimate" sheetId="1" r:id="rId1"/></sheets></workbook>',
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
      <p style="font-size:13px;color:#8a8a8e;margin:0 0 8px;text-transform:uppercase;letter-spacing:.04em;">Newsletter</p>
      <h1 style="font-size:24px;line-height:1.25;margin:0 0 14px;">{title}</h1>
      <p style="font-size:15px;line-height:1.6;margin:0 0 16px;">This issue rounds up the week's highlights: short reviews, links and a few notes from the editors.</p>
      <img src="cid:{chip_cid}" width="536" alt="" style="display:block;width:100%;height:auto;border-radius:10px;margin:6px 0 18px;">
      <a href="#" style="display:inline-block;background:#007aff;color:#fff;text-decoration:none;font-weight:600;font-size:15px;padding:11px 22px;border-radius:8px;">Read the issue</a>
    </div>
    <div style="padding:18px 32px;border-top:1px solid #ececef;font-size:12px;color:#8a8a8e;">You received this email because you're subscribed to our newsletter.</div>
  </div></body></html>"""


BANNERS = [((94, 155, 255), (10, 99, 214)), ((255, 106, 136), (255, 59, 48)),
           ((94, 224, 138), (26, 158, 75)), ((255, 177, 94), (255, 138, 0)),
           ((197, 139, 255), (138, 63, 252))]

# --------------------------------------------------------------------------- #
# content pool: (sender, subject, kind, body)  kind: plain | html | docs
# --------------------------------------------------------------------------- #
BODY = ("Hi,\n\n{L}\n\nIf you have any comments or suggestions, just reply and "
        "we'll sort it out by the end of the week.\n\nBest regards,\n{N}")
LINES = [
    "Took a look at the latest version — overall it's good, just a couple of small things to fix in the footer.",
    "Here's a short recap of the meeting so nothing gets lost: we agreed to move the navigation to the left.",
    "Sending over the updated documents for approval — the main changes are the hours buffer and hosting as a separate line.",
    "Attaching the closing documents for the period. Please double-check the details and the totals.",
    "We'd like to meet online to get acquainted and talk through the tasks. No test assignment required.",
    "The whole team reviewed the demo — great impression. I've gathered our questions into one email.",
    "I've edited the article — it reads well. The illustrations still need to be signed off separately.",
    "Scheduled maintenance overnight on Saturday from 02:00 to 04:00. No action is needed on your side.",
    "Your order has shipped and will arrive tomorrow between 10:00 and 18:00. The courier will call ahead.",
    "Thanks for the sprint — we closed almost everything. At the retro I suggest we don't take tasks without estimates.",
    "Comments on the contract: clause 4.2 needs clearer acceptance deadlines, and 7.1 should be made symmetric.",
    "We're preparing a new season of the newsletter: a roundup of materials and a couple of announcements inside.",
    "Product update: bulk actions, saved filters and a brand-new dark theme.",
    "A reminder about Friday's standup. I'll attach the agenda and the call link closer to the date.",
    "The quarterly budget adds up — sending the estimate broken down by stage for approval.",
]
NAMES = [
    ("Maria Lebedeva", "m.lebedeva@studio.design"), ("Anna Kovaleva", "anna@studio.design"),
    ("Dmitry Sokolov", "d.sokolov@host.example"), ("Sergey Nikolaev", "s.nikolaev@dev.team"),
    ("Ilya Romanov", "i.romanov@partner.co"), ("Kate Volkova", "k.volkova@hr.company"),
    ("Paul Tikhonov", "p.tikhonov@client.biz"), ("Olga Morozova", "o.morozova@editor.media"),
    ("Andrew Gusev", "a.gusev@legal.partners"), ("Accounting", "accounting@host.example"),
    ("Product Team", "product@saas.tools"), ("GitHub", "noreply@github.com"),
    ("Apple", "no_reply@apple.com"), ("Hosting Provider", "support@hosting.example"),
    ("Delivery Service", "track@delivery.example"),
]
SERVICES = [
    ("UX Weekly", "digest@uxweekly.io", "Weekly digest: 7 micro-animation tricks that don't annoy"),
    ("Design Newsletter", "hi@uxdaily.io", "Interface trends: depth and soft shadows are back"),
    ("Office Supplies Shop", "news@supplies.shop", "Summer sale: office gear up to 40% off"),
    ("DesignConf", "hello@designconf.io", "Program published — early-bird tickets ending soon"),
    ("Product Team", "product@saas.tools", "What's new: bulk actions, filters and dark mode"),
]
SUBJECTS = [
    "Newsletter layout revisions", "Redesign meeting summary", "Support & maintenance contract",
    "Statement and invoice for the period", "Interview invitation", "Feedback on the demo",
    "Edits to the article", "Scheduled maintenance", "Your order is on its way",
    "Sprint retrospective", "Legal comments on the contract", "Final estimate and schedule",
    "Weekly project report", "Quarterly budget approval", "Standup agenda",
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
                 "In this issue we break down the most important things from the past week."))


def to_bytes(m):
    # keep each header on one line: folding a non-ASCII filename into RFC2231
    # continuations (filename*0*/filename*1*) makes Roundcube drop the name and
    # show a generic "Part N" instead. 998 = RFC 5322 hard line limit.
    return m.as_bytes(policy=m.policy.clone(max_line_length=998))


def build(sender, subject, kind, body, i):
    m = EmailMessage()
    m["From"] = sender
    m["To"] = RCPT
    m["Subject"] = subject
    if kind == "html":
        m.set_content(body + "\n\n(HTML email — open in a client with image support.)")
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
            m.add_attachment(make_pdf(subject), maintype="application", subtype="pdf", filename="Contract.pdf")
            m.add_attachment(make_xlsx(subject), maintype="application",
                             subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="Estimate.xlsx")
    return m


def build_mega():
    """The newest inbox message — 10 attachments of varied types."""
    m = EmailMessage()
    m["From"] = "Project Office <pm@studio.design>"
    m["To"] = RCPT
    m["Subject"] = "Project Atlas document package — 10 files"
    m.set_content(
        "Hi,\n\nI've put the whole Project Atlas package into one email: the contract, the estimate, "
        "the requirements, the homepage mockup, a data export, the brief, the config, an assets "
        "archive, a meeting invite and a short README.\n\nPlease take a look and confirm — "
        "if everything's fine, we start on Monday.\n\nBest regards,\nProject Office")
    atts = [
        ("Contract 2026-07.pdf", make_pdf("Contract Atlas 2026-07"), "application", "pdf"),
        ("Estimate.xlsx", make_xlsx("Project Atlas estimate"), "application",
         "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("Requirements.docx", make_docx("Requirements - Atlas"), "application",
         "vnd.openxmlformats-officedocument.wordprocessingml.document"),
        ("Homepage mockup.png", make_png(600, 360, (94, 155, 255), (10, 99, 214)), "image", "png"),
        ("Data export.csv", "id;stage;hours;amount\n1;Analytics;40;120000\n2;Design;80;240000\n3;Frontend;60;180000\n".encode("utf-8"),
         "text", "csv"),
        ("Brief.txt", "Project Atlas brief\n\nGoal: relaunch the customer account area.\nTimeline: 8 weeks.\nTeam: 4 people.\n".encode("utf-8"),
         "text", "plain"),
        ("Config.json", json.dumps({"project": "Atlas", "phase": "kickoff", "budget": 540000,
         "team": ["pm", "design", "dev"]}, indent=2).encode("utf-8"),
         "application", "json"),
        ("Assets.zip", make_zip({"readme.txt": "Project Atlas assets",
         "palette.txt": "#007aff / #0a84ff"}), "application", "zip"),
        ("Meeting.ics", make_ics("Project Atlas kick-off").encode("utf-8"), "text", "calendar"),
        ("README.md", "# Project Atlas\n\n- Contract\n- Estimate\n- Requirements\n- Mockup\n\nKick-off on Monday.\n".encode("utf-8"),
         "text", "markdown"),
    ]
    for fn, data, mt, st in atts:
        m.add_attachment(data, maintype=mt, subtype=st, filename=fn)
    return m


FOLDERS = [
    "Clients", "Project Atlas", "Project Orion", "Project Mercury", "Contracts",
    "Invoices & Payments", "Accounting", "Reports", "Analytics", "Marketing",
    "Newsletters", "Social Media", "Design System", "Mockups", "Development",
    "Releases", "Bug Reports", "Support", "Infrastructure", "Security",
    "Legal", "Procurement", "Partners", "HR & Hiring", "Travel",
    "Standups", "Retrospectives", "Ideas", "Archive 2025", "Misc",
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
