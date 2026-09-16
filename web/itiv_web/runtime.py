# -*- coding: utf-8 -*-
"""Estado carregado na subida do serviço (pool, modelo, stats, IPCA)."""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from pyproj import Transformer
from sqlalchemy.orm import Session

from itiv_web.config import (
    ARQUIVO_MODELO,
    CRS_GEOGRAFICO,
    CRS_UTM,
    FEATURES_PRODUCAO_DEFAULT,
    FILL_MEDIANAS_DEFAULT,
)
from itiv_web.ipca import serie_ipca_de_linhas
from itiv_web.models import (
    NascimentoImovel,
    ParametroModelo,
    PoolTreino,
    SerieIpca,
    StatsSetorInscricao,
    ValsInscricaoSetor,
)

_CODIGO_APROVADO = Path(__file__).resolve().parents[2] / "Modelo_Apartamentos_Aprovado" / "codigo"
if str(_CODIGO_APROVADO) not in sys.path:
    sys.path.insert(0, str(_CODIGO_APROVADO))

import apartamentos_lib as aplib  # noqa: E402


def _param(session: Session, chave: str, default=None):
    row = session.get(ParametroModelo, chave)
    if row is None:
        return default
    return row.valor_json


def _pool_para_dataframe(linhas: list[PoolTreino]) -> pd.DataFrame:
    if not linhas:
        return pd.DataFrame()
    recs = []
    for r in linhas:
        recs.append(
            {
                "SQTRANSMISSAO": r.sqtransmissao,
                "CDINSCRICAOIMOB": r.cdinscricaoimob,
                "DATA_TRANSACAO": r.data_transacao,
                "VLTRANSACAO": r.vltransacao,
                "VLTRANSACAO_DEFLACIONADO": r.vltransacao_deflacionado,
                "VAR_TENDENCIA": r.var_tendencia,
                "LOG_AREA": r.log_area,
                "NUPAVIMENTOS": r.nupavimentos,
                "ANDAR_UNIDADE": r.andar_unidade,
                "FLAG_ANDAR_AUSENTE": r.flag_andar_ausente,
                "CDSETORFISCAL": r.cdsetorfiscal,
                "VLCOORDGEOX": r.vlcoordgeox,
                "VLCOORDGEOY": r.vlcoordgeoy,
                "VLVENALCADASTRO": r.vlvenalcadastro,
                "IDADE_NA_TRANSACAO_IMP": r.idade_na_transacao_imp,
                "FLAG_ANO_AUSENTE": r.flag_ano_ausente,
                "FLAG_ANO_INVALIDO": r.flag_ano_invalido,
                "LOG_INSCRICAO_REL": r.log_inscricao_rel,
                "RANK_INSCRICAO_SETOR": r.rank_inscricao_setor,
                "KNN_PROXY": r.knn_proxy,
            }
        )
    return pd.DataFrame(recs)


@dataclass
class RuntimeState:
    pronto: bool = False
    erro: str | None = None
    pool: pd.DataFrame = field(default_factory=pd.DataFrame)
    categorias_setor: pd.Index = field(default_factory=lambda: pd.Index([]))
    stats_setor: pd.DataFrame = field(default_factory=pd.DataFrame)
    nascimento_map: dict = field(default_factory=dict)
    features_producao: list[str] = field(default_factory=lambda: list(FEATURES_PRODUCAO_DEFAULT))
    fill_medianas: dict = field(default_factory=lambda: dict(FILL_MEDIANAS_DEFAULT))
    idade_mediana_treino: float = 13.0
    ic80_inf: float = 0.85
    ic80_sup: float = 1.15
    mediana_proxy: float = 8.5
    modelo_lgbm: object | None = None
    modelo_hed: object | None = None
    colunas_hed: object | None = None
    ipca: pd.DataFrame = field(default_factory=pd.DataFrame)
    utm2geo: object | None = None
    versao: str = ""

    def carregar(self, session: Session) -> None:
        self.pronto = False
        self.erro = None
        self.utm2geo = Transformer.from_crs(CRS_UTM, CRS_GEOGRAFICO, always_xy=True)

        pool_rows = session.query(PoolTreino).all()
        self.pool = _pool_para_dataframe(pool_rows)
        if self.pool.empty:
            self.erro = "pool_treino vazio — rode o script de popular a base"
            return

        if "KNN_PROXY" not in self.pool.columns or self.pool["KNN_PROXY"].isna().all():
            self.pool["KNN_PROXY"] = aplib.calcular_knn_proxy(self.pool, self.pool, k=aplib.K_VIZINHOS)
        else:
            faltantes = self.pool["KNN_PROXY"].isna()
            if faltantes.any():
                self.pool.loc[faltantes, "KNN_PROXY"] = aplib.calcular_knn_proxy(
                    self.pool, self.pool.loc[faltantes], k=aplib.K_VIZINHOS
                )

        self.categorias_setor = pd.Categorical(self.pool["CDSETORFISCAL"]).categories

        stats_rows = session.query(StatsSetorInscricao).all()
        self.stats_setor = pd.DataFrame(
            [
                {
                    "CDSETORFISCAL": r.cdsetorfiscal,
                    "LOG_INSCRICAO_MED_SETOR": r.log_inscricao_med_setor,
                    "n_setor": r.n_setor,
                }
                for r in stats_rows
            ]
        )
        vals_map: dict[float, np.ndarray] = {}
        for v in session.query(ValsInscricaoSetor).all():
            vals_map[float(v.cdsetorfiscal)] = np.asarray(v.vals_json, dtype=float)
        if self.stats_setor.empty:
            from inscricao_relativa import stats_setor_treino

            self.stats_setor = stats_setor_treino(self.pool)
        else:
            self.stats_setor.attrs["vals_por_setor"] = vals_map

        nasc_rows = session.query(NascimentoImovel).all()
        self.nascimento_map = {
            int(r.cdinscricaoimob): r.aaconstrucao
            for r in nasc_rows
            if r.cdinscricaoimob is not None
        }

        feats = _param(session, "features_producao")
        if isinstance(feats, dict) and "candidato" in feats:
            self.features_producao = list(feats["candidato"])
        elif isinstance(feats, list):
            self.features_producao = list(feats)
        else:
            self.features_producao = list(FEATURES_PRODUCAO_DEFAULT)

        meds = _param(session, "fill_medians")
        self.fill_medianas = dict(FILL_MEDIANAS_DEFAULT)
        if isinstance(meds, dict):
            self.fill_medianas.update(meds)
        self.idade_mediana_treino = float(self.fill_medianas.get("IDADE_NA_TRANSACAO_IMP", 13.0))

        ic_inf = _param(session, "ic80_inf")
        ic_sup = _param(session, "ic80_sup")
        if ic_inf is not None:
            self.ic80_inf = float(ic_inf)
        if ic_sup is not None:
            self.ic80_sup = float(ic_sup)

        versao = _param(session, "versao_modelo")
        self.versao = str(versao) if versao else ""

        if not ARQUIVO_MODELO.exists():
            self.erro = f"modelo LightGBM ausente: {ARQUIVO_MODELO}"
            return
        texto = ARQUIVO_MODELO.read_text(encoding="utf-8")
        self.modelo_lgbm = lgb.Booster(model_str=texto)

        _, _, self.mediana_proxy = aplib.montar_X_y(self.pool)
        self.modelo_hed, self.colunas_hed = aplib.treinar_hedonico(self.pool)

        ipca_rows = session.query(SerieIpca).order_by(SerieIpca.data).all()
        self.ipca = serie_ipca_de_linhas([(r.data, r.valor) for r in ipca_rows])

        self.pronto = True


STATE = RuntimeState()
