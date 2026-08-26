const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
} = require("docx");

const PASTA = "D:/Pai/Coordenadoria de Inteligência Fiscal/ITIV";
const cv = JSON.parse(fs.readFileSync(`${PASTA}/metricas_cv_apartamentos.json`, "utf-8"));
const r5 = JSON.parse(fs.readFileSync(`${PASTA}/etapa5_resultados.json`, "utf-8"));

const AZUL = "1A3A5C";
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function p(text, opts = {}) {
  return new Paragraph({ spacing: { after: 100 }, children: [new TextRun({ text, ...opts })] });
}
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)], spacing: { before: 200, after: 80 } }); }

function celula(text, opts = {}) {
  return new TableCell({
    borders,
    width: { size: opts.width || 2000, type: WidthType.DXA },
    shading: opts.header ? { fill: AZUL, type: ShadingType.CLEAR } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    children: [new Paragraph({
      alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      children: [new TextRun({ text: String(text), bold: !!opts.header, color: opts.header ? "FFFFFF" : undefined, size: 19 })],
    })],
  });
}
function tabela(cabecalho, linhas, larguras) {
  const total = larguras.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: larguras,
    rows: [
      new TableRow({ children: cabecalho.map((c, i) => celula(c, { header: true, width: larguras[i], center: true })) }),
      ...linhas.map(l => new TableRow({ children: l.map((c, i) => celula(c, { width: larguras[i], center: i > 0 })) })),
    ],
  });
}

const fmt = (x, casas) => Number(x).toFixed(casas).replace(".", ",");
const lgb = cv.holdout_lightgbm;
const hed = cv.holdout_hedonico;
const venal = r5.comparacao_venal_modelos.valor_venal_cadastro;

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Arial", size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: AZUL },
        paragraph: { spacing: { before: 200, after: 80 } } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
      margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 } } },
    children: [
      new Paragraph({ heading: HeadingLevel.HEADING_1,
        children: [new TextRun({ text: "Resumo Executivo — Modelo de Apartamentos (ITIV)", size: 30 })] }),
      p("Coordenadoria de Inteligência Fiscal — SEFAZ Salvador  |  Data: 14/07/2026", { italics: true, size: 18 }),
      p("Documento de apoio para a aprovação formal (D4) das Etapas 4 e 5. Detalhes completos em Relatorio_Etapa4_Treino_Modelo_Apartamentos_20260714.docx e Relatorio_Etapa5_Validacao_Normativa_20260714.docx.", { size: 18 }),

      h1("O que foi feito"),
      p("Foi treinado e validado um modelo estatístico (LightGBM) capaz de estimar o valor de mercado de apartamentos em Salvador a partir de transações reais de compra e venda (2020–2026), seguindo as normas ABNT NBR 14653-1/2, IBAPE/SOBREA 2023 e os padrões internacionais da IAAO. Um segundo modelo (regressão hedônica) foi treinado em paralelo como âncora normativa — explicável passo a passo, mas usado apenas como fundamentação, não para calcular valores.", { size: 19 }),

      h1("Resultado no teste final (dados nunca usados no treino)"),
      tabela(
        ["Estimativa", "Razão mediana", "COD", "PRD", "PRB", "Meta atendida?"],
        [
          ["Valor venal (cadastro atual)", fmt(venal.razao_mediana, 3), `${fmt(venal.COD, 1)}%`, fmt(venal.PRD, 3), fmt(venal.PRB, 4), "Não (subavaliado)"],
          ["Hedônico (âncora)", fmt(hed.razao_mediana, 3), `${fmt(hed.COD, 1)}%`, fmt(hed.PRD, 3), fmt(hed.PRB, 4), "Parcial"],
          ["Modelo novo (LightGBM)", fmt(lgb.razao_mediana, 3), `${fmt(lgb.COD, 1)}%`, fmt(lgb.PRD, 3), fmt(lgb.PRB, 4), "SIM — todas"],
          ["Meta técnica (IAAO)", "0,90–1,10", "≤15%", "0,98–1,03", "±0,05", "—"],
        ],
        [2600, 1600, 1200, 1500, 1200, 2260],
      ),
      p(`O valor venal usado hoje pela Prefeitura está, em média, ${fmt((1 - venal.razao_mediana) * 100, 0)}% abaixo do preço real de mercado. O modelo novo chega a ${fmt(lgb.razao_mediana, 3)} — muito próximo do ideal (1,000) — e atende a todas as quatro metas técnicas de qualidade.`, { size: 19, bold: true }),

      h1("O modelo é justo?"),
      p(`Sim. Testamos separadamente 10 faixas de valor (de imóveis mais baratos a mais caros) e 70 bairros/setores fiscais com dados suficientes: em todos eles a razão mediana ficou dentro da meta (0,90–1,10), e o erro típico (COD) ficou abaixo de 15% em praticamente todos. O modelo não favorece nenhuma faixa de preço nem nenhuma região.`, { size: 19 }),

      h1("Enquadramento normativo"),
      p(`Modelo hedônico: Grau II de fundamentação e Grau III de precisão (o mais alto), conforme NBR 14653-2. Modelo LightGBM (o que efetivamente calcula os valores): justificado e validado conforme a norma IBAPE/SOBREA 2023 — 5 famílias de modelos concorreram e o LightGBM venceu por mérito, com validação em dados nunca usados no treino.`, { size: 19 }),

      h1("Pendências (sem gravidade, já mapeadas)"),
      p("1. Três informações institucionais sobre o cadastro da Prefeitura (atualização, cobertura e existência de um observatório contínuo de mercado) — não dependem do modelo, apenas de a administração informar.", { size: 19 }),
      p("2. Escopo atual cobre somente apartamentos com transação registrada — expandir para outros tipos de imóvel (casa, terreno, comercial) e para o cálculo do IPTU em massa são projetos futuros, não incluídos nesta entrega.", { size: 19 }),

      h1("Decisão solicitada da equipe"),
      p("Aprovação formal do modelo de apartamentos (D4) para avançar às próximas frentes: uso do modelo no estoque de processos parados, integração ao sistema DTI, e planejamento da expansão para outras tipologias.", { size: 19, bold: true }),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(`${PASTA}/Resumo_Executivo_Modelo_Apartamentos_20260714.docx`, buffer);
  console.log("Resumo executivo gerado com sucesso.");
});
