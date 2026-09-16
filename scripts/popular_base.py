# -*- coding: utf-8 -*-
"""Carga da base PostgreSQL do avaliador ITIV.

Uso:
  python -m scripts.popular_base --recriar
  python -m scripts.popular_base --demo --recriar

Variáveis: DATABASE_URL, ITIV_DADOS_DIR, MODELO_DIR
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import pickle
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "Modelo_Apartamentos_Aprovado" / "codigo"))

from itiv_web.config import (  # noqa: E402
    ARQUIVO_MODELO,
    CRS_GEOGRAFICO,
    CRS_UTM,
    FEATURES_PRODUCAO_DEFAULT,
    FILL_MEDIANAS_DEFAULT,
    ITIV_DADOS_DIR,
    LAT_MAX,
    LAT_MIN,
    LON_MAX,
    LON_MIN,
    MODELO_DIR,
    VERSAO_MODELO,
)
from itiv_web.db import SessionLocal, criar_schema, engine  # noqa: E402
from itiv_web.ipca import (  # noqa: E402
    baixar_serie_ipca,
    construir_indice_deflator,
    deflacionar_valores,
    var_tendencia,
)
from itiv_web.models import (  # noqa: E402
    Base,
    Cadastro,
    NascimentoImovel,
    ParametroModelo,
    PoolTreino,
    SerieIpca,
    StatsSetorInscricao,
    Transmissao,
    ValsInscricaoSetor,
)

UTM2GEO = Transformer.from_crs(CRS_UTM, CRS_GEOGRAFICO, always_xy=True)

TABELAS = [
    "transmissao",
    "cadastro",
    "nascimento_imovel",
    "pool_treino",
    "stats_setor_inscricao",
    "vals_inscricao_setor",
    "parametro_modelo",
    "serie_ipca",
]


def log(msg: str) -> None:
    print(msg, flush=True)


def achar(base: Path, padroes: list[str]) -> Path | None:
    """Localiza o primeiro arquivo que casa com os globs (case-insensitive).

    Prefere `dados_importacao/pronto/` para não pegar cópias em _origem/legado.
    """
    if not base.exists():
        return None
    for raiz in (base / "pronto", base):
        if not raiz.exists():
            continue
        for padrao in padroes:
            hits = sorted(p for p in raiz.glob(padrao) if p.is_file())
            if hits:
                return hits[0]
        for p in raiz.rglob("*"):
            if not p.is_file():
                continue
            partes = {parte.casefold() for parte in p.relative_to(base).parts[:-1]}
            if "_origem" in partes or "legado_v20260714" in partes:
                continue
            nome = p.name.casefold()
            for padrao in padroes:
                if fnmatch.fnmatch(nome, padrao.casefold()):
                    return p
    return None


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().upper() for c in out.columns]
    return out


def _num(s):
    return pd.to_numeric(s, errors="coerce")


def _data_unificada(df: pd.DataFrame) -> pd.Series:
    if "DATA_TRANSACAO" in df.columns:
        d = pd.to_datetime(df["DATA_TRANSACAO"], errors="coerce")
        if d.notna().any():
            return d
    dpag = pd.to_datetime(df["DTPAGAMENTO"], errors="coerce") if "DTPAGAMENTO" in df.columns else pd.NaT
    dreg = pd.to_datetime(df["DTREGISTROCARTORIO"], errors="coerce") if "DTREGISTROCARTORIO" in df.columns else None
    dlav = pd.to_datetime(df["DTLAVRATURA"], errors="coerce") if "DTLAVRATURA" in df.columns else None
    dass = pd.to_datetime(df["DTASSINATURACONTRATO"], errors="coerce") if "DTASSINATURACONTRATO" in df.columns else None
    data = dpag if isinstance(dpag, pd.Series) else pd.Series(pd.NaT, index=df.index)
    for alt in (dreg, dlav, dass):
        if alt is None:
            continue
        data = data.where(data.notna(), alt)
    return data


def lat_lon_de_utm(x, y) -> tuple[float | None, float | None]:
    try:
        xf, yf = float(x), float(y)
    except (TypeError, ValueError):
        return None, None
    if not np.isfinite(xf) or not np.isfinite(yf) or xf == 0 or yf == 0:
        return None, None
    lon, lat = UTM2GEO.transform(xf, yf)
    if LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX:
        return float(lat), float(lon)
    return None, None


def truncar() -> None:
    nomes = ", ".join(TABELAS)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {nomes} RESTART IDENTITY CASCADE"))
    log(f"Tabelas esvaziadas: {nomes}")


def upsert_parametro(session, chave: str, valor) -> None:
    row = session.get(ParametroModelo, chave)
    if row is None:
        session.add(ParametroModelo(chave=chave, valor_json=valor, atualizado_em=datetime.utcnow()))
    else:
        row.valor_json = valor
        row.atualizado_em = datetime.utcnow()


def gravar_ipca(session, serie: pd.DataFrame) -> None:
    session.query(SerieIpca).delete()
    for _, r in serie.iterrows():
        session.add(SerieIpca(data=pd.Timestamp(r["data"]).date(), valor=float(r["valor"])))
    log(f"  IPCA: {len(serie)} meses")


def serie_ipca_sintetica() -> pd.DataFrame:
    inicio = date(2020, 1, 1)
    linhas = []
    for i in range(72):
        ano = inicio.year + (inicio.month - 1 + i) // 12
        mes = (inicio.month - 1 + i) % 12 + 1
        linhas.append({"data": pd.Timestamp(year=ano, month=mes, day=1), "valor": 0.4})
    return pd.DataFrame(linhas)


def obter_ipca(dados_dir: Path) -> pd.DataFrame:
    cache = achar(dados_dir, ["serie_ipca.csv", "ipca.csv"])
    if cache:
        df = pd.read_csv(cache)
        df.columns = [c.strip().lower() for c in df.columns]
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
        log(f"  IPCA lido de {cache}")
        return df.dropna()
    try:
        log("  Baixando IPCA SGS 433...")
        return baixar_serie_ipca()
    except Exception as exc:  # noqa: BLE001
        log(f"  Aviso: BCB indisponivel ({exc}); usando serie sintetica 0,4%/mes.")
        return serie_ipca_sintetica()


def ler_excel_ou_parquet(caminho: Path) -> pd.DataFrame:
    if caminho.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(caminho)
    try:
        return pd.read_excel(caminho, sheet_name="Exportar Planilha")
    except ValueError:
        return pd.read_excel(caminho)


def importar_transmissoes(session, caminho: Path, tabela_mod: Path | None, serie: pd.DataFrame) -> None:
    log(f"Transmissões: {caminho}")
    df = normalizar_colunas(ler_excel_ou_parquet(caminho))
    if "SQTRANSMISSAO" not in df.columns:
        raise SystemExit(f"Arquivo sem SQTRANSMISSAO: {list(df.columns)[:20]}")
    df["SQTRANSMISSAO"] = _num(df["SQTRANSMISSAO"]).astype("Int64")
    df = df.dropna(subset=["SQTRANSMISSAO"]).drop_duplicates("SQTRANSMISSAO")
    df["DATA_TRANSACAO"] = _data_unificada(df)
    geo = {}
    if tabela_mod and tabela_mod.exists():
        tab = normalizar_colunas(ler_excel_ou_parquet(tabela_mod))
        if "SQTRANSMISSAO" in tab.columns:
            tab["SQTRANSMISSAO"] = _num(tab["SQTRANSMISSAO"]).astype("Int64")
            for _, r in tab.iterrows():
                geo[int(r["SQTRANSMISSAO"])] = r
            log(f"  tabela modelagem: {len(geo):,} linhas")
    defl = deflacionar_valores(df.get("VLTRANSACAO", pd.Series(dtype=float)), df["DATA_TRANSACAO"], serie)
    data_ref = pd.Timestamp(serie["data"].max())
    tend = var_tendencia(df["DATA_TRANSACAO"], data_ref)
    n = 0
    for i, r in df.iterrows():
        sq = int(r["SQTRANSMISSAO"])
        extra = geo.get(sq, {})
        lat = extra.get("LATITUDE") if isinstance(extra, pd.Series) else None
        lon = extra.get("LONGITUDE") if isinstance(extra, pd.Series) else None
        if pd.isna(lat) or pd.isna(lon):
            lat, lon = lat_lon_de_utm(r.get("VLCOORDGEOX"), r.get("VLCOORDGEOY"))
        vdefl = extra.get("VLTRANSACAO_DEFLACIONADO") if isinstance(extra, pd.Series) else None
        if vdefl is None or pd.isna(vdefl):
            vdefl = defl.loc[i] if i in defl.index else None
        session.add(
            Transmissao(
                sq=sq,
                cdinscricaoimob=_int_or_none(r.get("CDINSCRICAOIMOB")),
                tipologia=_str_or_none(r.get("DSSUBUNIDADE") or r.get("TIPOLOGIA")),
                data_transacao=_date_or_none(r.get("DATA_TRANSACAO")),
                vltransacao=_float_or_none(r.get("VLTRANSACAO")),
                vlitiv=_float_or_none(r.get("VLITIV")),
                vlvenalcadastro=_float_or_none(r.get("VLVENALCADASTRO")),
                vlvenalcorrigido=_float_or_none(r.get("VLVENALCORRIGIDO")),
                vltransacao_deflacionado=_float_or_none(vdefl),
                var_tendencia=_float_or_none(tend.loc[i] if i in tend.index else None),
                vlareausopriv=_float_or_none(r.get("VLAREAUSOPRIV")),
                nupavimentos=_float_or_none(r.get("NUPAVIMENTOS")),
                nupavimentounidade=_float_or_none(r.get("NUPAVIMENTOUNIDADE")),
                cdsetorfiscal=_float_or_none(r.get("CDSETORFISCAL")),
                vlcoordgeox=_float_or_none(r.get("VLCOORDGEOX")),
                vlcoordgeoy=_float_or_none(r.get("VLCOORDGEOY")),
                latitude=_float_or_none(lat),
                longitude=_float_or_none(lon),
                vlfracaoterreno=_float_or_none(r.get("VLFRACAOTERRENO")),
                vlfracaoconstrucao=_float_or_none(r.get("VLFRACAOCONSTRUCAO")),
                dstipotransacao=_str_or_none(r.get("DSTIPOTRANSACAO")),
                dssituacaotransmissao=_str_or_none(r.get("DSSITUACAOTRANSMISSAO")),
            )
        )
        n += 1
        if n % 5000 == 0:
            session.flush()
            log(f"  ... {n:,} transmissões")
    log(f"  gravadas {n:,} transmissões")


def importar_cadastro(session, caminho: Path) -> None:
    log(f"Cadastro: {caminho}")
    df = normalizar_colunas(ler_excel_ou_parquet(caminho))
    if "CDINSCRICAOIMOB" not in df.columns:
        raise SystemExit(f"Cadastro sem CDINSCRICAOIMOB: {list(df.columns)[:20]}")
    df["CDINSCRICAOIMOB"] = _num(df["CDINSCRICAOIMOB"]).astype("Int64")
    df = df.dropna(subset=["CDINSCRICAOIMOB"]).drop_duplicates("CDINSCRICAOIMOB", keep="last")
    n = 0
    for _, r in df.iterrows():
        lat, lon = lat_lon_de_utm(r.get("VLCOORDGEOX"), r.get("VLCOORDGEOY"))
        session.add(
            Cadastro(
                cdinscricaoimob=int(r["CDINSCRICAOIMOB"]),
                dssubunidade=_str_or_none(r.get("DSSUBUNIDADE")),
                vlareausopriv=_float_or_none(r.get("VLAREAUSOPRIV")),
                nupavimentounidade=_float_or_none(r.get("NUPAVIMENTOUNIDADE")),
                nupavimentos=_float_or_none(r.get("NUPAVIMENTOS")),
                cdsetorfiscal=_float_or_none(r.get("CDSETORFISCAL")),
                vlcoordgeox=_float_or_none(r.get("VLCOORDGEOX")),
                vlcoordgeoy=_float_or_none(r.get("VLCOORDGEOY")),
                vlvenalcadastro=_float_or_none(r.get("VLVENALCADASTRO")),
                vliptu=_float_or_none(r.get("VLIPTU")),
                dslogradouro=_str_or_none(r.get("DSLOGRADOURO")),
                nuporta=_str_or_none(r.get("NUPORTA")),
                cdcep=_str_or_none(r.get("CDCEP")),
                latitude=lat,
                longitude=lon,
            )
        )
        n += 1
        if n % 5000 == 0:
            session.flush()
    log(f"  gravados {n:,} imóveis")


def importar_nascimento(session, caminho: Path) -> None:
    log(f"Nascimento: {caminho}")
    raw = pd.read_csv(caminho, sep=";", encoding="utf-8-sig", low_memory=False)
    raw = normalizar_colunas(raw)
    if "CDINSCRICAOIMOB" not in raw.columns:
        raw = pd.read_csv(caminho, encoding="utf-8-sig", low_memory=False)
        raw = normalizar_colunas(raw)
    raw = raw.dropna(subset=["CDINSCRICAOIMOB"])
    raw["CDINSCRICAOIMOB"] = _num(raw["CDINSCRICAOIMOB"]).astype(np.int64)
    raw = raw.drop_duplicates("CDINSCRICAOIMOB", keep="last")
    for _, r in raw.iterrows():
        session.add(
            NascimentoImovel(
                cdinscricaoimob=int(r["CDINSCRICAOIMOB"]),
                aaconstrucao=_float_or_none(r.get("AACONSTRUCAO")),
            )
        )
    log(f"  gravados {len(raw):,} anos de construção")


def importar_pool(session, caminho: Path) -> pd.DataFrame:
    log(f"Pool treino: {caminho}")
    df = normalizar_colunas(pd.read_parquet(caminho))
    n = 0
    for _, r in df.iterrows():
        session.add(
            PoolTreino(
                sqtransmissao=int(r["SQTRANSMISSAO"]),
                cdinscricaoimob=_int_or_none(r.get("CDINSCRICAOIMOB")),
                data_transacao=_date_or_none(r.get("DATA_TRANSACAO")),
                vltransacao=_float_or_none(r.get("VLTRANSACAO")),
                vltransacao_deflacionado=_float_or_none(r.get("VLTRANSACAO_DEFLACIONADO")),
                var_tendencia=_float_or_none(r.get("VAR_TENDENCIA")),
                log_area=_float_or_none(r.get("LOG_AREA")),
                nupavimentos=_float_or_none(r.get("NUPAVIMENTOS")),
                andar_unidade=_float_or_none(r.get("ANDAR_UNIDADE")),
                flag_andar_ausente=_int_or_none(r.get("FLAG_ANDAR_AUSENTE")),
                cdsetorfiscal=_float_or_none(r.get("CDSETORFISCAL")),
                vlcoordgeox=_float_or_none(r.get("VLCOORDGEOX")),
                vlcoordgeoy=_float_or_none(r.get("VLCOORDGEOY")),
                vlvenalcadastro=_float_or_none(r.get("VLVENALCADASTRO")),
                idade_na_transacao_imp=_float_or_none(r.get("IDADE_NA_TRANSACAO_IMP")),
                flag_ano_ausente=_int_or_none(r.get("FLAG_ANO_AUSENTE")),
                flag_ano_invalido=_int_or_none(r.get("FLAG_ANO_INVALIDO")),
                log_inscricao_rel=_float_or_none(r.get("LOG_INSCRICAO_REL")),
                rank_inscricao_setor=_float_or_none(r.get("RANK_INSCRICAO_SETOR")),
                knn_proxy=_float_or_none(r.get("KNN_PROXY")),
            )
        )
        n += 1
        if n % 2000 == 0:
            session.flush()
    log(f"  gravadas {n:,} linhas de pool")
    return df


def importar_stats(session, parquet_stats: Path | None, pkl_vals: Path | None, pool: pd.DataFrame | None) -> None:
    if parquet_stats and parquet_stats.exists():
        log(f"Stats setor: {parquet_stats}")
        st = normalizar_colunas(pd.read_parquet(parquet_stats))
        for _, r in st.iterrows():
            session.add(
                StatsSetorInscricao(
                    cdsetorfiscal=float(r["CDSETORFISCAL"]),
                    log_inscricao_med_setor=_float_or_none(r.get("LOG_INSCRICAO_MED_SETOR")),
                    n_setor=_int_or_none(r.get("N_SETOR") or r.get("N")),
                )
            )
    elif pool is not None and not pool.empty:
        from inscricao_relativa import stats_setor_treino

        log("Stats setor: calculadas a partir do pool")
        st = stats_setor_treino(pool)
        for _, r in st.iterrows():
            session.add(
                StatsSetorInscricao(
                    cdsetorfiscal=float(r["CDSETORFISCAL"]),
                    log_inscricao_med_setor=float(r["LOG_INSCRICAO_MED_SETOR"]),
                    n_setor=int(r["n_setor"]),
                )
            )
            session.add(
                ValsInscricaoSetor(
                    cdsetorfiscal=float(r["CDSETORFISCAL"]),
                    vals_json=st.attrs["vals_por_setor"][float(r["CDSETORFISCAL"])].tolist(),
                )
            )
        return
    if pkl_vals and pkl_vals.exists():
        log(f"Vals inscrição: {pkl_vals}")
        with open(pkl_vals, "rb") as fh:
            vals = pickle.load(fh)
        for setor, arr in vals.items():
            session.add(ValsInscricaoSetor(cdsetorfiscal=float(setor), vals_json=np.asarray(arr).tolist()))


def copiar_modelo(origem: Path | None) -> None:
    MODELO_DIR.mkdir(parents=True, exist_ok=True)
    if origem and origem.exists():
        if ARQUIVO_MODELO.exists() and origem.resolve() == ARQUIVO_MODELO.resolve():
            log(f"Modelo já está em {ARQUIVO_MODELO} (mesmo arquivo da origem)")
            return
        try:
            if ARQUIVO_MODELO.exists() and origem.samefile(ARQUIVO_MODELO):
                log(f"Modelo já está em {ARQUIVO_MODELO} (hardlink da origem)")
                return
        except OSError:
            pass
        try:
            shutil.copy2(origem, ARQUIVO_MODELO)
            log(f"Modelo copiado para {ARQUIVO_MODELO}")
        except shutil.SameFileError:
            log(f"Modelo já está em {ARQUIVO_MODELO}")
    elif ARQUIVO_MODELO.exists():
        log(f"Modelo já presente em {ARQUIVO_MODELO}")
    else:
        log(f"AVISO: nenhum modelo LightGBM em {ARQUIVO_MODELO}")


def ic80_do_holdout(caminho: Path | None) -> tuple[float, float]:
    if caminho is None or not caminho.exists():
        return 0.85, 1.15
    df = pd.read_parquet(caminho)
    col_pred = "PRED_idade_mais_rel" if "PRED_idade_mais_rel" in df.columns else "VALOR_PREVISTO_LGBM"
    if col_pred not in df.columns or "VLTRANSACAO_DEFLACIONADO" not in df.columns:
        return 0.85, 1.15
    razao = (df["VLTRANSACAO_DEFLACIONADO"] / df[col_pred]).replace([np.inf, -np.inf], np.nan).dropna()
    inf, sup = razao.quantile([0.10, 0.90])
    log(f"  IC80 holdout: {float(inf):.4f} – {float(sup):.4f}")
    return float(inf), float(sup)


def _float_or_none(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _int_or_none(v):
    f = _float_or_none(v)
    return int(f) if f is not None else None


def _str_or_none(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    s = str(v).strip()
    return s if s and s.lower() != "nan" else None


def _date_or_none(v):
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.date()


def gerar_demo(session) -> None:
    """Recorte sintético para subir o compose sem as planilhas fiscais."""
    log("Modo --demo: gerando recorte sintético de Salvador")
    rng = np.random.default_rng(42)
    serie = serie_ipca_sintetica()
    gravar_ipca(session, serie)

    n_pool = 40
    setores = [101.0, 102.0, 103.0]
    inscricoes = [450001 + i for i in range(n_pool)]
    hoje = date.today()
    pool_rows = []
    for i in range(n_pool):
        area = float(rng.uniform(45, 140))
        x = 548000 + rng.normal(0, 800)
        y = 8_565_000 + rng.normal(0, 800)
        lat, lon = lat_lon_de_utm(x, y)
        if lat is None:
            lat, lon = -12.97 + rng.normal(0, 0.01), -38.51 + rng.normal(0, 0.01)
        setor = setores[i % len(setores)]
        data_tx = hoje - timedelta(days=int(rng.integers(40, 900)))
        valor = area * float(rng.uniform(7000, 12000))
        sq = 900001 + i
        log_area = float(np.log(area))
        pool_rows.append(
            {
                "SQTRANSMISSAO": sq,
                "CDINSCRICAOIMOB": inscricoes[i],
                "DATA_TRANSACAO": data_tx,
                "VLTRANSACAO": valor,
                "VLTRANSACAO_DEFLACIONADO": valor * 1.02,
                "VAR_TENDENCIA": float((hoje.year - data_tx.year) * 12 + (hoje.month - data_tx.month)),
                "LOG_AREA": log_area,
                "NUPAVIMENTOS": float(rng.integers(4, 25)),
                "ANDAR_UNIDADE": float(rng.integers(1, 15)),
                "FLAG_ANDAR_AUSENTE": 0,
                "CDSETORFISCAL": setor,
                "VLCOORDGEOX": float(x),
                "VLCOORDGEOY": float(y),
                "VLVENALCADASTRO": valor * 0.9,
                "IDADE_NA_TRANSACAO_IMP": float(rng.integers(5, 40)),
                "FLAG_ANO_AUSENTE": 0,
                "FLAG_ANO_INVALIDO": 0,
                "lat": lat,
                "lon": lon,
                "area": area,
            }
        )

    pool_df = pd.DataFrame(pool_rows)
    from inscricao_relativa import anexar_inscricao_relativa, stats_setor_treino
    import apartamentos_lib as aplib

    stats = stats_setor_treino(pool_df)
    pool_df = anexar_inscricao_relativa(pool_df, stats)
    pool_df["KNN_PROXY"] = aplib.calcular_knn_proxy(pool_df, pool_df, k=min(10, n_pool - 1))

    for _, r in stats.iterrows():
        session.add(
            StatsSetorInscricao(
                cdsetorfiscal=float(r["CDSETORFISCAL"]),
                log_inscricao_med_setor=float(r["LOG_INSCRICAO_MED_SETOR"]),
                n_setor=int(r["n_setor"]),
            )
        )
        session.add(
            ValsInscricaoSetor(
                cdsetorfiscal=float(r["CDSETORFISCAL"]),
                vals_json=stats.attrs["vals_por_setor"][float(r["CDSETORFISCAL"])].tolist(),
            )
        )

    for _, r in pool_df.iterrows():
        session.add(
            PoolTreino(
                sqtransmissao=int(r["SQTRANSMISSAO"]),
                cdinscricaoimob=int(r["CDINSCRICAOIMOB"]),
                data_transacao=r["DATA_TRANSACAO"],
                vltransacao=float(r["VLTRANSACAO"]),
                vltransacao_deflacionado=float(r["VLTRANSACAO_DEFLACIONADO"]),
                var_tendencia=float(r["VAR_TENDENCIA"]),
                log_area=float(r["LOG_AREA"]),
                nupavimentos=float(r["NUPAVIMENTOS"]),
                andar_unidade=float(r["ANDAR_UNIDADE"]),
                flag_andar_ausente=int(r["FLAG_ANDAR_AUSENTE"]),
                cdsetorfiscal=float(r["CDSETORFISCAL"]),
                vlcoordgeox=float(r["VLCOORDGEOX"]),
                vlcoordgeoy=float(r["VLCOORDGEOY"]),
                vlvenalcadastro=float(r["VLVENALCADASTRO"]),
                idade_na_transacao_imp=float(r["IDADE_NA_TRANSACAO_IMP"]),
                flag_ano_ausente=0,
                flag_ano_invalido=0,
                log_inscricao_rel=float(r["LOG_INSCRICAO_REL"]),
                rank_inscricao_setor=float(r["RANK_INSCRICAO_SETOR"]),
                knn_proxy=_float_or_none(r["KNN_PROXY"]),
            )
        )
        session.add(
            Transmissao(
                sq=int(r["SQTRANSMISSAO"]),
                cdinscricaoimob=int(r["CDINSCRICAOIMOB"]),
                tipologia="Apartamento",
                data_transacao=r["DATA_TRANSACAO"],
                vltransacao=float(r["VLTRANSACAO"]),
                vlitiv=float(r["VLTRANSACAO"]) * 0.03,
                vlvenalcadastro=float(r["VLVENALCADASTRO"]),
                vltransacao_deflacionado=float(r["VLTRANSACAO_DEFLACIONADO"]),
                var_tendencia=float(r["VAR_TENDENCIA"]),
                vlareausopriv=float(r["area"]),
                nupavimentos=float(r["NUPAVIMENTOS"]),
                nupavimentounidade=float(r["ANDAR_UNIDADE"]),
                cdsetorfiscal=float(r["CDSETORFISCAL"]),
                vlcoordgeox=float(r["VLCOORDGEOX"]),
                vlcoordgeoy=float(r["VLCOORDGEOY"]),
                latitude=float(r["lat"]),
                longitude=float(r["lon"]),
                dstipotransacao="Compra e Venda",
                dssituacaotransmissao="Baixado",
            )
        )
        session.add(
            NascimentoImovel(
                cdinscricaoimob=int(r["CDINSCRICAOIMOB"]),
                aaconstrucao=float(2024 - r["IDADE_NA_TRANSACAO_IMP"]),
            )
        )

    # segunda transmissão na mesma inscrição (lista no /avaliar)
    r0 = pool_df.iloc[0]
    session.add(
        Transmissao(
            sq=910001,
            cdinscricaoimob=int(r0["CDINSCRICAOIMOB"]),
            tipologia="Apartamento",
            data_transacao=hoje - timedelta(days=1200),
            vltransacao=float(r0["VLTRANSACAO"]) * 0.8,
            vltransacao_deflacionado=float(r0["VLTRANSACAO_DEFLACIONADO"]) * 0.8,
            var_tendencia=36.0,
            vlareausopriv=float(r0["area"]),
            nupavimentos=float(r0["NUPAVIMENTOS"]),
            nupavimentounidade=float(r0["ANDAR_UNIDADE"]),
            cdsetorfiscal=float(r0["CDSETORFISCAL"]),
            vlcoordgeox=float(r0["VLCOORDGEOX"]),
            vlcoordgeoy=float(r0["VLCOORDGEOY"]),
            latitude=float(r0["lat"]),
            longitude=float(r0["lon"]),
            dstipotransacao="Compra e Venda",
        )
    )

    session.add(
        Cadastro(
            cdinscricaoimob=int(r0["CDINSCRICAOIMOB"]),
            dssubunidade="Apartamento",
            vlareausopriv=float(r0["area"]),
            nupavimentounidade=float(r0["ANDAR_UNIDADE"]),
            nupavimentos=float(r0["NUPAVIMENTOS"]),
            cdsetorfiscal=float(r0["CDSETORFISCAL"]),
            vlcoordgeox=float(r0["VLCOORDGEOX"]),
            vlcoordgeoy=float(r0["VLCOORDGEOY"]),
            vlvenalcadastro=float(r0["VLVENALCADASTRO"]),
            vliptu=2500.0,
            dslogradouro="Av. Sete de Setembro",
            nuporta="100",
            cdcep="40060-001",
            latitude=float(r0["lat"]),
            longitude=float(r0["lon"]),
        )
    )

    import lightgbm as lgb

    feats = [c for c in FEATURES_PRODUCAO_DEFAULT if c in pool_df.columns]
    X = pool_df[feats].copy()
    X["CDSETORFISCAL"] = X["CDSETORFISCAL"].astype("category")
    y = np.log(pool_df["VLTRANSACAO_DEFLACIONADO"])
    modelo = lgb.LGBMRegressor(n_estimators=80, num_leaves=15, min_child_samples=5, verbosity=-1)
    modelo.fit(X, y, categorical_feature=["CDSETORFISCAL"])
    MODELO_DIR.mkdir(parents=True, exist_ok=True)
    modelo.booster_.save_model(str(ARQUIVO_MODELO))
    log(f"  modelo demo salvo em {ARQUIVO_MODELO}")

    pred = np.exp(modelo.predict(X))
    razao = pool_df["VLTRANSACAO_DEFLACIONADO"] / pred
    ic_inf, ic_sup = float(razao.quantile(0.10)), float(razao.quantile(0.90))
    upsert_parametro(session, "features_producao", {"candidato": FEATURES_PRODUCAO_DEFAULT})
    upsert_parametro(session, "fill_medians", FILL_MEDIANAS_DEFAULT)
    upsert_parametro(session, "ic80_inf", ic_inf)
    upsert_parametro(session, "ic80_sup", ic_sup)
    upsert_parametro(session, "versao_modelo", VERSAO_MODELO + " [demo]")
    log("Demo gravado. SQ de teste: 900001  | inscrição cadastro: 450001")


def arquivos_obrigatorios(dados_dir: Path) -> dict[str, Path | None]:
    return {
        "transmissões ITIV (xlsx/parquet)": achar(
            dados_dir,
            [
                "itiv_bruto.parquet",
                "*itiv*.parquet",
                "*ITIV*.xlsx",
                "Informações ITIV*.xlsx",
                "bruto.parquet",
            ],
        ),
        "cadastro (Imoveis Salvador)": achar(
            dados_dir,
            [
                "Imoveis Salvador.parquet",
                "Imoveis Salvador.xlsx",
                "Imoveis*.parquet",
                "Imoveis*.xlsx",
                "*salvador*.parquet",
                "cadastro.parquet",
            ],
        ),
        "Nascimento_Imovel.csv": achar(dados_dir, ["Nascimento_Imovel.csv", "Nascimento*.csv"]),
        "pool_treino_parametros.parquet": achar(dados_dir, ["pool_treino_parametros.parquet", "pool_treino.parquet"]),
        "modelo LightGBM (.txt)": achar(dados_dir, ["modelo_lightgbm_apartamentos.txt", "modelo_lightgbm*.txt"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula o PostgreSQL do avaliador ITIV")
    parser.add_argument("--recriar", action="store_true", help="TRUNCATE de todas as tabelas antes de carregar")
    parser.add_argument("--demo", action="store_true", help="Carga sintética (sem planilhas da equipe)")
    parser.add_argument("--dados", type=Path, default=ITIV_DADOS_DIR)
    args = parser.parse_args()

    criar_schema()
    if args.recriar:
        truncar()

    session = SessionLocal()
    try:
        if args.demo:
            gerar_demo(session)
            session.commit()
            log("Concluído (--demo).")
            return

        dados_dir = args.dados
        encontrados = arquivos_obrigatorios(dados_dir)
        faltando = [nome for nome, p in encontrados.items() if p is None]
        if faltando:
            log("Arquivos obrigatórios não encontrados em " + str(dados_dir.resolve()))
            for nome in faltando:
                log(f"  - AUSENTE: {nome}")
            log("Arquivos localizados:")
            for nome, p in encontrados.items():
                if p:
                    log(f"  - OK: {nome} -> {p}")
            log("Coloque as planilhas em dados_importacao/ ou rode com --demo.")
            raise SystemExit(2)

        serie = obter_ipca(dados_dir)
        gravar_ipca(session, serie)

        tabela_mod = achar(dados_dir, ["tabela_modelagem.parquet", "*modelagem*.parquet"])
        importar_transmissoes(session, encontrados["transmissões ITIV (xlsx/parquet)"], tabela_mod, serie)
        session.flush()
        importar_cadastro(session, encontrados["cadastro (Imoveis Salvador)"])
        session.flush()
        importar_nascimento(session, encontrados["Nascimento_Imovel.csv"])
        session.flush()
        pool_df = importar_pool(session, encontrados["pool_treino_parametros.parquet"])
        session.flush()
        stats_p = achar(dados_dir, ["stats_setor_inscricao_treino.parquet", "stats_setor*.parquet"])
        vals_p = achar(dados_dir, ["vals_inscricao_por_setor.pkl"])
        importar_stats(session, stats_p, vals_p, pool_df)

        feats_p = achar(dados_dir, ["features_producao.json", "features_candidato.json"])
        meds_p = achar(dados_dir, ["fill_medians_producao.json", "fill_medians_candidato.json"])
        feats = json.loads(feats_p.read_text(encoding="utf-8")) if feats_p else {"candidato": FEATURES_PRODUCAO_DEFAULT}
        meds = json.loads(meds_p.read_text(encoding="utf-8")) if meds_p else FILL_MEDIANAS_DEFAULT
        holdout = achar(dados_dir, ["teste_final_previsoes_promovido.parquet", "teste_final_previsoes.parquet"])
        ic_inf, ic_sup = ic80_do_holdout(holdout)
        upsert_parametro(session, "features_producao", feats)
        upsert_parametro(session, "fill_medians", meds)
        upsert_parametro(session, "ic80_inf", ic_inf)
        upsert_parametro(session, "ic80_sup", ic_sup)
        upsert_parametro(session, "versao_modelo", VERSAO_MODELO)
        session.commit()
        copiar_modelo(encontrados["modelo LightGBM (.txt)"])
        log("Carga concluída.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
