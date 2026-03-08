# Open Wallpaper Engine for Linux

**[English](README.md)** | **[繁體中文](README.zh-TW.md)** | **[日本語](README.ja.md)**

一個功能豐富的現代化 [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) 圖形介面，靈感來自 [Open Wallpaper Engine for macOS](https://github.com/haren724/open-wallpaper-engine-mac)。

> 在 GNOME 和 KDE 上可能會遇到一些問題。建議在平鋪式視窗管理器（如 i3、Hyprland、bspwm）上使用。KDE 使用者可以嘗試這個[外掛](https://github.com/catsout/wallpaper-engine-kde-plugin#build-and-install)。

## 功能特色

- **Mac 風格分割面板佈局** — 左側內容區域 + 右側預覽面板，顯示桌布詳情、屬性和控制項
- **分頁介面** — 頂部標籤列包含「已安裝」/「工作坊」/「設定」分頁
- **Steam 工作坊整合** — 瀏覽、搜尋、依標籤篩選（分級、類型、風格），透過 steamcmd 直接下載桌布
- **Steam Web API 搜尋** — 依熱門、最新、最受歡迎或訂閱數排序
- **steamcmd 驗證** — 支援密碼登入、Steam Guard 及快取登入
- **桌布媒體庫掃描器** — 自動偵測 Steam、Flatpak 和 Snap 安裝路徑的桌布
- **即時桌布屬性** — 從預覽面板載入並編輯桌布特定屬性（顏色、速度、開關等）
- **個別桌布設定** — 螢幕選擇、音量、FPS、縮放、邊緣處理、滑鼠/視差/全螢幕暫停開關
- **視窗模式** — 用於 KDE/GNOME 合成器相容性
- **檔案系統監控** — 新增或移除桌布時自動重新整理媒體庫
- **系統匣** — 最小化至系統匣，快速存取工作坊
- **自動還原** — 啟動時自動記憶並還原上次使用的桌布
- **多語系支援** — 支援 English、繁體中文、Deutsch、Español、Français、Русский、Українська

## 螢幕截圖

<img width="2560" height="1440" alt="截圖" src="https://github.com/user-attachments/assets/15c6dc78-f51b-4c1b-aeb1-f2bad88bc898" />
<img width="2560" height="1440" alt="截圖 (2)" src="https://github.com/user-attachments/assets/d36990b8-641a-44fe-b4ff-ca582d9494da" />

## 安裝方式（Arch Linux / Manjaro）

最簡單的方式是透過 AUR 安裝，會自動安裝後端引擎（`linux-wallpaperengine`）及所有依賴套件。

```bash
yay -S simple-linux-wallpaperengine-gui-git
```

## 安裝方式（Nix）

**Flake 安裝（建議）**

加入你的 flake inputs：
```nix
inputs = {
  simple-wallpaper-engine = {
    url = "github:Unayung/simple-linux-wallpaperengine-gui";
    inputs = {
      nixpkgs.follows = "nixpkgs";
      home-manager.follows = "home-manager";
    };
  };
};
```

然後在 home-manager 設定中：
```nix
{inputs, ...}: {
  imports = [inputs.simple-wallpaper-engine.homeManagerModules.default];
  programs.simple-wallpaper-engine.enable = true;
}
```

**指令式安裝**
```bash
nix profile install github:Unayung/simple-linux-wallpaperengine-gui
```

## 手動安裝

### 1. 前置需求（後端引擎）

這是一個 GUI 前端 — 你**必須**先安裝 [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine)。如果你是透過 AUR 安裝的，後端引擎會作為依賴套件自動安裝。

**Arch / Manjaro：**
```bash
yay -S linux-wallpaperengine
```

**Debian / Ubuntu / Fedora（從原始碼編譯）：**

詳細說明請參考[這裡](https://github.com/Almamu/linux-wallpaperengine#compiling)：
```bash
# Debian/Ubuntu
sudo apt install build-essential cmake libx11-dev libxrandr-dev liblz4-dev

# Fedora
sudo dnf install cmake gcc-c++ libX11-devel libXrandr-devel lz4-devel

# 編譯
git clone https://github.com/Almamu/linux-wallpaperengine.git
cd linux-wallpaperengine && mkdir build && cd build
cmake .. && make && sudo make install
```

### 2. 安裝 GUI

```bash
git clone https://github.com/Unayung/simple-linux-wallpaperengine-gui.git
cd simple-linux-wallpaperengine-gui
chmod +x install.sh
./install.sh
```

### 3. 使用方式

```bash
./run_gui.sh
```

啟動時最小化至系統匣：
```bash
./run_gui.sh --background
```

## Steam 工作坊設定

要瀏覽和下載 Steam 工作坊的桌布：

1. **安裝 steamcmd** — `yay -S steamcmd`（Arch/AUR）或參考 [Valve 的指南](https://developer.valvesoftware.com/wiki/SteamCMD)
2. **取得 Steam Web API 金鑰** — 在 [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) 免費取得
3. 開啟**工作坊**分頁，用你的 Steam 帳號登入，並輸入 API 金鑰

> 你必須在 Steam 上擁有 Wallpaper Engine 才能下載工作坊項目。

## 疑難排解

**「找不到 linux-wallpaperengine」**
請確認後端引擎已安裝。執行 `linux-wallpaperengine --help` 來驗證。

**桌布沒有顯示？**
在「已安裝」分頁點擊**掃描媒體庫**，或使用**開啟資料夾**手動選擇桌布目錄。應用程式會搜尋標準 Steam 路徑，包括 `~/.local/share/Steam`、`~/.var/app/com.valvesoftware.Steam` 和 `~/snap/steam`。

**找不到 steamcmd？**
在 Arch Linux 上從 AUR 安裝：`yay -S steamcmd`。應用程式會自動偵測，或者你可以從工作坊分頁手動瀏覽選擇執行檔。

## 專案結構

```
wallpaper_gui.py       # 主應用程式（PyQt6）
steamcmd_service.py    # steamcmd 包裝器（驗證、下載）
workshop_api.py        # Steam 工作坊 API 客戶端
process_manager.py     # 桌布程序生命週期管理
locales/               # 多語系翻譯檔案（en, zh-TW, de, es, fr, ru, uk）
```

## 相關專案

- **[Open Wallpaper Engine for macOS](https://github.com/Unayung/wallpaper-engine-mac)** — 我們修補的 macOS 版本，新增了場景桌布渲染及網頁桌布修復。這個 Linux 版本的工作坊整合和 UI 設計皆移植自該專案。

## 致謝

- 後端引擎：[linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) by Almamu
- 原始 GUI：[simple-linux-wallpaperengine-gui](https://github.com/Maxnights/simple-linux-wallpaperengine-gui) by Maxnights
- macOS 上游：[Open Wallpaper Engine](https://github.com/haren724/open-wallpaper-engine-mac) by Haren
