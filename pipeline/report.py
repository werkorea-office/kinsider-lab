"""Monthly PDF report. Run: python -m pipeline.report [--force]

Generated automatically on the 1st of each month (KST) from the latest verified
snapshot and the breakout ledger. The edition is named after the month of the
data, and a report built before the month is complete is labelled "interim" and
replaced by the final edition on the 1st.
"""
import calendar
import datetime as dt
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import build

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports"
KST = dt.timezone(dt.timedelta(hours=9))
INK, MUTED, ACCENT = colors.HexColor("#121826"), colors.HexColor("#6b7385"), colors.HexColor("#d9481c")
UP, DOWN = colors.HexColor("#127a4f"), colors.HexColor("#b42318")

pdfmetrics.registerFont(TTFont("DV", str(ROOT / "assets/fonts/DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DVB", str(ROOT / "assets/fonts/DejaVuSans-Bold.ttf")))
ST = {
    "eyebrow": ParagraphStyle("e", fontName="DVB", fontSize=9, textColor=ACCENT, leading=12, spaceAfter=4),
    "h1": ParagraphStyle("h1", fontName="DVB", fontSize=24, textColor=INK, leading=29, spaceAfter=10),
    "h2": ParagraphStyle("h2", fontName="DVB", fontSize=14, textColor=INK, leading=18, spaceBefore=14, spaceAfter=6),
    "p": ParagraphStyle("p", fontName="DV", fontSize=9.5, textColor=INK, leading=14, spaceAfter=6),
    "small": ParagraphStyle("s", fontName="DV", fontSize=8, textColor=MUTED, leading=11, spaceAfter=4),
}


def rows_table(header, rows, col_widths, change_col=None):
    data = [header] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("FONT", (0, 0), (-1, 0), "DVB", 8), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONT", (0, 1), (-1, -1), "DV", 9), ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e4e6eb")),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if change_col is not None:
        for r, row in enumerate(rows, 1):
            v = row[change_col]
            if v.startswith("+") and v not in ("+0%", "+1%", "+2%", "+3%", "+4%"):
                style.append(("TEXTCOLOR", (change_col, r), (change_col, r), UP))
            elif v.startswith("-") and v not in ("-0%", "-1%", "-2%", "-3%", "-4%"):
                style.append(("TEXTCOLOR", (change_col, r), (change_col, r), DOWN))
    t.setStyle(TableStyle(style))
    return t


def item_rows(items, n):
    return [[str(i), it["en"], it["type"], build.pct(it["momentum"]), f"{it['level']:.0f}"]
            for i, it in enumerate(items[:n], 1)]


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "K-INSIDER LAB · kinsider-lab.com · Source: Naver DataLab Shopping Insight. "
                                        "Not affiliated with Naver.")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"{doc.page}")
    canvas.restoreState()


def make(snapshot, ledger, out_pdf):
    segs = {s["id"]: s for s in snapshot["segments"] if s.get("status") == "ok"}
    end = dt.date.fromisoformat(max(s["data_end"] for s in segs.values()))
    month_name = end.strftime("%B %Y")
    last_day = calendar.monthrange(end.year, end.month)[1]
    interim = end.day != last_day
    W = A4[0] - 36 * mm
    story = [
        Paragraph("K-INSIDER LAB · MONTHLY REPORT", ST["eyebrow"]),
        Paragraph(f"Korea K-Beauty & K-Food Demand Report<br/>{month_name}", ST["h1"]),
        Paragraph(("Interim edition, " if interim else "") + f"data through {build.nice_date(end.isoformat())}. "
                  "All figures are shopping-search click indices from Naver, Korea's largest search and shopping "
                  "platform, calculated by K-INSIDER LAB. Nothing in this report is estimated or written by hand.",
                  ST["p"]),
    ]
    beauty, brands, food = segs.get("beauty"), segs.get("brands"), segs.get("food")
    summary = []
    for seg in (beauty, brands, food):
        if not seg:
            continue
        r, c, _ = build.ranked(seg)
        if r:
            summary.append(f"<b>{seg['title']} rising:</b> " + ", ".join(f"{i['en']} ({build.pct(i['momentum'])})" for i in r[:3]))
        if c:
            summary.append(f"<b>{seg['title']} cooling:</b> {c[0]['en']} ({build.pct(c[0]['momentum'])})")
    month_calls = [x for x in ledger["signals"] if x["called"][:7] == end.strftime("%Y-%m")]
    if month_calls:
        summary.append("<b>Breakout calls this month:</b> " + ", ".join(x["en"] for x in month_calls[:6]))
    story.append(Paragraph("Key signals", ST["h2"]))
    for line in summary:
        story.append(Paragraph("• " + line, ST["p"]))

    cw = [10 * mm, W * 0.42, W * 0.22, W * 0.14, W * 0.14]
    head = ["#", "Term", "Type", "Momentum", "Index"]
    if beauty:
        r, c, b = build.ranked(beauty)
        story += [Paragraph("K-Beauty: rising categories & ingredients", ST["h2"]),
                  rows_table(head, item_rows(r, 10), cw, 3),
                  Paragraph("K-Beauty: largest demand", ST["h2"]), rows_table(head, item_rows(b, 8), cw, 3)]
    if brands:
        r, c, b = build.ranked(brands)
        story += [PageBreak(), Paragraph("K-Beauty brands: rising", ST["h2"]),
                  rows_table(["#", "Brand", "Type", "Momentum", "Index"], item_rows(r, 10), cw, 3),
                  Paragraph("K-Beauty brands: most searched", ST["h2"]),
                  rows_table(["#", "Brand", "Type", "Momentum", "Index"], item_rows(b, 10), cw, 3)]
    if food:
        r, c, b = build.ranked(food)
        story += [Paragraph("K-Food: rising", ST["h2"]), rows_table(head, item_rows(r, 8), cw, 3)]

    story += [PageBreak(), Paragraph("Breakout calls & track record", ST["h2"])]
    sigs = sorted(ledger["signals"], key=lambda x: x["called"], reverse=True)[:25]
    if sigs:
        def chk(x, k):
            return build.pct(x["checks"][k]["change"]) if k in x["checks"] else "pending"
        rows = [[build.nice_date(x["called"]), x["en"], x["segment_title"], chk(x, "d7"), chk(x, "d28")] for x in sigs]
        story.append(rows_table(["Called", "Term", "Segment", "+7 days", "+28 days"], rows,
                                [24 * mm, W * 0.36, W * 0.22, W * 0.13, W * 0.13], 4))
    else:
        story.append(Paragraph("No calls yet in the ledger.", ST["p"]))
    story += [Paragraph("Method", ST["h2"]),
              Paragraph("Demand index: shopping-search clicks in a Naver product category, rescaled so a fixed baseline "
                        "term's 8-week average equals 100 (Sunscreen for K-beauty, LANEIGE for brands, Ramyeon for "
                        "K-food). Momentum compares the last 7 days with the 28 days before. Terms with an index below "
                        "10 are excluded from rankings. A breakout is called only when a rise lasts two weeks; every "
                        "call is kept with its later results. Full method: kinsider-lab.com/methodology.html",
                        ST["small"])]
    doc = SimpleDocTemplate(str(out_pdf), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm,
                            title=f"K-INSIDER LAB Demand Report {month_name}", author="K-INSIDER LAB")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return {"month": end.strftime("%Y-%m"), "title": month_name, "interim": interim,
            "data_end": end.isoformat(), "file": f"/reports/{out_pdf.name}"}


def main(force=False):
    today = dt.datetime.now(KST).date()
    if not force and today.day != 1:
        print("Not the 1st of the month; no report.")
        return 0
    latest = json.loads((ROOT / "data" / "latest.json").read_text(encoding="utf-8"))
    if latest.get("status") != "ok":
        print("No verified data; no report.")
        return 0
    ledger = build.load_signals()
    OUT.mkdir(exist_ok=True)
    end = max(s["data_end"] for s in latest["segments"] if s.get("status") == "ok")
    pdf = OUT / f"kinsider-lab-demand-report-{end[:7]}.pdf"
    meta = make(latest, ledger, pdf)
    index_path = OUT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    index = [m for m in index if m["month"] != meta["month"]] + [meta]
    index.sort(key=lambda m: m["month"], reverse=True)
    index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"Report written: {pdf.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
