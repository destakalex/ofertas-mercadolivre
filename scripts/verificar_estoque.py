#!/usr/bin/env python3
"""
Verificação diária de stock — evita gastar em anúncios de produtos esgotados.

O que faz:
1. Lê data/produtos.json
2. Visita a página de cada produto no Mercado Livre (via requests)
3. Marca availability = "in stock" ou "out of stock" no feed
4. Produtos esgotados saem do feed.csv (o Google/Meta param de anunciar
   automaticamente esse produto assim que ele desaparece do feed)
5. Regenera o feed.csv e o index.html

Como correr: python3 scripts/verificar_estoque.py
Pensado para ser chamado todos os dias por uma tarefa agendada.

NOTA IMPORTANTE: em alguns ambientes (incluindo o sandbox usado pelo Claude
para construir isto), o acesso direto por "requests" a meli.la/mercadolivre
pode ser bloqueado por política de rede/proxy. Nesse caso, a verificação
diária real corre como tarefa agendada do Claude (que usa a ferramenta de
navegação/fetch em vez de "requests" puro) — este script serve na mesma
como referência da lógica e funciona normalmente em hosting normal
(HostGator/ServeShark/GitHub Actions), onde não há esse bloqueio.
"""
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "produtos.json"

OUT_OF_STOCK_MARKERS = [
    "produto sem estoque",
    "sem estoque no momento",
    "não há mais unidades",
    "esgotado",
]
IN_STOCK_MARKERS = [
    "estoque disponível",
    "comprar agora",
    "adicionar ao carrinho",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def check_stock(product_url: str) -> bool:
    """Devolve True se o produto parece disponível, False se esgotado."""
    try:
        r = requests.get(product_url, headers=HEADERS, timeout=15, allow_redirects=True)
        text = r.text.lower()
    except Exception as e:
        print(f"  aviso: falha ao verificar {product_url}: {e}", file=sys.stderr)
        return True  # em caso de dúvida, não remove o produto

    if any(m in text for m in OUT_OF_STOCK_MARKERS):
        return False
    if any(m in text for m in IN_STOCK_MARKERS):
        return True
    return True  # não encontrou nenhum marcador claro -> assume disponível


def main():
    produtos = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    mudou = False

    for p in produtos:
        disponivel = check_stock(p["link_afiliado"])
        novo_estado = "in stock" if disponivel else "out of stock"
        if p.get("availability") != novo_estado:
            mudou = True
            print(f"{'OK ' if disponivel else 'ESGOTOU '} {p['titulo'][:60]} -> {novo_estado}")
        p["availability"] = novo_estado

    DATA_FILE.write_text(json.dumps(produtos, ensure_ascii=False, indent=2), encoding="utf-8")

    if mudou:
        print("Stock mudou para pelo menos 1 produto — a regenerar páginas e feed...")
    else:
        print("Sem alterações de stock hoje.")

    # regenera sempre feed.csv/index.html para refletir o campo availability atual
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "scripts" / "gerar_paginas.py")], check=True)


if __name__ == "__main__":
    main()
