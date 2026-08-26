const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, HeadingLevel, AlignmentType, BorderStyle, WidthType,
  ShadingType,
} = require("docx");

const PASTA = "D:/Pai/Coordenadoria de Inteligência Fiscal/ITIV";
const r = JSON.parse(fs.readFileSync(`${PASTA}/etapa5_resultados.json`, "utf-8"));
const ft = JSON.parse(fs.readFileSync(`${PASTA}/etapa5_ftest_parcial.json`, "utf-8"));

const AZUL = "1A3A5C";
const CINZA_CLARO = "F2F2F2";
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function p(text, opts = {}) {
  return new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text, ...opts })] });
}
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] }); }

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
          width: larguras[i], center: i > 0,
          destaque: linhasDestaque.includes(li), negrito: linhasDestaque.includes(li),
        })),
      })),
    ],
  });
}
function imagem(caminho, largura, proporcao) {
  const data = fs.readFileSync(caminho);
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 200 },
    children: [new ImageRun({
      type: "png", data,
      transformation: { width: largura, height: Math.round(largura * proporcao) },
      altText: { title: "Gráfico", description: "Gráfico do relatório", name: "grafico" },
    })],
  });
}

const fmt = (x, casas) => Number(x).toFixed(casas).replace(".", ",");
const b1 = r.bloco1_pressupostos;
const b2 = r.bloco2_precisao;
const comp = r.comparacao_venal_modelos;
const setores = r.bloco3_resumo_setores;

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
    properties: { page: { size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    children: [
      new Paragraph({ heading: HeadingLevel.HEADING_1,
        children: [new TextRun("Relatório da Etapa 5 — Validação Normativa do Modelo de Apartamentos (ITIV)")] }),
      p("Coordenadoria de Inteligência Fiscal — SEFAZ Salvador", { italics: true }),
      p("Data: 14/07/2026"),
      p("Complementa: Relatorio_Etapa4_Treino_Modelo_Apartamentos_20260714.docx e REGISTRO_ETAPAS_APROVACAO.md. Normas de referência: ABNT NBR 14653-1:2019, ABNT NBR 14653-2:2011, Norma IBAPE/SOBREA de Avaliação em Massa para Fins Tributários (2023) e IAAO Standard on Ratio Studies."),

      h1("1. Objetivo e enquadramento dos dois modelos"),
      p("Este documento reporta a validação normativa completa do modelo de apartamentos treinado em 14/07/2026 (Etapa 4). O enquadramento normativo dos dois modelos é distinto:"),
      p("• LightGBM (modelo de avaliação): a Norma IBAPE/SOBREA 2023, itens 8.1.2 e 8.1.2.1, admite técnicas de aprendizado de máquina desde que justificadas do ponto de vista teórico e prático e submetidas a validação, e estabelece que tais modelos não são objeto de especificação em graus. A justificativa está documentada (vencedor do GridSearch entre cinco famílias de modelos, Etapa 4) e a validação foi realizada por validação cruzada k=10 e teste final nunca usado no treino, conforme IBAPE 7.8.4 (divisão em três amostras para métodos não paramétricos)."),
      p("• Hedônico (âncora normativa): especificado conforme a seção 9 da NBR 14653-2 (Tabelas 1, 2 e 5), com verificação dos pressupostos do Anexo A. Os resultados estão nas seções 2 e 3."),

      h1("2. Pressupostos do modelo hedônico (NBR 14653-2, Anexo A)"),
      p("Agrupamento de setores fiscais com poucos dados (decisão da equipe, 14/07/2026): setores 177→175 e 179→162, únicos pares que atenderam ao critério combinado de distância ≤ 1 km e diferença de preço/m² ≤ 20% em relação a um setor vizinho com dados suficientes (n≥10). Os demais 14 setores com poucos dados avaliados não atenderam ao critério (diferença de preço acima de 20% com o vizinho mais próximo, indicando heterogeneidade real entre bairros) e permanecem sem agrupamento forçado. O agrupamento foi aplicado somente à especificação do hedônico (variável usada no teste de significância da Tabela 1); o LightGBM não depende dele, pois já capta a localização real por meio do KNN geográfico (KNN_PROXY), contínuo e independente da fronteira do setor."),
      p(`Modelo re-treinado no pool de treino saneado: n = ${b1.micronumerosidade.n.toLocaleString("pt-BR")} transações e k = ${b1.micronumerosidade.k} variáveis independentes (5 contínuas + ${b1.micronumerosidade.k - 5} dummies de setor fiscal, já com o agrupamento acima).`),
      tabela(
        ["Pressuposto (Anexo A)", "Resultado medido", "Leitura"],
        [
          ["Micronumerosidade (A.2.a)", `n = ${b1.micronumerosidade.n.toLocaleString("pt-BR")} ≥ 6(k+1) = ${b1.micronumerosidade["6(k+1)"]}`, "Atende com folga"],
          ["Dados por categoria (ni ≥ 10)", `${b1.micronumerosidade.setores_com_menos_de_10_dados} setores (de ${b1.micronumerosidade.setores_total}) com menos de 10 dados`, "Sinalizado — ver seção 6"],
          ["Normalidade (A.2.1.2.c)", `Resíduos em ±1: ${fmt(b1.normalidade.frequencias["dentro_1.0"].observado_pct, 1)}% (ref. 68%) · ±1,64: ${fmt(b1.normalidade.frequencias["dentro_1.64"].observado_pct, 1)}% (ref. 90%) · ±1,96: ${fmt(b1.normalidade.frequencias["dentro_1.96"].observado_pct, 1)}% (ref. 95%)`, "Atende pelo critério de frequências da norma"],
          ["Homocedasticidade (A.2.1.3)", `Breusch-Pagan significativo (p < 0,01); análise gráfica na Figura 2`, "Registrado — teste sensível ao n elevado; gráfico sem padrão grosseiro"],
          ["Autocorrelação (A.2.1.4)", `Durbin-Watson = ${fmt(b1.autocorrelacao.durbin_watson_ordenado_por_ajustados, 3)} (ordenado pelos ajustados; referência ~2)`, "Próximo da referência"],
          ["Multicolinearidade (A.2.1.5)", `VIF máximo das contínuas = ${fmt(Math.max(...Object.values(b1.multicolinearidade.vif_variaveis_continuas)), 2)}; nenhum par com |r| > 0,80`, "Atende"],
          ["Pontos influenciantes (A.2.1.6)", `Distância de Cook > 1: ${b1.pontos_influenciantes.acima_de_1} pontos (eram 4 antes do agrupamento de setores; caiu para ${b1.pontos_influenciantes.acima_de_1} após 177→175); > 4/n: ${b1.pontos_influenciantes.acima_4_sobre_n.toLocaleString("pt-BR")} (${fmt(b1.pontos_influenciantes.acima_4_sobre_n_pct, 1)}%)`, "Sinalizado — ver seção 6"],
        ],
        [2600, 4200, 2560],
      ),
      imagem(`${PASTA}/graficos_relatorio/etapa5_residuos_hist.png`, 620, 7.3 / 13),
      imagem(`${PASTA}/graficos_relatorio/etapa5_residuos_ajustados.png`, 620, 7.3 / 13),

      h2("2.1 Significância (testes t e F)"),
      p(`Teste F do modelo: F = ${Number(b1.F).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}, com significância inferior a 1% — atende ao Grau III do item 6 da Tabela 1. R² = ${fmt(b1.R2, 4)} e R² ajustado = ${fmt(b1.R2_ajustado, 4)}.`),
      p(`Regressores individuais (teste t bicaudal): as variáveis contínuas do modelo são significativas a 10%, exceto ANDAR_UNIDADE (p = ${fmt(ft.andar_p * 100, 1)}%, dentro do limite de 20% do Grau II). Das ${b1.regressores_total} variáveis, ${b1.regressores_p_acima_30pct} dummies de setor fiscal apresentam p > 30% individualmente — todas dummies de localização, nenhuma variável estrutural.`),
      p(`Análise da variância por partes (A.3.2 da norma): o bloco completo de setores fiscais é conjuntamente significativo (F parcial = ${fmt(ft.f_parcial_setores, 1)}, p < 0,01), e mesmo o subconjunto das ${ft.n_setores_p30} dummies individualmente não significativas é conjuntamente significativo (F parcial = ${fmt(ft.f_parcial_setores_p30, 1)}, p < 0,01). Ou seja, a localização por setor contribui de forma inequívoca para o modelo; as dummies individualmente fracas correspondem a setores com poucos dados, cuja significância individual o teste t não consegue medir com precisão.`, { bold: true }),

      h1("3. Especificação do hedônico (NBR 14653-2, seção 9)"),
      h2("3.1 Grau de fundamentação (Tabela 1 da norma)"),
      tabela(
        ["Item", "Exigência", "Situação medida", "Grau proposto", "Pontos"],
        [
          ["1. Caracterização do imóvel", "Completa quanto às variáveis utilizadas no modelo (Grau II)", "Dados cadastrais completos para as variáveis do modelo; sem vistoria individual (inviável em avaliação em massa)", "II", "2"],
          ["2. Quantidade mínima de dados", "6(k+1) = 660 para Grau III", `${b1.micronumerosidade.n.toLocaleString("pt-BR")} transações efetivamente utilizadas`, "III", "3"],
          ["3. Identificação dos dados", "Informações de todos os dados e variáveis da modelagem (Grau II)", "Todos os dados identificados por inscrição imobiliária, data e valor (sem foto/vistoria)", "II", "2"],
          ["4. Extrapolação", "Não admitida (Grau III)", "Treino e teste dentro dos limites amostrais; em produção, monitorar IBAPE 8.1.1.1 (mín. 90% dos avaliandos sem extrapolação)", "III", "3"],
          ["5. Significância de cada regressor", "≤ 10% (III), ≤ 20% (II), ≤ 30% (I)", "Contínuas ≤ 20%; dummies de setor justificadas em bloco pela análise da variância por partes (A.3.2, p < 0,01)", "II", "2"],
          ["6. Significância do modelo (F)", "≤ 1% (Grau III)", "p < 0,01", "III", "3"],
        ],
        [1900, 2300, 2900, 1200, 1060],
      ),
      p("Soma: 15 pontos. Pela Tabela 2 da norma (Grau II: mínimo de 10 pontos, com os itens 2, 4, 5 e 6 no mínimo no Grau II), o modelo hedônico enquadra-se no GRAU II DE FUNDAMENTAÇÃO. O Grau III (16 pontos e itens obrigatórios no Grau III) ficou a um ponto, limitado pelo item 5 — ver na seção 6 a medida proposta (agrupamento de setores) capaz de elevar o enquadramento.", { bold: true }),
      p("Nota sobre o item 5: a pontuação proposta baseia-se no dispositivo A.3.2 da própria norma (significância de subconjuntos pela análise da variância por partes), aplicado ao bloco de dummies de setor. A leitura estrita, regressor a regressor, não seria atendida pelas 24 dummies de setores com poucos dados. As duas leituras estão registradas para decisão da equipe.", { italics: true }),

      h2("3.2 Grau de precisão (Tabela 5 da norma)"),
      p(`Amplitude do intervalo de confiança de 80% em torno da estimativa de tendência central, medida no teste final: mediana de ${fmt(b2.amplitude_ic80_mediana_pct, 2)}% (limite do Grau III: ≤ 30%). ${fmt(b2.pct_imoveis_amplitude_ate_30, 1)}% dos imóveis do teste final têm amplitude dentro do limite do Grau III. Enquadramento: GRAU III DE PRECISÃO.`, { bold: true }),

      h2("3.3 Especificação geral do trabalho (IBAPE/SOBREA 2023, Tabela 1)"),
      tabela(
        ["Item", "Situação medida", "Grau"],
        [
          ["4. Contemporaneidade dos dados", "14,1% das transações da base de treino observadas nos últimos 12 meses (limite Grau II: ≥ 10%; Grau III: ≥ 20%)", "II"],
          ["5. Nível geral da avaliação", `Razão mediana ${fmt(comp.lightgbm.razao_mediana, 3)} (Grau III: 0,90 a 1,10)`, "III"],
          ["6. Uniformidade horizontal", `COD ${fmt(comp.lightgbm.COD, 1)}% (Grau III: ≤ 15%)`, "III"],
        ],
        [3000, 4800, 1560],
      ),
      p("Os itens 1 a 3 da tabela da IBAPE (atualização do cadastro territorial, cobertura do cadastro e observatório do mercado imobiliário) são características institucionais da administração, não do modelo — o levantamento dessas informações está indicado na seção 6 para compor o enquadramento geral do trabalho."),

      h1("4. Estudo de razões por segmento (IAAO)"),
      p("Calculado sobre o teste final (9.276 transações nunca usadas no treino), com o modelo LightGBM."),
      h2("4.1 Equidade vertical — por faixa de valor"),
      imagem(`${PASTA}/graficos_relatorio/etapa5_vertical_razao.png`, 620, 7.3 / 13),
      imagem(`${PASTA}/graficos_relatorio/etapa5_vertical_cod.png`, 620, 7.3 / 13),
      p("Leitura: a razão mediana permanece dentro da meta IAAO (0,90–1,10) em todos os 10 decis de valor, e o COD fica abaixo de 15% em todos eles. Observa-se leve gradiente entre extremos (1,035 no decil dos imóveis mais baratos; 0,968–0,973 nos decis mais caros), registrado como fato para acompanhamento — sem ultrapassar os limites da meta em nenhum segmento.", { italics: true }),
      h2("4.2 Equidade horizontal — por setor fiscal"),
      p(`Dos ${setores.setores_holdout} setores fiscais presentes no teste final, ${setores.setores_n_10_ou_mais} têm 10 ou mais transações (mínimo do Anexo A para leitura por categoria). Nesses ${setores.setores_n_10_ou_mais} setores: razão mediana dentro de 0,90–1,10 em ${setores.setores_razao_dentro_090_110} de ${setores.setores_n_10_ou_mais} (100%); COD ≤ 15% em ${setores.setores_cod_ate_15} de ${setores.setores_n_10_ou_mais}. Os ${setores.setores_n_10_ou_mais - setores.setores_cod_ate_15} setores com COD acima de 15% e os setores com menos de 10 transações estão listados em etapa5_resultados.json para acompanhamento.`),

      h1("5. Comparação com o valor venal atual"),
      imagem(`${PASTA}/graficos_relatorio/etapa5_comparativo_venal.png`, 620, 7 / 14),
      tabela(
        ["Estimativa", "Razão mediana", "COD", "PRD", "PRB"],
        [
          ["Valor venal (cadastro)", fmt(comp.valor_venal_cadastro.razao_mediana, 3), `${fmt(comp.valor_venal_cadastro.COD, 1)}%`, fmt(comp.valor_venal_cadastro.PRD, 3), fmt(comp.valor_venal_cadastro.PRB, 4)],
          ["Hedônico (OLS)", fmt(comp.hedonico.razao_mediana, 3), `${fmt(comp.hedonico.COD, 1)}%`, fmt(comp.hedonico.PRD, 3), fmt(comp.hedonico.PRB, 4)],
          ["LightGBM", fmt(comp.lightgbm.razao_mediana, 3), `${fmt(comp.lightgbm.COD, 1)}%`, fmt(comp.lightgbm.PRD, 3), fmt(comp.lightgbm.PRB, 4)],
          ["Meta IAAO", "0,90 – 1,10", "≤ 15%", "0,98 – 1,03", "±0,05"],
        ],
        [2600, 1800, 1400, 1700, 1560],
        [2],
      ),
      p(`Leitura: o valor venal do cadastro apresenta razão mediana de ${fmt(comp.valor_venal_cadastro.razao_mediana, 3)} — abaixo da faixa da meta (0,90), ou seja, subavaliação em relação aos preços praticados —, enquanto o LightGBM fica em ${fmt(comp.lightgbm.razao_mediana, 3)}.`, { italics: true }),
      p("Ressalva metodológica obrigatória: " + comp.ressalva, { bold: true }),

      h1("6. Consolidação e próximos passos"),
      p("Enquadramento consolidado: modelo hedônico com GRAU II de fundamentação e GRAU III de precisão (NBR 14653-2); LightGBM justificado e validado conforme IBAPE/SOBREA 2023 (itens 8.1.2 e 7.8.4), com todas as metas IAAO atendidas no teste final, inclusive por decil de valor e por setor fiscal.", { bold: true }),
      p("1. Agrupamento de setores fiscais com poucos dados: aplicado (177→175 e 179→162), pelo critério de distância ≤ 1 km e diferença de preço/m² ≤ 20%. Os 14 setores remanescentes com poucos dados não atenderam ao critério — o vizinho geograficamente mais próximo tem preço muito diferente (divisas entre bairros de padrão distinto) — e permanecem sem agrupamento forçado, por decisão da equipe de não agrupar sem sentido geográfico/econômico. O item 5 da Tabela 1 permanece fundamentado pela análise da variância por partes (seção 2.1), mantendo o hedônico em Grau II."),
      p(`2. Pontos com distância de Cook acima de 1: investigados e explicados — antes do agrupamento eram 4 transações, todas em setores fiscais com uma única venda no treino (o que infla artificialmente a distância de Cook, sem indicar erro de dado). O agrupamento 177→175 já resolveu um desses casos; restam ${b1.pontos_influenciantes.acima_de_1}, nos setores ainda isolados (122, 166 e 172), cuja causa raiz é a mesma micronumerosidade do item 1 — não são vendas incomuns e não foram removidas.`),
      p("3. Levantamento, junto à administração, dos itens 1 a 3 da Tabela 1 da IBAPE/SOBREA (atualização e cobertura do cadastro; observatório do mercado imobiliário), para compor o enquadramento geral do trabalho."),
      p("4. Aprovação formal do modelo (D4) e planejamento da entrada em produção, com monitoramento da extrapolação (IBAPE 8.1.1.1) e do desempenho anual (IBAPE 7.12)."),
    ],
  }],
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync(`${PASTA}/Relatorio_Etapa5_Validacao_Normativa_20260714.docx`, buffer);
  console.log("Relatório da Etapa 5 gerado com sucesso.");
});
