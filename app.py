from datetime import date, time

import matplotlib.pyplot as plt
import streamlit as st

import solar
from solar import T

st.set_page_config(
    page_title="Simulador de Posição Solar e Irradiância",
    page_icon="☀️",
    layout="centered",
)

st.title("☀️ Simulador de Posição Solar e Irradiância")
st.write(
    "Calcula a posição aparente do Sol e estima a irradiância em um ponto da "
    "Terra, mostrando cada equação, a substituição dos valores e o resultado."
)

# --------------------------------------------------------------------------
# Entrada de dados
# --------------------------------------------------------------------------
st.markdown("### Dados de entrada")

with st.form("entrada"):
    c1, c2 = st.columns(2)
    with c1:
        data = st.date_input(
            "Data",
            value=date.today(),
            min_value=date(1900, 1, 1),
            max_value=date(2100, 12, 31),
            format="DD/MM/YYYY",
        )
    with c2:
        hora = st.time_input("Horário local (hh:mm)", value=time(12, 0), step=60)

    c3, c4 = st.columns(2)
    with c3:
        lat = st.number_input(
            "Latitude (graus decimais, − = Sul)",
            min_value=-90.0, max_value=90.0, value=-12.60, step=0.01, format="%.5f",
        )
    with c4:
        lon = st.number_input(
            "Longitude (graus decimais, − = Oeste)",
            min_value=-180.0, max_value=180.0, value=-38.97, step=0.01, format="%.5f",
        )

    calcular = st.form_submit_button("Calcular")


def validar(data, hora, lat, lon):
    erros = []
    if data is None or not isinstance(data, date):
        erros.append("Informe uma data válida.")
    if hora is None or not isinstance(hora, time):
        erros.append("Informe um horário válido.")
    if lat is None or not (-90 <= lat <= 90):
        erros.append("A latitude deve estar entre −90° e +90°.")
    if lon is None or not (-180 <= lon <= 180):
        erros.append("A longitude deve estar entre −180° e +180°.")
    return erros


if calcular:
    erros = validar(data, hora, lat, lon)
    if erros:
        for e in erros:
            st.error(e)
        st.session_state.pop("res", None)
    else:
        try:
            fuso = solar.identificar_fuso(lat, lon, data, hora)
            st.session_state["res"] = solar.calcular(data, hora, lat, lon, fuso)
        except Exception as erro:  # noqa: BLE001
            st.session_state.pop("res", None)
            st.error(f"Erro no cálculo: {erro}")

res = st.session_state.get("res")

# --------------------------------------------------------------------------
# Resultados
# --------------------------------------------------------------------------
if res:
    for aviso in res.avisos:
        st.warning(aviso)

    st.markdown("---")
    st.subheader("Resultados")

    st.metric(
        "Irradiância estimada no solo (GHI) — céu limpo",
        f"{T(res.ghi, 2)} W/m²",
    )
    st.caption(
        "Estimativa pelo modelo empírico de Haurwitz para céu limpo. "
        "Não é uma medição real."
    )

    linhas = [
        ("1", "Dados de entrada",
         f"{res.data.strftime('%d/%m/%Y')} (n = {res.n}), {res.hora.strftime('%H:%M')}, "
         f"φ = {T(res.lat, 5)}°, λ = {T(res.lon, 5)}°"),
        ("2", "Fuso horário identificado",
         f"{res.fuso.nome} (UTC{res.fuso.deslocamento:+g})"),
        ("3", "Meridiano central do fuso", f"{T(res.fuso.meridiano, 2)}°"),
        ("4", "Declinação solar (δ)", f"{T(res.delta, 4)}°"),
        ("5", "Correção da longitude (CL)", f"{T(res.cl, 4)} min"),
        ("6", "Equação do tempo (E)", f"{T(res.E, 4)} min"),
        ("7", "Hora solar verdadeira (T_sol)", f"{solar.hms(res.t_sol)} ({T(res.t_sol, 4)} h)"),
        ("8", "Ângulo horário (h)", f"{T(res.h, 4)}°"),
        ("9", "Altura solar (α)", f"{T(res.alpha, 4)}°"),
        ("10", "Ângulo zenital (θz)", f"{T(res.theta, 4)}°"),
        ("11", "Irradiância extraterrestre normal (Gon)", f"{T(res.gon, 2)} W/m²"),
        ("12", "Irradiância extraterrestre horizontal (G0h)", f"{T(res.g0h, 2)} W/m²"),
        ("13", "Irradiância estimada no solo (GHI, céu limpo)", f"{T(res.ghi, 2)} W/m²"),
    ]
    tabela = "| # | Grandeza | Valor |\n|---|---|---|\n"
    tabela += "\n".join(f"| {a} | {b} | {c} |" for a, b, c in linhas)
    st.markdown(tabela)

    # ----------------------------------------------------------------------
    # Passo a passo
    # ----------------------------------------------------------------------
    st.markdown("### Desenvolvimento matemático")
    for etapa in res.etapas:
        with st.expander(etapa.titulo):
            st.markdown("**Fórmula**")
            st.latex(etapa.formula)
            st.markdown("**Substituição**")
            st.latex(etapa.substituicao)
            st.markdown(f"**Resultado:** {etapa.resultado}")

    # ----------------------------------------------------------------------
    # Gráfico
    # ----------------------------------------------------------------------
    st.markdown("### Posição do Sol ao longo do dia")
    horas, alturas, g0h, ghi = solar.curva_do_dia(res.n, res.lat)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 7), sharex=True)

    ax1.plot(horas, alturas, color="orange", label="Altura solar (α)")
    ax1.axhline(0, color="gray", linewidth=1)
    ax1.scatter([res.t_sol], [res.alpha], color="red", zorder=5,
                label=f"Instante calculado (α = {T(res.alpha, 1)}°)")
    ax1.set_ylabel("Altura solar (°)")
    ax1.set_title("Altura do Sol × hora solar verdadeira")
    ax1.grid(alpha=0.3)
    ax1.legend()

    ax2.plot(horas, g0h, color="gold", label="G0h (topo da atmosfera)")
    ax2.plot(horas, ghi, color="steelblue", label="GHI (Haurwitz, céu limpo)")
    ax2.scatter([res.t_sol], [res.ghi], color="red", zorder=5,
                label=f"Instante calculado (GHI = {T(res.ghi, 0)} W/m²)")
    ax2.set_xlabel("Hora solar verdadeira (h)")
    ax2.set_ylabel("Irradiância (W/m²)")
    ax2.set_xlim(0, 24)
    ax2.set_xticks(range(0, 25, 3))
    ax2.grid(alpha=0.3)
    ax2.legend()

    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)

    st.caption(
        "As curvas usam as mesmas equações, para o dia (n) informado. "
        "Valores de irradiância em W/m²; ângulos em graus."
    )
