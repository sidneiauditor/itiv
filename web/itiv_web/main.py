# -*- coding: utf-8 -*-
from __future__ import annotations

import html
import json
import traceback
import urllib.parse
import urllib.request
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from itiv_web.config import GOOGLE_SV_KEY, PORTA, STATIC_DIR, TEMPLATES_DIR
from itiv_web.db import SessionLocal, criar_schema, postgres_ok
from itiv_web.runtime import STATE
from itiv_web.servico_avaliacao import avaliar_cadastro, buscar

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _garantir_runtime() -> None:
    if STATE.pronto:
        return
    session = SessionLocal()
    try:
        STATE.carregar(session)
    finally:
        session.close()


def _pagina(request: Request, *, q: str, conteudo: str, action: str, aba: str, placeholder: str):
    return templates.TemplateResponse(
        request,
        "pagina.html",
        {
            "q": q,
            "conteudo": conteudo,
            "action": action,
            "ativa_tx": "ativa" if aba == "tx" else "",
            "ativa_cad": "ativa" if aba == "cad" else "",
            "placeholder": placeholder,
        },
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    criar_schema()
    session = SessionLocal()
    try:
        STATE.carregar(session)
        if STATE.pronto:
            print("Avaliador ITIV pronto.", flush=True)
        else:
            print(f"Aviso: servico subiu sem modelo/dados ({STATE.erro})", flush=True)
    finally:
        session.close()
    yield


app = FastAPI(title="Avaliador ITIV", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health():
    db_ok = postgres_ok()
    if db_ok and not STATE.pronto:
        _garantir_runtime()
    modelo_ok = STATE.pronto
    codigo = 200 if db_ok and modelo_ok else 503
    return JSONResponse(
        {
            "db": db_ok,
            "modelo": modelo_ok,
            "pool": int(len(STATE.pool)),
            "erro": STATE.erro,
        },
        status_code=codigo,
    )


@app.get("/geocode")
def geocode(lat: float, lon: float):
    if not GOOGLE_SV_KEY:
        return JSONResponse({"endereco": "", "status": "NO_KEY", "erro": "GOOGLE_SV_KEY nao configurada"})
    url = (
        "https://maps.googleapis.com/maps/api/geocode/json?"
        + urllib.parse.urlencode({"latlng": f"{lat},{lon}", "language": "pt-BR", "key": GOOGLE_SV_KEY})
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = data.get("results", [])
        endereco = results[0].get("formatted_address", "") if results else ""
        corpo = {"endereco": endereco, "status": data.get("status", ""), "erro": data.get("error_message", "")}
        headers = {"Cache-Control": "public, max-age=86400" if endereco else "no-store"}
        return JSONResponse(corpo, headers=headers)
    except Exception:  # noqa: BLE001
        return JSONResponse({"endereco": "", "status": "ERROR", "erro": "falha na API"}, status_code=502)


@app.get("/streetview")
def streetview(lat: float, lon: float):
    if not GOOGLE_SV_KEY:
        return Response(status_code=204)
    params = urllib.parse.urlencode(
        {"size": "260x130", "location": f"{lat},{lon}", "fov": "90", "pitch": "0", "key": GOOGLE_SV_KEY}
    )
    sv_url = f"https://maps.googleapis.com/maps/api/streetview?{params}"
    try:
        with urllib.request.urlopen(sv_url, timeout=10) as resp:
            img = resp.read()
        return Response(content=img, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    except Exception:  # noqa: BLE001
        return Response(status_code=502)


@app.get("/", response_class=HTMLResponse)
@app.get("/avaliar", response_class=HTMLResponse)
def avaliar(request: Request, q: str = Query(default="")):
    placeholder = "Digite o SQ da transmissao ou a inscricao imobiliaria (apartamento)"
    if not q:
        conteudo = (
            "<p>Digite um SQ ou inscricao acima (apenas Apartamento). "
            "Modelo com idade + inscrição relativa (26/08/2026).</p>"
        )
        return _pagina(request, q="", conteudo=conteudo, action="/avaliar", aba="tx", placeholder=placeholder)
    _garantir_runtime()
    session = SessionLocal()
    try:
        conteudo = buscar(session, q)
    except Exception as exc:  # noqa: BLE001
        conteudo = (
            f"<p class='erro'>Erro: {html.escape(str(exc))}</p>"
            f"<pre>{html.escape(traceback.format_exc()[-1500:])}</pre>"
        )
    finally:
        session.close()
    return _pagina(request, q=q, conteudo=conteudo, action="/avaliar", aba="tx", placeholder=placeholder)


@app.get("/cadastro", response_class=HTMLResponse)
def cadastro(request: Request, q: str = Query(default="")):
    placeholder = "Digite a inscricao imobiliaria"
    if not q:
        conteudo = "<p>Digite a inscricao imobiliaria (apartamento) para comparar o valor venal com o mercado.</p>"
        return _pagina(request, q="", conteudo=conteudo, action="/cadastro", aba="cad", placeholder=placeholder)
    q_clean = q.strip().replace(".", "").replace("-", "")
    if not q_clean.isdigit():
        conteudo = "<p class='erro'>Digite apenas numeros da inscricao imobiliaria.</p>"
        return _pagina(request, q=q, conteudo=conteudo, action="/cadastro", aba="cad", placeholder=placeholder)
    _garantir_runtime()
    session = SessionLocal()
    try:
        conteudo = avaliar_cadastro(session, int(q_clean))
    except Exception as exc:  # noqa: BLE001
        conteudo = (
            f"<p class='erro'>Erro: {html.escape(str(exc))}</p>"
            f"<pre>{html.escape(traceback.format_exc()[-1500:])}</pre>"
        )
    finally:
        session.close()
    return _pagina(request, q=q, conteudo=conteudo, action="/cadastro", aba="cad", placeholder=placeholder)


def main() -> None:
    import uvicorn

    uvicorn.run("itiv_web.main:app", host="0.0.0.0", port=PORTA, reload=False)


if __name__ == "__main__":
    main()
