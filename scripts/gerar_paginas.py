#!/usr/bin/env python3
"""
Gerador automático de páginas de produto + feed (Google Merchant / Meta Catalog).

Como usar quando tiveres um produto novo:
1. Abre data/produtos.json
2. Copia um bloco {...} existente, cola no fim da lista e edita os valores
   (titulo, preco, imagem, link_afiliado, especificacoes, etc.)
3. Corre: python3 scripts/gerar_paginas.py
   -> cria/atualiza produtos/<slug>.html, index.html e data/feed.csv

Não precisas de escrever HTML nem mexer no template — só editar o JSON.
"""
import json
import csv
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "produtos.json"
TEMPLATE_FILE = ROOT / "template.html"
OUT_DIR = ROOT / "produtos"
INDEX_FILE = ROOT / "index.html"
FEED_FILE = ROOT / "data" / "feed.csv"

SITE_BASE_URL = "https://destakalex.github.io/ofertas-mercadolivre"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text


def render_product(template: str, p: dict) -> str:
    html = template

    ideal_para = p.get("ideal_para", [])
    if ideal_para:
        items = "\n".join(f"<li>{item}</li>" for item in ideal_para)
        ideal_section = f'<section><h2>Para quem é indicado</h2><ul class="tags">{items}</ul></section>'
    else:
        ideal_section = ""

    specs = p.get("especificacoes", [])
    if specs:
        rows = "\n".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in specs)
        specs_section = f'<section><h2>Especificações principais</h2><table>{rows}</table></section>'
    else:
        specs_section = ""

    if p.get("tem_video"):
        video_section = ('<div class="video-note" id="video-slot">🎥 Vídeo de demonstração do produto — '
                          'substitua este bloco pelo embed do teu vídeo (TikTok/Instagram/YouTube Shorts).</div>')
    else:
        video_section = ""

    num_aval = p.get("num_avaliacoes", "")
    num_aval_txt = f" ({num_aval} avaliações)" if num_aval else ""
    marca = p.get("marca", "")
    marca_txt = f" · Marca {marca}" if marca else ""
    desconto = p.get("desconto", "")
    desconto_txt = f"{desconto}% OFF no saldo do Mercado Pago · " if desconto else ""

    replacements = {
        "{{TITULO}}": p["titulo"],
        "{{SELO}}": p.get("selo", "Recomendado"),
        "{{AVALIACAO}}": p.get("avaliacao", ""),
        "{{NUM_AVALIACOES_TXT}}": num_aval_txt,
        "{{MARCA_TXT}}": marca_txt,
        "{{VENDIDOS}}": p.get("vendidos", ""),
        "{{IMAGEM}}": p.get("imagem", ""),
        "{{PRECO_DE}}": p.get("preco_de", ""),
        "{{PRECO_POR}}": p.get("preco_por", ""),
        "{{PRECO_OUTROS_MEIOS}}": p.get("preco_outros_meios", ""),
        "{{DESCONTO_TXT}}": desconto_txt,
        "{{FRETE}}": p.get("frete", ""),
        "{{LINK_AFILIADO}}": p["link_afiliado"],
        "{{REVIEW_RESUMO}}": p.get("review_resumo", ""),
        "{{CATEGORIA}}": p.get("categoria", ""),
        "{{IDEAL_SECTION}}": ideal_section,
        "{{SPECS_SECTION}}": specs_section,
        "{{VIDEO_SECTION}}": video_section,
    }
    for k, v in replacements.items():
        html = html.replace(k, str(v))
    return html


def build_index(produtos: list) -> str:
    cards = []
    for p in produtos:
        slug = p.get("slug") or slugify(p["titulo"])
        cards.append(
            f'<a class="card" href="produtos/{slug}.html">'
            f'<img src="{p.get("imagem","")}" alt="">'
            f'<div class="card-body"><h3>{p["titulo"]}</h3>'
            f'<span class="price">R$ {p.get("preco_por","")}</span></div></a>'
        )
    cards_html = "\n".join(cards)
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ofertas selecionadas</title>
<style>
body{{background:#0f1115;color:#eef1f6;font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px;max-width:960px;margin:0 auto}}
.card{{background:#171a21;border:1px solid #262b35;border-radius:12px;overflow:hidden;text-decoration:none;color:inherit;display:block}}
.card img{{width:100%;height:160px;object-fit:cover}}
.card-body{{padding:10px 12px}}
.card h3{{font-size:14px;margin:0 0 6px;line-height:1.3}}
.price{{color:#35c46a;font-weight:800}}
h1{{max-width:960px;margin:0 auto 20px}}
</style></head>
<body><h1>Ofertas selecionadas</h1><div class="grid">{cards_html}</div></body></html>"""


def build_feed_row(p: dict, page_url: str) -> dict:
    return {
        "id": p.get("slug"),
        "title": p["titulo"][:150],
        "description": p.get("review_resumo", p["titulo"])[:5000],
        "link": page_url,
        "image_link": p.get("imagem", ""),
        "price": f'{p.get("preco_numerico", p.get("preco_por","0").replace(",", "."))} BRL',
        "availability": p.get("availability", "in stock"),
        "condition": "new",
        "brand": p.get("marca", ""),
    }


def main():
    produtos = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    feed_rows = []
    for p in produtos:
        slug = p.get("slug") or slugify(p["titulo"])
        p["slug"] = slug
        html = render_product(template, p)
        (OUT_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
        page_url = f"{SITE_BASE_URL}/produtos/{slug}.html"
        # produtos esgotados ficam fora do feed (deixam de ser anunciados),
        # mas a página continua a existir para quem já tem o link partilhado
        if p.get("availability", "in stock") == "in stock":
            feed_rows.append(build_feed_row(p, page_url))
        print(f"OK: produtos/{slug}.html" + ("" if p.get("availability","in stock")=="in stock" else " (ESGOTADO - fora do feed)"))

    INDEX_FILE.write_text(build_index(produtos), encoding="utf-8")
    print(f"OK: {INDEX_FILE.relative_to(ROOT)}")

    fieldnames = ["id", "title", "description", "link", "image_link", "price", "availability", "condition", "brand"]
    with FEED_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(feed_rows)
    print(f"OK: {FEED_FILE.relative_to(ROOT)} ({len(feed_rows)} produto(s))")


if __name__ == "__main__":
    main()
