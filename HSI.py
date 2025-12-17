import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import math

# 設定 Windows 高 DPI 顯示支援，避免介面模糊
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

class HSIConverterApp:
    def __init__(self, master):
        self.master = master
        master.title("🎨 HSI 色彩空間轉換器")
        
        # 設定視窗關閉時的事件處理
        master.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 初始化變數
        self.file_path = None
        self.img_bgr_original = None
        
        # 儲存圖片轉換後的 HSI 原始數據 (浮點數格式)
        # H: 0~360 度, S: 0~255, I: 0~255
        self.h_orig = None
        self.s_orig = None
        self.i_orig = None 
        
        # 畫布圖片參照 (防止被 Python 回收機制清除)
        self.canvas_img_original_ref = None 
        self.canvas_img_adjusted_ref = None

        # 初始化滑桿變數
        self.hue_var = tk.IntVar(value=180)  # 色相 (偏移量基準)
        self.sat_var = tk.IntVar(value=100)  # 飽和度 (百分比)
        self.val_var = tk.IntVar(value=100)  # 強度 (百分比)
        
        # 綁定變數變更事件，當數值改變時即時更新圖片
        self.hue_var.trace_add('write', lambda *args: self.update_hsi(None))
        self.sat_var.trace_add('write', lambda *args: self.update_hsi(None))
        self.val_var.trace_add('write', lambda *args: self.update_hsi(None))

        # 設定 Grid 佈局權重
        master.grid_columnconfigure(0, weight=1) 
        master.grid_rowconfigure(0, weight=1)

        # === 圖片顯示區塊 ===
        self.image_frame = ttk.Frame(master)
        self.image_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.image_frame.grid_rowconfigure(0, weight=1)
        self.image_frame.grid_columnconfigure(0, weight=1) 
        
        self.canvas = tk.Canvas(self.image_frame, bg="gray")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Configure>", self.on_resize) 

        # === 控制面板區塊 ===
        self.control_frame = ttk.Frame(master, padding="10")
        self.control_frame.grid(row=0, column=1, sticky="ns")
        
        self.load_button = ttk.Button(self.control_frame, text="📂 點擊選擇圖片", command=self.load_image)
        self.load_button.pack(pady=10, fill='x')

        # 預設濾鏡區域
        filter_label = ttk.Label(self.control_frame, text="✨ 快速濾鏡", font=('Helvetica', 10, 'bold'))
        filter_label.pack(pady=(10, 5))
        
        self.filter_frame = ttk.Frame(self.control_frame)
        self.filter_frame.pack(pady=5)
        
        self.create_filter_button("復古", 180-30, 80, 110)
        self.create_filter_button("冷色調", 180-20, 115, 100)
        self.create_filter_button("暖色調", 180+20, 120, 105)
        self.create_filter_button("白平衡", 180, 100, 110)
        
        ttk.Separator(self.control_frame, orient='horizontal').pack(fill='x', pady=10)

        # 手動調整區域
        slider_label = ttk.Label(self.control_frame, text="⚙️ HSI 參數調整", font=('Helvetica', 10, 'bold'))
        slider_label.pack(pady=(5, 5))

        self.create_slider("色相 (Hue)", self.hue_var, 0, 360, "中心: 180", 180)
        self.create_slider("飽和度 (Sat)", self.sat_var, 0, 300, "中心: 100 (1x)", 100)
        self.create_slider("強度 (Int)", self.val_var, 0, 300, "中心: 100 (1x)", 100)
        
        # 初始狀態鎖定控制項
        self.set_controls_state(tk.DISABLED)

    def validate_input(self, text_var, min_val, max_val):
        """驗證輸入框數值是否在合法範圍內"""
        try:
            val = int(text_var.get())
            if min_val <= val <= max_val:
                return True
            else:
                text_var.set(max(min_val, min(max_val, val)))
                return False
        except ValueError:
            return False

    def create_filter_button(self, name, h, s, v):
        """建立濾鏡按鈕"""
        btn = ttk.Button(self.filter_frame, text=name, command=lambda: self.apply_filter(h, s, v))
        btn.pack(side=tk.LEFT, padx=5)

    def create_slider(self, label_text, var, from_, to, reset_text, default_value):
        """建立滑桿與輸入框元件"""
        frame = ttk.Frame(self.control_frame)
        frame.pack(pady=5, fill='x')
        
        top_frame = ttk.Frame(frame)
        top_frame.pack(fill='x')
        ttk.Label(top_frame, text=label_text).pack(side=tk.LEFT, anchor='w')
        
        entry = ttk.Entry(top_frame, width=5, textvariable=var, justify='center')
        entry.pack(side=tk.RIGHT, padx=5)

        slider = ttk.Scale(frame, from_=from_, to=to, variable=var)
        slider.pack(fill='x', padx=5, expand=True) 
        
        reset_btn = ttk.Button(frame, text="重設", command=lambda: self.reset_slider(var, default_value))
        reset_btn.pack(pady=(5, 0), anchor='e')

    def reset_slider(self, var, default_value):
        """重設滑桿至預設值"""
        var.set(default_value)

    def set_controls_state(self, state):
        """啟用或禁用控制面板元件"""
        for widget in self.control_frame.winfo_children():
            if widget != self.load_button:
                for child in widget.winfo_children():
                    try:
                        child.configure(state=state)
                    except:
                        pass
                try:
                    widget.configure(state=state)
                except:
                    pass
        self.load_button.config(state=tk.NORMAL)

    # ==========================================
    #  HSI 色彩空間轉換核心演算法
    # ==========================================

    def bgr_to_hsi(self, img_bgr):
        """
        將 BGR 影像轉換為 HSI 空間。
        數學定義：
        I (Intensity) = (R + G + B) / 3
        S (Saturation) = 1 - (3 / (R + G + B)) * min(R, G, B)
        H (Hue) = 幾何推導角度 (0-360度)
        """
        # 1. 將像素值正規化至 0.0 ~ 1.0 範圍
        img_float = img_bgr.astype(np.float32) / 255.0
        B, G, R = cv2.split(img_float)

        # 2. 計算強度 (Intensity)
        # 代表光的平均能量
        I = (R + G + B) / 3.0

        # 3. 計算飽和度 (Saturation)
        # 代表色彩的純度，公式：1 - 歸一化的最小通道值
        sum_rgb = R + G + B
        min_rgb = np.minimum(np.minimum(R, G), B)
        # 加 1e-6 是為了避免除以 0 的錯誤
        S = 1.0 - (3.0 * min_rgb / (sum_rgb + 1e-6))
        
        # 修正：當 RGB 總和為 0 (全黑) 時，飽和度定義為 0
        S[sum_rgb == 0] = 0

        # 4. 計算色相 (Hue)
        # 使用幾何法推導出的反餘弦公式
        num = 0.5 * ((R - G) + (R - B))
        den = np.sqrt((R - G)**2 + (R - B) * (G - B))
        theta = np.arccos(num / (den + 1e-6)) # 結果為弧度

        # 將弧度轉為角度
        H = np.degrees(theta)
        
        # 修正：若 B > G，角度需以 360 減去計算值 (因為 arccos 範圍僅 0-180)
        H[B > G] = 360.0 - H[B > G]

        # 5. 回傳結果
        # 將 S 與 I 映射回 0-255 以便後續處理，H 保持 0-360
        return H, S * 255.0, I * 255.0

    def hsi_to_bgr(self, H, S, I):
        """
        將 HSI 影像轉回 BGR 空間。
        由於 HSI 轉換 RGB 的公式依據色相角度分為三個扇形區間 (Sectors)，
        需分別計算。
        """
        # 1. 正規化數值
        H = H % 360      # 確保角度在 0-360 之間
        S = S / 255.0    # 轉回 0-1
        I = I / 255.0    # 轉回 0-1
        
        # 建立輸出通道矩陣
        R = np.zeros_like(I)
        G = np.zeros_like(I)
        B = np.zeros_like(I)

        # 將角度轉回弧度以進行三角函數運算
        H_rad = np.radians(H)

        # --- 第一扇區 (RG Sector): 0 <= H < 120 ---
        # 在此區間 B 是最小分量
        idx = (H >= 0) & (H < 120)
        if np.any(idx):
            b_val = I[idx] * (1 - S[idx])
            # R 的計算公式
            r_val = I[idx] * (1 + (S[idx] * np.cos(H_rad[idx])) / (np.cos(np.radians(60) - H_rad[idx]) + 1e-6))
            g_val = 3 * I[idx] - (r_val + b_val)
            B[idx], R[idx], G[idx] = b_val, r_val, g_val

        # --- 第二扇區 (GB Sector): 120 <= H < 240 ---
        # 在此區間 R 是最小分量
        idx = (H >= 120) & (H < 240)
        if np.any(idx):
            H_shifted = H_rad[idx] - np.radians(120) # 減去 120 度
            r_val = I[idx] * (1 - S[idx])
            g_val = I[idx] * (1 + (S[idx] * np.cos(H_shifted)) / (np.cos(np.radians(60) - H_shifted) + 1e-6))
            b_val = 3 * I[idx] - (r_val + g_val)
            R[idx], G[idx], B[idx] = r_val, g_val, b_val

        # --- 第三扇區 (BR Sector): 240 <= H < 360 ---
        # 在此區間 G 是最小分量
        idx = (H >= 240)
        if np.any(idx):
            H_shifted = H_rad[idx] - np.radians(240) # 減去 240 度
            g_val = I[idx] * (1 - S[idx])
            b_val = I[idx] * (1 + (S[idx] * np.cos(H_shifted)) / (np.cos(np.radians(60) - H_shifted) + 1e-6))
            r_val = 3 * I[idx] - (g_val + b_val)
            G[idx], B[idx], R[idx] = g_val, b_val, r_val

        # 2. 合併通道並轉換格式
        img_bgr = cv2.merge([B, G, R])
        # 限制數值在 0-255 並轉為無號整數 (uint8)
        img_bgr = np.clip(img_bgr * 255.0, 0, 255).astype(np.uint8)
        return img_bgr

    # ==========================================

    def load_image(self):
        """讀取影像並進行初始 HSI 轉換"""
        self.file_path = filedialog.askopenfilename(
            title="請選擇一張圖片",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.webp")]
        )
        
        if not self.file_path:
            return

        try:
            self.img_bgr_original = cv2.imdecode(np.fromfile(self.file_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        except Exception as e:
            print(f"讀取圖片失敗: {e}")
            return
            
        if self.img_bgr_original is None:
            print("讀取圖片失敗，請確認檔案是否損毀。")
            return

        # 載入圖片後，立即計算其 HSI 值並快取起來，供後續調整使用
        self.h_orig, self.s_orig, self.i_orig = self.bgr_to_hsi(self.img_bgr_original)

        self.set_controls_state(tk.NORMAL)
        # 重置滑桿
        self.hue_var.set(180)
        self.sat_var.set(100)
        self.val_var.set(100)
        
        # 顯示初始畫面
        self.update_hsi(None)

    def apply_filter(self, h, s, v):
        """套用預設濾鏡數值"""
        if self.img_bgr_original is None:
            return
        self.hue_var.set(h)
        self.sat_var.set(s)
        self.val_var.set(v)

    def update_hsi(self, event):
        """
        根據使用者調整的參數，重新計算 HSI 並顯示結果。
        流程：
        1. 讀取滑桿數值
        2. 計算調整後的 H, S, I 矩陣
        3. 將新矩陣轉回 BGR 以顯示
        """
        if self.img_bgr_original is None:
            return

        try:
            hue_slider = self.hue_var.get()
            sat_slider = self.sat_var.get()
            val_slider = self.val_var.get()
        except tk.TclError:
            return

        # 限制數值範圍
        hue_slider = np.clip(hue_slider, 0, 360)
        sat_slider = np.clip(sat_slider, 0, 300)
        val_slider = np.clip(val_slider, 0, 300)

        # 計算調整係數
        hue_shift = hue_slider - 180       # 色相偏移量 (-180 ~ +180)
        sat_factor = sat_slider / 100.0    # 飽和度倍率 (0.0 ~ 3.0)
        val_factor = val_slider / 100.0    # 強度倍率 (0.0 ~ 3.0)

        # 應用調整
        # 1. H (色相): 加法運算，並確保在 360 度內循環
        h_new = (self.h_orig + hue_shift) % 360  
        
        # 2. S (飽和度): 乘法運算，並限制最大值為 255
        s_new = np.clip(self.s_orig * sat_factor, 0, 255)
        
        # 3. I (強度): 乘法運算，並限制最大值為 255
        i_new = np.clip(self.i_orig * val_factor, 0, 255)

        # 4. 轉換回 BGR 色彩空間
        self.img_bgr_final = self.hsi_to_bgr(h_new, s_new, i_new)
        
        # 更新畫布顯示
        self.display_image()

    def on_resize(self, event):
        """處理視窗縮放事件"""
        if self.img_bgr_original is not None:
            self.display_image()

    def display_image(self):
        """將原始圖片與處理後的圖片並排顯示在 Canvas 上"""
        if self.img_bgr_original is None:
            self.canvas.delete("all")
            return

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            return
        
        # 計算縮放比例，讓兩張圖能並排塞入視窗
        max_display_width = canvas_width // 2 
        original_height, original_width = self.img_bgr_original.shape[:2]
        ratio_w = max_display_width / original_width
        ratio_h = canvas_height / original_height
        scale_ratio = min(ratio_w, ratio_h, 1.0) 

        new_width = int(original_width * scale_ratio)
        new_height = int(original_height * scale_ratio)
        
        if new_width <= 0 or new_height <= 0:
            return
            
        # 縮放原始圖片
        img_orig_resized_bgr = cv2.resize(self.img_bgr_original, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # 縮放處理後圖片 (防呆檢查)
        if not hasattr(self, 'img_bgr_final') or self.img_bgr_final is None:
             img_adj_resized_bgr = img_orig_resized_bgr
        else:
             img_adj_resized_bgr = cv2.resize(self.img_bgr_final, (new_width, new_height), interpolation=cv2.INTER_AREA)

        self.canvas.delete("all")

        # 計算顯示位置 (置中)
        total_image_width = new_width * 2 
        padding_x = (canvas_width - total_image_width) // 2
        center_y = canvas_height // 2
        
        # 繪製原始圖片 (左)
        img_orig_rgb = cv2.cvtColor(img_orig_resized_bgr, cv2.COLOR_BGR2RGB)
        img_orig_pil = Image.fromarray(img_orig_rgb)
        self.canvas_img_original_ref = ImageTk.PhotoImage(image=img_orig_pil)
        
        x_orig = padding_x + new_width // 2 
        self.canvas.create_image(x_orig, center_y, anchor=tk.CENTER, image=self.canvas_img_original_ref)
        self.canvas.create_text(x_orig, center_y - new_height // 2 - 15, text="原始圖片 (Original)", fill="white", font=('Helvetica', 10, 'bold'))

        # 繪製調整後圖片 (右)
        img_adj_rgb = cv2.cvtColor(img_adj_resized_bgr, cv2.COLOR_BGR2RGB)
        img_adj_pil = Image.fromarray(img_adj_rgb)
        self.canvas_img_adjusted_ref = ImageTk.PhotoImage(image=img_adj_pil)
        
        x_adj = padding_x + new_width + new_width // 2 
        self.canvas.create_image(x_adj, center_y, anchor=tk.CENTER, image=self.canvas_img_adjusted_ref)
        self.canvas.create_text(x_adj, center_y - new_height // 2 - 15, text="調整後 (HSI Adjusted)", fill="white", font=('Helvetica', 10, 'bold'))

        # 繪製分隔線
        self.canvas.create_line(canvas_width // 2, 0, canvas_width // 2, canvas_height, fill="white", dash=(4, 4))

    def on_closing(self):
        """程式關閉時清理資源"""
        print("應用程式關閉。")
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = HSIConverterApp(root)
    root.geometry("1000x600") 
    root.mainloop()