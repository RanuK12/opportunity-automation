#!/usr/bin/env python3
"""Generador de informes PDF con identidad Ranukita / Ranuk IT Solutions.

Esta es LA forma oficial de hacer informes PDF para Emilio. No reimplementar
reportlab a mano cada vez (ahi se rompia: texto invisible, emojis como 'S',
tablas cortadas). Pasale un spec JSON y listo.

Uso:
    ranukita_report.py <spec.json> <salida.pdf> [--theme dark|white]
    ranukita_report.py --demo /tmp/demo_dark.pdf --theme dark   # ejemplo

Formato del spec.json:
{
  "title":    "Resumen de Sesion",
  "subtitle": "Trabajo del 29 de mayo de 2026",
  "date":     "2026-05-29",                 # opcional, default hoy
  "sections": [
    {
      "heading":    "1. ranuk.dev",
      "paragraphs": ["Texto del parrafo.", "Otro parrafo."],
      "bullets":    ["Punto uno", "Punto dos"],
      "table": {"headers": ["Item","Estado"], "rows": [["Deploy","OK"]]}
    }
  ]
}
Todos los campos de una seccion son opcionales menos "heading".
"""
import sys
import json
import os
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Image,
    Table, TableStyle, KeepTogether, PageBreak, CondPageBreak,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab as _rl

# IMPORTANTE: en esta maquina las fuentes estandar de reportlab (Helvetica/Times)
# estan ROTAS -> el texto sale INVISIBLE (era el bug de todos los informes). Por eso
# registramos una TTF real (Arial del sistema, fallback Vera que trae reportlab) y la
# usamos en TODO. Sin esto, los PDFs salen sin texto.
RK_FONT = "RKSans"
RK_BOLD = "RKSans-Bold"


def _register_fonts():
    rl_fonts = os.path.join(os.path.dirname(_rl.__file__), "fonts")
    candidates = [
        ("/System/Library/Fonts/Supplemental/Arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        (os.path.join(rl_fonts, "Vera.ttf"), os.path.join(rl_fonts, "VeraBd.ttf")),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont(RK_FONT, reg))
                pdfmetrics.registerFont(TTFont(RK_BOLD, bold))
                pdfmetrics.registerFontFamily(RK_FONT, normal=RK_FONT, bold=RK_BOLD,
                                              italic=RK_FONT, boldItalic=RK_BOLD)
                return
            except Exception:
                continue
    raise RuntimeError("No se pudo registrar ninguna fuente TTF")


_register_fonts()

ASSETS = os.path.expanduser("~/Apps/ranukita-bridge/assets")
WOLF_LOGO = os.path.join(ASSETS, "ranukita-logo.png")          # lobo Ranukita -> portada
RANUKIT_LOGO = os.path.expanduser(                              # R} Ranuk IT -> footer
    "~/Desktop/Oficina_Ranuk/Ranuk.dev/assets/ranuk-badge.png")
FOOTER_LEFT = "Ranukita Bot — Propiedad de Ranuk IT Solutions"
FOOTER_LINKS = [("ranuk.dev", "https://ranuk.dev"),
                ("ranukorbit.com", "https://ranukorbit.com")]
_FADED_LOGO = "/tmp/.ranukit_badge_faded.png"


def _faded_ranukit_logo():
    """Devuelve una version apenas faded del logo Ranuk IT para el footer (marca de
    agua sutil). Cachea en /tmp. Si PIL falla, usa el original."""
    if os.path.exists(_FADED_LOGO):
        return _FADED_LOGO
    if not os.path.exists(RANUKIT_LOGO):
        return None
    try:
        from PIL import Image as _PImage
        im = _PImage.open(RANUKIT_LOGO).convert("RGBA")
        alpha = im.split()[3].point(lambda v: int(v * 0.85))
        im.putalpha(alpha)
        im.save(_FADED_LOGO)
        return _FADED_LOGO
    except Exception:
        return RANUKIT_LOGO

THEMES = {
    "dark": {
        "bg": colors.HexColor("#1a1a2e"),
        "panel": colors.HexColor("#16213e"),
        "text": colors.HexColor("#e6edf3"),
        "heading": colors.HexColor("#00d4ff"),   # cian exacto Ranukita
        "accent": colors.HexColor("#ffd700"),    # dorado exacto Ranukita
        "muted": colors.HexColor("#8b949e"),
        "thead_bg": colors.HexColor("#00d4ff"),
        "thead_tx": colors.HexColor("#1a1a2e"),
        "row_alt": colors.HexColor("#16213e"),
        "line": colors.HexColor("#30363d"),
        "logo_panel": True,   # panel oscuro detras del lobo (ya combina, lo ponemos igual)
    },
    "white": {
        "bg": colors.HexColor("#ffffff"),
        "panel": colors.HexColor("#0d1117"),     # panel oscuro para que el logo neon lea
        "text": colors.HexColor("#1a1a2e"),
        "heading": colors.HexColor("#0b5cad"),
        "accent": colors.HexColor("#b8860b"),    # dorado oscuro
        "muted": colors.HexColor("#5b6470"),
        "thead_bg": colors.HexColor("#1a1a2e"),
        "thead_tx": colors.HexColor("#ffffff"),
        "row_alt": colors.HexColor("#eef1f4"),
        "line": colors.HexColor("#d0d7de"),
        "logo_panel": True,
    },
}

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm


def _img(path, max_w, max_h):
    """Image escalada respetando aspecto. None si no existe."""
    if not os.path.exists(path):
        return None
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(path).getSize()
    ratio = min(max_w / iw, max_h / ih)
    return Image(path, width=iw * ratio, height=ih * ratio)


class _ReportDoc(BaseDocTemplate):
    """Doc que avisa cada heading de seccion al indice (TOC) con su nro de pagina."""
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and getattr(flowable, "_toc_level", None) is not None:
            self.notify("TOCEntry", (flowable._toc_level, flowable.getPlainText(), self.page))


def _normalize_section(s):
    """Tolera esquemas alternativos que arma el LLM y los mapea al canonico
    (heading/paragraphs/bullets/table). ROOT CAUSE de los PDFs VACIOS (06-08): el modelo a veces
    genera secciones {'name','content'} en vez de {'heading','paragraphs'} -> el renderer leia
    heading='' y paragraphs=[] -> todo en blanco aunque el contenido estaba en el spec. Ahora:
    name/title -> heading; content/text/body en bloque -> se parte en lineas y, si detecta una
    tabla markdown (lineas con '|'), la arma como table; el resto en parrafos/bullets."""
    if not isinstance(s, dict):
        return {"heading": "", "paragraphs": [str(s)], "bullets": [], "table": None}
    heading = s.get("heading") or s.get("name") or s.get("title") or ""
    paragraphs = list(s.get("paragraphs") or [])
    bullets = list(s.get("bullets") or [])
    table = s.get("table")
    blob = s.get("content") or s.get("text") or s.get("body") or ""
    if blob and not paragraphs and not bullets and not table:
        lines = [ln.strip() for ln in str(blob).split("\n") if ln.strip()]
        tbl_lines = [ln for ln in lines if ln.count("|") >= 2]
        if len(tbl_lines) >= 2:                       # tabla markdown embebida en el texto
            rows = []
            for ln in tbl_lines:
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if all(set(c) <= set("-: ") for c in cells):   # fila separadora |---|---|
                    continue
                rows.append(cells)
            if rows:
                table = {"headers": rows[0], "rows": rows[1:]}
            for ln in lines:                          # lineas que no son de la tabla -> parrafos
                if ln.count("|") < 2:
                    paragraphs.append(ln)
        else:
            for ln in lines:
                if ln.lstrip().startswith(("- ", "* ", "• ")):
                    bullets.append(ln.lstrip()[2:].strip())
                else:
                    paragraphs.append(ln)
    return {"heading": heading, "paragraphs": paragraphs, "bullets": bullets, "table": table}


def build(spec, out_path, theme_name="dark"):
    th = THEMES.get(theme_name, THEMES["dark"])
    date = spec.get("date") or datetime.date.today().isoformat()

    # ---- callback que pinta fondo + footer en CADA pagina ----
    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(th["bg"])
        canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        # linea separadora del footer (mas arriba para dar aire al logo)
        line_y = 15 * mm
        canvas.setStrokeColor(th["line"])
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, line_y, PAGE_W - MARGIN, line_y)
        # baseline comun del footer (centrado verticalmente con el logo)
        base_y = 8.3 * mm
        # logo Ranuk IT abajo a la izquierda, apenas faded (marca de agua sutil)
        logo_sz = 9 * mm
        faded = _faded_ranukit_logo()
        if faded:
            try:
                canvas.drawImage(faded, MARGIN, 5.0 * mm, width=logo_sz,
                                 height=logo_sz, mask="auto",
                                 preserveAspectRatio=True)
            except Exception:
                pass
        # texto de marca centrado; ranuk.dev / ranukorbit.com CLICABLES (en cian)
        fsize = 6.8
        sep = "     |     "
        canvas.setFont(RK_FONT, fsize)
        segs = [(FOOTER_LEFT + sep, th["muted"], None),
                (FOOTER_LINKS[0][0], th["heading"], FOOTER_LINKS[0][1]),
                (sep, th["muted"], None),
                (FOOTER_LINKS[1][0], th["heading"], FOOTER_LINKS[1][1])]
        total = sum(canvas.stringWidth(t, RK_FONT, fsize) for t, _, _ in segs)
        x = PAGE_W / 2 - total / 2
        for t, col, url in segs:
            w = canvas.stringWidth(t, RK_FONT, fsize)
            canvas.setFillColor(col)
            canvas.drawString(x, base_y, t)
            if url:
                canvas.linkURL(url, (x, base_y - 1.5, x + w, base_y + fsize + 1),
                               relative=0)
            x += w
        # numero de pagina a la derecha, dorado
        canvas.setFillColor(th["accent"])
        canvas.setFont(RK_BOLD, 8.5)
        canvas.drawRightString(PAGE_W - MARGIN, base_y, str(doc.page))
        canvas.restoreState()

    # estilos
    st_title = ParagraphStyle("title", fontName=RK_BOLD, fontSize=26,
                              textColor=th["text"], alignment=TA_CENTER, leading=30)
    st_sub = ParagraphStyle("sub", fontName=RK_FONT, fontSize=12,
                            textColor=th["muted"], alignment=TA_CENTER, leading=16)
    st_date = ParagraphStyle("date", fontName=RK_BOLD, fontSize=10,
                             textColor=th["accent"], alignment=TA_CENTER)
    st_h = ParagraphStyle("h", fontName=RK_BOLD, fontSize=15,
                          textColor=th["heading"], spaceBefore=16, spaceAfter=2, leading=18)
    st_body = ParagraphStyle("body", fontName=RK_FONT, fontSize=10.5,
                             textColor=th["text"], leading=15, spaceAfter=6, alignment=TA_LEFT)
    st_bullet = ParagraphStyle("bullet", parent=st_body, leftIndent=6, spaceAfter=3)
    st_toc_h = ParagraphStyle("toch", fontName=RK_BOLD, fontSize=16,
                              textColor=th["heading"], spaceAfter=10)

    story = []

    # ---------- PORTADA ----------
    story.append(Spacer(1, 55 * mm))
    wolf = _img(WOLF_LOGO, 55 * mm, 55 * mm)
    if wolf:
        # panel oscuro detras del logo (clave para el tema blanco)
        panel = Table([[wolf]], hAlign="CENTER")
        panel.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), th["panel"]),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("ROUNDEDCORNERS", [8, 8, 8, 8]),
        ]))
        story.append(panel)
        story.append(Spacer(1, 14 * mm))
    story.append(Paragraph(spec.get("title", "Informe"), st_title))
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width=64, thickness=2.2, color=th["accent"],
                            spaceBefore=0, spaceAfter=6, hAlign="CENTER",
                            lineCap="round"))
    if spec.get("subtitle"):
        story.append(Paragraph(spec["subtitle"], st_sub))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(date, st_date))
    story.append(PageBreak())

    sections = spec.get("sections", [])
    # spec PLANO sin 'sections' (el LLM a veces pone content/paragraphs a nivel raíz) -> envolver en
    # una sección única para no renderizar en blanco (caso guide_spec 06-08).
    if not sections and (spec.get("content") or spec.get("paragraphs") or spec.get("body")):
        sections = [{"heading": spec.get("subtitle") or "Detalle",
                     "content": spec.get("content") or spec.get("body") or "",
                     "paragraphs": spec.get("paragraphs") or []}]

    # ---------- INDICE con nro de pagina (solo si el informe es largo) ----------
    if len(sections) >= 3:
        story.append(Paragraph("Indice", st_toc_h))
        story.append(HRFlowable(width="100%", thickness=0.8, color=th["accent"],
                                spaceBefore=2, spaceAfter=12, lineCap="round"))
        toc = TableOfContents()
        toc.levelStyles = [ParagraphStyle(
            "toc0", fontName=RK_FONT, fontSize=11.5, textColor=th["text"],
            leading=24, firstLineIndent=0)]
        story.append(toc)
        story.append(PageBreak())

    # ---------- SECCIONES ----------
    ac = th["accent"]
    acc = "%02X%02X%02X" % (int(ac.red * 255), int(ac.green * 255), int(ac.blue * 255))
    content_chars = 0   # contenido real renderizado; si queda ~0 el PDF saldría vacío -> fallar ruidoso
    for s in sections:
        s = _normalize_section(s)   # tolera name/content/text -> heading/paragraphs/table (PDFs vacios 06-08)
        content_chars += sum(len(str(p)) for p in s.get("paragraphs", []))
        content_chars += sum(len(str(b)) for b in s.get("bullets", []))
        _tb = s.get("table") or {}
        content_chars += sum(len(str(c)) for r in _tb.get("rows", []) for c in r)
        # si queda poco espacio, salta de pagina para no dejar el titulo huerfano
        story.append(CondPageBreak(46 * mm))
        heading = Paragraph(s.get("heading", ""), st_h)
        heading._toc_level = 0   # lo registra el indice
        story.append(heading)
        story.append(HRFlowable(width="100%", thickness=0.6, color=th["line"],
                                spaceBefore=1, spaceAfter=8, lineCap="round"))
        for p in s.get("paragraphs", []):
            story.append(Paragraph(p, st_body))
        for b in s.get("bullets", []):
            # bullet dorado inline (a prueba de balas: nada de emojis que salen como 'S')
            story.append(Paragraph(
                f'<font color="#{acc}">&bull;</font>&nbsp;&nbsp;{b}', st_bullet))

        tbl = s.get("table")
        if tbl and tbl.get("headers"):
            story.append(Spacer(1, 4 * mm))
            data = [tbl["headers"]] + tbl.get("rows", [])
            # envolver celdas en Paragraph para que hagan wrap
            cell_h = ParagraphStyle("ch", fontName=RK_BOLD, fontSize=9.5,
                                    textColor=th["thead_tx"], leading=12)
            cell_b = ParagraphStyle("cb", fontName=RK_FONT, fontSize=9.5,
                                    textColor=th["text"], leading=12)
            wrapped = [[Paragraph(str(c), cell_h) for c in data[0]]]
            for row in data[1:]:
                wrapped.append([Paragraph(str(c), cell_b) for c in row])
            ncols = len(data[0])
            usable = PAGE_W - 2 * MARGIN
            t = Table(wrapped, colWidths=[usable / ncols] * ncols, repeatRows=1)
            style = [
                ("BACKGROUND", (0, 0), (-1, 0), th["thead_bg"]),
                ("GRID", (0, 0), (-1, -1), 0.5, th["line"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ]
            for i in range(1, len(wrapped)):
                if i % 2 == 0:
                    style.append(("BACKGROUND", (0, i), (-1, i), th["row_alt"]))
            t.setStyle(TableStyle(style))
            # KeepTogether: la tabla no se parte entre paginas
            story.append(KeepTogether(t))

    # FALLAR RUIDOSO si el informe quedaría vacío: antes escribía un PDF en blanco (solo título+footer)
    # que "parecía" exitoso y el agente lo daba por hecho. Ahora explota con exit!=0 para que el agente
    # vea que su spec no tenía contenido en las secciones y lo regenere bien. (mejora 06-09)
    if content_chars < 80:
        raise SystemExit(f"ERROR: el spec no tiene contenido real en las secciones ({content_chars} chars). "
                         f"El PDF saldría vacío. Cada sección necesita 'paragraphs' (lista de strings), "
                         f"'bullets' o 'table' con datos. NO se escribió el PDF.")
    doc = _ReportDoc(
        out_path, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=20 * mm, bottomMargin=20 * mm,
        title=spec.get("title", "Informe"), author="Ranukita Bot",
    )
    frame = Frame(MARGIN, 18 * mm, PAGE_W - 2 * MARGIN,
                  PAGE_H - 20 * mm - 18 * mm, id="main")
    doc.addPageTemplates([PageTemplate(id="all", frames=[frame], onPage=decorate)])
    # multiBuild: 2+ pasadas para resolver los nros de pagina del indice
    doc.multiBuild(story)
    return out_path


_DEMO = {
    "title": "Resumen de Sesion",
    "subtitle": "Trabajo realizado el 29 de mayo de 2026",
    "date": "2026-05-29",
    "sections": [
        {"heading": "1. ranuk.dev",
         "paragraphs": ["Se corrigio la timeline de la historia y se reemplazo la foto repetida debajo del Act III por la foto de la Sagrada Familia."],
         "bullets": ["ACT I: 1995 a 2024 - recibido de Ingeniero", "ACT II: 2024 a 2025 - Italia, Paises Bajos, Booking", "ACT III: 2025 a hoy - Ranuk IT", "6 commits pusheados a main"]},
        {"heading": "2. Bot Ranukita",
         "paragraphs": ["Se arreglo el loop infinito de tools, se agrego persistencia inmediata del historial y se conecto MiMo 2.5 Pro."],
         "table": {"headers": ["Componente", "Estado", "Detalle"],
                   "rows": [["Tools", "OK", "Argumentos tolerantes, sin loops"],
                            ["Historial", "OK", "Persistencia inmediata + archivo"],
                            ["MiMo 2.5 Pro", "OK", "Texto directo + vision omni"],
                            ["Permisos", "OK", "Full Disk Access + python pineado"]]}},
        {"heading": "3. Estado del sistema",
         "bullets": ["Mac M4 operativa", "Bridge corriendo via launchd", "Sin errores en logs"]},
    ],
}


def main():
    args = sys.argv[1:]
    theme = "dark"
    if "--theme" in args:
        i = args.index("--theme")
        theme = args[i + 1]
        del args[i:i + 2]
    if args and args[0] == "--demo":
        out = args[1] if len(args) > 1 else "/tmp/ranukita_demo.pdf"
        build(_DEMO, out, theme)
        print(out)
        return
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    spec = json.loads(open(args[0], encoding="utf-8").read())
    out = build(spec, args[1], theme)
    print(out)


if __name__ == "__main__":
    main()
