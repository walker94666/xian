import streamlit as st
import cv2
import numpy as np
from PIL import Image
import requests

# === 設定網頁標題與配置 ===
st.set_page_config(page_title="HSI 色彩空間轉換器", layout="wide")

st.title("🎨 HSI 色彩空間轉換器 Web 版")
st.markdown("上傳圖片或輸入網址，即時調整 HSI 參數！")

# === HSI 核心演算法 ===
@st.cache_data
def bgr_to_hsi(img_bgr):
    img_float = img_bgr.astype(np.float32) / 255.0
    B, G, R = cv2.split(img_float)
    I = (R + G + B) / 3.0
    
    sum_rgb = R + G + B
    min_rgb = np.minimum(np.minimum(R, G), B)
    S = 1.0 - (3.0 * min_rgb / (sum_rgb + 1e-6))
    S[sum_rgb == 0] = 0

    num = 0.5 * ((R - G) + (R - B))
    den = np.sqrt((R - G)**2 + (R - B) * (G - B))
    theta = np.arccos(num / (den + 1e-6)) 

    H = np.degrees(theta)
    H[B > G] = 360.0 - H[B > G]
    return H, S * 255.0, I * 255.0

def hsi_to_bgr(H, S, I):
    H = H % 360
    S = S / 255.0
    I = I / 255.0
    R = np.zeros_like(I)
    G = np.zeros_like(I)
    B = np.zeros_like(I)
    H_rad = np.radians(H)

    # Sector 1: 0 <= H < 120
    idx = (H >= 0) & (H < 120)
    if np.any(idx):
        b_val = I[idx] * (1 - S[idx])
        r_val = I[idx] * (1 + (S[idx] * np.cos(H_rad[idx])) / (np.cos(np.radians(60) - H_rad[idx]) + 1e-6))
        g_val = 3 * I[idx] - (r_val + b_val)
        B[idx], R[idx], G[idx] = b_val, r_val, g_val

    # Sector 2: 120 <= H < 240
    idx = (H >= 120) & (H < 240)
    if np.any(idx):
        H_shifted = H_rad[idx] - np.radians(120)
        r_val = I[idx] * (1 - S[idx])
        g_val = I[idx] * (1 + (S[idx] * np.cos(H_shifted)) / (np.cos(np.radians(60) - H_shifted) + 1e-6))
        b_val = 3 * I[idx] - (r_val + g_val)
        R[idx], G[idx], B[idx] = r_val, g_val, b_val

    # Sector 3: 240 <= H < 360
    idx = (H >= 240)
    if np.any(idx):
        H_shifted = H_rad[idx] - np.radians(240)
        g_val = I[idx] * (1 - S[idx])
        b_val = I[idx] * (1 + (S[idx] * np.cos(H_shifted)) / (np.cos(np.radians(60) - H_shifted) + 1e-6))
        r_val = 3 * I[idx] - (g_val + b_val)
        G[idx], B[idx], R[idx] = g_val, b_val, r_val

    img_bgr = cv2.merge([B, G, R])
    img_bgr = np.clip(img_bgr * 255.0, 0, 255).astype(np.uint8)
    return img_bgr

# === 側邊欄控制區 ===
st.sidebar.header("⚙️ 控制面板")

source_option = st.sidebar.radio("圖片來源", ["上傳檔案", "輸入網址 URL"])
img_bgr_original = None

if source_option == "上傳檔案":
    uploaded_file = st.sidebar.file_uploader("選擇圖片", type=['jpg', 'png', 'jpeg', 'webp'])
    if uploaded_file is not None:
        file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
        img_bgr_original = cv2.imdecode(file_bytes, 1)

elif source_option == "輸入網址 URL":
    url = st.sidebar.text_input("圖片網址", placeholder="https://example.com/image.jpg")
    if url:
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, stream=True)
            if resp.status_code == 200:
                file_bytes = np.asarray(bytearray(resp.content), dtype=np.uint8)
                img_bgr_original = cv2.imdecode(file_bytes, 1)
            else:
                st.sidebar.error("無法讀取網址")
        except:
            st.sidebar.error("網址格式錯誤或無法連線")

# === 參數調整滑桿 ===
st.sidebar.subheader("HSI 參數")

col1, col2, col3, col4 = st.sidebar.columns(4)
hue_default, sat_default, val_default = 180, 100, 100

if col1.button("復古"):
    hue_default, sat_default, val_default = 150, 80, 110
if col2.button("冷色"):
    hue_default, sat_default, val_default = 160, 115, 100
if col3.button("暖色"):
    hue_default, sat_default, val_default = 200, 120, 105
if col4.button("重設"):
    hue_default, sat_default, val_default = 180, 100, 100

hue_val = st.sidebar.slider("色相 (Hue)", 0, 360, hue_default, key="hue")
sat_val = st.sidebar.slider("飽和度 (Sat %)", 0, 300, sat_default, key="sat")
val_val = st.sidebar.slider("強度 (Int %)", 0, 300, val_default, key="val")

# === 主要顯示區 ===
if img_bgr_original is not None:
    # 計算 HSI
    with st.spinner("正在分析 HSI 色彩空間..."):
        h_orig, s_orig, i_orig = bgr_to_hsi(img_bgr_original)

    hue_shift = hue_val - 180
    sat_factor = sat_val / 100.0
    val_factor = val_val / 100.0

    h_new = (h_orig + hue_shift) % 360
    s_new = np.clip(s_orig * sat_factor, 0, 255)
    i_new = np.clip(i_orig * val_factor, 0, 255)

    img_bgr_final = hsi_to_bgr(h_new, s_new, i_new)

    img_rgb_orig = cv2.cvtColor(img_bgr_original, cv2.COLOR_BGR2RGB)
    img_rgb_final = cv2.cvtColor(img_bgr_final, cv2.COLOR_BGR2RGB)

    col_orig, col_res = st.columns(2)
    
    with col_orig:
        st.subheader("原始圖片")
        st.image(img_rgb_orig, use_container_width=True)

    with col_res:
        st.subheader("調整結果")
        st.image(img_rgb_final, use_container_width=True)

else:
    st.info("👈 請從左側選單上傳圖片或貼上網址開始使用！")