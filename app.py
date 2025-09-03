
import os, glob
from io import BytesIO
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Explorer de Servidores", layout="wide")
-
def normalize_columns(cols):
    def strip_accents(s):
        return "".join(ch for ch in (
            unicodedata.normalize("NFD", s)
        ) if unicodedata.category(ch) != "Mn")
    out = []
    for c in cols.astype(str):
        s = strip_accents(c).lower()
        import re
        s = re.sub(r"[^a-z0-9_]+", "_", s)
        s = re.sub(r"_{2,}", "_", s).strip("_")
        out.append(s)
    return out

@st.cache_data
def load_data(source):
    def _read(_src):
        name = _src if isinstance(_src, str) else _src.name
        name_l = name.lower()
        if name_l.endswith((".xlsx", ".xls")):
            return pd.read_excel(_src, engine="openpyxl")
        elif name_l.endswith(".csv"):
            return pd.read_csv(_src, sep=None, engine="python")
        else:
            raise ValueError("Formato não suportado. Use .xlsx/.xls ou .csv.")

    df = _read(source)
    df.columns = normalize_columns(df.columns)
    return df

ALIASES = {
    "equipe": [
        "equipe", "team", "squad",
        "equipe_responsavel", "equipe_responsavel_pelo_servidor"
    ],
    "sistema": [
        "sistema", "application", "app",
        "sistema_servico_produto", "sistema_aplicacao"
    ],
    "descricao": [
        "descricao", "description", "desc", "descricao_do_ic"
    ],
    "hostname": [
        "hostname", "host", "servidor", "server", "fqdn",
        "nome" 
    ],
    "ambiente": [
        "ambiente", "environment", "env", "entorno"
    ],
    "status": [
        "status", "situacao", "situacao_", "state", "situacao__",
        "situacao__status", "situacao_status"
    ],
}

def pick_col(df, keys):
    for k in keys:
        if k in df.columns:
            return k
    return None

def filter_df(df, col, values):
    if not col or not values:
        return df
    return df[df[col].isin(values)]

def text_search(df, cols, query):
    if not query:
        return df
    mask = pd.Series([False]*len(df))
    for c in cols:
        if c and c in df.columns:
            mask = mask | df[c].astype(str).str.contains(query, case=False, na=False)
    return df[mask]

st.sidebar.header("Dados")

uploaded = st.sidebar.file_uploader("Envie um Excel (.xlsx) ou CSV", type=["xlsx","xls","csv"])

source = None
if uploaded is not None:
    source = uploaded
else:
    if os.path.exists("servidores.xlsx"):
        source = "servidores.xlsx"
    else:
        xlsx_list = sorted(glob.glob("*.xlsx"))
        if xlsx_list:
            source = xlsx_list[0]

if source is None:
    st.info("Envie um arquivo na barra lateral **ou** coloque um **.xlsx** (ex.: FULL MIDD - 2025.xlsx) na mesma pasta do app.")
    st.stop()

import unicodedata  

df = load_data(source)

col_equipe = pick_col(df, ALIASES["equipe"])
col_sistema = pick_col(df, ALIASES["sistema"])
col_desc   = pick_col(df, ALIASES["descricao"])
col_host   = pick_col(df, ALIASES["hostname"])
col_amb    = pick_col(df, ALIASES["ambiente"])
col_status = pick_col(df, ALIASES["status"])

essential_missing = [("Equipe", col_equipe), ("Sistema", col_sistema), ("Descrição", col_desc), ("Hostname/Nome", col_host)]
miss = [name for name, c in essential_missing if c is None]
if miss:
    st.warning("Colunas essenciais não encontradas: " + ", ".join(miss) + ". "
               "Dica: use cabeçalhos como 'Equipe Responsável', 'Sistema/Serviço/Produto', 'Descrição do IC', 'Nome' (ou 'Hostname').")

st.sidebar.header("Filtros")

# 1) Equipe
equipe_opts = sorted(df[col_equipe].dropna().unique()) if col_equipe else []
equipe_sel = st.sidebar.multiselect("Equipe", equipe_opts, default=equipe_opts)

df_f = filter_df(df, col_equipe, equipe_sel)

# 2) Ambiente
ambiente_opts = sorted(df_f[col_amb].dropna().unique()) if col_amb else []
ambiente_sel = st.sidebar.multiselect("Ambiente", ambiente_opts, default=ambiente_opts)

df_f = filter_df(df_f, col_amb, ambiente_sel)

# 3) Sistema
sistema_opts = sorted(df_f[col_sistema].dropna().unique()) if col_sistema else []
sistema_sel = st.sidebar.multiselect("Sistema", sistema_opts, default=sistema_opts)

df_f = filter_df(df_f, col_sistema, sistema_sel)

# 4) Descrição
desc_opts = sorted(df_f[col_desc].dropna().unique()) if col_desc else []
desc_sel = st.sidebar.multiselect("Descrição", desc_opts)

df_f = filter_df(df_f, col_desc, desc_sel)

# 5) Busca
query = st.sidebar.text_input("Busca (hostname/nome/descrição)", placeholder="ex.: web01, prd, oracle")
df_f = text_search(df_f, [col_host, col_desc], query)

st.title("Explorer de Servidores")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total (base)", len(df))
c2.metric("Filtrados", len(df_f))
if col_equipe:
    c3.metric("Equipes", df[col_equipe].nunique())
if col_amb:
    c4.metric("Ambientes", df[col_amb].nunique())

st.dataframe(df_f, use_container_width=True)

st.subheader("Detalhes do servidor (todas as colunas)")
id_col = col_host if col_host else (col_desc if col_desc else None)
if id_col:
    ids = df_f[id_col].dropna().astype(str).unique().tolist()
    if ids:
        chosen = st.selectbox("Selecione um servidor", ids)
        row = df_f[df_f[id_col].astype(str) == str(chosen)]
        if len(row) >= 1:
            st.write("Registro encontrado:")
            st.table(row.iloc[0].T.reset_index().rename(columns={"index": "Campo", 0: "Valor"}))
    else:
        st.caption("Nenhum servidor disponível com os filtros atuais.")
else:
    st.caption("Não foi possível identificar a coluna de servidor (Hostname/Nome).")

if col_sistema:
    st.subheader("Servidores por Sistema (após filtros)")
    chart_sis = df_f.groupby(col_sistema).size().sort_values(ascending=False).head(20)
    st.bar_chart(chart_sis)

if col_amb:
    st.subheader("Servidores por Ambiente (após filtros)")
    chart_amb = df_f.groupby(col_amb).size().sort_values(ascending=False)
    st.bar_chart(chart_amb)

def to_csv_bytes(_df):
    out = BytesIO()
    _df.to_csv(out, index=False)
    out.seek(0)
    return out.getvalue()

st.download_button(
    "Baixar resultado (CSV)",
    data=to_csv_bytes(df_f),
    file_name="servidores_filtrado.csv",
    mime="text/csv"
)

st.caption("Dica: cabeçalhos reconhecidos: 'Equipe Responsável', 'Sistema/Serviço/Produto', 'Descrição do IC', 'Nome' (ou 'Hostname'), 'Ambiente'.")
