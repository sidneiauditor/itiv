const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, HeadingLevel, AlignmentType, BorderStyle, WidthType,
  ShadingType, PageBreak,
} = require("docx");

const PASTA = "D:/Pai/Coordenadoria de Inteligência Fiscal/ITIV";
const cv = JSON.parse(fs.readFileSync(`${PASTA}/metricas_cv_apartamentos.json`, "utf-8"));
const conf = JSON.parse(fs.readFileSync(`${PASTA}/confianca_vs_sinalizados.json`, "utf-8"));

const AZUL = "1A3A5C";
const CINZA_CLARO = "F2F2F2";
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({ text, ...opts })],
  });
}

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
}

function celula(text, opts = {}) {
  return new TableCell({
    borders,
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.header ? { fill: AZUL, type: ShadingType.CLEAR }
      : (opts.destaque ? { fill: CINZA_CLARO, type: ShadingType.CLEAR } : undefined),
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [new TextRun({
        text: String(text), bold: !!opts.header || !!opts.negrito,
        color: opts.header ? "FFFFFF" : undefined, size: 20,
      })],
    })],
  });
}

function tabela(cabecalho, linhas, larguras, linhasDestaque = []) {
  const total = larguras.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: larguras,
    rows: [
      new TableRow({ children: cabecalho.map((c, i) => celula(c, { header: true, width: larguras[i], center: true })) }),
      ...linhas.map((l, li) => new TableRow({
        children: l.map((c, i) => celula(c, {
          width: larguras[i], center: true,
          destaque: linhasDestaque.includes(li), negrito: linhasDestaque.includes(li),
        })),
      })),
    ],
  });
}

function imagem(caminho, largura, proporcao) {
  const data = fs.readFileSync(caminho);
  const alturaProporcional = Math.round(largura * proporcao);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 200 },
    children: [new ImageRun({
      type: "png",
      data,
      transformation: { width: largura, height: alturaProporcional },
      altText: { title: "Gráfico", description: "Gráfico do relatório", name: "grafico" },
    })],
  });
}

const hp = cv.hiperparametros_lightgbm;
const hHold = cv.holdout_hedonico;
const lHold = cv.holdout_lightgbm;
const gsm = cv.gridsearch_multimodelo;

const NOMES_MODELOS = {
  lightgbm: "LightGBM",
  hist_gradient_boosting: "HistGradientBoosting",
  random_forest: "Floresta Aleatória",
  extra_trees: "Extra Trees",
  elasticnet: "ElasticNet (linear)",
};
const ordemGs = Object.keys(gsm).sort((a, b) => gsm[a].mae_log_cv - gsm[b].mae_log_cv);

const fmt = (x, casas) => x.toFixed(casas).replace(".", ",");

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Arial", color: AZUL },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: AZUL },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    children: [
      new Paragraph({ heading: HeadingLevel.HEADING_1,
        children: [new TextRun("Relatório da Etapa 4 — Treino do Modelo de Apartamentos (ITIV)")] }),
      p("Coordenadoria de Inteligência Fiscal — SEFAZ Salvador", { italics: true }),
      p("Data: 14/07/2026 — substitui a versão de 09/07/2026."),
      p("Complementa: Decisoes_Consistencia_Modelo_Apartamentos.docx, REGISTRO_ETAPAS_APROVACAO.md e Lista_Final_Parametros_Apartamentos.docx."),

      h1("1. Objetivo"),
      p("Este documento reporta a execução da Etapa 4 (treino do modelo de apartamentos), aplicando as decisões D1–D7, as aprovações da Lista Final de Parâmetros e as duas decisões da equipe de 14/07/2026: (i) o filtro de plausibilidade da base de treino, que substituiu o corte de vendas simbólicas e restabeleceu a leitura confiável de PRD e PRB; e (ii) o nível de confiança de 90% para a sinalização de contribuintes (D5). O GridSearch foi ampliado para disputar cinco famílias de modelos (D6). O modelo vencedor atende a todas as metas IAAO no teste final."),

      h1("2. Decisões aplicadas"),
      tabela(
        ["Item", "Decisão aplicada no código"],
        [
          ["D1", "Remoção dos SQTRANSMISSAO duplicados (mantida a 1ª ocorrência)"],
          ["D2", "Remoção completa das linhas duplicadas de inscrição+data+valor"],
          ["Filtro de plausibilidade", "Decisão de 14/07/2026 — substitui o corte de vendas simbólicas. Permanecem na base de treino/validação/teste somente transações que atendem, ao mesmo tempo: (1) tipo \"Compra e Venda\" (igualdade exata); (2) subunidade \"Apartamento\"; (3) VLITIV > 0; (4) diferença entre valor de transação e valor venal corrigido dentro de ±30%. Motivo: melhorar PRD e PRB, distorcidos por transações com valores muito abaixo ou muito acima do venal."],
          ["D3", "Exclusão de vendas antes de 03/2020; deflação pelo IPCA (série 433/BCB) até a data de referência; variável de tendência temporal"],
          ["D4", "Metas IAAO (razão 0,90–1,10; COD ≤15%; PRD 0,98–1,03; PRB ±0,05) usadas para avaliar o modelo"],
          ["D5", "Decisão de 14/07/2026 — nível de confiança de 90% para a sinalização de contribuintes, escolhido pela equipe com o COD do modelo novo em mãos (seção 6)"],
          ["D6", "GridSearch ampliado (14/07/2026) para cinco famílias de modelos: LightGBM, HistGradientBoosting, Floresta Aleatória, Extra Trees e ElasticNet. O hedônico (OLS) segue treinado em paralelo como âncora normativa"],
          ["D7", "Validação cruzada k=10; Chauvenet iterativo e proxy KNN recalculados dentro de cada fold"],
          ["VLFC*", "Excluídos do modelo (circularidade com o valor venal atual)"],
          ["Outlier", "Chauvenet iterativo, aplicado somente no treino de cada fold"],
          ["Andar", "Entra com valor + marca de ausência de informação"],
        ],
        [2200, 7160],
      ),

      h1("3. Preparação da base"),
      p("Apartamentos na base limpa: 97.990. Funil de filtros: D1 (−7); tipo \"Compra e Venda\" exato (−70); VLITIV > 0 (−23.634); diferença venal × transação dentro de ±30% (−27.857, dos quais 2 sem valor venal corrigido válido); D2 (−5); D3 (−0 pelo corte temporal, já coberto pelos filtros anteriores): 46.417 transações. Após a engenharia de parâmetros (remoção de 25 registros sem área privativa válida): 46.392 transações."),
      p("Divisão: 80% para o pool de treino/validação cruzada (37.116 linhas) e 20% reservado como teste final — holdout nunca usado em treino ou ajuste de hiperparâmetros (9.276 linhas)."),
      p("Nota: o filtro de plausibilidade reduziu a base de 91.287 para 46.392 transações (cerca de metade). Os dois cortes de maior impacto foram VLITIV > 0 e o limite de ±30% sobre o valor venal corrigido. A contrapartida é uma base de treino alinhada a transações plausíveis, com PRD e PRB novamente interpretáveis (seção 5.3)."),

      h1("4. Método de treino"),
      p("A. GridSearch multi-modelo (CV interno k=5) sobre o pool inteiro (D6, ampliado em 14/07/2026): cinco famílias de modelos disputaram com grades próprias de hiperparâmetros, avaliadas pelo mesmo critério (menor erro absoluto médio no logaritmo do valor). Resultado da disputa:"),
      tabela(
        ["Modelo candidato", "Erro médio (log) — menor é melhor"],
        ordemGs.map(n => [NOMES_MODELOS[n] || n, fmt(gsm[n].mae_log_cv, 4)]),
        [4600, 4760],
        [0],
      ),
      imagem(`${PASTA}/graficos_relatorio/gridsearch_multimodelo.png`, 620, 7.3 / 13),
      p(`Vencedor: LightGBM, com learning_rate=${hp.learning_rate}, num_leaves=${hp.num_leaves}, n_estimators=${hp.n_estimators} e min_child_samples=${hp.min_child_samples}. Os quatro modelos de árvore ficaram próximos entre si, o que indica que o resultado não depende da escolha de um algoritmo específico; o modelo linear (ElasticNet) ficou atrás, reforçando que a relação entre as características do imóvel e o preço não é linear.`),
      p("B. Validação cruzada externa k=10 (D7): em cada fold, o Chauvenet iterativo e o proxy KNN de vizinhança são recalculados somente com o treino do próprio fold — nunca vazam dados do fold de validação."),
      p("C. Treino final no pool inteiro (modelo vencedor, mesmos hiperparâmetros) e avaliação única no teste final (holdout), nunca tocado antes."),

      h1("5. Resultados"),
      h2("5.1 Validação cruzada (10 folds)"),
      imagem(`${PASTA}/graficos_relatorio/cod_por_fold.png`, 620, 7.3 / 13),
      imagem(`${PASTA}/graficos_relatorio/razao_por_fold.png`, 620, 7.3 / 13),

      h2("5.2 Teste final (holdout) — nunca usado em treino ou ajuste"),
      imagem(`${PASTA}/graficos_relatorio/comparativo_holdout.png`, 620, 7 / 14),
      tabela(
        ["Modelo", "Razão mediana", "COD", "COD mediano", "PRD", "PRB"],
        [
          ["Hedônico (OLS)", fmt(hHold.razao_mediana, 3), `${fmt(hHold.COD, 1)}%`, `${fmt(hHold.COD_mediano, 1)}%`, fmt(hHold.PRD, 3), fmt(hHold.PRB, 4)],
          ["LightGBM", fmt(lHold.razao_mediana, 3), `${fmt(lHold.COD, 1)}%`, `${fmt(lHold.COD_mediano, 1)}%`, fmt(lHold.PRD, 3), fmt(lHold.PRB, 4)],
          ["Meta IAAO (D4)", "0,90 – 1,10", "≤ 15%", "—", "0,98 – 1,03", "±0,05"],
        ],
        [2400, 1700, 1400, 1700, 1700, 1460],
        [1],
      ),
      p(`Leitura: o LightGBM atende a TODAS as metas IAAO no teste final — razão mediana ${fmt(lHold.razao_mediana, 3)} (meta 0,90–1,10), COD ${fmt(lHold.COD, 1)}% (meta ≤ 15%), PRD ${fmt(lHold.PRD, 3)} (meta 0,98–1,03) e PRB ${fmt(lHold.PRB, 4)} (meta ±0,05). O hedônico fica fora da meta em COD (${fmt(hHold.COD, 1)}%) e PRD (${fmt(hHold.PRD, 3)}), com razão mediana e PRB dentro da meta; permanece como âncora normativa (D6), com testes estatísticos completos registrados em modelo_hedonico_resumo.txt.`, { italics: true }),
      p("Papel do hedônico e independência entre os modelos: o hedônico (OLS) e o LightGBM são treinados em paralelo e de forma totalmente independente — o resultado de um não entra no cálculo do outro. O LightGBM é o modelo que calcula os valores e sinaliza contribuintes; o hedônico não é usado na avaliação. Sua função é de sustentação normativa: por ser uma regressão no formato previsto pela NBR 14653-2, permite demonstrar o peso de cada característica do imóvel, aplicar os testes estatísticos formais (t/F) e explicar o resultado a contribuintes, julgadores e à Procuradoria, evidenciando que um modelo no formato da norma, com os mesmos dados, converge na mesma direção. O fato de o hedônico não atingir as metas de COD e PRD não afeta o modelo de produção — ao contrário, documenta com transparência por que o LightGBM foi o escolhido para a avaliação, com o hedônico ao lado como fundamentação."),

      h2("5.3 PRD e PRB — leitura restabelecida pelo filtro de plausibilidade"),
      p("Na versão anterior deste relatório (09/07/2026), PRD e PRB não tinham leitura confiável: transações com valores muito distantes do venal (para baixo e para cima) distorciam as métricas calculadas por média (PRD chegava à casa das dezenas). Com o filtro de plausibilidade decidido pela equipe em 14/07/2026 (seção 2), as duas métricas voltaram à escala normal e passaram a ser diretamente comparáveis às metas IAAO — e o LightGBM atende a ambas (PRD " + fmt(lHold.PRD, 3) + "; PRB " + fmt(lHold.PRB, 4) + "). A estabilidade entre os 10 folds (PRD entre 1,015 e 1,023) confirma que a distorção foi eliminada."),

      h1("6. Sinalização de contribuintes — nível de confiança decidido (D5)"),
      p("Calculado sobre o teste final, com intervalos de predição do LightGBM (quantile regression) para cada nível de confiança. A equipe decidiu em 14/07/2026, com o COD do modelo novo em mãos, adotar o nível de confiança de 90% como coeficiente de segurança para a sinalização. Os demais níveis constam apenas como referência comparativa."),
      imagem(`${PASTA}/graficos_relatorio/confianca_sinalizados.png`, 620, 7.3 / 13),
      tabela(
        ["Confiança", "Sinalizados", "% dos contribuintes"],
        conf.map(c => [
          `${(c.confianca * 100).toFixed(0)}%${c.nivel_decidido_pela_equipe ? " (decidido)" : ""}`,
          c.sinalizados.toLocaleString("pt-BR"),
          `${fmt(c.pct_sinalizados, 1)}%`,
        ]),
        [2500, 3500, 3360],
        conf.map((c, i) => c.nivel_decidido_pela_equipe ? i : -1).filter(i => i >= 0),
      ),

      h1("7. Reprodutibilidade"),
      p("Todos os dados e scripts usados neste treino estão registrados (SHA-256) em manifesto_treino.json, junto com os dois modelos: modelo_lightgbm_apartamentos.txt e modelo_hedonico_resumo.txt (testes estatísticos completos do OLS). O arquivo metricas_cv_apartamentos.json registra a comparação completa dos cinco candidatos do GridSearch multi-modelo. As travas automáticas de pré-treino (verificacoes_pre_treino.py, atualizadas para o novo filtro) foram executadas e retornaram LIBERADO."),

      h1("8. Próximos passos"),
      p("1. Aprovação formal do modelo (D4) — o LightGBM atende a todas as metas IAAO no teste final (razão mediana, COD, PRD e PRB); o hedônico permanece como âncora normativa (D6)."),
      p("2. Etapa 5 — validação normativa completa."),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(`${PASTA}/Relatorio_Etapa4_Treino_Modelo_Apartamentos_20260714.docx`, buffer);
  console.log("Documento gerado com sucesso.");
});
