# -*- coding: utf-8 -*-
"""Fechamento rapido Selan: usa preds ja geradas + treino unico do candidato.

Evita re-rodar OOF (longo). Gera status Compativel no holdout e cruzamento
com a planilha operacional.

  python -u desafiante_idade/fechar_candidato_selan.py
"""
from __future__ import annotations

import json
import pickle
import sys
import warnings
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PASTA_ITIV = HERE.parent
CODIGO = PASTA_ITIV / "Modelo_Apartamentos_Aprovado" / "codigo"
sys.path.insert(0, str(CODIGO))
sys.path.insert(0, str(HERE))

from idade_features import (  # noqa: E402
    FEATURES_IDADE,
    FAIXAS_IDADE,
    FAIXAS_INSCRICAO,
    anexar_idade,
    carregar_nascimento,
    faixa_idade,
    faixa_inscricao,
)
from teste_inscricao_relativa_setor import (  # noqa: E402
    FEATURES_REL,
    anexar_inscricao_relativa,
    stats_setor_treino,
)
from apartamentos_lib import (  # noqa: E402
    AMOSTRAS,
    CAT_LGBM,
    FEATURES_LGBM,
    K_VIZINHOS,
    SEMENTE,
    calcular_knn_proxy,
    metricas_completas,
    preparar_area_saneamento,
)
from saneamento_chauvenet_iterativo import aplicar_chauvenet_iterativo  # noqa: E402

warnings.filterwarnings("ignore")

SAIDA = HERE / "saida"
TOLERANCIA = 0.15
LIMITE_SUSPEITO_INF, LIMITE_SUSPEITO_SUP = 0.5, 2.0
COMPATIVEL = "Compatível"
COMPATIVEL_ABAIXO = "Compatível (valor da transação abaixo do valor estimado pelo modelo)"
NECESSITA_AUDITOR = "Necessidade Avaliação por Auditor"
SUSPEITO = "Valor da Transação Suspeito (fora de padrão)"
FORA_ESCOPO = "Fora de Escopo do Modelo"
STATUS_XLSX = PASTA_ITIV / "Informações ITIV 20260610 - Status Apartamentos.xlsx"

PARAMS = {
    "learning_rate": 0.05,
    "min_child_samples": 20,
    "n_estimators": 800,
    "num_leaves": 63,
    "random_state": SEMENTE,
    "verbosity": -1,
}
MODELOS = ["baseline", "idade_mais_rel", "idade_abs_rel"]


def classificar(valor, est):
    if pd.isna(est) or est <= 0 or pd.isna(valor) or valor <= 0:
        return FORA_ESCOPO
    r = est / valor
    if r < LIMITE_SUSPEITO_INF or r > LIMITE_SUSPEITO_SUP:
        return SUSPEITO
    if (1 - TOLERANCIA) <= r <= (1 + TOLERANCIA):
        return COMPATIVEL
    if r < (1 - TOLERANCIA):
        return COMPATIVEL_ABAIXO
    return NECESSITA_AUDITOR


def eh_comp(s):
    return str(s or "").startswith("Compatível")


def tabela(df, col_status, col_faixa, ordem):
    rows = []
    for faixa in ordem:
        sub = df[df[col_faixa] == faixa]
        n = len(sub)
        if not n:
            continue
        nc = int(sub[col_status].map(eh_comp).sum())
        na = int((sub[col_status] == NECESSITA_AUDITOR).sum())
        rows.append({
            "faixa": faixa,
            "n": n,
            "n_compativel": nc,
            "pct_compativel": round(100 * nc / n, 2),
            "n_auditor": na,
            "pct_auditor": round(100 * na / n, 2),
            "idade_mediana": float(sub["IDADE_NA_TRANSACAO"].median())
            if sub["IDADE_NA_TRANSACAO"].notna().any() else None,
        })
    return rows


def resumo(df, col_status, rotulo):
    n = len(df)
    nc = int(df[col_status].map(eh_comp).sum())
    n900 = int((df[col_status].map(eh_comp) & (df["CDINSCRICAOIMOB"] > 900_000)).sum())
    return {
        "rotulo": rotulo,
        "n": n,
        "n_compativel": nc,
        "pct_compativel": round(100 * nc / n, 2) if n else None,
        "pct_compativel_com_inscricao_gt_900k": round(100 * n900 / nc, 2) if nc else None,
        "por_inscricao": tabela(df, col_status, "FAIXA_INSCRICAO", [x[0] for x in FAIXAS_INSCRICAO]),
        "por_idade": tabela(df, col_status, "FAIXA_IDADE", [x[0] for x in FAIXAS_IDADE] + ["(sem idade)"]),
        "contagem_status": df[col_status].astype(str).value_counts().to_dict(),
    }


def main():
    print("Fechamento candidato Selan (holdout + cruzamento)", flush=True)
    nasc = carregar_nascimento()

    # --- treino unico do candidato (artefato) ---
    pool = pd.read_parquet(AMOSTRAS / "pool_treino_parametros.parquet")
    teste = pd.read_parquet(AMOSTRAS / "teste_final_parametros.parquet")
    pool = anexar_idade(pool, nasc)
    teste = anexar_idade(teste, nasc)
    pool_limpo = aplicar_chauvenet_iterativo(preparar_area_saneamento(pool)).copy()
    pool_limpo["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, pool_limpo, k=K_VIZINHOS)
    teste_p = teste.copy()
    teste_p["KNN_PROXY"] = calcular_knn_proxy(pool_limpo, teste_p, k=K_VIZINHOS)
    stats = stats_setor_treino(pool_limpo)
    pool_limpo = anexar_inscricao_relativa(pool_limpo, stats)
    teste_p = anexar_inscricao_relativa(teste_p, stats)
    pool_limpo["LOG_INSCRICAO"] = np.log1p(pd.to_numeric(pool_limpo["CDINSCRICAOIMOB"], errors="coerce").clip(lower=0))
    teste_p["LOG_INSCRICAO"] = np.log1p(pd.to_numeric(teste_p["CDINSCRICAOIMOB"], errors="coerce").clip(lower=0))

    feats = list(FEATURES_LGBM) + FEATURES_IDADE + FEATURES_REL
    fill = {c: float(pool_limpo[c].median()) for c in feats if c != "CDSETORFISCAL" and c in pool_limpo}
    Xtr = pool_limpo[feats].copy()
    Xtr["CDSETORFISCAL"] = Xtr["CDSETORFISCAL"].astype("category")
    for c, m in fill.items():
        Xtr[c] = Xtr[c].fillna(m)
    ytr = np.log(pool_limpo["VLTRANSACAO_DEFLACIONADO"])
    model = lgb.LGBMRegressor(**PARAMS)
    model.fit(Xtr, ytr, categorical_feature=[c for c in CAT_LGBM if c in Xtr.columns])
    (SAIDA / "modelo_lightgbm_candidato_idade_rel.txt").write_text(
        model.booster_.model_to_string(), encoding="utf-8"
    )
    with open(SAIDA / "vals_inscricao_por_setor.pkl", "wb") as fh:
        pickle.dump(stats.attrs.get("vals_por_setor", {}), fh)
    st = stats.copy()
    st.attrs = {}
    st.to_parquet(SAIDA / "stats_setor_inscricao_treino.parquet", index=False)
    (SAIDA / "fill_medians_candidato.json").write_text(
        json.dumps(fill, indent=2), encoding="utf-8"
    )
    print("  modelo candidato gravado", flush=True)

    # --- preds holdout ja existentes ---
    preds = pd.read_csv(SAIDA / "preds_inscricao_relativa_setor.csv")
    hold = teste_p.merge(preds, on="SQTRANSMISSAO", how="inner")
    hold["FAIXA_INSCRICAO"] = faixa_inscricao(hold["CDINSCRICAOIMOB"])
    hold["FAIXA_IDADE"] = faixa_idade(hold["IDADE_NA_TRANSACAO"])
    real = hold["VLTRANSACAO_DEFLACIONADO"].to_numpy()

    holdout_metricas = {}
    for nome in MODELOS:
        col = f"PRED_{nome}"
        met = metricas_completas(hold[col].to_numpy(), real)
        holdout_metricas[nome] = {k: float(v) for k, v in met.items()}
        hold[f"STATUS_{nome}"] = [classificar(v, e) for v, e in zip(real, hold[col])]
        print(
            f"  holdout {nome}: CODmed={met['COD_mediano']:.3f}% "
            f"Compat={100*hold[f'STATUS_{nome}'].map(eh_comp).mean():.1f}%",
            flush=True,
        )

    # --- status operacional ---
    preview = pd.read_excel(STATUS_XLSX, sheet_name="Exportar Planilha", nrows=0)
    wanted, colmap = [], {}
    for c in preview.columns:
        cu = str(c).upper()
        cu_ascii = " ".join("".join(ch if ord(ch) < 128 else " " for ch in cu).split())
        dest = None
        if str(c).strip().upper() == "CDINSCRICAOIMOB":
            dest = "CDINSCRICAOIMOB"
        elif str(c).strip().upper() == "SQTRANSMISSAO":
            dest = "SQTRANSMISSAO"
        elif "ESTIMATIVA DO MODELO" in cu and "LIGHTGBM" in cu:
            dest = "VALOR_MODELO"
        elif "STATUS DA AVAL" in cu or "STATUS DA AVAL" in cu_ascii:
            dest = "STATUS_ORIGINAL"
        elif ("VALOR DA TRANS" in cu or "VALOR DA TRANS" in cu_ascii) and "ATUALIZADO" in cu_ascii:
            dest = "VALOR_TX"
        if dest:
            wanted.append(c)
            colmap[c] = dest
    status = pd.read_excel(STATUS_XLSX, sheet_name="Exportar Planilha", usecols=wanted).rename(columns=colmap)
    status["VALOR_MODELO"] = pd.to_numeric(status["VALOR_MODELO"], errors="coerce")
    status["VALOR_TX"] = pd.to_numeric(status["VALOR_TX"], errors="coerce")
    status["CDINSCRICAOIMOB"] = pd.to_numeric(status["CDINSCRICAOIMOB"], errors="coerce")
    status = status[status["VALOR_MODELO"].notna() & (status["VALOR_MODELO"] > 0)].copy()
    status["DATA_TRANSACAO"] = pd.NaT  # leitura enxuta sem data → idade usa ano ref
    status = anexar_idade(status, nasc)

    cruz = status.merge(
        hold[["SQTRANSMISSAO"] + [f"PRED_{n}" for n in MODELOS]],
        on="SQTRANSMISSAO",
        how="inner",
    )
    print(f"  cruzamento holdout×status: {len(cruz):,}", flush=True)
    cruz["FAIXA_INSCRICAO"] = faixa_inscricao(cruz["CDINSCRICAOIMOB"])
    cruz["FAIXA_IDADE"] = faixa_idade(cruz["IDADE_NA_TRANSACAO"])
    for nome in MODELOS:
        cruz[f"STATUS_NOVO_{nome}"] = [
            classificar(v, e) for v, e in zip(cruz["VALOR_TX"], cruz[f"PRED_{nome}"])
        ]

    holdout_comp = {n: resumo(hold, f"STATUS_{n}", n) for n in MODELOS}
    operacional = {"aprovado_planilha": resumo(cruz, "STATUS_ORIGINAL", "aprovado_planilha")}
    for n in MODELOS:
        operacional[n] = resumo(cruz, f"STATUS_NOVO_{n}", n)

    pacote = {
        "candidato_recomendado": "idade_mais_rel",
        "alternativa_equidade_antigos": "idade_abs_rel",
        "universo_compativel": "holdout cruzado com planilha de status (VALOR_TX operacional)",
        "holdout_metricas": holdout_metricas,
        "compativel_holdout_deflacionado": holdout_comp,
        "compativel_cruzamento_status_operacional": operacional,
        "n_cruzamento": int(len(cruz)),
        "n_holdout": int(len(hold)),
    }
    (SAIDA / "comparativo_compativel_candidato_selan.json").write_text(
        json.dumps(pacote, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    hold.to_parquet(SAIDA / "preds_candidato_selan_holdout.parquet", index=False)
    cruz.to_parquet(SAIDA / "cruzamento_status_candidato_holdout.parquet", index=False)

    try:
        import matplotlib.pyplot as plt
        ordem = [x[0] for x in FAIXAS_INSCRICAO]
        fig, ax = plt.subplots(figsize=(8, 4.5))
        x = np.arange(len(ordem))
        width = 0.25
        for i, nome in enumerate(MODELOS):
            tab = {r["faixa"]: r["pct_compativel"] for r in operacional[nome]["por_inscricao"]}
            ax.bar(x + i * width, [tab.get(f, 0) for f in ordem], width, label=nome)
        ax.set_xticks(x + width)
        ax.set_xticklabels(ordem)
        ax.set_ylabel("% Compatível")
        ax.set_ylim(0, 100)
        ax.set_title("% Compatível por inscrição (holdout × status operacional)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(SAIDA / "grafico_compativel_candidato_por_inscricao.png", dpi=140)
        plt.close(fig)
    except Exception as exc:
        print(f"  grafico: {exc}", flush=True)

    def fmt(rows):
        lines = ["| Faixa | N | % Compatível | % Auditor |", "|---|---:|---:|---:|"]
        for r in rows:
            lines.append(
                f"| {r['faixa']} | {r['n']:,} | {r['pct_compativel']:.1f}% | {r['pct_auditor']:.1f}% |"
            )
        return "\n".join(lines)

    b, r, a = operacional["baseline"], operacional["idade_mais_rel"], operacional["idade_abs_rel"]
    h = holdout_metricas
    hb, hr, ha = holdout_comp["baseline"], holdout_comp["idade_mais_rel"], holdout_comp["idade_abs_rel"]

    nota = f"""# Nota para decisão Selan — candidato idade + inscrição relativa

**Data:** 11/08/2026  
**Status:** experimental — **não** substitui o modelo aprovado (14/07/2026) até decisão formal.  
**Candidato recomendado:** `idade_mais_rel` (aprovado + idade + inscrição relativa no setor).  
**Alternativa (melhor nos antigos nos testes anteriores):** `idade_abs_rel`.

---

## 1. O que foi feito

1. Confirmou-se o candidato **idade + inscrição relativa** (`LOG_INSCRICAO_REL`, `RANK_INSCRICAO_SETOR`).
2. Gravou-se o artefato LightGBM do candidato (mesmos hiperparâmetros do aprovado).
3. Reprocessou-se o status **Compatível** no **holdout** com a regra operacional (±15%; suspeito fora de 0,5–2,0).
4. Cruzou-se com a planilha de status (mesmo `VALOR_TX` usado no diagnóstico do David).

SELIC permanece fora (teste anterior sem ganho).

---

## 2. Holdout — métricas IAAO

| Modelo | COD mediano | COD | PRD |
|---|---:|---:|---:|
| baseline | {h['baseline']['COD_mediano']:.3f}% | {h['baseline']['COD']:.3f}% | {h['baseline']['PRD']:.4f} |
| idade_mais_rel | {h['idade_mais_rel']['COD_mediano']:.3f}% | {h['idade_mais_rel']['COD']:.3f}% | {h['idade_mais_rel']['PRD']:.4f} |
| idade_abs_rel | {h['idade_abs_rel']['COD_mediano']:.3f}% | {h['idade_abs_rel']['COD']:.3f}% | {h['idade_abs_rel']['PRD']:.4f} |

---

## 3. Holdout — % Compatível (valor deflacionado da amostra)

| Modelo | % Compatível | % dos Compatível com inscrição >900k |
|---|---:|---:|
| baseline | {hb['pct_compativel']:.1f}% | {hb['pct_compativel_com_inscricao_gt_900k']:.1f}% |
| idade_mais_rel | {hr['pct_compativel']:.1f}% | {hr['pct_compativel_com_inscricao_gt_900k']:.1f}% |
| idade_abs_rel | {ha['pct_compativel']:.1f}% | {ha['pct_compativel_com_inscricao_gt_900k']:.1f}% |

### Por inscrição — candidato idade_mais_rel (holdout)
{fmt(hr['por_inscricao'])}

### Por inscrição — baseline (holdout)
{fmt(hb['por_inscricao'])}

---

## 4. Cruzamento com planilha de status (VALOR_TX operacional)

N = {len(cruz):,} (holdout ∩ status com estimativa).

### Baseline reclassificado
{fmt(b['por_inscricao'])}

### idade_mais_rel
{fmt(r['por_inscricao'])}

### idade_abs_rel
{fmt(a['por_inscricao'])}

**Concentração David (% Compatível que tem inscrição >900k):**  
baseline {b.get('pct_compativel_com_inscricao_gt_900k')}% · idade_mais_rel {r.get('pct_compativel_com_inscricao_gt_900k')}% · idade_abs_rel {a.get('pct_compativel_com_inscricao_gt_900k')}%

---

## 5. Recomendação

| Pergunta | Sugestão |
|---|---|
| Promover agora a produção? | **Não automaticamente** — falta Etapa 5 normativa + manifesto + lote completo |
| Qual candidato? | **idade_mais_rel** (melhor COD global) |
| Prioridade = antigos? | Avaliar também **idade_abs_rel** |
| Modelo aprovado? | Continua congelado até decisão formal |

### Checklist promoção
- [ ] Revisar esta nota e `desafiante_idade/saida/grafico_compativel_candidato_por_inscricao.png`
- [ ] Etapa 5 normativa no candidato
- [ ] Regenerar lote + planilha de status completa
- [ ] Manifesto SHA-256
- [ ] Registro formal de aprovação

---

## 6. Artefatos

| Arquivo | Conteúdo |
|---|---|
| `modelo_lightgbm_candidato_idade_rel.txt` | LightGBM candidato |
| `stats_setor_inscricao_treino.parquet` | Medianas por setor |
| `vals_inscricao_por_setor.pkl` | Distribuições para rank |
| `comparativo_compativel_candidato_selan.json` | Números completos |
| `cruzamento_status_candidato_holdout.parquet` | Status reprocessado |
| `grafico_compativel_candidato_por_inscricao.png` | Comparativo visual |

---

*Coordenadoria de Inteligência Fiscal — SEFAZ Salvador*
"""
    (SAIDA / "Nota_Candidato_Selan_Idade_Relativa.md").write_text(nota, encoding="utf-8")
    (PASTA_ITIV / "Nota_Candidato_Selan_Idade_Relativa.md").write_text(nota, encoding="utf-8")

    # Word
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Cm
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
        import re

        AZUL = RGBColor(0x1A, 0x3A, 0x5C)

        def shade(cell, hexc):
            tcPr = cell._tc.get_or_add_tcPr()
            sh = OxmlElement("w:shd")
            sh.set(qn("w:val"), "clear")
            sh.set(qn("w:color"), "auto")
            sh.set(qn("w:fill"), hexc)
            tcPr.append(sh)

        doc = Document()
        for s in doc.sections:
            s.top_margin = Cm(2.2)
            s.bottom_margin = Cm(2.2)
            s.left_margin = Cm(2.5)
            s.right_margin = Cm(2.2)
        doc.styles["Normal"].font.name = "Arial"
        doc.styles["Normal"].font.size = Pt(11)

        for ln in nota.split("\n"):
            s = ln.rstrip()
            if not s.strip() or s.startswith("---"):
                continue
            if s.startswith("|"):
                continue
            if s.startswith("# "):
                p = doc.add_heading(s[2:], level=1)
            elif s.startswith("## "):
                p = doc.add_heading(s[3:], level=2)
            elif s.startswith("### "):
                p = doc.add_heading(s[4:], level=3)
            elif s.startswith("- ["):
                doc.add_paragraph(s[2:], style="List Bullet")
                continue
            elif s.startswith("- "):
                doc.add_paragraph(s[2:], style="List Bullet")
                continue
            elif re.match(r"^\d+\. ", s):
                doc.add_paragraph(re.sub(r"^\d+\. ", "", s), style="List Number")
                continue
            else:
                p = doc.add_paragraph()
                for part in re.split(r"(\*\*.+?\*\*)", s):
                    if part.startswith("**") and part.endswith("**"):
                        run = p.add_run(part[2:-2]); run.bold = True
                    else:
                        run = p.add_run(part)
                    run.font.name = "Arial"
                continue
            for run in p.runs:
                run.font.color.rgb = AZUL

        doc.add_heading("Anexo — Compatível por inscrição (cruzamento operacional)", level=2)
        for titulo, rows in (("Baseline", b["por_inscricao"]), ("idade_mais_rel", r["por_inscricao"]), ("idade_abs_rel", a["por_inscricao"])):
            doc.add_heading(titulo, level=3)
            t = doc.add_table(rows=1 + len(rows), cols=4)
            t.style = "Table Grid"
            for j, hcell in enumerate(["Faixa", "N", "% Compatível", "% Auditor"]):
                cell = t.cell(0, j)
                shade(cell, "1A3A5C")
                run = cell.paragraphs[0].add_run(hcell)
                run.font.bold = True
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                run.font.size = Pt(9)
            for i, row in enumerate(rows):
                for j, v in enumerate([row["faixa"], f"{row['n']:,}", f"{row['pct_compativel']:.1f}%", f"{row['pct_auditor']:.1f}%"]):
                    run = t.cell(i + 1, j).paragraphs[0].add_run(v)
                    run.font.size = Pt(9)
                    run.font.name = "Arial"
            doc.add_paragraph()

        doc.save(SAIDA / "Nota_Candidato_Selan_Idade_Relativa.docx")
        doc.save(PASTA_ITIV / "Nota_Candidato_Selan_Idade_Relativa.docx")
        print("Word OK", flush=True)
    except Exception as exc:
        print(f"Word: {exc}", flush=True)

    print("\n=== RESUMO ===", flush=True)
    for nome in MODELOS:
        o = operacional[nome]
        print(f"  {nome}: Compat={o['pct_compativel']}% | %Compat>900k={o['pct_compativel_com_inscricao_gt_900k']}%", flush=True)
        for row in o["por_inscricao"]:
            print(f"    {row['faixa']}: Compat={row['pct_compativel']}% Auditor={row['pct_auditor']}%", flush=True)


if __name__ == "__main__":
    main()
