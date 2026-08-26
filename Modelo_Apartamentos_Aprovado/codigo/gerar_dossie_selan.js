const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  ImageRun, HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat,
} = require("docx");

const PASTA = "D:/Pai/Coordenadoria de Inteligência Fiscal/ITIV";
const AZUL = "1A3A5C";
const CINZA_CLARO = "F2F2F2";
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

function p(text, opts = {}) {
  return new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text, ...opts })] });
}
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] }); }
function h3(text) { return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] }); }

function bullet(text, opts = {}) {
  return new Paragraph({
    numbering: { reference: "lista-padrao", level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text, ...opts })],
  });
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
        color: opts.header ? "FFFFFF" : undefined, size: 19,
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

const doc = new Document({
  numbering: {
    config: [{
      reference: "lista-padrao",
      levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 400, hanging: 260 } } } }],
    }],
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 30, bold: true, font: "Arial", color: AZUL },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: AZUL },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, italics: true, font: "Arial", color: AZUL },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
      margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    children: [
      // ======================================================================
      // CAPA
      // ======================================================================
      new Paragraph({ heading: HeadingLevel.HEADING_1,
        children: [new TextRun("Dossiê de Validação — Modelo de Avaliação de Apartamentos (ITIV)")] }),
      p("Coordenadoria de Inteligência Fiscal — SEFAZ Salvador", { italics: true }),
      p("Documento preparado para avaliação e validação da equipe SELAN. Data: 17/07/2026."),
      p("Complementa: Relatorio_Etapa4_Treino_Modelo_Apartamentos_20260714.docx, Relatório da Etapa 5 — Validação Normativa, Informações ITIV 20260610 - Status Apartamentos.xlsx e ITIV_Base_Consolidada_2025_2026 - Status Apartamentos.xlsx."),
      p("Sumário: (1) Referencial teórico e normativo; (2) Diagnóstico declarado vs. valor venal; (3) Universo das impugnações de valor venal; (4) Indicadores de validação do modelo em produção; (5) Conclusão e recomendações.", { italics: true }),

      // ======================================================================
      // 1. REFERENCIAL TEORICO
      // ======================================================================
      h1("1. Referencial Teórico e Normativo"),
      p("Este capítulo reúne a fundamentação teórica e normativa que sustenta cada escolha técnica do projeto: as normas de avaliação em massa (IAAO), as normas brasileiras de avaliação de imóveis (ABNT NBR 14653), o guia normativo nacional para avaliação em massa para fins tributários (IBAPE/SOBREA) e os algoritmos estatísticos e de aprendizado de máquina utilizados (regressão hedônica e LightGBM)."),

      h2("1.1 Normas de avaliação em massa (IAAO)"),
      p("A International Association of Assessing Officers (IAAO) é a entidade internacional de referência em avaliação em massa de imóveis para fins tributários (mass appraisal). Duas publicações da IAAO fundamentam este projeto:"),

      h3("IAAO Standard on Ratio Studies (2013, atualizações posteriores)"),
      p("Define os \"estudos de razão\" (ratio studies): comparações sistemáticas entre o valor estimado pela administração (avaliação) e o valor de mercado observado (preço de transação), usadas para medir o desempenho de um sistema de avaliação em massa. Os quatro indicadores centrais desta norma, usados em todo o projeto, são:"),
      bullet("Razão mediana (Median Ratio) — mediana de (valor avaliado / valor de mercado). Mede o nível geral da avaliação: 1,00 significa que a administração acompanha o mercado no imóvel típico. A norma recomenda a faixa de 0,90 a 1,10 para aprovação geral."),
      bullet("COD — Coefficient of Dispersion (Coeficiente de Dispersão). Mede a uniformidade horizontal: o quanto a razão varia de imóvel para imóvel em torno da mediana, independentemente da direção do erro. Fórmula: média dos desvios absolutos em relação à mediana, dividida pela própria mediana, em percentual. A norma recomenda COD ≤ 15% para imóveis residenciais em áreas homogêneas — limite adotado no projeto como meta de precisão do modelo."),
      bullet("PRD — Price-Related Differential. Mede a equidade vertical: se o sistema trata melhor imóveis baratos do que caros, ou o inverso (regressividade/progressividade). Calculado como a média aritmética das razões dividida pela razão ponderada pelo valor. A faixa recomendada é 0,98 a 1,03; valores acima de 1,03 indicam regressividade (imóveis caros subavaliados em relação aos baratos)."),
      bullet("PRB — Price-Related Bias, refinamento estatístico do PRD introduzido em revisões mais recentes da norma, menos sensível a valores extremos isolados: mede o mesmo viés por meio de uma regressão do log da razão contra o log do valor. Faixa recomendada: -0,05 a +0,05. Adotado no projeto como indicador mais robusto de viés por faixa de valor, complementando o PRD."),

      h3("IAAO Standard on Mass Appraisal of Real Property (2017)"),
      p("Estabelece os fundamentos metodológicos da avaliação em massa: uso de modelos estatísticos calibrados sobre amostras de transações reais, separação entre amostra de treino e amostra de teste/validação (nunca usada na calibração), e a premissa central de que a avaliação em massa não busca acertar cada imóvel individualmente, mas produzir estimativas consistentes e equitativas para a população de imóveis — sendo o erro individual aceitável quando medido e reportado (o que os intervalos de confiança do modelo fazem). Esta norma fundamenta a divisão treino/teste usada nas Etapas 4 e 5 do projeto e a prática de reportar intervalo de confiança (IC 80%) junto com a estimativa pontual."),

      h2("1.2 Normas brasileiras de avaliação (ABNT NBR 14653)"),
      h3("NBR 14653-1:2019 — Avaliação de bens, Parte 1: Procedimentos gerais"),
      p("Estabelece os conceitos e procedimentos gerais aplicáveis a qualquer avaliação de bens no Brasil: definição de valor de mercado, identificação da finalidade da avaliação, e os princípios gerais de fundamentação (adequação dos dados, tratamento estatístico, identificação da amostra). É a norma-base sobre a qual a NBR 14653-2 (específica para imóveis urbanos) se apoia."),
      h3("NBR 14653-2:2011 — Avaliação de bens, Parte 2: Imóveis urbanos"),
      p("Norma central para a especificação do modelo hedônico do projeto. Define:"),
      bullet("Método comparativo direto de dados de mercado com tratamento por inferência estatística (regressão), exigindo amostra representativa de transações reais."),
      bullet("Graus de fundamentação (Tabela 1) e de precisão (Tabela 5): classificam o rigor metodológico do trabalho (Grau I a III) segundo critérios como caracterização dos dados, quantidade mínima de dados (regra 6(k+1), onde k é o número de variáveis independentes), significância estatística dos regressores (teste t) e do modelo (teste F), e amplitude do intervalo de confiança."),
      bullet("Anexo A — pressupostos do modelo de regressão linear: micronumerosidade, normalidade dos resíduos, homocedasticidade, ausência de autocorrelação, ausência de multicolinearidade (VIF) e ausência de pontos excessivamente influentes (distância de Cook). Todos verificados e reportados na Etapa 5 do projeto para o modelo hedônico."),
      p("O modelo hedônico deste projeto foi enquadrado, com base nesses critérios, no Grau II de fundamentação e Grau III de precisão (ver Relatório da Etapa 5, seções 2 e 3)."),

      h2("1.3 Norma nacional de avaliação em massa para fins tributários (IBAPE/SOBREA, 2023)"),
      p("O Instituto Brasileiro de Avaliações e Perícias de Engenharia (IBAPE), em conjunto com a Sociedade Brasileira de Avaliações (SOBREA), publicou em 2023 a norma técnica específica para avaliação em massa aplicada a fins tributários no Brasil — preenchendo uma lacuna que a NBR 14653-2 (voltada a avaliações individuais) não cobria integralmente. Pontos centrais para este projeto:"),
      bullet("Item 8.1.2 e 8.1.2.1: admitem expressamente o uso de técnicas de aprendizado de máquina (machine learning) na avaliação em massa, desde que a escolha do modelo seja justificada do ponto de vista teórico e prático e submetida a validação — e estabelece que tais modelos não são objeto de classificação em graus (ao contrário do modelo hedônico regido pela NBR 14653-2). É o dispositivo que autoriza normativamente o uso do LightGBM."),
      bullet("Item 7.8.4: para métodos não paramétricos (como o aprendizado de máquina), recomenda a divisão da base em três amostras — treino, validação e teste final nunca utilizado na calibração —, adotada neste projeto (validação cruzada k=10 mais teste final holdout, Etapa 4)."),
      bullet("Tabela 1 (itens de especificação do trabalho): contempla, além dos indicadores IAAO (nível geral, uniformidade), itens institucionais como contemporaneidade dos dados, cobertura do cadastro territorial e existência de observatório do mercado imobiliário — usados na Etapa 5 para o enquadramento geral do trabalho."),

      h2("1.4 Algoritmos utilizados"),
      h3("Regressão hedônica (mínimos quadrados ordinários — OLS)"),
      p("Modelo estatístico clássico que estima o valor do imóvel como uma combinação linear de suas características (área, andar, pavimentos, localização por setor fiscal, tendência temporal), calibrada por mínimos quadrados ordinários. É o método exigido pela NBR 14653-2 para o \"método comparativo direto de dados de mercado com tratamento científico\", com a vantagem de ser inteiramente interpretável: cada coeficiente tem significado direto e é auditável pelos testes estatísticos do Anexo A da norma. Neste projeto, funciona como a âncora normativa do modelo — o \"modelo de referência\" exigido pelas normas brasileiras, cujos pressupostos são integralmente verificáveis."),
      h3("LightGBM (Gradient Boosting de árvores de decisão)"),
      p("LightGBM (Light Gradient Boosting Machine) é um algoritmo de aprendizado de máquina da família gradient boosting: constrói sequencialmente centenas de árvores de decisão simples, em que cada árvore nova corrige os erros residuais das anteriores, combinando-as num modelo final mais preciso. Diferentemente da regressão hedônica, não presume relação linear entre as variáveis e o valor do imóvel — captura automaticamente interações e não linearidades (por exemplo, o efeito do andar pode variar conforme o setor fiscal, sem que essa interação precise ser especificada manualmente)."),
      p("Sua escolha, entre cinco famílias de modelos testadas em GridSearch (Etapa 4), respalda-se em maior capacidade de capturar relações complexas entre localização, área e demais características, e em desempenho superior nos indicadores IAAO (razão mediana e COD) medidos no teste final. É respaldada pelo item 8.1.2 da norma IBAPE/SOBREA 2023, com a validação normativa documentada na Etapa 4 (GridSearch e validação cruzada k=10) e na Etapa 5 (teste final holdout e estudo de razões IAAO)."),
      p("Uma característica do LightGBM explorada neste projeto é a explicabilidade via valores SHAP (SHapley Additive exPlanations): técnica baseada na teoria dos jogos cooperativos que decompõe cada estimativa individual do modelo na contribuição de cada variável de entrada — permitindo gerar, para cada imóvel avaliado, uma \"memória de cálculo\" auditável (percentual de contribuição de área, localização, andar etc.), tal como aparece no avaliador web e nas planilhas de lote."),

      h2("1.5 Como as peças se encaixam"),
      p("O desenho normativo do projeto usa cada norma no papel para o qual foi concebida: a IAAO fornece os indicadores universais de desempenho de um sistema de avaliação em massa (razão mediana, COD, PRD/PRB), aplicados a qualquer modelo. A NBR 14653-2 rege especificamente o modelo hedônico (regressão linear), com seus graus de fundamentação e precisão e a verificação formal dos pressupostos do Anexo A. A norma IBAPE/SOBREA 2023 preenche a lacuna que a NBR 14653-2 deixa em aberto para modelos de aprendizado de máquina, autorizando o uso do LightGBM desde que justificado e validado — e é sob essa norma, com os indicadores IAAO como métrica de desempenho, que o LightGBM é avaliado. Os capítulos seguintes deste dossiê aplicam esse mesmo referencial — tolerância de ±15% ancorada na meta de COD do IAAO/IBAPE — para diagnosticar a base de dados e validar o modelo em produção."),

      // ======================================================================
      // 2. DIAGNOSTICO DECLARADO x VENAL
      // ======================================================================
      h1("2. Diagnóstico: Valor Declarado vs. Valor Venal"),
      p("Este capítulo documenta a análise da razão entre o valor declarado nas transações de apartamentos e o valor venal corrigido (VVA), com o objetivo de qualificar a base de dados usada no treino do modelo e identificar transações incompatíveis (prováveis erros de dado) que devem ser excluídas de qualquer estudo de razões."),

      h2("2.1 Distribuição da razão declarado/venal"),
      p("Sobre 107.643 transações de apartamentos com valor declarado e venal corrigido positivos: a mediana da razão é 97,3% (metade das transações entre 74% e 120% do venal) — ou seja, o comportamento típico é declarar próximo do valor venal, embora apenas 1,7% declarem exatamente esse valor (o que indica que a proximidade reflete calibração de mercado, não cópia mecânica)."),
      imagem(`${PASTA}/graficos_relatorio/compat_hist_razao.png`, 620, 7.3 / 13),
      p("O histograma (escala logarítmica) evidencia dois grupos de valores incompatíveis, claramente segregados do corpo central da distribuição:"),
      bullet("Para baixo: declarações de até R$ 1,00 (3.915 transações, 3,5% da base) — concentradas em tipos de transação onde o campo \"valor\" tem outro significado operacional (Guia Complementar, Enfiteuse) ou cuja guia é tributada integralmente pelo venal independentemente do valor declarado."),
      bullet("Para cima: declarações acima de 10x o valor venal (52 transações, 0,05% da base, somando R$ 20,3 bilhões declarados) — padrão compatível com erro de digitação (salto direto de valores plausíveis para múltiplos de 100x ou mais, sem gradação intermediária); 50 das 52 permanecem com a transmissão \"Em aberto\"."),

      h2("2.2 Efeito sobre os indicadores"),
      p("A tabela a seguir mostra o quanto a presença desses valores incompatíveis distorce indicadores baseados em média — e a interpretabilidade que se recupera ao excluí-los:"),
      tabela(
        ["Recorte", "n", "Média (%)", "Mediana (%)", "COD", "PRD"],
        [
          ["Base completa", "107.643", "139,1", "97,3", "1.119.145", "15.286,6"],
          ["Sem absurdos (>10x ou <10% do venal)", "106.500", "100,1", "97,7", "41,8", "1,130"],
        ],
        [3400, 1400, 1600, 1600, 1600, 1400],
        [1],
      ),
      p("Referências IAAO: COD ≤ 15 (residencial); PRD 0,98–1,03.", { italics: true, size: 18 }),
      imagem(`${PASTA}/graficos_relatorio/compat_media_ano.png`, 620, 7.3 / 13),
      p("A série anual confirma que, sem os absurdos, a média acompanha a mediana de forma estável em todos os anos (2021–2026), enquanto a média da base completa oscila sem padrão discernível — sinal de que a oscilação é ruído desses poucos casos extremos, não uma tendência real de mercado."),

      h2("2.3 Critério proposto de exclusão"),
      p("Com base nesta análise, o projeto adota o seguinte critério para sinalizar transações com valor \"suspeito\" (fora de padrão, provável erro de dado) nas planilhas de status do modelo (Capítulo 4): razão entre a estimativa do modelo e o valor da transação atualizado fora do intervalo de 0,5 a 2,0 (diferença superior a 100%) — limite ancorado na pior amplitude de erro já observada na validação oficial do modelo (Etapa 5: amplitude do IC 80% de 53,9%). Diferenças além desse patamar não se explicam pela incerteza normal do modelo, apenas por erro de dado.", { bold: true }),

      // ======================================================================
      // 3. UNIVERSO DAS IMPUGNACOES
      // ======================================================================
      h1("3. Universo das Impugnações de Valor Venal"),
      p("Levantamento do universo de transações com resultado de impugnação administrativa do VVA (Valor Venal de Referência) registrado na base ITIV, motivado pelo gargalo relatado pela equipe: ações judiciais movidas por contribuintes contra o valor venal têm resultado em perdas de arrecadação para a Prefeitura."),

      h2("3.1 Dimensão do universo"),
      tabela(
        ["Característica", "Resultado"],
        [
          ["Total de transmissões com \"Resultado Impugnação VVA\"", "3.529"],
          ["Por tipologia", "Apartamento 1.894 (54%) · Sala 978 (28%) · Casa 345 · Terreno 106 · Loja 103"],
          ["Evolução anual", "95 (2021) → 142 → 386 → 842 → 1.532 (2025) → 532 (2026, parcial)"],
          ["Situação da transmissão", "Baixado 2.818 · Cancelado 368 · Em aberto 341"],
        ],
        [4200, 5000],
      ),
      p("As Salas comerciais estão fortemente sobrerrepresentadas (28% das impugnações), e o volume de impugnações multiplicou por 16 entre 2021 e 2025."),

      h2("3.2 Indicadores do universo impugnado (venal corrigido vs. declarado)"),
      tabela(
        ["Grupo", "n", "Mediana venal/declarado", "COD", "PRD", "Declarado típico"],
        [
          ["Todas as impugnações", "3.529", "1,86", "185,4", "2,091", "54% do venal"],
          ["— Apartamento", "1.894", "1,69", "32,5", "1,136", "59% do venal"],
          ["— Sala", "978", "2,13", "30,7", "1,140", "47% do venal"],
          ["— Casa", "345", "2,17", "680,7", "7,553", "46% do venal"],
          ["— Terreno", "106", "4,01", "1.020,1", "12,839", "25% do venal"],
          ["— Loja", "103", "2,30", "156,4", "1,713", "43% do venal"],
        ],
        [2600, 1000, 2000, 1200, 1200, 1800],
      ),
      p("Comparação com transações de \"Compra e Venda\" comuns (sem impugnação) — mediana venal/declarado por tipologia:"),
      tabela(
        ["Tipologia", "Mediana venal/declarado", "Declarado típico"],
        [
          ["Apartamento", "1,01", "99% do venal"],
          ["Casa", "1,25", "80% do venal"],
          ["Loja", "1,31", "76% do venal"],
          ["Terreno", "1,58", "63% do venal"],
          ["Sala", "1,79", "56% do venal"],
        ],
        [3000, 3000, 3600],
      ),
      p("O padrão é consistente: onde o venal descola do mercado — mais acentuadamente em Salas — a impugnação floresce. Nos Apartamentos, única tipologia com modelo aprovado, o venal já é calibrado com o mercado na mediana (1,01), o que evidencia que o problema de descalibração está concentrado nas tipologias ainda não cobertas pelo modelo."),

      h2("3.3 Desfecho administrativo"),
      p("O campo de valor venal arbitrado (resultado da decisão administrativa da impugnação) está preenchido em 100% dos casos, e revela um padrão determinante:"),
      bullet("Mediana, percentil 25 e percentil 75 do arbitrado como razão do declarado: 100,0% nos três — ou seja, o desfecho tipicamente iguala o arbitrado ao valor declarado pelo contribuinte."),
      bullet("Em valores agregados: soma do venal corrigido R$ 5,82 bilhões vs. soma do venal arbitrado R$ 2,67 bilhões — redução agregada de 54,0% da base de cálculo."),
      bullet("Em 99,3% dos casos, o venal corrigido superava o declarado antes da impugnação — a motivação típica da contestação."),
      p("Este é o argumento central para a defesa do modelo: a Justiça e a via administrativa tendem a acolher o valor do contribuinte porque o venal de avaliação em massa, mesmo calibrado na média, carece de precisão individual (COD de 25 a 42 nos apartamentos fora das impugnações). O modelo aprovado entrega exatamente essa precisão individual — com memória de cálculo (SHAP), intervalo de confiança e validação normativa —, sendo o instrumento técnico apropriado para sustentar o lançamento tanto no estoque atual de impugnações quanto nas futuras, via integração por API.", { bold: true }),

      // ======================================================================
      // 4. VALIDACAO EM PRODUCAO
      // ======================================================================
      h1("4. Indicadores de Validação do Modelo em Produção"),
      p("Aplicação do modelo LightGBM aprovado (Etapa 4/5) sobre a totalidade das transações de Apartamento disponíveis, comparando a estimativa do modelo com o valor da transação atualizado pelo IPCA (mesma fórmula do treino), com ajuste por fração transmitida e tolerância de ±15% (meta normativa de COD ≤ 15%, IAAO/IBAPE). Gerados dois conjuntos de planilhas de status, detalhados a seguir."),

      h2("4.1 Base completa (Informações ITIV 20260610 - Status Apartamentos.xlsx)"),
      p("114.341 transações de Apartamento (todas as tipologias da base bruta, filtradas para Apartamento):"),
      tabela(
        ["Status", "Quantidade", "%"],
        [
          ["Compatível (±15%)", "59.803", "52,3%"],
          ["Necessidade Avaliação por Auditor", "22.534", "19,7%"],
          ["Compatível (transação acima do modelo — sem risco)", "19.541", "17,1%"],
          ["Valor Suspeito (fora de padrão — provável erro de dado)", "8.439", "7,4%"],
          ["Fora de Escopo", "4.024", "3,5%"],
        ],
        [4600, 2400, 1600],
      ),

      h2("4.2 Planilha do SELAN (ITIV_Base_Consolidada_2025_2026 - Status Apartamentos.xlsx)"),
      p("Aplicação da mesma metodologia sobre a base consolidada fornecida pelo SELAN (Nosso_Número/VT/VVA, janeiro–maio de 2025 e 2026): 6.428 guias de Apartamento em 2025 e 5.472 em 2026, com ~20% classificadas como \"Necessidade Avaliação por Auditor\" em ambos os anos."),

      h2("4.3 Indicadores IAAO (Compra e Venda, excluídos os \"Suspeito\")"),
      tabela(
        ["Recorte", "n", "Razão mediana", "COD mediano", "PRD", "PRB"],
        [
          ["Base completa — Total", "94.931", "0,995", "10,9%", "1,022", "+0,022"],
          ["Planilha SELAN — 2025", "4.959", "1,004", "11,0%", "1,047", "-0,017"],
          ["Planilha SELAN — 2026", "4.524", "0,988", "12,0%", "1,054", "-0,022"],
          ["Planilha SELAN — Total", "9.483", "0,996", "11,4%", "1,051", "-0,020"],
          ["Meta IAAO/IBAPE", "—", "0,90–1,10", "≤15%", "0,98–1,03", "-0,05–0,05"],
        ],
        [3000, 1200, 1600, 1600, 1400, 1400],
        [4],
      ),
      p("Leitura: na mediana, o modelo acerta praticamente em cheio o valor real das transações (razão 0,995–0,996), e a dispersão (COD mediano 10,9%–12,0%) permanece dentro da meta normativa de 15% também em dados de produção — não apenas na amostra de teste da Etapa 5. O único indicador fora da faixa de referência é o PRD em 2025/2026 (1,047–1,054, limite 1,03), que isoladamente sugeriria leve regressividade; contudo o PRB — indicador mais robusto para a mesma finalidade — permanece confortavelmente dentro da meta (±0,022, limite ±0,05), o que relativiza essa leitura.", { italics: true }),

      // ======================================================================
      // 5. CONCLUSAO
      // ======================================================================
      h1("5. Conclusão e Recomendações"),
      bullet("O diagnóstico declarado × venal confirma que o venal de apartamentos é, na média, calibrado com o mercado (mediana 97–101%), mas carece de precisão individual (COD 25–42) — exatamente a lacuna que o modelo aprovado preenche."),
      bullet("O universo de 3.529 impugnações mostra que o desfecho administrativo tende a acolher o valor do contribuinte (arbitrado = declarado na mediana), com impacto de R$ 3,37 bilhões em base de cálculo — argumento central para adoção do modelo como instrumento de defesa técnica do lançamento."),
      bullet("Em produção, sobre toda a base disponível e sobre a planilha do SELAN, o modelo mantém razão mediana entre 0,988 e 1,004 e COD mediano entre 10,9% e 12,0% — dentro da meta normativa de 15% (IAAO/IBAPE/NBR 14653-2)."),
      bullet("Recomenda-se: (1) validação formal destes indicadores pela equipe SELAN; (2) adoção do critério de \"Valor Suspeito\" (razão fora de 0,5–2,0) como filtro de qualidade de dado, tanto na triagem retroativa quanto na futura integração via API; (3) avaliação de expansão do modelo para as tipologias com maior descalibração do venal (Sala, Terreno), priorizadas pelo volume de impugnações."),
    ],
  }],
});

const SAIDA = `${PASTA}/Modelo_Apartamentos_Aprovado/Dossie_Validacao_SELAN_Modelo_Apartamentos.docx`;
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(SAIDA, buf);
  console.log("Gerado:", SAIDA);
});
