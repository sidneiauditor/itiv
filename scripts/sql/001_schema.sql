-- Espelho documentado do schema criado pelo SQLAlchemy (itiv_web.models).
-- A aplicação usa Base.metadata.create_all; este arquivo é referência.

CREATE TABLE IF NOT EXISTS transmissao (
    sq              BIGINT PRIMARY KEY,
    cdinscricaoimob BIGINT,
    tipologia       VARCHAR(80),
    data_transacao  DATE,
    vltransacao     DOUBLE PRECISION,
    vlitiv          DOUBLE PRECISION,
    vlvenalcadastro DOUBLE PRECISION,
    vlvenalcorrigido DOUBLE PRECISION,
    vltransacao_deflacionado DOUBLE PRECISION,
    var_tendencia   DOUBLE PRECISION,
    vlareausopriv   DOUBLE PRECISION,
    nupavimentos    DOUBLE PRECISION,
    nupavimentounidade DOUBLE PRECISION,
    cdsetorfiscal   DOUBLE PRECISION,
    vlcoordgeox     DOUBLE PRECISION,
    vlcoordgeoy     DOUBLE PRECISION,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    vlfracaoterreno DOUBLE PRECISION,
    vlfracaoconstrucao DOUBLE PRECISION,
    dstipotransacao VARCHAR(120),
    dssituacaotransmissao VARCHAR(80)
);
CREATE INDEX IF NOT EXISTS ix_transmissao_inscricao ON transmissao (cdinscricaoimob);
CREATE INDEX IF NOT EXISTS ix_transmissao_tipologia ON transmissao (tipologia);
CREATE INDEX IF NOT EXISTS ix_transmissao_data ON transmissao (data_transacao);

CREATE TABLE IF NOT EXISTS cadastro (
    cdinscricaoimob BIGINT PRIMARY KEY,
    dssubunidade    VARCHAR(80),
    vlareausopriv   DOUBLE PRECISION,
    nupavimentounidade DOUBLE PRECISION,
    nupavimentos    DOUBLE PRECISION,
    cdsetorfiscal   DOUBLE PRECISION,
    vlcoordgeox     DOUBLE PRECISION,
    vlcoordgeoy     DOUBLE PRECISION,
    vlvenalcadastro DOUBLE PRECISION,
    vliptu          DOUBLE PRECISION,
    dslogradouro    VARCHAR(255),
    nuporta         VARCHAR(40),
    cdcep           VARCHAR(20),
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS nascimento_imovel (
    cdinscricaoimob BIGINT PRIMARY KEY,
    aaconstrucao    DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS pool_treino (
    sqtransmissao   BIGINT PRIMARY KEY,
    cdinscricaoimob BIGINT,
    data_transacao  DATE,
    vltransacao     DOUBLE PRECISION,
    vltransacao_deflacionado DOUBLE PRECISION,
    var_tendencia   DOUBLE PRECISION,
    log_area        DOUBLE PRECISION,
    nupavimentos    DOUBLE PRECISION,
    andar_unidade   DOUBLE PRECISION,
    flag_andar_ausente INTEGER,
    cdsetorfiscal   DOUBLE PRECISION,
    vlcoordgeox     DOUBLE PRECISION,
    vlcoordgeoy     DOUBLE PRECISION,
    vlvenalcadastro DOUBLE PRECISION,
    idade_na_transacao_imp DOUBLE PRECISION,
    flag_ano_ausente INTEGER,
    flag_ano_invalido INTEGER,
    log_inscricao_rel DOUBLE PRECISION,
    rank_inscricao_setor DOUBLE PRECISION,
    knn_proxy       DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS stats_setor_inscricao (
    cdsetorfiscal DOUBLE PRECISION PRIMARY KEY,
    log_inscricao_med_setor DOUBLE PRECISION,
    n_setor INTEGER
);

CREATE TABLE IF NOT EXISTS vals_inscricao_setor (
    cdsetorfiscal DOUBLE PRECISION PRIMARY KEY,
    vals_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS parametro_modelo (
    chave VARCHAR(80) PRIMARY KEY,
    valor_json JSONB,
    atualizado_em TIMESTAMP
);

CREATE TABLE IF NOT EXISTS serie_ipca (
    data DATE PRIMARY KEY,
    valor DOUBLE PRECISION NOT NULL,
    observacao TEXT
);
