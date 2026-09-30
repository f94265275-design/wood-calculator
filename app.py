import streamlit as st
import pandas as pd
from collections import Counter
import json
import os
import io

# 設定網頁標題與圖示
st.set_page_config(page_title="木材切割配置計算器", layout="wide", page_icon="🪵")

# 設定檔儲存路徑
CONFIG_FILE = "config.json"

# 預設參數 (包含「備註」欄位)
DEFAULT_CONFIG = {
    "log_length": 4280.0,
    "trim_length": 50.0,
    "kerf_width": 3.5,
    "max_species": 3,
    "box_count": 50,
    "items": [
        {"裁切長度 (mm)": 2467, "單箱需求 (支)": 4, "備註": "肚"},
        {"裁切長度 (mm)": 2285, "單箱需求 (支)": 9, "備註": "肚、頭、背、原2287"},
        {"裁切長度 (mm)": 1753, "單箱需求 (支)": 2, "備註": "上蓋"},
        {"裁切長度 (mm)": 1520, "單箱需求 (支)": 4, "備註": "肚、原1522"},
        {"裁切長度 (mm)": 1194, "單箱需求 (支)": 4, "備註": "頭、背"},
        {"裁切長度 (mm)": 1012, "單箱需求 (支)": 7, "備註": "上蓋、背、原1014"},
        {"裁切長度 (mm)": 635, "單箱需求 (支)": 2, "備註": "背"},
        {"裁切長度 (mm)": 770, "單箱需求 (支)": 6, "備註": "肚"},
        {"裁切長度 (mm)": 545, "單箱需求 (支)": 6, "備註": "肚"},
        {"裁切長度 (mm)": 822, "單箱需求 (支)": 2, "備註": "背"},
        {"裁切長度 (mm)": 273, "單箱需求 (支)": 2, "備註": "背"},
        {"裁切長度 (mm)": 89, "單箱需求 (支)": 6, "備註": ""}
    ]
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(config_data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=4)

def format_num(val):
    """去除無意義的小數點，例如 1194.0 轉為 1194"""
    if isinstance(val, (float, int)):
        if float(val).is_integer():
            return str(int(val))
        return f"{float(val):.1f}"
    return str(val)

config = load_config()

st.title("🪵 木材切割排程優化工具")
st.caption("自動進行最佳化組合，支援首刀齊頭、鋸片厚度扣除、規格種類限制、備註欄位與一鍵導出表格。")

st.markdown("---")

col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("⚙️ 參數設定")
    log_length = st.number_input("原木單根總長 (mm):", value=float(config.get("log_length", 4880.0)), step=100.0)
    trim_length = st.number_input("首刀齊頭/修邊長度 (mm):", value=float(config.get("trim_length", 20.0)), step=5.0)
    kerf_width = st.number_input("鋸片厚度 / 鋸縫 (mm):", value=float(config.get("kerf_width", 3.5)), step=0.5)
    max_species = st.number_input("單根原木最多允許規格種類數:", value=int(config.get("max_species", 3)), min_value=1, max_value=10, step=1)
    
    effective_log_length = log_length - trim_length - (kerf_width if trim_length > 0 else 0)
    st.info(f"💡 扣除齊頭與鋸縫後，單根可用長度為：**{format_num(effective_log_length)} mm**")

    st.markdown("---")
    st.subheader("📦 箱數與裁切需求")
    
    box_count = st.number_input("📦 預計生產總箱數 (箱):", value=int(config.get("box_count", 30)), min_value=1, step=1)
    
    st.write("請輸入單個木箱所需的裁切尺寸、單箱數量與備註：")
    current_df = pd.DataFrame(config.get("items", DEFAULT_CONFIG["items"]))
    
    if "備註" not in current_df.columns:
        current_df["備註"] = ""
    current_df = current_df[["裁切長度 (mm)", "單箱需求 (支)", "備註"]]

    edited_df = st.data_editor(
        current_df, 
        num_rows="dynamic", 
        use_container_width=True
    )
    
    if st.button("💾 儲存目前輸入為預設值", use_container_width=True):
        new_config = {
            "log_length": log_length,
            "trim_length": trim_length,
            "kerf_width": kerf_width,
            "max_species": max_species,
            "box_count": box_count,
            "items": edited_df.dropna(subset=["裁切長度 (mm)", "單箱需求 (支)"]).to_dict(orient="records")
        }
        save_config(new_config)
        st.toast("✅ 已成功記憶常用規格與參數！下次開啟將自動載入。", icon="💾")

with col2:
    st.subheader("📊 批量裁切生產單")
    
    if st.button("🚀 開始計算最佳排程", type="primary", use_container_width=True):
        demand = {}
        total_pieces_needed = 0
        
        for index, row in edited_df.dropna(subset=["裁切長度 (mm)", "單箱需求 (支)"]).iterrows():
            try:
                l = float(row["裁切長度 (mm)"])
                per_box = int(row["單箱需求 (支)"])
                note = str(row["備註"]).strip() if pd.notna(row["備註"]) else ""
                total_qty = per_box * box_count
                
                if l > 0 and total_qty > 0:
                    key = (l, note)
                    demand[key] = demand.get(key, 0) + total_qty
                    total_pieces_needed += total_qty
            except Exception:
                pass

        if not demand:
            st.warning("請先在左側輸入有效的裁切需求與數量！")
        elif effective_log_length <= 0:
            st.error("齊頭扣除長度大於或等於原木長度，請重新確認參數！")
        else:
            pattern_list = []

            while sum(demand.values()) > 0:
                current_log_pieces = []
                remaining_len = effective_log_length
                species_set = set()

                available_keys = sorted([k for k, count in demand.items() if count > 0], key=lambda x: x[0], reverse=True)
                made_cut = False
                
                for key in available_keys:
                    item_length, item_note = key
                    item_space = item_length + kerf_width
                    
                    while demand[key] > 0:
                        actual_deduction = item_length if remaining_len == item_length else item_space
                        can_fit = remaining_len >= actual_deduction
                        spec_allowed = len(species_set | {key}) <= max_species

                        if can_fit and spec_allowed:
                            current_log_pieces.append(key)
                            remaining_len -= actual_deduction
                            species_set.add(key)
                            demand[key] -= 1
                            made_cut = True
                        else:
                            break

                if not made_cut:
                    st.error("警告：有規格長度大於單根可用長度，無法進行裁切！")
                    break

                current_log_pieces.sort(key=lambda x: x[0], reverse=True)
                total_scrap = remaining_len + trim_length + (kerf_width if trim_length > 0 else 0)
                pattern_list.append((tuple(current_log_pieces), max(0, total_scrap)))

            pattern_counts = Counter(pattern_list)
            total_logs = len(pattern_list)
            
            st.success(f"計算完成！生產 **{box_count}** 箱（共 **{total_pieces_needed}** 支木材），總共需要原木數量：**{total_logs}** 根")

            # 建立用於匯出的原始資料表 (DataFrame)
            export_rows = []
            pattern_idx = 1
            for (pieces, scrap), count in pattern_counts.items():
                piece_counts = Counter(pieces)
                used_length = sum(size for size, note in pieces)
                utilization = (used_length / log_length) * 100
                trim_str = f"{format_num(trim_length)} mm" if trim_length > 0 else "無"

                for (size, note), qty in piece_counts.items():
                    export_rows.append({
                        "裁切模式": f"模式 {pattern_idx}",
                        "重複使用原木數": f"{count} 根",
                        "首刀齊頭": trim_str,
                        "裁切尺寸 (mm)": format_num(size),
                        "數量 (支)": f"{qty} 支",
                        "備註": note if note else "-",
                        "單根廢料": f"{format_num(round(scrap, 1))} mm",
                        "材料利用率": f"{utilization:.1f}%"
                    })
                pattern_idx += 1

            export_df = pd.DataFrame(export_rows)

            # 將 CSV 轉為帶 BOM 的 UTF-8 格式，防止 Excel 開啟時中文亂碼
            csv_data = export_df.to_csv(index=False, encoding="utf-8-sig")

            # 放置導出下載按鈕
            st.download_button(
                label="📥 下載生產單 CSV 檔案",
                data=csv_data,
                file_name=f"木材裁切生產單_{box_count}箱.csv",
                mime="text/csv",
                use_container_width=True
            )

            # HTML & CSS 生產單表格
            html_code = """
            <style>
                .custom-table {
                    width: 100%;
                    border-collapse: collapse;
                    border: 4px solid #000000;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    text-align: center;
                    margin-top: 10px;
                }
                .custom-table th {
                    border-bottom: 4px solid #000000;
                    border-right: 1px solid #e0e0e0;
                    padding: 12px 8px;
                    background-color: #f8f9fa;
                    font-size: 15px;
                    font-weight: 700;
                }
                .custom-table th:last-child {
                    border-right: none;
                }
                .custom-table td {
                    border-right: 1px solid #e0e0e0;
                    padding: 10px 8px;
                    vertical-align: middle;
                    font-size: 14px;
                    height: 40px;
                    box-sizing: border-box;
                }
                .custom-table td:last-child {
                    border-right: none;
                }
                .mode-group {
                    border-bottom: 4px solid #000000;
                }
                .mode-group:last-child {
                    border-bottom: none;
                }
                .sub-border {
                    border-bottom: 1px solid #000000;
                }
            </style>
            <table class="custom-table">
                <thead>
                    <tr>
                        <th>裁切模式</th>
                        <th>重複使用原木數</th>
                        <th>首刀齊頭</th>
                        <th>裁切尺寸 (mm)</th>
                        <th>數量 (支)</th>
                        <th>備註</th>
                        <th>單根廢料</th>
                        <th>材料利用率</th>
                    </tr>
                </thead>
            """

            pattern_idx = 1
            for (pieces, scrap), count in pattern_counts.items():
                piece_counts = Counter(pieces)
                used_length = sum(size for size, note in pieces)
                utilization = (used_length / log_length) * 100
                trim_str = f"{format_num(trim_length)} mm" if trim_length > 0 else "無"
                
                items_list = list(piece_counts.items())
                row_span = len(items_list)
                
                html_code += '<tbody class="mode-group">'
                
                for i, ((size, note), qty) in enumerate(items_list):
                    is_last_item = (i == row_span - 1)
                    td_class = '' if is_last_item else ' class="sub-border"'
                    
                    html_code += '<tr>'
                    
                    if i == 0:
                        html_code += f'<td rowspan="{row_span}">模式 {pattern_idx}</td>'
                        html_code += f'<td rowspan="{row_span}"><b>【 {count} 根 】</b></td>'
                        html_code += f'<td rowspan="{row_span}">{trim_str}</td>'
                    
                    html_code += f'<td{td_class}>{format_num(size)}</td>'
                    html_code += f'<td{td_class}>{qty} 支</td>'
                    html_code += f'<td{td_class}>{note if note else "-"}</td>'
                    
                    if i == 0:
                        html_code += f'<td rowspan="{row_span}">{format_num(round(scrap, 1))} mm</td>'
                        html_code += f'<td rowspan="{row_span}">{utilization:.1f}%</td>'
                    
                    html_code += '</tr>'
                
                html_code += '</tbody>'
                pattern_idx += 1

            html_code += "</table>"

            clean_html = "".join([line.strip() for line in html_code.split("\n")])
            st.markdown(clean_html, unsafe_allow_html=True)