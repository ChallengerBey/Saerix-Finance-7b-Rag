import pandas as pd
from pathlib import Path

EXCEL_PATH = "EVDS_14-07-2026.xlsx"
SERIES_NAMES = {
    "TP_DK_USD_A_YTL": "USD/TRY (YTL)",
    "TP_DK_USD_A_EF_YTL": "USD/TRY efektif",
    "TP_RK_T1_Y": "Reel kesim güven (mevsimsel)",
    "TP_RK_T2_Y": "Reel kesim güven (arındırılmamış)",
    "TP_RK_T3_Y": "Reel kesim güven trend",
    "TP_PKAUO_S01_A_U": "İhtiyaç Kredisi (TL, %)",
    "TP_PKAUO_S01_B_U": "Taşıt Kredisi (TL, %)",
    "TP_PKAUO_S01_C_U": "Konut Kredisi (TL, %)",
    "TP_PKAUO_S01_D_U": "Ticari Krediler (TL, %)",
    "TP_PKAUO_S01_E_U": "Ticari Krediler (döviz, %)",
    "TP_HUFE_GK378119440": "HUFE endeksi",
    "TP_HUFE_GK18197": "HUFE alt kalem 1",
    "TP_HUFE_GK18199": "HUFE alt kalem 2",
    "TP_YI001": "Genç işsizlik (toplam)",
    "TP_YI002_DE": "Genç işsizlik (DE)",
    "TP_YI003_AT": "Genç işsizlik (AT)",
    "TP_YI004_BE": "Genç işsizlik (BE)",
}


def load_evds_excel(path: str = EXCEL_PATH) -> pd.DataFrame:
    df = pd.read_excel(path)
    df["Tarih"] = pd.to_datetime(df["Tarih"], format="%Y-%m", errors="coerce")
    for c in df.columns:
        if c != "Tarih":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("Tarih")


def get_latest(df: pd.DataFrame, column: str) -> float:
    return df[column].dropna().iloc[-1]


def get_trend(df: pd.DataFrame, column: str, months: int = 3) -> str:
    df = df.dropna(subset=[column]).tail(months + 5)
    vals = df[column].dropna().tail(months)
    if len(vals) < 2:
        return "yetersiz veri"
    pct = (vals.iloc[-1] - vals.iloc[0]) / vals.iloc[0] * 100
    direction = "yukari" if pct > 0 else "asagi"
    return f"{direction} (%{pct:+.1f}, son {months} ay)"


def format_macro_context(df: pd.DataFrame) -> str:
    df = df.dropna(subset=["Tarih"])
    son_tarih = df["Tarih"].max()
    lines = [f"MAKRO VERI (guncel: {son_tarih.strftime('%Y-%m')})", ""]

    for col, name in SERIES_NAMES.items():
        if col not in df.columns:
            continue
        son_df = df.dropna(subset=[col])
        if son_df.empty:
            lines.append(f"  {name}: veri yok")
            continue
        son_val = son_df[col].iloc[-1]
        trend = get_trend(df, col)
        lines.append(f"  {name}: {son_val:.2f} | {trend}")

    return "\n".join(lines)


def format_inflation_context(df: pd.DataFrame) -> str:
    df = df.dropna(subset=["Tarih"])
    hufe_cols = [c for c in df.columns if "HUFE" in c]
    if not hufe_cols:
        return "HUFE verisi yok"

    son = df.dropna(subset=hufe_cols).iloc[-1] if not df.dropna(subset=hufe_cols).empty else df.iloc[-1]
    onceki_idx = df.index.get_loc(son.name) - 1 if son.name in df.index else -1
    onceki = df.iloc[onceki_idx] if onceki_idx >= 0 else son
    lines = ["HUFE (URE) VERILERI:", ""]

    for col in hufe_cols:
        name = SERIES_NAMES.get(col, col)
        if pd.notna(son[col]) and pd.notna(onceki[col]) and onceki[col] != 0:
            aylik = (son[col] - onceki[col]) / onceki[col] * 100
            lines.append(f"  {name}: {son[col]:.2f} (aylik %{aylik:+.2f})")

    return "\n".join(lines)


if __name__ == "__main__":
    df = load_evds_excel()
    print(f"Yuklendi: {len(df)} satir, {len([c for c in df.columns if c != 'Tarih'])} seri")
    print(f"Tarih araligi: {df['Tarih'].min()} -> {df['Tarih'].max()}")
    print()
    print(format_macro_context(df))
    print()
    print(format_inflation_context(df))
