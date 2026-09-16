# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Transmissao(Base):
    __tablename__ = "transmissao"

    sq: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cdinscricaoimob: Mapped[int | None] = mapped_column(BigInteger, index=True)
    tipologia: Mapped[str | None] = mapped_column(String(80), index=True)
    data_transacao: Mapped[date | None] = mapped_column(Date, index=True)
    vltransacao: Mapped[float | None] = mapped_column(Float)
    vlitiv: Mapped[float | None] = mapped_column(Float)
    vlvenalcadastro: Mapped[float | None] = mapped_column(Float)
    vlvenalcorrigido: Mapped[float | None] = mapped_column(Float)
    vltransacao_deflacionado: Mapped[float | None] = mapped_column(Float)
    var_tendencia: Mapped[float | None] = mapped_column(Float)
    vlareausopriv: Mapped[float | None] = mapped_column(Float)
    nupavimentos: Mapped[float | None] = mapped_column(Float)
    nupavimentounidade: Mapped[float | None] = mapped_column(Float)
    cdsetorfiscal: Mapped[float | None] = mapped_column(Float, index=True)
    vlcoordgeox: Mapped[float | None] = mapped_column(Float)
    vlcoordgeoy: Mapped[float | None] = mapped_column(Float)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    vlfracaoterreno: Mapped[float | None] = mapped_column(Float)
    vlfracaoconstrucao: Mapped[float | None] = mapped_column(Float)
    dstipotransacao: Mapped[str | None] = mapped_column(String(120))
    dssituacaotransmissao: Mapped[str | None] = mapped_column(String(80))


class Cadastro(Base):
    __tablename__ = "cadastro"

    cdinscricaoimob: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dssubunidade: Mapped[str | None] = mapped_column(String(80))
    vlareausopriv: Mapped[float | None] = mapped_column(Float)
    nupavimentounidade: Mapped[float | None] = mapped_column(Float)
    nupavimentos: Mapped[float | None] = mapped_column(Float)
    cdsetorfiscal: Mapped[float | None] = mapped_column(Float)
    vlcoordgeox: Mapped[float | None] = mapped_column(Float)
    vlcoordgeoy: Mapped[float | None] = mapped_column(Float)
    vlvenalcadastro: Mapped[float | None] = mapped_column(Float)
    vliptu: Mapped[float | None] = mapped_column(Float)
    dslogradouro: Mapped[str | None] = mapped_column(String(255))
    nuporta: Mapped[str | None] = mapped_column(String(40))
    cdcep: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)


class NascimentoImovel(Base):
    __tablename__ = "nascimento_imovel"

    cdinscricaoimob: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    aaconstrucao: Mapped[float | None] = mapped_column(Float)


class PoolTreino(Base):
    __tablename__ = "pool_treino"

    sqtransmissao: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cdinscricaoimob: Mapped[int | None] = mapped_column(BigInteger)
    data_transacao: Mapped[date | None] = mapped_column(Date)
    vltransacao: Mapped[float | None] = mapped_column(Float)
    vltransacao_deflacionado: Mapped[float | None] = mapped_column(Float)
    var_tendencia: Mapped[float | None] = mapped_column(Float)
    log_area: Mapped[float | None] = mapped_column(Float)
    nupavimentos: Mapped[float | None] = mapped_column(Float)
    andar_unidade: Mapped[float | None] = mapped_column(Float)
    flag_andar_ausente: Mapped[int | None] = mapped_column(Integer)
    cdsetorfiscal: Mapped[float | None] = mapped_column(Float)
    vlcoordgeox: Mapped[float | None] = mapped_column(Float)
    vlcoordgeoy: Mapped[float | None] = mapped_column(Float)
    vlvenalcadastro: Mapped[float | None] = mapped_column(Float)
    idade_na_transacao_imp: Mapped[float | None] = mapped_column(Float)
    flag_ano_ausente: Mapped[int | None] = mapped_column(Integer)
    flag_ano_invalido: Mapped[int | None] = mapped_column(Integer)
    log_inscricao_rel: Mapped[float | None] = mapped_column(Float)
    rank_inscricao_setor: Mapped[float | None] = mapped_column(Float)
    knn_proxy: Mapped[float | None] = mapped_column(Float)


class StatsSetorInscricao(Base):
    __tablename__ = "stats_setor_inscricao"

    cdsetorfiscal: Mapped[float] = mapped_column(Float, primary_key=True)
    log_inscricao_med_setor: Mapped[float | None] = mapped_column(Float)
    n_setor: Mapped[int | None] = mapped_column(Integer)


class ValsInscricaoSetor(Base):
    __tablename__ = "vals_inscricao_setor"

    cdsetorfiscal: Mapped[float] = mapped_column(Float, primary_key=True)
    vals_json: Mapped[list] = mapped_column(JSONB)


class ParametroModelo(Base):
    __tablename__ = "parametro_modelo"

    chave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor_json: Mapped[object] = mapped_column(JSONB)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime)


class SerieIpca(Base):
    __tablename__ = "serie_ipca"

    data: Mapped[date] = mapped_column(Date, primary_key=True)
    valor: Mapped[float] = mapped_column(Float)
    observacao: Mapped[str | None] = mapped_column(Text)
