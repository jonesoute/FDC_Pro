import streamlit as st
import yfinance as yf
import requests
import pandas as pd
import numpy as np

st.set_page_config(page_title="Valuation por Lucro", layout="centered")
st.title("📊 Valuation com base no Lucro por Ação (LPA)")

ticker = st.text_input("Ticker da ação (ex: PETR4)", "PETR4").upper()
consultar = st.button("🔍 Consultar dados")

def get_taxa_selic_futura():
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1178/dados/ultimos/1?formato=json"
        response = requests.get(url)
        data = response.json()
        valor = float(data[0]["valor"].replace(",", "."))
        return valor / 100
    except:
        return 0.105

def calcular_cagr(valores):
    if len(valores) >= 2 and valores[0] > 0 and valores[-1] > 0:
        anos = len(valores) - 1
        return (valores[-1] / valores[0]) ** (1 / anos) - 1
    return None

if consultar:
    try:
        ticker_api = ticker + ".SA"
        acao = yf.Ticker(ticker_api)
        info = acao.info
        preco = acao.history(period="1d")["Close"].iloc[-1]
        lpa = info.get("trailingEps", None)
        beta = info.get("beta", 1.0)
        dividends = acao.dividends

        if lpa is None or lpa <= 0:
            st.error("❌ Não foi possível obter o LPA para esse papel.")
        else:
            st.success(f"Preço atual: R$ {preco:.2f}")
            st.write(f"Lucro por ação (LPA, últimos 12 meses): R$ {lpa:.2f}")
            st.write(f"Beta: {beta:.2f}")

            ibov = yf.Ticker("^BVSP").history(period="1y")["Close"]
            retorno_mercado = ((ibov[-1] / ibov[0]) - 1)
            taxa_risco = get_taxa_selic_futura()
            capm = taxa_risco + beta * (retorno_mercado - taxa_risco)
            st.write(f"CAPM estimado: {capm:.2%}".replace(".", ","))

            st.markdown("### Parâmetros de projeção")

            # Simulação de CAGR Lucro Líq. 5 anos
            income_stmt = acao.financials
            if income_stmt is not None and not income_stmt.empty and "Net Income" in income_stmt.index:
                net_incomes = income_stmt.loc["Net Income"].dropna().sort_index(ascending=True)
                if len(net_incomes) >= 5:
                    cagr_lucro = calcular_cagr(net_incomes[-5:].values)
                    if cagr_lucro is not None:
                        st.info(f"📈 CAGR Lucro Líquido 5 anos: {cagr_lucro * 100:.2f}%".replace(".", ","))

            # Simulação de Dividend Yield médio 5 anos
            if dividends is not None and not dividends.empty:
                hist = acao.history(period="5y")
                hist["Year"] = hist.index.year
                dividendos_anuais = dividends.groupby(dividends.index.year).sum()
                precos_medios_anuais = hist.groupby("Year")["Close"].mean()
                dy_anuais = []
                for ano in dividendos_anuais.index:
                    if ano in precos_medios_anuais:
                        dy = dividendos_anuais[ano] / precos_medios_anuais[ano]
                        dy_anuais.append(dy)
                if dy_anuais:
                    dy_medio = np.mean(dy_anuais)
                    st.info(f"📤 Dividend Yield médio 5 anos: {dy_medio * 100:.2f}%".replace(".", ","))

            crescimento = st.slider("Crescimento anual do lucro (%)", 0.00, 0.30, 0.10, step=0.01)
            payout = st.slider("Payout Ratio (%)", 0, 100, 50) / 100
            anos = st.slider("Período de análise (anos)", 1, 20, 10)
            margem = st.slider("Margem de segurança (%)", 0, 50, 10) / 100

            calcular = st.button("📈 Calcular valor justo")

            if calcular:
                dividendo = lpa * payout
                fcd_fase1 = 0
                for t in range(1, anos + 1):
                    div = dividendo * (1 + crescimento) ** t
                    fcd_fase1 += div / (1 + capm) ** t

                div_final = dividendo * (1 + crescimento) ** (anos + 1)
                valor_residual = (div_final * (1 + crescimento)) / (capm - crescimento)
                vp_residual = valor_residual / (1 + capm) ** anos

                valor_justo = fcd_fase1 + vp_residual
                valor_ajustado = valor_justo * (1 - margem)
                upside = valor_ajustado - preco
                upside_pct = (valor_ajustado / preco) - 1

                st.markdown("## 🧮 Resultado da Avaliação")
                st.write(f"**Valor justo (sem margem):** R$ {valor_justo:.2f}".replace(".", ","))
                st.write(f"**Valor justo ajustado:** R$ {valor_ajustado:.2f}".replace(".", ","))
                st.write(f"**Upside estimado:** {upside_pct:.2%}".replace(".", ","))
                st.write("🔼 Upside" if upside > 0 else "🔻 Downside")
    except Exception as e:
        st.error(f"Erro: {e}")
