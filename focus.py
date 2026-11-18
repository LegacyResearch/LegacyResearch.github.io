"""
focus.py — Busca as projeções do Boletim Focus na API do Banco Central,
salva o histórico em CSV e gera os gráficos de IPCA, Selic, câmbio e PIB
nas cores da Legacy Research, um por indicador e um painel com os quatro.

Roda sozinho toda segunda-feira pelo GitHub Actions (.github/workflows/atualizar-focus.yml).
"""
from datetime import date
from pathlib import Path
from urllib.parse import quote

import matplotlib
matplotlib.use("Agg")  # gera a imagem sem precisar de tela (o GitHub roda sem monitor)
import matplotlib.dates
import matplotlib.pyplot as plt
import pandas as pd
import requests

# Anos que aparecem nos gráficos: o ano atual e o próximo (muda sozinho na virada do ano)
ANO = date.today().year
ANOS = [str(ANO), str(ANO + 1)]

PASTA_GRAFICOS = Path("graficos")
PASTA_DADOS = Path("dados")

# Cores da Legacy
FUNDO = "#000000"
TEXTO = "#FFFFFF"
GRADE = "#333333"
CORES = ["#00C8FF", "#3D6BFF"]  # azul fluorescente e azul royal

# Os indicadores: nome na API do Banco Central, título, unidade, nome do arquivo e escala mínima
INDICADORES = {
    "IPCA":      {"titulo": "IPCA",            "unidade": "%",        "arquivo": "ipca",   "meta": True},
    "Selic":     {"titulo": "Selic – fim do ano", "unidade": "% a.a.", "arquivo": "selic",  "meta": False, "faixa_minima": 3.0},
    "Câmbio":    {"titulo": "Câmbio – fim do ano", "unidade": r"R\$/US\$", "arquivo": "cambio", "meta": False, "faixa_minima": 1.0},
    "PIB Total": {"titulo": "PIB",             "unidade": "%",        "arquivo": "pib",    "meta": False, "faixa_minima": 2.0},
}


def buscar_dados(indicador):
    """Pede ao Banco Central as projeções de um indicador para os anos de ANOS."""
    anos_filtro = "%20or%20".join(f"DataReferencia%20eq%20'{a}'" for a in ANOS)
    nome = quote(indicador)  # "Câmbio" vira "C%C3%A2mbio", "PIB Total" vira "PIB%20Total"
    url = (
        "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
        f"?$filter=Indicador%20eq%20'{nome}'%20and%20({anos_filtro})%20and%20baseCalculo%20eq%200"
        "&$orderby=Data%20desc"
        "&$top=400"
        "&$format=json"
        "&$select=Indicador,Data,DataReferencia,Mediana"
    )
    headers = {"User-Agent": "Mozilla/5.0 (focus-tracker; Legacy Research)"}
    resposta = requests.get(url, headers=headers, timeout=60)
    resposta.raise_for_status()

    df = pd.DataFrame(resposta.json()["value"])
    df["Data"] = pd.to_datetime(df["Data"])
    return df.sort_values("Data")


def desenhar(ax, df, config):
    """Desenha um indicador num espaço de gráfico (ax): uma linha por ano."""
    ax.set_facecolor(FUNDO)

    # Só o IPCA tem meta: 3%, com tolerância de 1,5% a 4,5%
    if config["meta"]:
        ax.axhspan(1.5, 4.5, color="#FFFFFF", alpha=0.06)
        ax.axhline(3.0, color="#AAAAAA", linestyle="--", linewidth=1.2)
        ax.text(df["Data"].iloc[0], 3.0, " Meta 3%", color="#AAAAAA", va="bottom", fontsize=9)

    for ano, cor in zip(ANOS, CORES):
        dados = df[df["DataReferencia"] == ano]
        if dados.empty:
            continue
        ax.plot(dados["Data"], dados["Mediana"], color=cor, linewidth=2.5, label=ano)
        ultimo = dados.iloc[-1]
        ax.annotate(f"{ultimo['Mediana']:.2f}", (ultimo["Data"], ultimo["Mediana"]),
                    xytext=(8, 0), textcoords="offset points",
                    color=cor, fontweight="bold", va="center")

    # Escala mínima do eixo vertical: evita que mudanças pequenas pareçam enormes
    baixo, alto = ax.get_ylim()
    faixa = config.get("faixa_minima", 0)
    if alto - baixo < faixa:
        meio = (alto + baixo) / 2
        ax.set_ylim(meio - faixa / 2, meio + faixa / 2)

    ax.set_title(f"{config['titulo']} ({config['unidade']})", color=TEXTO, fontsize=13, fontweight="bold")
    ax.tick_params(colors=TEXTO)
    for borda in ax.spines.values():
        borda.set_color(GRADE)
    ax.grid(color=GRADE, linewidth=0.6)
    ax.margins(x=0.12)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d/%m"))
    ax.legend(facecolor=FUNDO, edgecolor=GRADE, labelcolor=TEXTO, loc="best", fontsize=9)


def salvar_figura(fig, nome):
    PASTA_GRAFICOS.mkdir(exist_ok=True)
    caminho = PASTA_GRAFICOS / nome
    fig.savefig(caminho, dpi=200, facecolor=FUNDO)
    plt.close(fig)
    return caminho


def gerar_graficos(tabelas):
    """Um gráfico por indicador e um painel 2x2 com todos."""
    data_txt = max(df["Data"].max() for df in tabelas.values()).strftime("%d/%m/%Y")
    rodape = f"Legacy Research · Fonte: Focus/BCB · projeções medianas · atualizado em {data_txt}"
    caminhos = []

    # Gráficos individuais
    for indicador, df in tabelas.items():
        config = INDICADORES[indicador]
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor(FUNDO)
        desenhar(ax, df, config)
        fig.text(0.99, 0.01, rodape, color="#888888", ha="right", fontsize=8)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        caminhos.append(salvar_figura(fig, f"{config['arquivo']}_focus.png"))

    # Painel com os quatro
    fig, eixos = plt.subplots(2, 2, figsize=(14, 9))
    fig.patch.set_facecolor(FUNDO)
    for ax, (indicador, df) in zip(eixos.flat, tabelas.items()):
        desenhar(ax, df, INDICADORES[indicador])
    fig.suptitle("Boletim Focus – projeções do mercado", color=TEXTO, fontsize=16, fontweight="bold")
    fig.text(0.99, 0.01, rodape, color="#888888", ha="right", fontsize=9)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    caminhos.append(salvar_figura(fig, "painel_focus.png"))
    return caminhos


def salvar_dados(tabelas):
    """Guarda todas as projeções num CSV, para ter o histórico no repositório."""
    PASTA_DADOS.mkdir(exist_ok=True)
    caminho = PASTA_DADOS / "focus.csv"
    pd.concat(tabelas.values()).to_csv(caminho, index=False)
    return caminho


if __name__ == "__main__":
    tabelas = {indicador: buscar_dados(indicador) for indicador in INDICADORES}
    print("Dados salvos em", salvar_dados(tabelas))
    for caminho in gerar_graficos(tabelas):
        print("Gráfico salvo em", caminho)
