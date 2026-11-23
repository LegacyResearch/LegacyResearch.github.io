"""
focus_mobile.py — Gera a versão "para post" do painel do Focus, feita para ler no celular:
fundo branco, letra grande, vírgula decimal e só os últimos meses.

Usa o CSV que o focus.py já salva (dados/focus.csv), então não chama a API de novo.
Saídas:
  graficos/focus_post.png        -> painel 2x2 para o carrossel
  dados/focus_comparacao.csv     -> números da comparação de duas semanas (para o texto do post)

Rodar depois do focus.py:  python focus_mobile.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # gera a imagem sem tela (o GitHub Actions roda sem monitor)
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter, MaxNLocator

ARQUIVO_DADOS = Path("dados/focus.csv")
SAIDA_GRAFICO = Path("graficos/focus_post.png")
SAIDA_TABELA = Path("dados/focus_comparacao.csv")

MESES_NA_TELA = 4      # quantos meses de histórico o gráfico mostra
SEMANAS_COMPARACAO = 2  # compara com o Focus de duas semanas antes

# Cores do carrossel da Legacy (versão clara)
PRETO, AZUL, CINZA, GRADE, FAIXA = "#0B0D10", "#2456D6", "#6B7380", "#E3E6EA", "#EAF0FD"

# Indicador na API -> título no gráfico, escala mínima do eixo e casas decimais do eixo
INDICADORES = {
    "IPCA":      {"titulo": "IPCA (%)",                 "faixa_minima": 0.6, "casas_eixo": 1},
    "Selic":     {"titulo": "Selic no fim do ano (%)",  "faixa_minima": 1.2, "casas_eixo": 1},
    "Câmbio":    {"titulo": "Dólar no fim do ano (R$)", "faixa_minima": 0.3, "casas_eixo": 2},
    "PIB Total": {"titulo": "PIB (%)",                  "faixa_minima": 0.8, "casas_eixo": 1},
}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def virgula(valor, casas=2):
    """5.1214 -> '5,12' (padrão brasileiro)."""
    return f"{valor:.{casas}f}".replace(".", ",")


def usar_fonte_inter():
    """Usa a Inter se estiver instalada; se não, fica a fonte padrão do matplotlib."""
    for arquivo in font_manager.findSystemFonts():
        if "Inter" in Path(arquivo).name:
            font_manager.fontManager.addfont(arquivo)
            plt.rcParams["font.family"] = "Inter"


def valor_em(serie, data):
    """Último valor disponível até uma data (o Focus não tem dado em fim de semana e feriado)."""
    return serie[serie["Data"] <= data].iloc[-1]


def desenhar(ax, df, indicador, anos, inicio, base, fim, linhas_tabela):
    cfg = INDICADORES[indicador]
    dados = df[df["Indicador"] == indicador]

    # Faixa azul clara: as duas últimas semanas, que é o que o post compara
    ax.axvspan(base, fim, color=FAIXA, zorder=0)

    finais = []
    for ano, cor in zip(anos, (PRETO, AZUL)):
        serie = dados[dados["DataReferencia"] == ano].sort_values("Data")
        if serie.empty:
            continue
        tela = serie[serie["Data"] >= inicio]
        ax.plot(tela["Data"], tela["Mediana"], color=cor, linewidth=2.6, zorder=3)
        antes, agora = valor_em(serie, base), serie.iloc[-1]
        finais.append((ano, cor, agora))
        linhas_tabela.append({
            "Indicador": indicador, "Ano": ano,
            "Data_base": antes["Data"].date(), "Valor_base": round(antes["Mediana"], 2),
            "Data_final": agora["Data"].date(), "Valor_final": round(agora["Mediana"], 2),
        })

    # Escala mínima: evita que uma mudança pequena pareça enorme
    baixo, alto = ax.get_ylim()
    if alto - baixo < cfg["faixa_minima"]:
        meio = (alto + baixo) / 2
        ax.set_ylim(meio - cfg["faixa_minima"] / 2, meio + cfg["faixa_minima"] / 2)
    baixo, alto = ax.get_ylim()

    # Valor escrito no fim de cada linha; se os dois estão colados, afasta um para cima e outro para baixo
    perto = len(finais) == 2 and abs(finais[0][2]["Mediana"] - finais[1][2]["Mediana"]) / (alto - baixo) < 0.12
    for ano, cor, ponto in finais:
        outro = [f[2]["Mediana"] for f in finais if f[0] != ano]
        desvio = 0
        if perto:
            desvio = 10 if ponto["Mediana"] >= outro[0] else -10
        ax.annotate(f"{ano}: {virgula(ponto['Mediana'])}", (ponto["Data"], ponto["Mediana"]),
                    xytext=(8, desvio), textcoords="offset points", color=cor,
                    fontsize=14, fontweight="bold", va="center", annotation_clip=False)

    # Visual: título à esquerda, sem bordas, grade só horizontal, meses em português
    ax.set_title(cfg["titulo"], loc="left", fontsize=16, fontweight="bold", color=PRETO, pad=8)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: MESES[mdates.num2date(x).month - 1]))
    casas = cfg["casas_eixo"]
    ax.yaxis.set_major_formatter(FuncFormatter(
        lambda v, _: virgula(v, casas) if casas == 2 else virgula(v, 1).rstrip("0").rstrip(",")))
    ax.yaxis.set_major_locator(MaxNLocator(4, steps=[1, 2, 2.5, 5]))
    ax.tick_params(colors=CINZA, labelsize=12.5, length=0)
    ax.grid(axis="y", color=GRADE, linewidth=1)
    for borda in ax.spines.values():
        borda.set_visible(False)
    ax.set_xlim(inicio, fim + pd.Timedelta(days=4))


def main():
    usar_fonte_inter()
    df = pd.read_csv(ARQUIVO_DADOS, parse_dates=["Data"])

    fim = df["Data"].max()                                   # último dia com dado
    # O relatório de segunda usa os dados até a sexta anterior. Então a base é o último dia
    # com dado até a sexta de duas semanas antes (ex.: fim 19/11 -> sexta 20/11 -> base 6/11)
    sexta = fim + pd.Timedelta(days=4 - fim.weekday())
    base = df[df["Data"] <= sexta - pd.Timedelta(weeks=SEMANAS_COMPARACAO)]["Data"].max()
    inicio = fim - pd.DateOffset(months=MESES_NA_TELA)
    anos = [fim.year, fim.year + 1]                          # muda sozinho na virada do ano

    fig, eixos = plt.subplots(2, 2, figsize=(9.2, 6.6), dpi=200)
    linhas_tabela = []
    for ax, indicador in zip(eixos.flat, INDICADORES):
        desenhar(ax, df, indicador, anos, inicio, base, fim, linhas_tabela)
    fig.subplots_adjust(left=0.065, right=0.835, top=0.93, bottom=0.06, wspace=0.62, hspace=0.42)

    SAIDA_GRAFICO.parent.mkdir(exist_ok=True)
    fig.savefig(SAIDA_GRAFICO, facecolor="white")
    plt.close(fig)

    tabela = pd.DataFrame(linhas_tabela)
    tabela.to_csv(SAIDA_TABELA, index=False)
    print(f"Gráfico: {SAIDA_GRAFICO}  |  dados de {base.date()} a {fim.date()}")
    print(tabela.to_string(index=False))


if __name__ == "__main__":
    main()
