# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ===============================================================
# Configuração da página (painel mais largo)
# ===============================================================
st.set_page_config(layout="wide")

# ===============================================================
# Constantes de colunas
# ===============================================================
COL_CODIGO   = "Código Interno"
COL_REGIONAL = "Regional"
COL_ESCOLA   = "Escola"

# Colunas de Redação
COL_PART_RED = [
    "1º Simulado: Participação (%)",
    "1º Teste de Redação: Participação (%)",
    "2º Teste de Redação: Participação (%)",
    "2º Simulado: Participação (%)",
    "3º Teste de Redação: Participação (%)",
    "4º Teste de Redação: Participação (%)",
]

COL_NOTAS_RED = [
    "1º Simulado: Nota",
    "1º Teste de Redação: Nota",
    "2º Teste de Redação: Nota",
    "2º Simulado: Nota",
    "3º Teste de Redação: Nota",
    "4º Teste de Redação: Nota",
]

# Colunas de Objetivas
COL_PART_OBJ = [
    "Objetivas - 1º Simulado: Participação (%)",
    "Objetivas - 2º Simulado: Participação (%)",
]

COL_ACERTOS_OBJ = [
    "Objetivas - 1º Simulado: Acertos (%)",
    "Objetivas - 2º Simulado: Acertos (%)",
]


# ===============================================================
# Funções auxiliares
# ===============================================================
def serie_para_float(s: pd.Series, eh_percentual: bool = False) -> pd.Series:
    """
    Converte uma Series com valores tipo '85,12%' / '202,71'
    em float. Se eh_percentual=True, remove '%'.
    """
    s = s.astype(str).str.strip()

    if eh_percentual:
        s = s.str.replace('%', '', regex=False)

    # remove separador de milhar e troca vírgula por ponto
    s = s.str.replace('.', '', regex=False)
    s = s.str.replace(',', '.', regex=False)

    return pd.to_numeric(s, errors="coerce")


def calcular_variacao(valores) -> list:
    """
    Retorna lista com variação (com sinal) em relação ao ponto anterior.
    Primeiro ponto recebe 0.0.
    """
    vals = []
    for v in valores:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            vals.append(None)
        else:
            vals.append(float(v))

    variacoes = [0.0]
    for i in range(1, len(vals)):
        if vals[i] is not None and vals[i - 1] is not None:
            variacoes.append(vals[i] - vals[i - 1])  # COM SINAL
        else:
            variacoes.append(0.0)
    return variacoes


# ===============================================================
# 1) Carregar dados
# ===============================================================
@st.cache_data
def load_data():
    df = pd.read_csv(
        "Dados_RJ.csv",
        sep=",",
        encoding="utf-8-sig",
        dtype=str
    )

    df.columns = (
        df.columns
        .str.strip()
        .str.replace('\ufeff', '', regex=False)
    )
    return df


df = load_data()

st.title("Painel de Participação e Notas por Escola")

# Verificar colunas básicas
for col_needed in [COL_REGIONAL, COL_ESCOLA, COL_CODIGO]:
    if col_needed not in df.columns:
        st.error(f"Coluna '{col_needed}' não encontrada no arquivo.")
        st.write("Colunas disponíveis:", list(df.columns))
        st.stop()

# ===============================================================
# 2) Seleção de regional (sem autenticação)
# ===============================================================
regionais_no_arquivo = sorted(df[COL_REGIONAL].dropna().unique())
regional_escolhida = st.selectbox("Selecione a Regional", regionais_no_arquivo)

df_regional = df[df[COL_REGIONAL] == regional_escolhida].copy()

if df_regional.empty:
    st.warning("Não há escolas cadastradas para essa regional no arquivo.")
    st.stop()

st.subheader(f"Regional selecionada: {regional_escolhida}")

# ===============================================================
# 3) Abas laterais
# ===============================================================
aba = st.sidebar.radio("Selecione a aba", ["Redações", "Objetivas"])

# ===============================================================
# 4) Filtrar escolas SEM dados faltantes para a aba atual
# ===============================================================
df_regional_numerico = df_regional.copy()

if aba == "Redações":
    # Converter colunas numéricas primeiro (para detectar NaN de verdade)
    for c in COL_PART_RED:
        if c in df_regional_numerico.columns:
            df_regional_numerico[c] = serie_para_float(df_regional_numerico[c], eh_percentual=True)
    for c in COL_NOTAS_RED:
        if c in df_regional_numerico.columns:
            df_regional_numerico[c] = serie_para_float(df_regional_numerico[c], eh_percentual=False)

    # Máscara de linhas sem nenhum NaN nas colunas de interesse
    mask_valid = (
        df_regional_numerico[COL_PART_RED].notna().all(axis=1) &
        df_regional_numerico[COL_NOTAS_RED].notna().all(axis=1)
    )

elif aba == "Objetivas":
    for c in COL_PART_OBJ:
        if c in df_regional_numerico.columns:
            df_regional_numerico[c] = serie_para_float(df_regional_numerico[c], eh_percentual=True)
    for c in COL_ACERTOS_OBJ:
        if c in df_regional_numerico.columns:
            df_regional_numerico[c] = serie_para_float(df_regional_numerico[c], eh_percentual=True)

    mask_valid = (
        df_regional_numerico[COL_PART_OBJ].notna().all(axis=1) &
        df_regional_numerico[COL_ACERTOS_OBJ].notna().all(axis=1)
    )

df_regional_valid = df_regional[mask_valid].copy()

if df_regional_valid.empty:
    st.warning("Nenhuma escola desta regional possui todos os dados necessários para a aba selecionada.")
    st.stop()

# ===============================================================
# 5) Escolha da escola + busca (somente escolas SEM dados faltantes)
# ===============================================================
escolas_validas = sorted(df_regional_valid[COL_ESCOLA].dropna().unique())

col1, col2 = st.columns([1, 1])

with col1:
    escola_dropdown = st.selectbox("Escola", escolas_validas, key="escola_dropdown")

with col2:
    termo_busca = st.text_input("Buscar escola", key="busca_escola")

escola_escolhida = escola_dropdown

if termo_busca:
    termo_lower = termo_busca.lower()
    escolas_filtradas = [e for e in escolas_validas if termo_lower in e.lower()]
    if escolas_filtradas:
        escola_escolhida = escolas_filtradas[0]
        st.caption(f"Busca: usando a escola **{escola_escolhida}**")
    else:
        st.info("Nenhuma escola encontrada para esse termo de busca.")

df_escola = df_regional_valid[df_regional_valid[COL_ESCOLA] == escola_escolhida].copy()
if df_escola.empty:
    st.warning("Não há dados completos para a escola selecionada.")
    st.stop()


# ===============================================================
# 6) ABA REDAÇÕES
# ===============================================================
if aba == "Redações":
    faltando_part = [c for c in COL_PART_RED if c not in df_escola.columns]
    faltando_notas = [c for c in COL_NOTAS_RED if c not in df_escola.columns]

    if faltando_part or faltando_notas:
        st.error("Algumas colunas de REDAÇÃO não foram encontradas.")
        if faltando_part:
            st.write("Faltando (participação):", faltando_part)
        if faltando_notas:
            st.write("Faltando (notas):", faltando_notas)
        st.write("Colunas disponíveis:", list(df_escola.columns))
        st.stop()

    # Série única (primeira linha da escola)
    part = serie_para_float(df_escola[COL_PART_RED].iloc[0], eh_percentual=True)
    notas = serie_para_float(df_escola[COL_NOTAS_RED].iloc[0], eh_percentual=False)

    # (teoricamente não terá NaN aqui, pois já filtramos no dropdown)
    part_frac = part / 100.0
    notas_norm = notas / 1000.0

    var_part = calcular_variacao(part)
    var_notas = calcular_variacao(notas)

    etapas_red = [
        "1º Simulado",
        "1º Teste de Redação",
        "2º Teste de Redação",
        "2º Simulado",
        "3º Teste de Redação",
        "4º Teste de Redação",
    ]

    fig = go.Figure()

    # -------- Participação (laranja, rótulo embaixo) --------
    customdata_part = [
        [part.iloc[i], var_part[i]] for i in range(len(part))
    ]

    fig.add_trace(
        go.Scatter(
            x=etapas_red,
            y=part_frac,
            mode="lines+markers+text",
            name="Participação",
            text=[f"{v:.2f}%" if pd.notna(v) else "" for v in part],
            textposition="bottom center",
            marker=dict(color="#FF8C00"),
            line=dict(color="#FF8C00"),
            customdata=customdata_part,
            hovertemplate=(
                "Etapa: %{x}<br>"
                "Participação: %{customdata[0]:.2f}%<br>"
                "Variação: %{customdata[1]:.2f}%<extra></extra>"
            ),
        )
    )

    # -------- Notas (preto, rótulo em cima) --------
    customdata_notas = [
        [notas.iloc[i], var_notas[i]] for i in range(len(notas))
    ]

    fig.add_trace(
        go.Scatter(
            x=etapas_red,
            y=notas_norm,
            mode="lines+markers+text",
            name="Notas",
            text=[f"{v:.0f}" if pd.notna(v) else "" for v in notas],
            textposition="top center",
            marker=dict(color="#000000"),
            line=dict(color="#000000"),
            customdata=customdata_notas,
            hovertemplate=(
                "Etapa: %{x}<br>"
                "Nota: %{customdata[0]:.0f}<br>"
                "Variação: %{customdata[1]:.2f}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=f"Redações — {escola_escolhida}",
        yaxis=dict(
            title="Escala normalizada (0–1)",
            range=[-0.2, 1.2],
            showticklabels=False,   # remove valores do eixo Y
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    # -------- Tabela da regional (Redações) --------
    st.subheader("Participações e notas de redação da regional selecionada")
    cols_tabela = [COL_CODIGO, COL_ESCOLA] + COL_PART_RED + COL_NOTAS_RED
    df_tabela = df_regional[cols_tabela].copy()
    st.dataframe(df_tabela, use_container_width=True)


# ===============================================================
# 7) ABA OBJETIVAS
# ===============================================================
elif aba == "Objetivas":
    faltando_part_obj = [c for c in COL_PART_OBJ if c not in df_escola.columns]
    faltando_acertos_obj = [c for c in COL_ACERTOS_OBJ if c not in df_escola.columns]

    if faltando_part_obj or faltando_acertos_obj:
        st.error("Algumas colunas de OBJETIVAS não foram encontradas.")
        if faltando_part_obj:
            st.write("Faltando (participação):", faltando_part_obj)
        if faltando_acertos_obj:
            st.write("Faltando (acertos):", faltando_acertos_obj)
        st.write("Colunas disponíveis:", list(df_escola.columns))
        st.stop()

    part_obj = serie_para_float(df_escola[COL_PART_OBJ].iloc[0], eh_percentual=True)
    acertos_obj = serie_para_float(df_escola[COL_ACERTOS_OBJ].iloc[0], eh_percentual=True)

    part_obj_frac = part_obj / 100.0
    acertos_obj_frac = acertos_obj / 100.0

    var_part_obj = calcular_variacao(part_obj)
    var_acertos_obj = calcular_variacao(acertos_obj)

    etapas_obj = ["1º Simulado", "2º Simulado"]

    fig_obj = go.Figure()

    # -------- Participação (Objetivas) --------
    customdata_part_obj = [
        [part_obj.iloc[i], var_part_obj[i]] for i in range(len(part_obj))
    ]

    fig_obj.add_trace(
        go.Scatter(
            x=etapas_obj,
            y=part_obj_frac,
            mode="lines+markers+text",
            name="Participação",
            text=[f"{v:.2f}%" if pd.notna(v) else "" for v in part_obj],
            textposition="bottom center",
            marker=dict(color="#FF8C00"),
            line=dict(color="#FF8C00"),
            customdata=customdata_part_obj,
            hovertemplate=(
                "Etapa: %{x}<br>"
                "Participação: %{customdata[0]:.2f}%<br>"
                "Variação: %{customdata[1]:.2f}%<extra></extra>"
            ),
        )
    )

    # -------- Acertos (Objetivas) --------
    customdata_acertos_obj = [
        [acertos_obj.iloc[i], var_acertos_obj[i]] for i in range(len(acertos_obj))
    ]

    fig_obj.add_trace(
        go.Scatter(
            x=etapas_obj,
            y=acertos_obj_frac,
            mode="lines+markers+text",
            name="Acertos",
            text=[f"{v:.2f}%" if pd.notna(v) else "" for v in acertos_obj],
            textposition="top center",
            marker=dict(color="#000000"),
            line=dict(color="#000000"),
            customdata=customdata_acertos_obj,
            hovertemplate=(
                "Etapa: %{x}<br>"
                "Acertos: %{customdata[0]:.2f}%<br>"
                "Variação: %{customdata[1]:.2f}%<extra></extra>"
            ),
        )
    )

    fig_obj.update_layout(
        title=f"Objetivas — {escola_escolhida}",
        yaxis=dict(
            title="Escala normalizada (0–1)",
            range=[-0.2, 1.2],
            showticklabels=False,
        ),
    )

    st.plotly_chart(fig_obj, use_container_width=True)

    # -------- Tabela da regional (Objetivas) --------
    st.subheader("Participações e acertos das objetivas da regional selecionada")
    cols_tabela_obj = [COL_CODIGO, COL_ESCOLA] + COL_PART_OBJ + COL_ACERTOS_OBJ
    df_tabela_obj = df_regional[cols_tabela_obj].copy()
    st.dataframe(df_tabela_obj, use_container_width=True)