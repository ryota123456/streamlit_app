import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(page_title="チーズ需給データ可視化", layout="wide")
st.title("チーズ需給データ可視化")

def read_estat_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    header_idx = None
    for i, line in enumerate(lines):
        if "各種チーズ" in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("ヘッダー行（各種チーズを含む行）が見つかりませんでした。")
    return pd.read_csv(path, skiprows=header_idx, engine="python")

df = read_estat_csv("FEH_00500509_260126101555.csv")

label_cols = [c for c in df.columns if "各種チーズ" in str(c)]
if len(label_cols) == 0:
    st.error("指標名の列（各種チーズ）が見つかりませんでした。")
    st.stop()
label_col = label_cols[-1]

year_cols = [c for c in df.columns if ("平成" in str(c) and "年" in str(c)) or ("令和" in str(c) and "年" in str(c))]
if len(year_cols) == 0:
    st.error("年の列（平成/令和○年）が見つかりませんでした。")
    st.stop()

def to_num(x):
    s = str(x).replace(",", "").strip()
    if s in ["", "-", "***"]:
        return np.nan
    try:
        return float(s)
    except:
        return np.nan

tmp = df[[label_col] + year_cols].copy()
tmp = tmp.rename(columns={label_col: "指標"})
for c in year_cols:
    tmp[c] = tmp[c].apply(to_num)

long_df = tmp.melt(id_vars="指標", var_name="年", value_name="値").dropna(subset=["値"])

def era_to_year(y):
    y = str(y).strip()
    if "平成" in y and "年" in y:
        n = y.replace("平成", "").replace("年", "")
        try:
            return 1988 + int(n)
        except:
            return np.nan
    if "令和" in y and "年" in y:
        n = y.replace("令和", "").replace("年", "")
        try:
            return 2018 + int(n)
        except:
            return np.nan
    return np.nan

long_df["西暦"] = long_df["年"].apply(era_to_year)
years = sorted(long_df["西暦"].dropna().unique().astype(int))
all_inds = sorted(long_df["指標"].dropna().unique())

if len(years) == 0 or len(all_inds) == 0:
    st.error("データの整形に失敗しました（年または指標が取得できません）。")
    st.stop()

with st.sidebar:
    st.subheader("条件設定")
    inds = st.multiselect("指標（複数選択可）", options=all_inds, default=all_inds[:2] if len(all_inds) >= 2 else all_inds)
    y0, y1 = st.slider("期間（西暦）", min_value=int(years[0]), max_value=int(years[-1]), value=(int(years[0]), int(years[-1])), step=1)
    view = st.radio("表示", ["グラフ", "表"])
    chart = st.radio("グラフ種類", ["折れ線", "棒", "散布図（2指標）"])
    st.caption("※ 指標により単位が異なります。")

if len(inds) == 0:
    st.warning("サイドバーで指標を1つ以上選んでください。")
    st.stop()

f = long_df[(long_df["指標"].isin(inds)) & (long_df["西暦"].between(y0, y1))].copy()
f = f.sort_values("西暦")

wide = f.pivot_table(index="西暦", columns="指標", values="値", aggfunc="mean").sort_index()

tab1, tab2, tab3 = st.tabs(["可視化", "データ確認", "解釈・考察"])

with tab1:
    st.subheader("可視化")
    if view == "表":
        st.dataframe(wide, use_container_width=True, height=360)
    else:
        if chart == "折れ線":
            st.line_chart(wide)
        elif chart == "棒":
            if wide.shape[0] == 0:
                st.warning("表示できるデータがありません。")
            else:
                idx_list = list(wide.index)
                target_year = st.selectbox("比較する年（西暦）", options=idx_list, index=len(idx_list) - 1)
                one = wide.loc[[target_year]].T
                one.columns = [str(target_year)]
                st.bar_chart(one)
        else:
            if len(inds) < 2:
                st.info("散布図は指標を2つ以上選択してください。")
            else:
                x_ind = st.selectbox("X軸の指標", inds, index=0)
                y_ind = st.selectbox("Y軸の指標", inds, index=1 if len(inds) > 1 else 0)
                if x_ind == y_ind:
                    st.info("X軸とY軸は別の指標を選ぶと見やすいです。")
                cols = [c for c in [x_ind, y_ind] if c in wide.columns]
                sct = wide[cols].dropna().reset_index(drop=True)
                if len(cols) < 2 or sct.shape[0] == 0:
                    st.warning("散布図に必要なデータが不足しています。")
                else:
                    st.scatter_chart(sct, x=x_ind, y=y_ind)

    st.download_button(
        "絞り込み結果をCSVでダウンロード",
        data=f.to_csv(index=False).encode("utf-8-sig"),
        file_name="filtered_cheese_data.csv",
        mime="text/csv"
    )

with tab2:
    st.subheader("データ確認")
    st.write(f"レコード数：{len(f)}")
    st.dataframe(f.head(30), use_container_width=True)

    with st.expander("列の意味（簡易）"):
        st.markdown(
            "- 指標：チーズ需給表の項目名（生産量、輸入量、消費量、国産割合など）\n"
            "- 年：平成/令和の年次\n"
            "- 値：指標の値"
        )

with tab3:
    st.subheader("比較")

    ind0 = inds[0]
    tmp0 = f[f["指標"] == ind0].sort_values("西暦")
    if tmp0["西暦"].nunique() >= 2:
        first_y = int(tmp0["西暦"].iloc[0])
        last_y = int(tmp0["西暦"].iloc[-1])
        first_v = float(tmp0["値"].iloc[0])
        last_v = float(tmp0["値"].iloc[-1])
        delta = last_v - first_v
        st.info(
            f"『{ind0}』は {first_y}年→{last_y}年で "
            f"{'増加' if delta > 0 else '減少' if delta < 0 else '横ばい'}（差分 {delta:.2f}）です。"
        )
    else:
        st.info("期間内のデータ点が少ないため、増減の自動判定ができません。")

