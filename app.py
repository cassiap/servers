import os
import glob
import unicodedata
import html
from io import BytesIO

import pandas as pd
import streamlit as st

# ===================== CSS =====================
st.set_page_config(page_title="Explorer de Servidores", layout="wide", menu_items={
    "Get Help": None, "Report a bug": None, "About": None
})
st.markdown("""
<style>
[data-testid="stHeader"]{display:none;}
[data-testid="stToolbar"]{display:none;}
footer{visibility:hidden;}
#MainMenu{visibility:hidden;}
.badge{padding:2px 8px;border-radius:9999px;font-size:12px;display:inline-block}
.badge.prod{background:#ef4444;color:#fff}
.badge.homolog{background:#3b82f6;color:#fff}
.badge.dev{background:#10b981;color:#fff}
.badge.qa{background:#a855f7;color:#fff}
.badge.trans{background:#f59e0b;color:#000}
.badge.white{background:#e5e7eb;color:#000;border:1px solid #cbd5e1}

/* -------- clamp de células: até 3 linhas com reticências -------- */
table.dataframe { table-layout: fixed; width: 100%; }
table.dataframe th, table.dataframe td { max-width: 320px; vertical-align: top; }
table.dataframe td div.clip, table.dataframe th div.clip {
  display: -webkit-box;
  -webkit-line-clamp: 3;       /* <= nº de linhas visíveis */
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: normal;
  word-break: break-word;
}
</style>
""", unsafe_allow_html=True)

def _strip_accents(text: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")

def normalize_columns(cols):
    out = []
    for c in map(str, cols):
        s = _strip_accents(c).lower()
        s = pd.Series([s]).str.replace(r"[^a-z0-9_]+", "_", regex=True)[0]
        s = pd.Series([s]).str.replace(r"_{2,}", "_", regex=True)[0].strip("_")
        out.append(s)
    return out

def build_colmap(original_cols):
    norm = normalize_columns(original_cols)
    return dict(zip(norm, original_cols)), dict(zip(original_cols, norm))

@st.cache_data
def load_data(source):
    def _read(_src):
        name = _src if isinstance(_src, str) else _src.name
        n = name.lower()
        if n.endswith((".xlsx", ".xls")):
            df0 = pd.read_excel(_src, engine="openpyxl")
        elif n.endswith(".csv"):
            df0 = pd.read_csv(_src, sep=None, engine="python")
        else:
            raise ValueError("Formato não suportado: use .xlsx/.xls ou .csv")
        return df0

    df0 = _read(source)
    map_norm2orig, map_orig2norm = build_colmap(df0.columns)
    df = df0.copy()
    df.columns = [map_orig2norm[c] for c in df0.columns]
    return df, map_norm2orig

ALIASES = {
    "equipe":   ["equipe", "team", "squad", "equipe_responsavel", "equipe_responsavel_pelo_servidor"],
    "sistema":  ["sistema", "application", "app", "sistema_servico_produto", "sistema_aplicacao"],
    "descricao":["descricao", "description", "desc", "descricao_do_ic"],
    "hostname": ["hostname", "host", "servidor", "server", "fqdn", "nome"],
    "ambiente": ["ambiente", "environment", "env", "entorno"],
    "status":   ["status", "situacao", "situucao", "state", "situacao__status", "situacao_status"],
}

def pick_col(df, keys):
    for k in keys:
        if k in df.columns:
            return k
    return None

def filter_df(df, col, values):
    if col and values:
        return df[df[col].astype(str).isin(list(map(str, values)))]
    return df

def text_search(df, cols, query):
    if not query:
        return df
    mask = pd.Series(False, index=df.index)
    for c in cols:
        if c and c in df.columns:
            mask |= df[c].astype(str).str.contains(query, case=False, na=False)
    return df[mask]

def badge_for_amb(v):
    if not isinstance(v, str): return v
    x = v.strip().lower()
    if x.startswith("prod"): cls = "prod"
    elif x.startswith("homo"): cls = "homolog"
    elif x.startswith("dev") or x.startswith("desenv"): cls = "dev"
    elif "qa" in x or x.startswith("qualid"): cls = "qa"
    elif x.startswith("trans"): cls = "trans"
    elif x.startswith("white"): cls = "white"
    else: return v
    return f'<span class="badge {cls}">{v}</span>'

def to_xlsx_bytes(df):
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="dados")
    bio.seek(0)
    return bio.getvalue()

def parse_server_list(raw: str):
    if not raw:
        return []
    parts = []
    for token in raw.replace(",", "\n").replace(";", "\n").split():
        token = token.strip()
        if token:
            parts.append(token.lower())
    seen, out = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out

def cell_html(value, rich=False):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        txt = ""
    else:
        txt = str(value).replace("\r\n", " ").replace("\n", " ")
    if rich:
        inner = txt
    else:
        inner = html.escape(txt)
    return f"<div class='clip' title='{html.escape(txt)}'>{inner}</div>"

st.sidebar.header("Dados")
uploaded = st.sidebar.file_uploader("Envie um Excel (.xlsx) ou CSV", type=["xlsx","xls","csv"])

source = None
if uploaded is not None:
    source = uploaded
else:
    if os.path.exists("servidores.xlsx"):
        source = "servidores.xlsx"
    else:
        xfiles = sorted(glob.glob("*.xlsx"))
        if xfiles:
            source = xfiles[0]

if source is None:
    st.info("Envie um arquivo na barra lateral **ou** coloque um .xlsx (ex.: FULL MIDD - 2025.xlsx) na mesma pasta do app.")
    st.stop()

df, colmap = load_data(source)
col_equipe = pick_col(df, ALIASES["equipe"])
col_sistema = pick_col(df, ALIASES["sistema"])
col_desc   = pick_col(df, ALIASES["descricao"])
col_host   = pick_col(df, ALIASES["hostname"])
col_amb    = pick_col(df, ALIASES["ambiente"])
col_status = pick_col(df, ALIASES["status"])

st.sidebar.header("Filtros")

equipe_opts = sorted(df[col_equipe].dropna().unique()) if col_equipe else []
equipe_sel  = st.sidebar.multiselect("Equipe", equipe_opts, default=[])
df_f = filter_df(df, col_equipe, equipe_sel)

ambiente_opts = sorted(df_f[col_amb].dropna().unique()) if col_amb else []
ambiente_sel  = st.sidebar.multiselect("Ambiente", ambiente_opts, default=[])
df_f = filter_df(df_f, col_amb, ambiente_sel)

sistema_opts = sorted(df_f[col_sistema].dropna().unique()) if col_sistema else []
sistema_sel  = st.sidebar.multiselect("Sistema", sistema_opts, default=[])
df_f = filter_df(df_f, col_sistema, sistema_sel)

desc_opts = sorted(df_f[col_desc].dropna().unique()) if col_desc else []
desc_sel  = st.sidebar.multiselect("Descrição", desc_opts, default=[])
df_f = filter_df(df_f, col_desc, desc_sel)

query = st.sidebar.text_input("Busca (hostname/nome/descrição)", placeholder="ex.: web01, prd, oracle")
df_f = text_search(df_f, [col_host, col_desc], query)

st.sidebar.subheader("Colar lista de servidores")
paste_text = st.sidebar.text_area(
    "Cole aqui (um por linha, vírgula ou espaço)",
    placeholder="srv-app-01\nsrv-app-02\nsrv-db-03"
)
match_contains = st.sidebar.checkbox("Permitir correspondência por 'contém' (parciais)", value=False)

id_col = col_host or col_desc
if id_col and paste_text:
    wanted = parse_server_list(paste_text)  # tudo em lower()
    series_lower = df_f[id_col].astype(str).str.lower()
    if match_contains:
        mask = series_lower.apply(lambda x: any(w in x for w in wanted))
        df_f = df_f[mask]
    else:
        df_f = df_f[series_lower.isin(wanted)]

st.sidebar.header("Opções de visualização")
all_cols = list(df_f.columns)
default_cols = [c for c in [col_host, col_equipe, col_amb, col_sistema, col_desc] if c and c in all_cols]
if not default_cols:
    default_cols = all_cols
cols_selected = st.sidebar.multiselect("Colunas para mostrar", all_cols, default=default_cols)

page_size = st.sidebar.selectbox("Linhas por página", [25, 50, 100, 200], index=1)
max_page = max(1, (len(df_f) + page_size - 1) // page_size)
page = st.sidebar.number_input("Página", min_value=1, max_value=int(max_page), value=1, step=1)

st.title("Explorer de Servidores")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total (base)", len(df))
c2.metric("Filtrados", len(df_f))
if col_equipe: c3.metric("Equipes", df[col_equipe].nunique())
if col_amb:    c4.metric("Ambientes", df[col_amb].nunique())

disp = df_f.copy()

amb_disp_name = None
if col_amb and col_amb in disp.columns:
    disp["_amb_badge"] = disp[col_amb].astype(str).map(badge_for_amb)
    amb_disp_name = colmap.get(col_amb, col_amb)
    disp[amb_disp_name] = disp["_amb_badge"]
    disp.drop(columns=[col_amb, "_amb_badge"], inplace=True)

# renomeia colunas para os cabeçalhos originais
rename_back = {c: colmap.get(c, c) for c in disp.columns if c in colmap}
disp.rename(columns=rename_back, inplace=True)

to_show = [colmap.get(c, c) for c in cols_selected if (colmap.get(c, c) in disp.columns)]
# paginação
start = (int(page)-1)*int(page_size)
end = start + int(page_size)
disp_page = disp[to_show].iloc[start:end] if to_show else disp.iloc[start:end]

rich_cols = {amb_disp_name} if amb_disp_name else set()
disp_vis = disp_page.copy()
for c in disp_vis.columns:
    is_rich = c in rich_cols  # preserva HTML do badge
    disp_vis[c] = disp_vis[c].apply(lambda v: cell_html(v, rich=is_rich))

st.write(f"Mostrando linhas {start+1}–{min(end, len(disp))} de {len(disp)}")
st.write(disp_vis.to_html(escape=False, index=False, classes="dataframe"), unsafe_allow_html=True)

st.subheader("Detalhes do servidor (todas as colunas)")
if id_col and id_col in df_f.columns and not df_f.empty:
    if paste_text:
        wanted_display = parse_server_list(paste_text)
        id_series = df_f[id_col].astype(str)
        chosen_list = []
        for w in wanted_display:
            if match_contains:
                hits = id_series[id_series.str.lower().str.contains(w)].tolist()
                chosen_list.extend(hits)
            else:
                hits = id_series[id_series.str.lower() == w].tolist()
                chosen_list.extend(hits)
        # remove duplicados preservando ordem
        seen, ordered = set(), []
        for h in chosen_list:
            if h not in seen:
                seen.add(h)
                ordered.append(h)
    else:
        opts = sorted(df_f[id_col].dropna().astype(str).unique())
        chosen = st.selectbox("Selecione um servidor", opts) if opts else None
        ordered = [chosen] if chosen else []

    for chosen in ordered:
        row = df_f[df_f[id_col].astype(str) == str(chosen)]
        if len(row) >= 1:
            r = row.iloc[0].copy()
            series = pd.Series({colmap.get(k, k): v for k, v in r.items()})
            st.markdown(f"**{chosen}**")
            st.table(series.reset_index().rename(columns={"index":"Campo",0:"Valor"}))
else:
    st.caption("Nenhum servidor disponível com os filtros atuais.")

# ===================== Downloads =====================
st.download_button(
    "Baixar (CSV)",
    data=df_f.to_csv(index=False).encode("utf-8"),
    file_name="servidores_filtrado.csv",
    mime="text/csv"
)
st.download_button(
    "Baixar (XLSX)",
    data=to_xlsx_bytes(df_f.rename(columns={c: colmap.get(c, c) for c in df_f.columns})),
    file_name="servidores_filtrado.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.caption("Cole vários servidores na barra lateral para filtrar de uma vez. Linhas da tabela são limitadas visualmente a 3 linhas (passe o mouse para ver o conteúdo completo).")
