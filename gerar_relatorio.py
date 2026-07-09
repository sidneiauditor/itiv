import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

# ── Paleta ──────────────────────────────────────────────────────────────
AZUL      = RGBColor(0x1a, 0x3a, 0x5c)
AZUL_MED  = RGBColor(0x2e, 0x75, 0xb6)
CINZA_CLR = RGBColor(0xf2, 0xf2, 0xf2)
BRANCO    = RGBColor(0xff, 0xff, 0xff)
LARANJA   = RGBColor(0xe8, 0x7a, 0x1e)
VERDE     = RGBColor(0x2e, 0x86, 0x48)
VERMELHO  = RGBColor(0xc0, 0x39, 0x2b)

def hex_str(rgb): return f"{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

AZ_HEX  = "1A3A5C"
AZM_HEX = "2E75B6"
CIN_HEX = "F2F2F2"
LAR_HEX = "E87A1E"
VER_HEX = "2E8648"
VRM_HEX = "C0392B"

# ── Helpers ──────────────────────────────────────────────────────────────
def set_cell_bg(cell, hex_color):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)

def set_cell_borders(cell, color="CCCCCC", size="4"):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for side in ("top","left","bottom","right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), size)
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        tcBorders.append(el)
    tcPr.append(tcBorders)

def para_style(para, size=11, bold=False, color=None, align=None, space_before=0, space_after=0):
    run_fmt = para.runs[0] if para.runs else None
    if run_fmt:
        run_fmt.font.size = Pt(size)
        run_fmt.font.bold = bold
        if color: run_fmt.font.color.rgb = color
    para.paragraph_format.space_before = Pt(space_before)
    para.paragraph_format.space_after  = Pt(space_after)
    if align: para.alignment = align

def add_heading(doc, text, level=1, color=AZUL):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after  = Pt(6)
    for run in p.runs:
        run.font.color.rgb = color
        run.font.name = "Arial"
    return p

def add_para(doc, text, size=11, bold=False, color=None, align=None, before=0, after=4):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = "Arial"
    if color: run.font.color.rgb = color
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after  = Pt(after)
    if align: p.alignment = align
    return p

def img_buf(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf

# ── Gráficos ─────────────────────────────────────────────────────────────
def grafico_pizza():
    labels = ["Defasado\n44,6%", "Compatível\n36,3%", "Acima\n19,2%"]
    sizes  = [307968, 250561, 132461]
    colors = [f"#{LAR_HEX}", f"#{VER_HEX}", f"#{VRM_HEX}"]
    fig, ax = plt.subplots(figsize=(5.5, 4))
    wedges, texts = ax.pie(sizes, colors=colors, startangle=90,
                           wedgeprops=dict(edgecolor="white", linewidth=2))
    legend = ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(0.85, 0.5),
                       fontsize=10, frameon=False)
    ax.set_title("Distribuição por Classificação", fontsize=12, fontweight="bold",
                 color=f"#{AZ_HEX}", pad=10)
    fig.tight_layout()
    return img_buf(fig)

def grafico_barras_tipologia():
    tipos   = ["Apartamento", "Casa", "Sala", "Loja"]
    medias  = [26.7, 42.4, -24.3, 22.6]
    colors  = [f"#{LAR_HEX}" if v > 0 else f"#{VRM_HEX}" for v in medias]
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    bars = ax.barh(tipos, medias, color=colors, edgecolor="white", height=0.55)
    ax.axvline(0, color="gray", linewidth=0.8, linestyle="--")
    for bar, val in zip(bars, medias):
        sign = "+" if val >= 0 else ""
        ax.text(val + (1 if val >= 0 else -1), bar.get_y() + bar.get_height()/2,
                f"{sign}{val:.1f}%", va="center", ha="left" if val >= 0 else "right",
                fontsize=10, fontweight="bold")
    ax.set_xlabel("Diferença média (%) — positivo = venal abaixo do mercado", fontsize=9)
    ax.set_title("Defasagem Média por Tipologia", fontsize=12, fontweight="bold",
                 color=f"#{AZ_HEX}")
    ax.set_facecolor("#FAFAFA")
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    return img_buf(fig)

def grafico_barras_classificacao():
    tipos   = ["Apartamento", "Casa", "Sala", "Loja"]
    defas   = [165944, 127837, 2506, 11681]
    compat  = [149991, 81820,  8293, 10457]
    acima   = [45069,  52564, 24144, 10684]
    x = np.arange(len(tipos))
    w = 0.26
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x - w, defas,  width=w, label="Defasado",    color=f"#{LAR_HEX}", edgecolor="white")
    ax.bar(x,     compat, width=w, label="Compatível",  color=f"#{VER_HEX}", edgecolor="white")
    ax.bar(x + w, acima,  width=w, label="Acima",       color=f"#{VRM_HEX}", edgecolor="white")
    ax.set_xticks(x); ax.set_xticklabels(tipos, fontsize=10)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{int(v):,}".replace(",",".")))
    ax.set_title("Classificação por Tipologia — Quantidade de Imóveis", fontsize=11,
                 fontweight="bold", color=f"#{AZ_HEX}")
    ax.legend(fontsize=9, frameon=False)
    ax.set_facecolor("#FAFAFA")
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    return img_buf(fig)

# ── Documento ────────────────────────────────────────────────────────────
doc = Document()

# Margens
for section in doc.sections:
    section.top_margin    = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin   = Cm(3.0)
    section.right_margin  = Cm(2.5)

# Estilo base
style = doc.styles["Normal"]
style.font.name = "Arial"
style.font.size = Pt(11)

# ── CABEÇALHO ──────────────────────────────────────────────────────────
section = doc.sections[0]
header = section.header
hp = header.paragraphs[0]
hp.clear()
run = hp.add_run("Coordenadoria de Inteligência Fiscal — SEFAZ Salvador")
run.font.size = Pt(9); run.font.color.rgb = RGBColor(0x88,0x88,0x88); run.font.name = "Arial"
hp.paragraph_format.space_after = Pt(0)
border_pPr = hp.paragraph_format._element.get_or_add_pPr()
pBdr = OxmlElement("w:pBdr")
bottom = OxmlElement("w:bottom")
bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "4")
bottom.set(qn("w:space"), "1"); bottom.set(qn("w:color"), AZ_HEX)
pBdr.append(bottom); border_pPr.append(pBdr)

# ── RODAPÉ ─────────────────────────────────────────────────────────────
footer = section.footer
fp = footer.paragraphs[0]
fp.clear()
run = fp.add_run("Coordenadoria de Inteligência Fiscal — SEFAZ Salvador  |  Junho 2026  |  Confidencial          Pág. ")
run.font.size = Pt(9); run.font.color.rgb = RGBColor(0x88,0x88,0x88); run.font.name = "Arial"
run_pn = fp.add_run()
fldChar = OxmlElement("w:fldChar"); fldChar.set(qn("w:fldCharType"), "begin")
run_pn._r.append(fldChar)
instrText = OxmlElement("w:instrText"); instrText.text = "PAGE"
run_pn._r.append(instrText)
fldChar2 = OxmlElement("w:fldChar"); fldChar2.set(qn("w:fldCharType"), "end")
run_pn._r.append(fldChar2)
fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT

# ══════════════════════════════════════════════════════════════════════
# CAPA
# ══════════════════════════════════════════════════════════════════════
doc.add_paragraph()
doc.add_paragraph()
doc.add_paragraph()

p = doc.add_paragraph()
run = p.add_run("PREFEITURA MUNICIPAL DE SALVADOR")
run.font.size = Pt(13); run.font.bold = True; run.font.color.rgb = AZUL; run.font.name = "Arial"
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(2)

p = doc.add_paragraph()
run = p.add_run("Secretaria Municipal da Fazenda — SEFAZ")
run.font.size = Pt(12); run.font.color.rgb = AZUL; run.font.name = "Arial"
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(2)

p = doc.add_paragraph()
run = p.add_run("Coordenadoria de Inteligência Fiscal")
run.font.size = Pt(12); run.font.color.rgb = AZUL; run.font.name = "Arial"
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(40)

# Linha decorativa
p = doc.add_paragraph()
pPr = p._element.get_or_add_pPr()
pBdr = OxmlElement("w:pBdr")
bot = OxmlElement("w:bottom")
bot.set(qn("w:val"), "single"); bot.set(qn("w:sz"), "12")
bot.set(qn("w:space"), "1"); bot.set(qn("w:color"), AZ_HEX)
pBdr.append(bot); pPr.append(pBdr)
p.paragraph_format.space_after = Pt(20)

p = doc.add_paragraph()
run = p.add_run("Análise de Defasagem do\nValor Venal dos Imóveis de Salvador")
run.font.size = Pt(26); run.font.bold = True; run.font.color.rgb = AZUL; run.font.name = "Arial"
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(20)
p.paragraph_format.space_after  = Pt(10)

p = doc.add_paragraph()
run = p.add_run("Avaliação por Modelo de Machine Learning — ITIV (sem anúncios)")
run.font.size = Pt(14); run.font.color.rgb = AZUL_MED; run.font.name = "Arial"
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_after = Pt(60)

p = doc.add_paragraph()
run = p.add_run("Junho de 2026")
run.font.size = Pt(12); run.font.color.rgb = RGBColor(0x55,0x55,0x55); run.font.name = "Arial"
p.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_page_break()

# ══════════════════════════════════════════════════════════════════════
# SUMÁRIO EXECUTIVO — CARDS
# ══════════════════════════════════════════════════════════════════════
add_heading(doc, "1. Sumário Executivo", level=1)

add_para(doc,
    "Esta análise avaliou 690.992 imóveis do cadastro imobiliário de Salvador utilizando modelo "
    "de Machine Learning treinado com dados históricos de transações do ITIV. O objetivo é "
    "identificar imóveis com valor venal defasado em relação ao mercado, prevenindo perdas de "
    "arrecadação e demandas administrativas ou judiciais.",
    before=0, after=12)

# Cards — tabela 2x2
cards = [
    ("690.992", "Imóveis Avaliados",       AZM_HEX, "Total do cadastro imobiliário municipal avaliado"),
    ("307.968\n44,6%", "Venal Defasado",   LAR_HEX, "Valor venal abaixo do valor de mercado"),
    ("+29,9%", "Defasagem Média",          VRM_HEX, "O valor venal está, em média, 30% abaixo do mercado"),
    ("250.561\n36,3%", "Valor Compatível", VER_HEX, "Imóveis com valor venal adequado ao mercado"),
]
tbl = doc.add_table(rows=2, cols=2)
tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
tbl.style = "Table Grid"
idx = 0
for row in tbl.rows:
    for cell in row.cells:
        val, label, color, desc = cards[idx]; idx += 1
        set_cell_bg(cell, color)
        cell.width = Cm(8)
        p1 = cell.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p1.add_run(val)
        r1.font.size = Pt(28); r1.font.bold = True
        r1.font.color.rgb = BRANCO; r1.font.name = "Arial"
        p2 = cell.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r2 = p2.add_run(label)
        r2.font.size = Pt(13); r2.font.bold = True
        r2.font.color.rgb = BRANCO; r2.font.name = "Arial"
        p3 = cell.add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r3 = p3.add_run(desc)
        r3.font.size = Pt(9)
        r3.font.color.rgb = RGBColor(0xdd,0xdd,0xdd); r3.font.name = "Arial"
        p3.paragraph_format.space_after = Pt(6)

doc.add_paragraph()

# ══════════════════════════════════════════════════════════════════════
# CONTEXTO E METODOLOGIA
# ══════════════════════════════════════════════════════════════════════
add_heading(doc, "2. Contexto e Metodologia", level=1)

add_para(doc,
    "O ITIV (Imposto sobre Transmissão Inter Vivos) incide sobre o valor de mercado do imóvel "
    "no momento da transmissão. Para garantir a correta apuração do imposto e prevenir litígios, "
    "é fundamental que o valor venal registrado no cadastro municipal esteja alinhado ao valor "
    "real de mercado.")

add_heading(doc, "Como o Modelo Funciona", level=2)

bullets = [
    "Treinamento com transações reais: o modelo aprendeu com milhares de transações imobiliárias "
    "históricas registradas no ITIV em Salvador, capturando padrões de preço por localização, "
    "tipologia e características do imóvel.",
    "Avaliação cadastral: com esse aprendizado, o modelo estima o valor de mercado de qualquer "
    "imóvel do cadastro municipal — mesmo sem registro de venda recente — usando as características "
    "já disponíveis: área, tipo (apartamento, casa, sala, loja), setor fiscal, número de pavimentos "
    "e localização geográfica.",
    "Algoritmos utilizados: LightGBM (Machine Learning), modelo hedônico de preços e "
    "K-Nearest Neighbors geoespacial — técnicas amplamente utilizadas em avaliação imobiliária "
    "em massa.",
    "Comparação: o valor estimado é comparado ao VLVENALCADASTRO registrado no cadastro "
    "imobiliário municipal, identificando defasagens.",
]
for b in bullets:
    p = doc.add_paragraph(style="List Bullet")
    run = p.add_run(b)
    run.font.size = Pt(11); run.font.name = "Arial"
    p.paragraph_format.space_after = Pt(4)

add_heading(doc, "Nota sobre Anúncios Imobiliários", level=2)

# Caixa de aviso
tbl_av = doc.add_table(rows=1, cols=1)
tbl_av.style = "Table Grid"
cell_av = tbl_av.cell(0,0)
set_cell_bg(cell_av, "FFF3CD")
tc = cell_av._tc; tcPr = tc.get_or_add_tcPr()
tcBorders = OxmlElement("w:tcBorders")
for side in ("top","left","bottom","right"):
    el = OxmlElement(f"w:{side}")
    el.set(qn("w:val"), "single"); el.set(qn("w:sz"), "6")
    el.set(qn("w:space"), "0"); el.set(qn("w:color"), "E87A1E")
    tcBorders.append(el)
tcPr.append(tcBorders)

p_av = cell_av.paragraphs[0]
r_tit = p_av.add_run("ℹ Nota Metodológica — Avaliação sem Anúncios Imobiliários")
r_tit.font.size = Pt(11); r_tit.font.bold = True
r_tit.font.color.rgb = RGBColor(0x7B,0x4B,0x00); r_tit.font.name = "Arial"

p_av2 = cell_av.add_paragraph()
r_txt = p_av2.add_run(
    "O modelo foi desenvolvido com capacidade de incorporar dados de anúncios imobiliários "
    "(Zap Imóveis, VivaReal, OLX) como fonte complementar de referência de preços. "
    "Este relatório apresenta exclusivamente a avaliação SEM anúncios — baseada apenas em "
    "transações imobiliárias efetivamente registradas no ITIV. "
    "Esta escolha é metodologicamente mais conservadora: os preços de anúncio tendem a ser "
    "superiores ao preço efetivo de transação, podendo inflar as estimativas. "
    "Ao excluir os anúncios, as estimativas refletem com maior fidelidade os preços praticados "
    "no mercado real de Salvador."
)
r_txt.font.size = Pt(10.5); r_txt.font.name = "Arial"
r_txt.font.color.rgb = RGBColor(0x55,0x33,0x00)
p_av2.paragraph_format.space_after = Pt(6)
doc.add_paragraph()

# ══════════════════════════════════════════════════════════════════════
# PANORAMA GERAL
# ══════════════════════════════════════════════════════════════════════
add_heading(doc, "3. Panorama Geral", level=1)

# Tabela resumo
add_para(doc, "Tabela 1 — Classificação dos Imóveis de Salvador", bold=True, size=10,
         color=RGBColor(0x44,0x44,0x44), after=4)

headers_t1 = ["Classificação", "Qtd. de Imóveis", "Percentual", "Significado"]
rows_t1 = [
    ("Venal Defasado",           "307.968", "44,6%", "VV abaixo do mercado (>10%)"),
    ("Compatível",               "250.561", "36,3%", "VV adequado ao mercado"),
    ("Venal Acima do Mercado",   "132.461", "19,2%", "VV acima do mercado (>10%)"),
    ("TOTAL",                    "690.992", "100%",  ""),
]
col_w = [3800, 2200, 1600, 4200]  # DXA aprox
tbl1 = doc.add_table(rows=1+len(rows_t1), cols=4)
tbl1.style = "Table Grid"
tbl1.alignment = WD_TABLE_ALIGNMENT.LEFT

for i, hdr in enumerate(headers_t1):
    cell = tbl1.cell(0, i)
    set_cell_bg(cell, AZ_HEX)
    p = cell.paragraphs[0]
    r = p.add_run(hdr)
    r.font.bold = True; r.font.color.rgb = BRANCO; r.font.size = Pt(10.5); r.font.name = "Arial"
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

row_colors = [LAR_HEX, VER_HEX, VRM_HEX, "DDDDDD"]
for ri, (row_data, bg) in enumerate(zip(rows_t1, row_colors)):
    for ci, val in enumerate(row_data):
        cell = tbl1.cell(ri+1, ci)
        set_cell_bg(cell, bg if ri < 3 else "EEEEEE")
        p = cell.paragraphs[0]
        r = p.add_run(val)
        r.font.size = Pt(10.5); r.font.name = "Arial"
        if ri < 3: r.font.color.rgb = BRANCO
        else: r.font.bold = True; r.font.color.rgb = AZUL
        if ci in (1,2): p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_cell_borders(cell)

doc.add_paragraph()

# Gráfico pizza
add_para(doc, "Gráfico 1 — Distribuição por Classificação", bold=True, size=10,
         color=RGBColor(0x44,0x44,0x44), after=4)
buf_pizza = grafico_pizza()
doc.add_picture(buf_pizza, width=Inches(5.5))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
doc.add_paragraph()

# ══════════════════════════════════════════════════════════════════════
# ANÁLISE POR TIPOLOGIA
# ══════════════════════════════════════════════════════════════════════
add_heading(doc, "4. Análise por Tipologia", level=1)

add_para(doc, "Tabela 2 — Defasagem por Tipo de Imóvel", bold=True, size=10,
         color=RGBColor(0x44,0x44,0x44), after=4)

headers_t2 = ["Tipologia", "Total", "Defasados", "Compatíveis", "Acima", "Dif. Média", "Dif. Mediana"]
rows_t2 = [
    ("Apartamento", "361.006", "165.944", "149.991", "45.069",  "+26,7%", "+15,8%"),
    ("Casa",        "262.221", "127.837",  "81.820", "52.564",  "+42,4%", "+18,2%"),
    ("Sala",         "34.943",   "2.506",   "8.293", "24.144", "−24,3%", "−33,2%"),
    ("Loja",         "32.822",  "11.681",  "10.457", "10.684",  "+22,6%",  "−1,3%"),
]
tbl2 = doc.add_table(rows=1+len(rows_t2), cols=7)
tbl2.style = "Table Grid"
for i, hdr in enumerate(headers_t2):
    cell = tbl2.cell(0, i)
    set_cell_bg(cell, AZ_HEX)
    p = cell.paragraphs[0]
    r = p.add_run(hdr)
    r.font.bold = True; r.font.color.rgb = BRANCO; r.font.size = Pt(10); r.font.name = "Arial"
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

for ri, row_data in enumerate(rows_t2):
    bg = CIN_HEX if ri % 2 == 0 else "FFFFFF"
    for ci, val in enumerate(row_data):
        cell = tbl2.cell(ri+1, ci)
        set_cell_bg(cell, bg)
        p = cell.paragraphs[0]
        r = p.add_run(val)
        r.font.size = Pt(10); r.font.name = "Arial"
        if ci > 0: p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        # Colorir diferença
        if ci == 5:
            r.font.bold = True
            if val.startswith("+"):  r.font.color.rgb = LARANJA
            elif val.startswith("−"): r.font.color.rgb = VERMELHO
        set_cell_borders(cell)

doc.add_paragraph()

add_para(doc, "Gráfico 2 — Defasagem Média por Tipologia", bold=True, size=10,
         color=RGBColor(0x44,0x44,0x44), after=4)
buf_bar = grafico_barras_tipologia()
doc.add_picture(buf_bar, width=Inches(6))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph()
add_para(doc, "Gráfico 3 — Classificação por Tipologia (Quantidade de Imóveis)", bold=True,
         size=10, color=RGBColor(0x44,0x44,0x44), after=4)
buf_cls = grafico_barras_classificacao()
doc.add_picture(buf_cls, width=Inches(6))
doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph()

# ══════════════════════════════════════════════════════════════════════
# DISTRIBUIÇÃO DA DEFASAGEM
# ══════════════════════════════════════════════════════════════════════
add_heading(doc, "5. Distribuição da Defasagem", level=1)

add_para(doc,
    "A diferença percentual (Dif. %) representa a variação entre o valor venal cadastral e o "
    "valor estimado de mercado pelo modelo. A interpretação é direta:")

# Legenda
for icone, texto, cor in [
    ("▲ Positivo (+%)", "O valor venal está ABAIXO do mercado — imóvel subavaliado. "
     "A prefeitura pode estar calculando o ITIV sobre uma base inferior ao valor real, "
     "resultando em perda de arrecadação.", LARANJA),
    ("▼ Negativo (−%)", "O valor venal está ACIMA do mercado — imóvel superavaliado. "
     "Risco de impugnação administrativa ou judicial pelo contribuinte, que pode alegar "
     "que o imposto foi calculado sobre valor superior ao praticado no mercado.", VERMELHO),
]:
    p = doc.add_paragraph()
    r1 = p.add_run(f"{icone}:  ")
    r1.font.bold = True; r1.font.color.rgb = cor; r1.font.size = Pt(11); r1.font.name = "Arial"
    r2 = p.add_run(texto)
    r2.font.size = Pt(11); r2.font.name = "Arial"
    p.paragraph_format.space_after = Pt(6)

doc.add_paragraph()
add_para(doc, "Tabela 3 — Distribuição Estatística da Diferença (%)", bold=True, size=10,
         color=RGBColor(0x44,0x44,0x44), after=4)

rows_t3 = [
    ("Média",        "+29,9%", "Em média, o valor venal está 30% abaixo do mercado"),
    ("Mediana",      "+13,4%", "Metade dos imóveis tem defasagem acima de 13,4%"),
    ("Percentil 25", "−13,4%", "25% dos imóveis têm valor venal acima do mercado"),
    ("Percentil 75", "+51,4%", "25% dos imóveis têm defasagem superior a 51%"),
]
tbl3 = doc.add_table(rows=1+len(rows_t3), cols=3)
tbl3.style = "Table Grid"
for i, h in enumerate(["Estatística", "Valor", "Interpretação"]):
    cell = tbl3.cell(0, i)
    set_cell_bg(cell, AZ_HEX)
    p = cell.paragraphs[0]
    r = p.add_run(h)
    r.font.bold = True; r.font.color.rgb = BRANCO; r.font.size = Pt(10.5); r.font.name = "Arial"
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

for ri, row_data in enumerate(rows_t3):
    bg = CIN_HEX if ri % 2 == 0 else "FFFFFF"
    for ci, val in enumerate(row_data):
        cell = tbl3.cell(ri+1, ci)
        set_cell_bg(cell, bg)
        p = cell.paragraphs[0]
        r = p.add_run(val)
        r.font.size = Pt(10.5); r.font.name = "Arial"
        if ci == 1:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r.font.bold = True
            if val.startswith("+"): r.font.color.rgb = LARANJA
            elif val.startswith("−"): r.font.color.rgb = VERMELHO
        set_cell_borders(cell)

doc.add_paragraph()

# ══════════════════════════════════════════════════════════════════════
# RISCOS E IMPLICAÇÕES
# ══════════════════════════════════════════════════════════════════════
add_heading(doc, "6. Riscos e Implicações", level=1)

riscos = [
    ("Risco Fiscal — Perda de Arrecadação", VRM_HEX,
     "307.968 imóveis (44,6% do cadastro) estão com valor venal abaixo do mercado. Nas "
     "transmissões desses imóveis, o ITIV é calculado sobre base inferior ao valor real, "
     "podendo resultar em perda de receita. As casas são o grupo mais crítico, com defasagem "
     "média de 42,4% — quase metade do valor de mercado não é capturado pelo valor venal."),
    ("Risco Jurídico — Impugnações", LAR_HEX,
     "132.461 imóveis (19,2%) estão com valor venal acima do valor de mercado. Contribuintes "
     "que transacionam esses imóveis podem questionar administrativamente ou judicialmente o "
     "lançamento do ITIV, alegando que o imposto foi exigido sobre base superior ao preço de "
     "mercado. Salas comerciais são o grupo mais vulnerável, com valor venal em média 24,3% "
     "acima do mercado."),
    ("Risco de Insegurança Jurídica", AZM_HEX,
     "A ausência de revisão periódica e sistemática do valor venal — apoiada em metodologia "
     "técnica robusta — fragiliza a posição da Fazenda Municipal em eventuais disputas. "
     "O presente modelo fornece a base metodológica necessária para sustentar atualizações "
     "fundamentadas em dados de mercado."),
]
for titulo, cor, texto in riscos:
    add_heading(doc, titulo, level=2, color=RGBColor(
        int(cor[:2],16), int(cor[2:4],16), int(cor[4:],16)))
    add_para(doc, texto, after=10)

# ══════════════════════════════════════════════════════════════════════
# RECOMENDAÇÕES
# ══════════════════════════════════════════════════════════════════════
add_heading(doc, "7. Recomendações", level=1)

recomendacoes = [
    ("1. Revisão Prioritária dos Imóveis Defasados",
     "Iniciar processo de atualização dos 328.518 imóveis classificados como VENAL DEFASADO, "
     "com prioridade para casas (136.536 unidades, defasagem média +48,6%) e apartamentos "
     "(175.295 unidades, defasagem média +30,6%)."),
    ("2. Análise Comparativa com Avaliação Com Anúncios",
     "Realizar análise paralela incorporando dados de anúncios imobiliários (Zap, VivaReal, OLX) "
     "para comparar com os resultados sem anúncios, a fim de calibrar o impacto dos anúncios "
     "nas estimativas e avaliar se há diferença significativa nos imóveis classificados."),
    ("3. Atualização Periódica Baseada no Modelo",
     "Estabelecer ciclo anual de reavaliação em massa do valor venal utilizando o modelo "
     "de Machine Learning, garantindo que o cadastro reflita a dinâmica do mercado imobiliário "
     "de Salvador de forma contínua."),
    ("4. Investigação dos Imóveis Superavaliados",
     "Analisar os 108.432 imóveis com valor venal acima do mercado, especialmente as salas "
     "comerciais (22.178 unidades), para prevenir demandas de restituição e impugnações "
     "administrativas."),
    ("5. Integração com o Processo de Fiscalização do ITIV",
     "Utilizar as estimativas do modelo como parâmetro de referência nas fiscalizações de "
     "ITIV, identificando transmissões declaradas com valor significativamente abaixo do "
     "estimado pelo modelo."),
]

for titulo, texto in recomendacoes:
    p = doc.add_paragraph()
    r1 = p.add_run(titulo + "\n")
    r1.font.bold = True; r1.font.size = Pt(11.5); r1.font.color.rgb = AZUL; r1.font.name = "Arial"
    r2 = p.add_run(texto)
    r2.font.size = Pt(11); r2.font.name = "Arial"
    p.paragraph_format.space_after = Pt(10)

# ══════════════════════════════════════════════════════════════════════
# CONCLUSÃO
# ══════════════════════════════════════════════════════════════════════
add_heading(doc, "8. Conclusão", level=1)

add_para(doc,
    "A avaliação em massa de 690.992 imóveis do cadastro de Salvador — realizada com metodologia "
    "conservadora, baseada exclusivamente em transações reais sem incorporação de anúncios — "
    "revelou que 44,6% do estoque imobiliário municipal apresenta valor venal defasado em relação "
    "ao mercado, com defasagem média de 29,9%. Essa situação representa risco tanto de perda de "
    "arrecadação do ITIV quanto de aumento de demandas por parte de contribuintes com imóveis "
    "superavaliados.",
    after=8)

add_para(doc,
    "O modelo de Machine Learning desenvolvido pela Coordenadoria de Inteligência Fiscal "
    "oferece uma ferramenta técnica robusta, replicável e auditável para subsidiar a "
    "atualização do valor venal. A adoção de revisões periódicas com base nessa metodologia "
    "contribuirá para maior segurança jurídica, justiça fiscal e eficiência na arrecadação "
    "do município de Salvador.",
    after=8)

# ══════════════════════════════════════════════════════════════════════
# SALVAR
# ══════════════════════════════════════════════════════════════════════
out = r"D:\Pai\Coordenadoria de Inteligência Fiscal\ITIV\Relatorio_Defasagem_Valor_Venal_Salvador_Jun2026.docx"
doc.save(out)
print(f"Relatório salvo em:\n{out}")
