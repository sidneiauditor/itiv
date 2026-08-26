# Modelo candidato — Apartamentos com idade + inscrição relativa

**Pacote:** `Modelo_Apartamentos_Candidato_Idade_20260811`  
**Data:** 2026-08-11  
**Status:** CANDIDATO para avaliação do Selan — **não substitui** o modelo aprovado em `Modelo_Apartamentos_Aprovado/` (14/07/2026).

---

## Comece por aqui (Selan)

1. **`Dados ITIV - Avaliacao pelo Modelo Candidato.xlsx`** — planilha no mesmo espírito da que foi encaminhada com o modelo aprovado (`Dados ITIV -Avaliação pelo Modelo.xlsx`): dados do ITIV + estimativa/status do **aprovado** + estimativa/status do **candidato** (lado a lado).
2. **`relatorios/Resumo_Executivo_Candidato_Selan.docx`** — 1 página, linguagem simples.
3. **`relatorios/Nota_Candidato_Selan_Idade_Relativa.docx`** — números de Compatível e decisão sugerida.
4. **`dados/avaliacao_holdout_candidato.json`** — métricas IAAO no holdout.
5. **`dados/graficos/`** — COD e % Compatível por faixa de inscrição.

---

## O que é este modelo

O modelo aprovado avalia bem apartamentos **novos** e erra mais nos **antigos**.  
Este candidato acrescenta:

- **idade** do imóvel (quando o ano de construção existe);
- **inscrição relativa no setor** (se o imóvel é novo/velho *naquele bairro*).

Assim o sistema “enxerga” melhor a idade mesmo quando falta o ano de construção.

Alternativa testada (melhor ainda nos antigos, quase empatada no global):  
**idade + inscrição absoluta + relativa** (`idade_abs_rel`).

---

## Resultado no teste final (holdout)

| Modelo | COD mediano | COD | PRD | PRB | COD antigos (&lt;300k) |
|---|---:|---:|---:|---:|---:|
| Baseline (aprovado) | 6.530% | 9.603% | 1.0175 | -0.0094 | 10.82% |
| **Candidato (idade+rel)** | **6.383%** | 9.231% | 1.0157 | -0.0084 | 9.68% |
| Alternativa (idade+abs+rel) | 6.392% | 9.187% | 1.0160 | -0.0090 | 9.58% |
| Meta IAAO | — | ≤15% | 0,98–1,03 | ±0,05 | — |

No reprocessamento do status Compatível (±15%), os antigos sobem de ~74% para ~81% Compatível (menos auditoria desnecessária).

---

## Conteúdo da pasta

| Pasta | Conteúdo |
|---|---|
| `dados/` | Modelo LightGBM, features, medianas, stats de setor, manifesto SHA-256, amostras |
| `dados/graficos/` | Gráficos da avaliação |
| `relatorios/` | Resumo executivo + nota Selan |
| `decisoes_e_notas/` | Notas técnicas (idade, inscrição, SELIC) |
| `codigo/` | Scripts para reproduzir a avaliação |

---

## O que **não** está neste pacote

- Substituição automática do modelo em produção  
- Planilha de status completa regenerada para 100% do universo (só holdout cruzado)  
- Etapa 5 hedônica refeita linha a linha (âncora normativa do aprovado permanece válida; o ganho aqui é do LightGBM com novas features)

---

## Decisão solicitada ao Selan

1. Autorizar a equipe a tratar `idade_mais_rel` como **candidato oficial a promoção**?  
2. Preferir a alternativa `idade_abs_rel` (foco nos antigos)?  
3. Autorizar Etapa 5 completa + regeneração do lote/status antes da troca em produção?

Enquanto isso, o modelo aprovado em 14/07/2026 **permanece** o oficial.


---

## Status atualizado em 2026-08-26

**PROMOVIDO À PRODUÇÃO.** Artefatos copiados para `Modelo_Apartamentos_Aprovado/`. Avaliador HTML atualizado.
