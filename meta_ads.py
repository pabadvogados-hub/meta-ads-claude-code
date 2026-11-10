#!/usr/bin/env python3
"""
meta_ads.py - Ferramenta unica para criar e acompanhar campanhas na Meta (Facebook/Instagram Ads)
a partir do Claude Code.

REGRAS DE SEGURANCA (nao mude sem saber o que esta fazendo):
  1. Tudo que for CRIADO nasce PAUSADO. Voce confere no Gerenciador de Anuncios e so depois ativa.
  2. Sem a flag --executar o comando `criar` so MOSTRA o plano (nao grava nada na conta).
  3. Ativar exige --confirmo.
  4. O orcamento diario total e limitado por MAX_ORCAMENTO_DIARIO (.env).
  5. Os textos passam por um verificador do Provimento 205/2021 da OAB antes de subir.

Uso rapido:
  python meta_ads.py configurar      (cola o token e ele preenche o resto)
  python meta_ads.py testar
  python meta_ads.py contas
  python meta_ads.py paginas
  python meta_ads.py campanhas
  python meta_ads.py buscar-local "Guarulhos"
  python meta_ads.py validar exemplos/campanha_exemplo.json
  python meta_ads.py criar    exemplos/campanha_exemplo.json              (so mostra o plano)
  python meta_ads.py criar    exemplos/campanha_exemplo.json --executar   (cria, tudo PAUSADO)
  python meta_ads.py relatorio --periodo last_7d
  python meta_ads.py ativar  <id> --confirmo
  python meta_ads.py pausar  <id>
  python meta_ads.py orcamento <id_do_conjunto> 25
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("Falta instalar: pip install -r requirements.txt")

AQUI = Path(__file__).resolve().parent
VERSAO = os.getenv("META_API_VERSION", "v21.0")
BASE = f"https://graph.facebook.com/{VERSAO}"
CONVERSA = "onsite_conversion.messaging_conversation_started_7d"


# ------------------------------------------------------------------ .env
def carregar_env():
    p = AQUI / ".env"
    if not p.exists():
        return
    for linha in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        linha = linha.strip()
        if linha and not linha.startswith("#") and "=" in linha:
            k, v = linha.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


carregar_env()
TOKEN = os.getenv("META_ADS_TOKEN", "")
CONTA = os.getenv("META_AD_ACCOUNT", "")
PAGINA = os.getenv("META_PAGE_ID", "")
INSTAGRAM = os.getenv("META_INSTAGRAM_ID", "")
WHATSAPP = os.getenv("META_WHATSAPP_NUMERO", "")
TETO = float(os.getenv("MAX_ORCAMENTO_DIARIO", "100").replace(",", "."))


def exigir_token():
    if not TOKEN or TOKEN.startswith("COLE_AQUI"):
        sys.exit("META_ADS_TOKEN nao esta no arquivo .env. Veja o README, passo 3.")


# ------------------------------------------------------------------ HTTP
class ErroMeta(Exception):
    pass


def _erro(r):
    try:
        e = r.json().get("error", {})
        msg = e.get("error_user_msg") or e.get("message") or r.text[:300]
        return f"[{r.status_code}] {msg} (code {e.get('code')}/{e.get('error_subcode')})"
    except Exception:
        return f"[{r.status_code}] {r.text[:300]}"


def get(caminho, **params):
    exigir_token()
    params["access_token"] = TOKEN
    r = requests.get(f"{BASE}/{caminho}", params=params, timeout=90)
    if r.status_code != 200:
        raise ErroMeta(_erro(r))
    return r.json()


def get_todos(caminho, **params):
    """Segue a paginacao e devolve a lista completa."""
    out, url, first = [], None, True
    while True:
        if first:
            d = get(caminho, **params)
            first = False
        else:
            r = requests.get(url, timeout=90)
            if r.status_code != 200:
                raise ErroMeta(_erro(r))
            d = r.json()
        out += d.get("data", [])
        url = d.get("paging", {}).get("next")
        if not url:
            return out


def post(caminho, dados=None, arquivos=None, validar=False):
    exigir_token()
    dados = dict(dados or {})
    dados["access_token"] = TOKEN
    if validar:
        dados["execution_options"] = json.dumps(["validate_only"])
    for k, v in list(dados.items()):
        if isinstance(v, (dict, list)):
            dados[k] = json.dumps(v, ensure_ascii=False)
    r = requests.post(f"{BASE}/{caminho}", data=dados, files=arquivos, timeout=600)
    if r.status_code not in (200, 201):
        raise ErroMeta(_erro(r))
    return r.json()


# ------------------------------------------------------------------ Provimento 205/2021
# Lista de alerta, nao de proibicao absoluta: o advogado decide. Serve para pegar o erro comum.
PROIBIDOS = [
    (r"\bgarant\w*", "promessa/garantia de resultado"),
    (r"\b100\s?%", "promessa de resultado"),
    (r"\bsucesso\s+(certo|garantido|absoluto)", "promessa de resultado"),
    (r"\bganh(e|amos|ar)\b.{0,25}(causa|processo|dinheiro|indeniza)", "promessa de resultado"),
    (r"\bgr[aá]tis\b|\bgratuit\w*|\bsem custo\b|\bde gra[cç]a\b", "oferta gratuita / chamariz"),
    (r"\bpromo[cç][aã]o\b|\bdesconto\b|\boferta imperd\w*|\bliquida[cç][aã]o\b", "linguagem de mercado"),
    (r"\bhonor[aá]rios?\b|\bR\$\s?\d", "valor ou honorario no anuncio"),
    (r"\bn[uú]mero\s*1\b|\bmelhor\s+advogad\w*|\bmelhor\s+escrit\w*|\bl[ií]der\b", "autopromocao / superioridade"),
    (r"\bclique (agora|j[aá])\b|\bchame agora\b|\bultimas vagas\b|\búltimas vagas\b|\bapenas hoje\b", "captacao ostensiva / urgencia"),
    (r"\bindeniza[cç][aã]o\s+(certa|garantida|na hora)", "promessa de resultado"),
]


def sem_acento(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def verificar_oab(textos):
    """textos: dict nome -> texto. Retorna lista de (onde, trecho, motivo)."""
    achados = []
    for onde, texto in textos.items():
        if not texto:
            continue
        for padrao, motivo in PROIBIDOS:
            for m in re.finditer(padrao, texto, flags=re.IGNORECASE):
                achados.append((onde, m.group(0), motivo))
    return achados


# ------------------------------------------------------------------ localizacao
def buscar_local(texto, tipo="city", pais="BR"):
    d = get("search", type="adgeolocation", q=texto, location_types=json.dumps([tipo]),
            country_code=pais, limit=8)
    return d.get("data", [])


def resolver_locais(loc):
    """Converte nomes em chaves da Meta. loc = {paises, regioes, cidades:[{nome, raio_km}]}"""
    geo = {}
    if loc.get("paises"):
        geo["countries"] = loc["paises"]
    regs = []
    for nome in loc.get("regioes", []):
        r = buscar_local(nome, "region")
        if not r:
            raise ErroMeta(f"Regiao nao encontrada: {nome}")
        regs.append({"key": r[0]["key"]})
    if regs:
        geo["regions"] = regs
    cids = []
    for c in loc.get("cidades", []):
        nome = c["nome"] if isinstance(c, dict) else c
        raio = c.get("raio_km", 17) if isinstance(c, dict) else 17
        r = buscar_local(nome, "city")
        if not r:
            raise ErroMeta(f"Cidade nao encontrada: {nome}")
        cids.append({"key": r[0]["key"], "radius": raio, "distance_unit": "kilometer"})
    if cids:
        geo["cities"] = cids
    if not geo:
        raise ErroMeta("Defina ao menos um local (paises, regioes ou cidades).")
    return geo


# ------------------------------------------------------------------ configuracao guiada
def _gravar_env(valores):
    p = AQUI / ".env"
    linhas = p.read_text(encoding="utf-8").splitlines() if p.exists() else \
        (AQUI / ".env.example").read_text(encoding="utf-8").splitlines()
    feitos = set()
    for i, l in enumerate(linhas):
        k = l.split("=", 1)[0].strip()
        if "=" in l and not l.strip().startswith("#") and k in valores:
            linhas[i] = f"{k}={valores[k]}"
            feitos.add(k)
    for k, v in valores.items():
        if k not in feitos:
            linhas.append(f"{k}={v}")
    p.write_text("\n".join(linhas) + "\n", encoding="utf-8")


def _escolher(titulo, itens):
    """itens: lista de (valor, descricao). Devolve o valor escolhido."""
    if len(itens) == 1:
        print(f"  {titulo}: {itens[0][1]}")
        return itens[0][0]
    print(f"  {titulo}:")
    for i, (_, d) in enumerate(itens, 1):
        print(f"    {i}) {d}")
    while True:
        r = input("  Número da escolha: ").strip()
        if r.isdigit() and 1 <= int(r) <= len(itens):
            return itens[int(r) - 1][0]


def cmd_configurar(_):
    """Pede o token (e o WhatsApp), descobre conta e pagina sozinho e grava o .env."""
    import getpass
    global TOKEN, CONTA, PAGINA, INSTAGRAM, WHATSAPP
    print("Cole o token da Meta (não aparece na tela enquanto você cola) e aperte Enter.")
    tok = getpass.getpass("Token: ").strip()
    if len(tok) < 50:
        sys.exit("Isso não parece um token da Meta (muito curto). Veja o README, passo 3.")
    TOKEN = tok
    try:
        me = get("me", fields="id,name")
    except ErroMeta as e:
        sys.exit(f"A Meta não aceitou esse token: {e}")
    print(f"Token aceito. Conectado como: {me.get('name')}")
    contas = [c for c in get_todos("me/adaccounts", fields="name,account_id,account_status", limit=100)
              if c.get("account_status") == 1]
    if not contas:
        sys.exit("Nenhuma conta de anúncio ativa visível. Atribua a conta ao usuário do sistema (README, passo 3.3).")
    CONTA = "act_" + _escolher("Conta de anúncio", [(f"{c['account_id']}", f"{c['name']} (act_{c['account_id']})") for c in contas])
    paginas = get_todos("me/accounts", fields="id,name,instagram_business_account", limit=100)
    if not paginas:
        sys.exit("Nenhuma Página visível. Atribua a Página ao usuário do sistema (README, passo 3.3).")
    pg = _escolher("Página do Facebook", [(p["id"], p["name"]) for p in paginas])
    ig = next((p.get("instagram_business_account", {}).get("id", "") for p in paginas if p["id"] == pg), "")
    wa = input("  WhatsApp que recebe os leads, com DDI e DDD (ex.: +5511999999999): ").strip()
    _gravar_env({"META_ADS_TOKEN": tok, "META_AD_ACCOUNT": CONTA, "META_PAGE_ID": pg,
                 "META_INSTAGRAM_ID": ig, "META_WHATSAPP_NUMERO": wa})
    print("\nPronto: .env gravado. Rode agora:  python meta_ads.py testar")


# ------------------------------------------------------------------ comandos de leitura
def cmd_testar(_):
    exigir_token()
    print("Token presente. Testando na Meta...")
    me = get("me", fields="id,name")
    print(f"  Conectado como: {me.get('name')} ({me.get('id')})")
    try:
        dbg = get("debug_token", input_token=TOKEN)
        perm = dbg.get("data", {}).get("scopes", [])
        print("  Permissoes do token:", ", ".join(perm) or "(nao informado)")
        falta = [p for p in ("ads_management", "ads_read", "business_management") if p not in perm]
        if falta:
            print("  ATENCAO - faltam permissoes para CRIAR campanha:", ", ".join(falta))
    except ErroMeta:
        print("  (nao consegui listar as permissoes; siga em frente e veja se `contas` funciona)")
    contas = get("me/adaccounts", fields="name,account_id,account_status", limit=50).get("data", [])
    print(f"  Contas de anuncio visiveis: {len(contas)}")
    for c in contas:
        print(f"    - {c.get('name')}  act_{c.get('account_id')}")
    print(f"  META_AD_ACCOUNT no .env: {CONTA or '(vazio)'}")
    print(f"  META_PAGE_ID no .env:    {PAGINA or '(vazio - rode: python meta_ads.py paginas)'}")
    print(f"  Teto diario:             R$ {TETO:.2f}")


def cmd_contas(_):
    for c in get_todos("me/adaccounts", fields="name,account_id,currency,account_status,amount_spent", limit=100):
        st = {1: "ativa", 2: "desativada", 3: "pendente de pagamento"}.get(c.get("account_status"), c.get("account_status"))
        print(f"act_{c['account_id']}  {c.get('name')}  [{st}]  moeda {c.get('currency')}")


def cmd_paginas(_):
    ps = get_todos("me/accounts", fields="id,name,instagram_business_account", limit=100)
    if not ps:
        print("Nenhuma pagina visivel. No Business Manager, adicione a Pagina como ATIVO do usuario do sistema (README, passo 3).")
    for p in ps:
        ig = p.get("instagram_business_account", {}).get("id", "-")
        print(f"{p['id']}  {p['name']}  (instagram {ig})")


def cmd_buscar_local(a):
    for tipo in ("city", "region"):
        for r in buscar_local(a.texto, tipo):
            print(f"{tipo:7} {r.get('name')} - {r.get('region', '')}  (key {r.get('key')})")


def cmd_campanhas(a):
    conta = a.conta or CONTA
    camps = get_todos(f"{conta}/campaigns",
                      fields="id,name,status,effective_status,objective,created_time", limit=200)
    for c in camps:
        if a.ativas and c.get("effective_status") != "ACTIVE":
            continue
        print(f"{c['id']}  {c.get('effective_status'):10}  {c['name']}")


def _conversas(acts):
    for x in acts or []:
        if x.get("action_type") == CONVERSA:
            return int(float(x["value"]))
    return 0


def cmd_relatorio(a):
    conta = a.conta or CONTA
    nivel = a.nivel
    campos = "campaign_name,adset_name,ad_name,spend,impressions,clicks,ctr,actions"
    linhas = get_todos(f"{a.id or conta}/insights", level=nivel, fields=campos,
                       date_preset=a.periodo, limit=500)
    if not linhas:
        print("Sem dados nesse periodo.")
        return
    print(f"{'NOME':50} {'GASTO':>9} {'CONV':>5} {'R$/CONV':>9} {'CTR%':>6}")
    tot_g = tot_c = 0
    for r in sorted(linhas, key=lambda x: -float(x.get("spend", 0))):
        nome = r.get({"campaign": "campaign_name", "adset": "adset_name", "ad": "ad_name"}[nivel], "?")
        g = float(r.get("spend", 0))
        c = _conversas(r.get("actions"))
        tot_g += g
        tot_c += c
        cpc = f"{g / c:9.2f}" if c else "   sem conv"
        print(f"{nome[:50]:50} {g:9.2f} {c:5d} {cpc} {float(r.get('ctr', 0)):6.2f}")
    print("-" * 84)
    print(f"{'TOTAL':50} {tot_g:9.2f} {tot_c:5d} {(tot_g / tot_c if tot_c else 0):9.2f}")
    print("\nLembrete: decida pelo CUSTO POR CONTRATO ASSINADO (planilha), nao so por conversa.")


# ------------------------------------------------------------------ alteracoes simples
def cmd_pausar(a):
    post(a.id, {"status": "PAUSED"})
    print("Pausado:", a.id)


def cmd_ativar(a):
    if not a.confirmo:
        sys.exit("Para ativar (comeca a gastar dinheiro de verdade) rode de novo com --confirmo.")
    post(a.id, {"status": "ACTIVE"})
    print("ATIVADO:", a.id)


def cmd_orcamento(a):
    if a.reais > TETO:
        sys.exit(f"R$ {a.reais:.2f} passa do teto diario (MAX_ORCAMENTO_DIARIO = R$ {TETO:.2f}).")
    post(a.id, {"daily_budget": int(round(a.reais * 100))})
    print(f"Orcamento diario do conjunto {a.id}: R$ {a.reais:.2f}")


# ------------------------------------------------------------------ especificacao da campanha
def carregar_spec(caminho):
    p = Path(caminho)
    if not p.exists():
        sys.exit(f"Arquivo nao encontrado: {caminho}")
    spec = json.loads(p.read_text(encoding="utf-8"))
    spec["_pasta"] = str(p.resolve().parent)
    return spec


def textos_da_spec(spec):
    t = {"mensagem_inicial": spec.get("mensagem_inicial", "")}
    for cj in spec.get("conjuntos", []):
        for ad in cj.get("anuncios", []):
            cod = ad.get("codigo", "?")
            for campo in ("texto_principal", "titulo", "descricao"):
                t[f"{cod}.{campo}"] = ad.get(campo, "")
    return t


def validar_spec(spec, falar=True):
    erros, avisos = [], []
    for campo in ("nome_campanha", "conjuntos"):
        if not spec.get(campo):
            erros.append(f"Falta '{campo}' no JSON.")
    if not (spec.get("pagina_id") or PAGINA):
        erros.append("Falta pagina_id (JSON) ou META_PAGE_ID (.env). Rode: python meta_ads.py paginas")
    if not (spec.get("conta") or CONTA):
        erros.append("Falta a conta de anuncio (META_AD_ACCOUNT no .env).")
    if spec.get("destino", "WHATSAPP") == "WHATSAPP" and not (spec.get("whatsapp_numero") or WHATSAPP):
        erros.append("Falta o numero do WhatsApp (whatsapp_numero no JSON ou META_WHATSAPP_NUMERO no .env), com DDI. Ex.: +5511999999999")
    total = 0.0
    codigos = set()
    for i, cj in enumerate(spec.get("conjuntos", []), 1):
        nome = cj.get("nome", f"conjunto {i}")
        if not cj.get("orcamento_diario"):
            erros.append(f"{nome}: falta orcamento_diario (em reais).")
        else:
            total += float(cj["orcamento_diario"])
        if not cj.get("locais"):
            erros.append(f"{nome}: faltam os locais.")
        if not cj.get("anuncios"):
            erros.append(f"{nome}: nenhum anuncio.")
        for ad in cj.get("anuncios", []):
            cod = ad.get("codigo")
            if not cod:
                erros.append(f"{nome}: anuncio sem 'codigo' (A1, A2...). Sem codigo voce nao sabe qual anuncio fecha contrato.")
            elif cod in codigos:
                erros.append(f"Codigo repetido: {cod}. Nunca reaproveite um codigo.")
            codigos.add(cod)
            if not (ad.get("video") or ad.get("imagem")):
                erros.append(f"{cod}: informe 'video' ou 'imagem' (arquivo da pasta midia/ ou ID ja na Meta).")
            if not ad.get("texto_principal"):
                erros.append(f"{cod}: falta texto_principal.")
            m = spec.get("mensagem_inicial", "")
            if cod and m and f"[{cod}]" not in m and not ad.get("mensagem_inicial"):
                avisos.append(f"{cod}: a mensagem_inicial geral nao traz [{cod}]; use mensagem_inicial no anuncio.")
    if total > TETO:
        erros.append(f"Orcamento diario somado R$ {total:.2f} passa do teto R$ {TETO:.2f} (MAX_ORCAMENTO_DIARIO no .env).")
    oab = verificar_oab(textos_da_spec(spec))
    if falar:
        print(f"Campanha: {spec.get('nome_campanha')}")
        print(f"Orcamento diario somado: R$ {total:.2f}  (teto R$ {TETO:.2f})")
        for e in erros:
            print("  ERRO:", e)
        for v in avisos:
            print("  AVISO:", v)
        if oab:
            print("\n  PROVIMENTO 205/2021 - revise estes trechos antes de subir:")
            for onde, trecho, motivo in oab:
                print(f"    [{onde}] \"{trecho}\"  ->  {motivo}")
        if not erros and not oab:
            print("  OK: estrutura valida e nenhum alerta do Provimento 205.")
    return erros, oab, total


# ------------------------------------------------------------------ criacao
def subir_video(conta, ref, pasta):
    """ref = caminho de arquivo (relativo ao JSON ou a midia/) ou ID numerico de video ja na Meta."""
    if str(ref).isdigit():
        return str(ref)
    p = Path(ref)
    for cand in (p, Path(pasta) / ref, AQUI / "midia" / ref):
        if cand.exists():
            p = cand
            break
    else:
        raise ErroMeta(f"Video nao encontrado: {ref}")
    print(f"    enviando video {p.name} ({p.stat().st_size / 1e6:.1f} MB)...")
    with open(p, "rb") as f:
        vid = post(f"{conta}/advideos", {"name": p.stem}, arquivos={"source": f})["id"]
    for _ in range(90):  # ate ~7 min
        st = get(vid, fields="status").get("status", {}).get("video_status")
        if st == "ready":
            return vid
        if st == "error":
            raise ErroMeta(f"A Meta rejeitou o video {p.name}.")
        time.sleep(5)
    raise ErroMeta(f"Video {p.name} ainda processando; tente de novo em alguns minutos (id {vid}).")


def subir_imagem(conta, ref, pasta):
    p = Path(ref)
    for cand in (p, Path(pasta) / ref, AQUI / "midia" / ref):
        if cand.exists():
            p = cand
            break
    else:
        raise ErroMeta(f"Imagem nao encontrada: {ref}")
    with open(p, "rb") as f:
        d = post(f"{conta}/adimages", arquivos={"filename": f})
    return list(d["images"].values())[0]["hash"]


def mensagem_boas_vindas(texto):
    """Texto pre-preenchido que aparece no WhatsApp do cliente (formato 'autofill_message')."""
    return json.dumps({
        "type": "VISUAL_EDITOR", "version": 2, "landing_screen_type": "welcome_message",
        "media_type": "text",
        "text_format": {"customer_action_type": "autofill_message",
                        "message": {"autofill_message": {"content": texto}, "text": ""}},
    }, ensure_ascii=False)


def montar_criativo(conta, pagina, spec, ad, pasta):
    destino = spec.get("destino", "WHATSAPP")
    msg = ad.get("mensagem_inicial") or spec.get("mensagem_inicial", "")
    cta = {"type": "WHATSAPP_MESSAGE", "value": {"app_destination": "WHATSAPP"}} if destino == "WHATSAPP" \
        else {"type": "LEARN_MORE", "value": {"link": spec.get("link", "")}}
    oss = {"page_id": pagina}
    ig = spec.get("instagram_id") or INSTAGRAM
    if ig:
        oss["instagram_user_id"] = ig
    if ad.get("video"):
        vid = subir_video(conta, ad["video"], pasta)
        capa = get(vid, fields="picture").get("picture", "")
        vd = {"video_id": vid, "message": ad["texto_principal"], "call_to_action": cta}
        if capa:
            vd["image_url"] = capa
        if ad.get("titulo"):
            vd["title"] = ad["titulo"]
        if ad.get("descricao"):
            vd["link_description"] = ad["descricao"]
        if destino == "WHATSAPP" and msg:
            vd["page_welcome_message"] = mensagem_boas_vindas(msg)
        oss["video_data"] = vd
    else:
        h = subir_imagem(conta, ad["imagem"], pasta)
        ld = {"image_hash": h, "message": ad["texto_principal"], "call_to_action": cta,
              "link": "https://api.whatsapp.com/send" if destino == "WHATSAPP" else spec.get("link", "")}
        if ad.get("titulo"):
            ld["name"] = ad["titulo"]
        if ad.get("descricao"):
            ld["description"] = ad["descricao"]
        if destino == "WHATSAPP" and msg:
            ld["page_welcome_message"] = mensagem_boas_vindas(msg)
        oss["link_data"] = ld
    return {"name": f"[{ad['codigo']}] {ad.get('nome', 'criativo')}", "object_story_spec": oss}


def cmd_validar(a):
    spec = carregar_spec(a.arquivo)
    erros, oab, _ = validar_spec(spec)
    sys.exit(1 if erros else 0)


def cmd_criar(a):
    spec = carregar_spec(a.arquivo)
    erros, oab, total = validar_spec(spec)
    if erros:
        sys.exit("\nCorrija os erros acima e rode de novo.")
    if oab and not a.ignorar_oab:
        sys.exit("\nTrechos do Provimento 205 acima precisam de revisao do advogado. "
                 "Ajuste o texto (recomendado) ou, se o advogado responsavel aprovou, use --ignorar-oab.")
    conta = spec.get("conta") or CONTA
    pagina = spec.get("pagina_id") or PAGINA
    numero = re.sub(r"\D", "", spec.get("whatsapp_numero") or WHATSAPP)
    destino = spec.get("destino", "WHATSAPP")
    exigir_token()

    print("\nPLANO (nada foi criado ainda)" if not a.executar else "\nCRIANDO (tudo nasce PAUSADO)")
    print(f"  campanha: {spec['nome_campanha']}")
    for cj in spec["conjuntos"]:
        print(f"  conjunto: {cj['nome']}  R$ {cj['orcamento_diario']}/dia  anuncios: "
              + ", ".join(ad['codigo'] for ad in cj['anuncios']))

    camp_payload = {
        "name": spec["nome_campanha"],
        "objective": "OUTCOME_ENGAGEMENT" if destino == "WHATSAPP" else "OUTCOME_TRAFFIC",
        "status": "PAUSED",
        "special_ad_categories": [],
        "is_adset_budget_sharing_enabled": False,
    }
    # valida sem gravar
    try:
        post(f"{conta}/campaigns", camp_payload, validar=True)
        print("  [ok] a Meta aceitou o formato da campanha")
    except ErroMeta as e:
        sys.exit(f"  [erro] a Meta recusou a campanha: {e}")

    if not a.executar:
        print("\nPara criar de verdade: repita o comando com --executar")
        return

    camp = post(f"{conta}/campaigns", camp_payload)["id"]
    print(f"  campanha criada: {camp} (PAUSADA)")
    resultado = {"campanha": camp, "conjuntos": []}
    pasta = spec["_pasta"]
    for cj in spec["conjuntos"]:
        geo = resolver_locais(cj["locais"])
        targeting = {
            "geo_locations": geo,
            "age_min": cj.get("idade_min", 25),
            "age_max": cj.get("idade_max", 65),
            "publisher_platforms": cj.get("plataformas", ["facebook", "instagram"]),
            "targeting_automation": {"advantage_audience": 0},
        }
        if cj.get("genero") in (1, 2):
            targeting["genders"] = [cj["genero"]]
        adset = {
            "name": cj["nome"], "campaign_id": camp, "status": "PAUSED",
            "daily_budget": int(round(float(cj["orcamento_diario"]) * 100)),
            "billing_event": "IMPRESSIONS", "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "optimization_goal": "CONVERSATIONS" if destino == "WHATSAPP" else "LINK_CLICKS",
            "targeting": targeting,
        }
        if destino == "WHATSAPP":
            adset["destination_type"] = "WHATSAPP"
            adset["promoted_object"] = {"page_id": pagina, "whatsapp_phone_number": numero}
        else:
            adset["destination_type"] = "WEBSITE"
        cid = post(f"{conta}/adsets", adset)["id"]
        print(f"  conjunto criado: {cid}  {cj['nome']}")
        item = {"id": cid, "nome": cj["nome"], "anuncios": []}
        for ad in cj["anuncios"]:
            cr = post(f"{conta}/adcreatives", montar_criativo(conta, pagina, spec, ad, pasta))["id"]
            aid = post(f"{conta}/ads", {
                "name": f"[{ad['codigo']}] {ad.get('nome', 'anuncio')}", "adset_id": cid,
                "creative": {"creative_id": cr}, "status": "PAUSED"})["id"]
            print(f"    anuncio criado: {aid}  [{ad['codigo']}]")
            item["anuncios"].append({"id": aid, "codigo": ad["codigo"]})
        resultado["conjuntos"].append(item)

    saida = AQUI / "campanhas_criadas.json"
    hist = json.loads(saida.read_text(encoding="utf-8")) if saida.exists() else []
    hist.append({"quando": time.strftime("%Y-%m-%d %H:%M"), **resultado})
    saida.write_text(json.dumps(hist, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nPRONTO. Tudo esta PAUSADO. Proximo passo:")
    print("  1) Abra o Gerenciador de Anuncios e confira anuncio, texto, publico e a mensagem do WhatsApp.")
    print(f"  2) Se estiver certo:  python meta_ads.py ativar {camp} --confirmo")
    print("     (ative tambem os conjuntos e anuncios se estiverem pausados)")
    print("  3) Nos proximos 7 dias NAO mexa em video nem texto. So a verba.")


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description="Meta Ads pelo Claude Code")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("configurar").set_defaults(f=cmd_configurar)
    sub.add_parser("testar").set_defaults(f=cmd_testar)
    sub.add_parser("contas").set_defaults(f=cmd_contas)
    sub.add_parser("paginas").set_defaults(f=cmd_paginas)
    p = sub.add_parser("buscar-local"); p.add_argument("texto"); p.set_defaults(f=cmd_buscar_local)
    p = sub.add_parser("campanhas"); p.add_argument("--conta"); p.add_argument("--ativas", action="store_true"); p.set_defaults(f=cmd_campanhas)
    p = sub.add_parser("relatorio"); p.add_argument("--id"); p.add_argument("--conta")
    p.add_argument("--periodo", default="last_7d"); p.add_argument("--nivel", default="ad", choices=["campaign", "adset", "ad"]); p.set_defaults(f=cmd_relatorio)
    p = sub.add_parser("validar"); p.add_argument("arquivo"); p.set_defaults(f=cmd_validar)
    p = sub.add_parser("criar"); p.add_argument("arquivo"); p.add_argument("--executar", action="store_true")
    p.add_argument("--ignorar-oab", action="store_true"); p.set_defaults(f=cmd_criar)
    p = sub.add_parser("pausar"); p.add_argument("id"); p.set_defaults(f=cmd_pausar)
    p = sub.add_parser("ativar"); p.add_argument("id"); p.add_argument("--confirmo", action="store_true"); p.set_defaults(f=cmd_ativar)
    p = sub.add_parser("orcamento"); p.add_argument("id"); p.add_argument("reais", type=float); p.set_defaults(f=cmd_orcamento)
    a = ap.parse_args()
    try:
        a.f(a)
    except ErroMeta as e:
        sys.exit(f"Erro da Meta: {e}")


if __name__ == "__main__":
    main()
