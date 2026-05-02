#!/usr/bin/env python3
"""
r5_pdf.py — R5 Race Card PDF Generator
One page per race, landscape, styled for presentation.
"""

from pathlib import Path
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph,
    Spacer, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# ── Palette ───────────────────────────────────────────────────────────────────
GOLD       = colors.HexColor("#C9A84C")
DARK_NAVY  = colors.HexColor("#1A1A2E")
NAVY       = colors.HexColor("#16213E")
MID_BLUE   = colors.HexColor("#0F3460")
GREEN      = colors.HexColor("#27AE60")
RED        = colors.HexColor("#E74C3C")
ORANGE     = colors.HexColor("#E67E22")
LIGHT_BLUE = colors.HexColor("#E8F4F8")
WHITE      = colors.white
BLACK      = colors.black
GREY       = colors.HexColor("#666666")
LIGHT_GREY = colors.HexColor("#F5F5F5")

TIER_COLORS = {
    "HIGH":        GREEN,
    "SOLID":       colors.HexColor("#2980B9"),
    "FAIR":        ORANGE,
    "SPECULATIVE": RED,
}

PAGE_W, PAGE_H = landscape(letter)
MARGIN = 0.4 * inch


def _styles():
    base = getSampleStyleSheet()

    def ps(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    return {
        "title":    ps("title",    fontSize=18, textColor=GOLD,      fontName="Helvetica-Bold",
                       alignment=TA_CENTER, spaceAfter=2),
        "subtitle": ps("subtitle", fontSize=9,  textColor=GOLD,      fontName="Helvetica",
                       alignment=TA_CENTER, spaceAfter=4),
        "label":    ps("label",    fontSize=8,  textColor=WHITE,      fontName="Helvetica-Bold"),
        "cell":     ps("cell",     fontSize=8,  textColor=BLACK,      fontName="Helvetica"),
        "cell_bold":ps("cell_b",   fontSize=8,  textColor=BLACK,      fontName="Helvetica-Bold"),
        "pick_lbl": ps("pick_lbl", fontSize=9,  textColor=DARK_NAVY,  fontName="Helvetica-Bold"),
        "pick_val": ps("pick_val", fontSize=9,  textColor=BLACK,      fontName="Helvetica"),
        "footer":   ps("footer",   fontSize=7,  textColor=GREY,       fontName="Helvetica",
                       alignment=TA_CENTER),
        "high":     ps("high",     fontSize=8,  textColor=GREEN,      fontName="Helvetica-Bold"),
        "fair":     ps("fair",     fontSize=8,  textColor=ORANGE,     fontName="Helvetica-Bold"),
        "spec":     ps("spec",     fontSize=8,  textColor=RED,        fontName="Helvetica-Bold"),
        "solid":    ps("solid",    fontSize=8,  textColor=colors.HexColor("#2980B9"),
                       fontName="Helvetica-Bold"),
    }


def _tier_style(tier, styles):
    return styles.get(tier.lower() if tier else "spec", styles["cell"])


def _header_bg(canvas, doc):
    pass  # page-level bg drawn via Table


def build_race_page(horses, styles):
    """Build a list of flowables for one race page."""
    if not horses:
        return []

    h0          = horses[0]
    track       = h0.get("track", "")
    race_num    = h0.get("race", "")
    race_date   = h0.get("date", "")
    dist_f      = round(h0.get("dist_y", 0) / 220, 1) if h0.get("dist_y") else "?"
    surface_raw = h0.get("surface", "D")
    surface     = {"D": "Dirt", "T": "Turf", "AW": "All-Weather",
                   "S": "Synthetic"}.get(surface_raw, surface_raw)
    purse       = h0.get("purse", 0)
    race_type   = h0.get("race_type", "")

    # Pace scenario
    speed_count = sum(1 for h in horses if h.get("pace_style") == "speed")
    if   speed_count >= 5: pace_scenario = f"HOT PACE ({speed_count} speed)"
    elif speed_count <= 1: pace_scenario = f"SLOW PACE ({speed_count} speed)"
    else:                  pace_scenario = f"NORMAL PACE ({speed_count} speed)"

    purse_str   = f"${purse:,.0f}" if purse else "N/A"
    date_fmt    = (datetime.strptime(race_date, "%Y%m%d").strftime("%B %d, %Y")
                   if race_date and len(race_date) == 8 else race_date)

    flowables = []

    # ── Race title banner ─────────────────────────────────────────────────────
    banner_data = [[
        Paragraph(f"R5 ANALYSIS  ·  {track}  RACE {race_num}", styles["title"]),
    ]]
    banner = Table(banner_data, colWidths=[PAGE_W - 2 * MARGIN])
    banner.setStyle(TableStyle([
        ("BACKGROUND",  (0,0), (-1,-1), DARK_NAVY),
        ("TOPPADDING",  (0,0), (-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))
    flowables.append(banner)
    flowables.append(Spacer(1, 4))

    # ── Race info strip ───────────────────────────────────────────────────────
    info_data = [[
        Paragraph(date_fmt,         styles["subtitle"]),
        Paragraph(f"{dist_f}f · {surface}", styles["subtitle"]),
        Paragraph(race_type or "—", styles["subtitle"]),
        Paragraph(f"Purse {purse_str}", styles["subtitle"]),
        Paragraph(pace_scenario,    styles["subtitle"]),
    ]]
    col_w = (PAGE_W - 2 * MARGIN) / 5
    info = Table(info_data, colWidths=[col_w] * 5)
    info.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), NAVY),
        ("TOPPADDING",   (0,0), (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("TEXTCOLOR",    (0,0), (-1,-1), GOLD),
        ("FONTNAME",     (0,0), (-1,-1), "Helvetica"),
        ("FONTSIZE",     (0,0), (-1,-1), 8),
        ("ALIGN",        (0,0), (-1,-1), "CENTER"),
    ]))
    flowables.append(info)
    flowables.append(Spacer(1, 6))

    # ── Main horse table ──────────────────────────────────────────────────────
    col_headers = ["#", "Horse", "ML", "Spd 1-4", "WS4", "Trend", "FCI",
                   "vPar", "Ped", "T/J", "Pace", "Val", "Comp", "Tier"]
    col_widths  = [22, 130, 36, 76, 38, 38, 38, 38, 30, 30, 34, 30, 38, 46]

    table_data  = [col_headers]
    row_styles  = []

    sorted_horses = sorted(horses, key=lambda h: h.get("comp", 0), reverse=True)

    for i, h in enumerate(sorted_horses):
        spds = h.get("bris_speed", [None]*4)[:4]
        spd_str = "  ".join(str(int(s)) if s else "--" for s in spds)

        ws4   = h.get("ws4")
        trend = h.get("trend", 0)
        fci   = h.get("fci")
        comp  = h.get("comp", 0)
        tier  = h.get("tier", "SPECULATIVE")

        row = [
            h.get("pgm", ""),
            h.get("name", ""),
            f"{h.get('ml_odds', 0):.0f}-1",
            spd_str,
            f"{ws4:.1f}"   if ws4   is not None else "N/A",
            f"{trend:+.1f}",
            f"{fci:.1f}"   if fci   is not None else "N/A",
            f"{h.get('par_diff', 0):+.1f}" if h.get('par_diff') is not None else "?",
            f"{h.get('ped_n', 0):.1f}",
            f"{h.get('tj_n', 0):.1f}",
            (h.get("pace_style") or "?")[:3].upper(),
            f"{h.get('val_n', 0):.1f}",
            f"{comp:.2f}",
            tier,
        ]
        table_data.append(row)

        # Row background
        bg = LIGHT_BLUE if i % 2 == 0 else WHITE
        row_styles.append(("BACKGROUND", (0, i+1), (-1, i+1), bg))

        # Tier colour on last column
        tier_col = colors.HexColor("#2980B9")
        if tier == "HIGH":        tier_col = GREEN
        elif tier == "FAIR":      tier_col = ORANGE
        elif tier == "SPECULATIVE": tier_col = RED
        row_styles.append(("TEXTCOLOR", (13, i+1), (13, i+1), tier_col))
        row_styles.append(("FONTNAME",  (13, i+1), (13, i+1), "Helvetica-Bold"))

        # Bold top pick row
        if i == 0:
            row_styles.append(("FONTNAME",    (0, 1), (-1, 1), "Helvetica-Bold"))
            row_styles.append(("BACKGROUND",  (0, 1), (-1, 1), colors.HexColor("#FFF3CD")))

    total_w = sum(col_widths)
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",    (0,0), (-1,0),  NAVY),
        ("TEXTCOLOR",     (0,0), (-1,0),  WHITE),
        ("FONTNAME",      (0,0), (-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0), (-1,-1), 8),
        ("ALIGN",         (0,0), (-1,-1), "CENTER"),
        ("ALIGN",         (1,1), (1,-1),  "LEFT"),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("GRID",          (0,0), (-1,-1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [LIGHT_BLUE, WHITE]),
    ] + row_styles))
    flowables.append(tbl)
    flowables.append(Spacer(1, 8))

    # ── Top pick detail box ───────────────────────────────────────────────────
    top = sorted_horses[0]
    top_tier = top.get("tier", "SPECULATIVE")
    top_color = TIER_COLORS.get(top_tier, RED)

    # Value alt — highest val_n outside top pick with model_rank <= 6
    value_alt = next(
        (h for h in sorted_horses[1:]
         if (h.get("val_n") or 0) >= 7.0 and sorted_horses.index(h) < 6),
        sorted_horses[1] if len(sorted_horses) > 1 else None
    )

    pick_left = [
        [Paragraph("🏆  TOP WIN PICK", styles["pick_lbl"]),
         Paragraph(f"#{top['pgm']}  {top['name']}", styles["pick_lbl"])],
        [Paragraph("ML Odds:", styles["cell"]),
         Paragraph(f"{top.get('ml_odds',0):.0f}-1", styles["cell_bold"])],
        [Paragraph("Composite:", styles["cell"]),
         Paragraph(f"{top.get('comp',0):.2f}", styles["cell_bold"])],
        [Paragraph("Tier:", styles["cell"]),
         Paragraph(top_tier, ParagraphStyle("t", parent=styles["cell"],
                                            textColor=top_color, fontName="Helvetica-Bold",
                                            fontSize=8))],
        [Paragraph("Pace Style:", styles["cell"]),
         Paragraph((top.get("pace_style") or "?").upper(), styles["cell_bold"])],
        [Paragraph("Min Odds:", styles["cell"]),
         Paragraph(f"{top.get('ml_odds',0):.0f}-1", styles["cell_bold"])],
    ]

    trnr_lines = []
    for ts in (top.get("trnr_stats") or [])[:3]:
        wp  = f"{ts['win_pct']:.1f}%" if ts.get("win_pct") else "?"
        trnr_lines.append(f"• {ts.get('situation','')[:30]}  {wp}")

    pick_right = [
        [Paragraph("Trainer:", styles["cell"]),
         Paragraph(top.get("trainer",""), styles["cell_bold"])],
        [Paragraph("Jockey:", styles["cell"]),
         Paragraph(top.get("jockey",""), styles["cell_bold"])],
        [Paragraph("FCI:", styles["cell"]),
         Paragraph(f"{top.get('fci') or 'N/A'}", styles["cell_bold"])],
        [Paragraph("Last Race:", styles["cell"]),
         Paragraph((top.get("last_race_name") or "")[:40], styles["cell"])],
    ]
    for line in trnr_lines:
        pick_right.append([Paragraph("", styles["cell"]),
                           Paragraph(line, styles["cell"])])

    tbl_left  = Table(pick_left,  colWidths=[70, 130])
    tbl_right = Table(pick_right, colWidths=[70, 200])

    for t in [tbl_left, tbl_right]:
        t.setStyle(TableStyle([
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0), (-1,-1), 2),
            ("BOTTOMPADDING", (0,0), (-1,-1), 2),
            ("LEFTPADDING",   (0,0), (-1,-1), 4),
        ]))

    # Value alt box
    val_content = []
    if value_alt:
        val_content = [
            Paragraph("💰  VALUE ALT", styles["pick_lbl"]),
            Paragraph(f"#{value_alt['pgm']}  {value_alt['name']}", styles["pick_lbl"]),
            Paragraph(f"ML: {value_alt.get('ml_odds',0):.0f}-1   "
                      f"Comp: {value_alt.get('comp',0):.2f}   "
                      f"Val: {value_alt.get('val_n',0):.1f}", styles["cell"]),
        ]
    val_tbl = Table([[v] for v in val_content] or [[Paragraph("", styles["cell"])]],
                    colWidths=[200])
    val_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
    ]))

    # Exotics
    exotic_lines = [
        f"WIN:        #{top['pgm']} {top['name']}",
    ]
    if len(sorted_horses) >= 2:
        s2 = sorted_horses[1]
        exotic_lines.append(f"EXACTA:     #{top['pgm']} / #{s2['pgm']}")
    if len(sorted_horses) >= 3:
        s3 = sorted_horses[2]
        exotic_lines.append(f"TRIFECTA:   #{top['pgm']} / #{s2['pgm']} / #{s3['pgm']}")
    if len(sorted_horses) >= 6:
        s4s = "  ".join(f"#{h['pgm']}" for h in sorted_horses[3:6])
        exotic_lines.append(f"SUPER:      #{top['pgm']} / #{s2['pgm']} / #{s3['pgm']} / {s4s}")

    exotic_data = [[Paragraph(line, styles["cell"])] for line in exotic_lines]
    exotic_tbl  = Table(exotic_data, colWidths=[220])
    exotic_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LEFTPADDING",   (0,0), (-1,-1), 4),
    ]))

    # Assemble bottom row
    bottom_row = Table(
        [[tbl_left, tbl_right, val_tbl, exotic_tbl]],
        colWidths=[210, 280, 210, 230]
    )
    bottom_row.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (0,0), colors.HexColor("#FFF3CD")),
        ("BACKGROUND",    (1,0), (1,0), colors.HexColor("#FFF3CD")),
        ("BACKGROUND",    (2,0), (2,0), colors.HexColor("#EAF7EF")),
        ("BACKGROUND",    (3,0), (3,0), colors.HexColor("#EEF2FF")),
        ("BOX",           (0,0), (0,0), 0.5, GOLD),
        ("BOX",           (1,0), (1,0), 0.5, GOLD),
        ("BOX",           (2,0), (2,0), 0.5, GREEN),
        ("BOX",           (3,0), (3,0), 0.5, MID_BLUE),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
    ]))
    flowables.append(KeepTogether([bottom_row]))

    return flowables


def generate_pdf(races_horses, out_path, track="", race_date=""):
    """
    races_horses: dict {race_num: [horse_dicts]}
    out_path: Path or str
    """
    doc = BaseDocTemplate(
        str(out_path),
        pagesize=landscape(letter),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=MARGIN + 14,
    )

    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawCentredString(
            PAGE_W / 2, 0.2 * inch,
            f"R5 Handicapping System  ·  {track}  {race_date}  ·  Generated {generated}  ·  Page {doc.page}"
        )
        canvas.restoreState()

    frame = Frame(
        MARGIN, MARGIN + 14,
        PAGE_W - 2 * MARGIN,
        PAGE_H - 2 * MARGIN - 14,
        id="main"
    )
    doc.addPageTemplates([PageTemplate(id="main", frames=frame, onPage=footer)])

    styles    = _styles()
    story     = []
    race_nums = sorted(races_horses.keys(), key=lambda x: int(x))

    for i, race_num in enumerate(race_nums):
        horses = races_horses[race_num]
        if not horses:
            continue
        story.extend(build_race_page(horses, styles))
        if i < len(race_nums) - 1:
            story.append(PageBreak())

    doc.build(story)
    return out_path
