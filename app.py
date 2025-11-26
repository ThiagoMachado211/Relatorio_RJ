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
    "Objetivas - 2º Simulado: Acertos (%)",  # ajuste se o nome estiver ligeiramente diferente
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
# 1) Carregar dados do Excel
# ===============================================================
@st.cache_data
def load_data():
    xls = pd.ExcelFile("Dados_RJ.xlsx")

    def read_sheet(sheet_name):
        df_ = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)
        df_.columns = (
            df_.columns
            .str.strip()
            .str.replace('\ufeff', '', regex=False)
        )
        return df_

    df_original   = read_sheet("Original")
    df_redacao    = read_sheet("Dados_Redação")
    df_objetivas  = read_sheet("Dados_Objetivas")
    df_particip   = read_sheet("Dados_Participação")
    df_acessos    = read_sheet("Dados_Acesso_Detalhado")

    return {
        "original": df_original,
        "redacao": df_redacao,
        "objetivas": df_objetivas,
        "participacao": df_particip,
        "acessos": df_acessos,
    }


data = load_data()
df_redacao   = data["redacao"]
df_objetivas = data["objetivas"]
df_part      = data["participacao"]
df_acessos   = data["acessos"]

st.title("Painel de Participação e Desempenhos")

# ===============================================================
# 2) Seleção de regional (com base na união das abas)
# ===============================================================
regionais_set = set()

for df_src in [df_redacao, df_objetivas, df_part, df_acessos]:
    if COL_REGIONAL in df_src.columns:
        regionais_set.update(df_src[COL_REGIONAL].dropna().unique())

regionais_no_arquivo = sorted(regionais_set)

if not regionais_no_arquivo:
    st.error("Nenhuma regional encontrada nas planilhas.")
    st.stop()


st.markdown(
    "<div style='font-size:22px; margin-bottom:10px;'>Selecione a Regional:</div>",
    unsafe_allow_html=True
)
regional_escolhida = st.selectbox(
    "Selecione a Regional",        # label NÃO vazio
    regionais_no_arquivo,
    label_visibility="collapsed",  # esconde visualmente o label nativo
)


# st.subheader(f"")

# ===============================================================
# 3) Abas laterais
# ===============================================================
aba = st.sidebar.radio(
    "",
    [
        "Desempenhos em Redação",
        "Desempenhos nas Provas Objetivas",
        "Tempos e Volumes de Participação nas Aplicações",
        "Detalhamento de Acessos",
    ]
)


# ===============================================================
# 4) Função auxiliar: filtrar escolas válidas (sem faltantes) por aba
# ===============================================================
def filtrar_escolas_validas(df_base: pd.DataFrame, cols_part, cols_notas_ou_acertos, percentual_notas: bool):
    """
    Retorna df_regional_valid (apenas linhas sem NaN nas colunas indicadas).
    """
    df_reg_regional = df_base[df_base[COL_REGIONAL] == regional_escolhida].copy()
    if df_reg_regional.empty:
        return df_reg_regional, df_reg_regional  # vazio

    df_num = df_reg_regional.copy()

    # Converter colunas numéricas para detectar NaN
    for c in cols_part:
        if c in df_num.columns:
            df_num[c] = serie_para_float(df_num[c], eh_percentual=True)
    for c in cols_notas_ou_acertos:
        if c in df_num.columns:
            df_num[c] = serie_para_float(df_num[c], eh_percentual=percentual_notas)

    mask_valid = (
        df_num[cols_part].notna().all(axis=1) &
        df_num[cols_notas_ou_acertos].notna().all(axis=1)
    )

    df_valid = df_reg_regional[mask_valid].copy()
    return df_reg_regional, df_valid


# ===============================================================
# 5) ABA: Desempenhos em Redação
# ===============================================================
if aba == "Desempenhos em Redação":
    # Filtra regionais e escolas válidas
    if COL_REGIONAL not in df_redacao.columns:
        st.error(f"A aba Dados_Redação não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    for c in COL_PART_RED + COL_NOTAS_RED:
        if c not in df_redacao.columns:
            st.error(f"Coluna '{c}' não encontrada em Dados_Redação.")
            st.stop()

    df_reg_red, df_reg_red_valid = filtrar_escolas_validas(
        df_redacao, COL_PART_RED, COL_NOTAS_RED, percentual_notas=False
    )

    if df_reg_red_valid.empty:
        st.warning("Nenhuma escola desta regional possui todos os dados de redação completos.")
        st.stop()

    # Escolha de escola + busca (apenas escolas sem faltantes)
    escolas_validas = sorted(df_reg_red_valid[COL_ESCOLA].dropna().unique())

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(
        "<div style='font-size:22px; margin-bottom:10px;'>Selecione a Escola:</div>",
        unsafe_allow_html=True
        )
        escola_dropdown = st.selectbox(
        "Escola",
        escolas_validas,
        key="escola_dropdown_red",
        label_visibility="collapsed",
    )

#        escola_dropdown = st.selectbox("", escolas_validas, key="escola_dropdown_red")


    with col2:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Buscar escola:</div>",
            unsafe_allow_html=True
        )
        termo_busca = st.text_input(
            "Buscar escola",
            key="busca_escola_red",
            label_visibility="collapsed",  # esconde o label padrão do Streamlit
        )
        # termo_busca = st.text_input("Buscar escola", key="busca_escola_red")


    escola_escolhida = escola_dropdown
    if termo_busca:
        termo_lower = termo_busca.lower()
        filtradas = [e for e in escolas_validas if termo_lower in e.lower()]
        if filtradas:
            escola_escolhida = filtradas[0]
            st.caption(f"Busca: usando a escola **{escola_escolhida}**")
        else:
            st.info("Nenhuma escola encontrada para esse termo de busca.")

    df_escola = df_reg_red_valid[df_reg_red_valid[COL_ESCOLA] == escola_escolhida].copy()
    if df_escola.empty:
        st.warning("Não há dados completos para a escola selecionada.")
        st.stop()

    # Série única (primeira linha)
    part = serie_para_float(df_escola[COL_PART_RED].iloc[0], eh_percentual=True)
    notas = serie_para_float(df_escola[COL_NOTAS_RED].iloc[0], eh_percentual=False)

    part_frac   = part / 100.0
    notas_norm  = notas / 1000.0
    var_part    = calcular_variacao(part)
    var_notas   = calcular_variacao(notas)

    etapas_red = [
        "1º Simulado",
        "1º Teste de Redação",
        "2º Teste de Redação",
        "2º Simulado",
        "3º Teste de Redação",
        "4º Teste de Redação",
    ]

    fig = go.Figure()

    # Participação (laranja, rótulo embaixo)
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
                "Variação: %{customdata[1]:.2f} p.p.<extra></extra>"
            ),
        )
    )

    # Notas (preto, rótulo em cima)
    customdata_notas = [
        [notas.iloc[i], var_notas[i]] for i in range(len(notas))
    ]
    fig.add_trace(
        go.Scatter(
            x=etapas_red,
            y=notas_norm,
            mode="lines+markers+text",
            name="Notas",
            text=[f"{v:.2f}" if pd.notna(v) else "" for v in notas],
            textposition="top center",
            marker=dict(color="#000000"),
            line=dict(color="#000000"),
            customdata=customdata_notas,
            hovertemplate=(
                "Etapa: %{x}<br>"
                "Nota: %{customdata[0]:.2f}<br>"
                "Variação: %{customdata[1]:.2f}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        title=dict(
            text=f"Desempenhos em Redação: {escola_escolhida}",
            font=dict(size=26)  # só o título
        ),
        font=dict(size=16),     # resto (legenda, etc.)
        height=800,
        legend=dict(
        font=dict(size=16)  # <<< TAMANHO DA FONTE DA LEGENDA
        ),
        yaxis=dict(
            title="",
            range=[-0.2, 1.2],
            showticklabels=False,
        ),
        xaxis=dict(
        tickfont=dict(size=16)    # rótulos das etapas no eixo X
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Tabela da regional (Redação)
    st.subheader("Participações e notas de redação da regional selecionada")
    cols_tabela = [COL_CODIGO, COL_ESCOLA] + COL_PART_RED + COL_NOTAS_RED
    df_tabela = df_reg_red[cols_tabela].copy()
    st.dataframe(df_tabela, use_container_width=True, hide_index=True)


# ===============================================================
# 6) ABA: Desempenhos nas Provas Objetivas
# ===============================================================
elif aba == "Desempenhos nas Provas Objetivas":
    if COL_REGIONAL not in df_objetivas.columns:
        st.error(f"A aba Dados_Objetivas não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    for c in COL_PART_OBJ + COL_ACERTOS_OBJ:
        if c not in df_objetivas.columns:
            st.error(f"Coluna '{c}' não encontrada em Dados_Objetivas.")
            st.stop()

    df_reg_obj, df_reg_obj_valid = filtrar_escolas_validas(
        df_objetivas, COL_PART_OBJ, COL_ACERTOS_OBJ, percentual_notas=True
    )

    if df_reg_obj_valid.empty:
        st.warning("Nenhuma escola desta regional possui todos os dados de objetivas completos.")
        st.stop()

    escolas_validas = sorted(df_reg_obj_valid[COL_ESCOLA].dropna().unique())

    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Selecione a Escola:</div>",
            unsafe_allow_html=True
        )
        escola_dropdown = st.selectbox(
            "Escola",
            escolas_validas,
            key="escola_dropdown_obj",
            label_visibility="collapsed",
        )
#        escola_dropdown = st.selectbox("", escolas_validas, key="escola_dropdown_red")

    with col2:
        st.markdown(
            "<div style='font-size:22px; margin-bottom:10px;'>Buscar escola:</div>",
            unsafe_allow_html=True
        )
        termo_busca = st.text_input(
            "Buscar escola",
            key="busca_escola_red",
            label_visibility="collapsed",  # esconde o label padrão do Streamlit
        )
#        termo_busca = st.text_input("Buscar escola", key="busca_escola_obj")

    escola_escolhida = escola_dropdown
    if termo_busca:
        termo_lower = termo_busca.lower()
        filtradas = [e for e in escolas_validas if termo_lower in e.lower()]
        if filtradas:
            escola_escolhida = filtradas[0]
            st.caption(f"Busca: usando a escola **{escola_escolhida}**")
        else:
            st.info("Nenhuma escola encontrada para esse termo de busca.")

    df_escola = df_reg_obj_valid[df_reg_obj_valid[COL_ESCOLA] == escola_escolhida].copy()
    if df_escola.empty:
        st.warning("Não há dados completos para a escola selecionada.")
        st.stop()

    part_obj    = serie_para_float(df_escola[COL_PART_OBJ].iloc[0], eh_percentual=True)
    acertos_obj = serie_para_float(df_escola[COL_ACERTOS_OBJ].iloc[0], eh_percentual=True)

    part_obj_frac    = part_obj / 100.0
    acertos_obj_frac = acertos_obj / 100.0

    var_part_obj    = calcular_variacao(part_obj)
    var_acertos_obj = calcular_variacao(acertos_obj)

    etapas_obj = ["1º Simulado", "2º Simulado"]

    fig_obj = go.Figure()

    # Participação (Objetivas)
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
                "Variação: %{customdata[1]:.2f} p.p.<extra></extra>"
            ),
        )
    )

    # Acertos (Objetivas)
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
                "Variação: %{customdata[1]:.2f} p.p.<extra></extra>"
            ),
        )
    )

    fig_obj.update_layout(
        title=dict(
            text=f"Desempenhos nas Provas Objetivas: {escola_escolhida}",
            font=dict(size=26)  # só o título
        ),
        font=dict(size=16),     # resto (legenda, etc.)
        height=800,
        legend=dict(
        font=dict(size=16)  # <<< TAMANHO DA FONTE DA LEGENDA
        ),
        yaxis=dict(
            title="",
            range=[-0.2, 1.2],
            showticklabels=False,
        ),
        xaxis=dict(
        tickfont=dict(size=16)    # rótulos das etapas no eixo X
        ),
    )

    st.plotly_chart(fig_obj, use_container_width=True)

    # Tabela da regional (Objetivas)
    st.subheader("Participações e acertos das provas objetivas da regional selecionada")
    cols_tabela_obj = [COL_CODIGO, COL_ESCOLA] + COL_PART_OBJ + COL_ACERTOS_OBJ
    df_tabela_obj = df_reg_obj[cols_tabela_obj].copy()
    st.dataframe(df_tabela_obj, use_container_width=True, hide_index=True)


# ===============================================================
# 8) ABA: Tempos e Volumes de Participação nas Aplicações
# ===============================================================
elif aba == "Tempos e Volumes de Participação nas Aplicações":
    if COL_REGIONAL not in df_part.columns:
        st.error(f"A aba Dados_Participação não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    df_part_reg = df_part[df_part[COL_REGIONAL] == regional_escolhida].copy()

    if df_part_reg.empty:
        st.warning("Não há registros de tempos/volumes de participação para esta regional.")
    else:
        st.subheader("Tempos e Volumes de Participação nas Aplicações")
        st.dataframe(df_part_reg, use_container_width=True, hide_index=True)


# ===============================================================
# 9) ABA: Detalhamento de Acessos
# ===============================================================
elif aba == "Detalhamento de Acessos":
    if COL_REGIONAL not in df_acessos.columns:
        st.error(f"A aba Dados_Acesso_Detalhado não possui a coluna '{COL_REGIONAL}'.")
        st.stop()

    df_acessos_reg = df_acessos[df_acessos[COL_REGIONAL] == regional_escolhida].copy()

    if df_acessos_reg.empty:
        st.warning("Não há registros de acessos detalhados para esta regional.")
    else:
        st.subheader("Detalhamento de Acessos")

        st.dataframe(df_acessos_reg, use_container_width=True, hide_index=True)
