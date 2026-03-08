# Open Wallpaper Engine for Linux

**[English](README.md)** | **[繁體中文](README.zh-TW.md)** | **[日本語](README.ja.md)**

[linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) 向けの、モダンで多機能な GUI。[Open Wallpaper Engine for macOS](https://github.com/haren724/open-wallpaper-engine-mac) にインスパイアされています。

> GNOME や KDE では問題が発生する場合があります。i3、Hyprland、bspwm などのタイル型ウィンドウマネージャーでの使用を推奨します。KDE ユーザーはこちらの[プラグイン](https://github.com/catsout/wallpaper-engine-kde-plugin#build-and-install)をお試しください。

## 主な機能

- **Mac スタイルの分割パネルレイアウト** — 左側のコンテンツエリア + 右側のプレビューパネル（壁紙の詳細、プロパティ、コントロール）
- **タブインターフェース** — トップバーに「インストール済み」/「ワークショップ」/「設定」タブ
- **Steam ワークショップ統合** — タグ（レーティング、タイプ、ジャンル）でフィルタリング、steamcmd 経由で壁紙を直接ダウンロード
- **Steam Web API 検索** — トレンド、最新、人気順、サブスクライブ数順でソート
- **steamcmd 認証** — パスワード、Steam Guard、キャッシュセッションによるログイン
- **壁紙ライブラリスキャナー** — Steam、Flatpak、Snap のインストールパスから壁紙を自動検出
- **リアルタイム壁紙プロパティ** — プレビューパネルから壁紙固有のプロパティ（色、速度、トグル）を読み込み・編集
- **壁紙ごとの設定** — スクリーン選択、音量、FPS、スケーリング、クランプ、マウス/パララックス/フルスクリーン一時停止の切り替え
- **ウィンドウモード** — KDE/GNOME コンポジター互換性向け
- **ファイルシステム監視** — 壁紙の追加・削除時にライブラリを自動更新
- **システムトレイ** — トレイに最小化、ワークショップへのクイックアクセス
- **自動復元** — 起動時に最後に使用した壁紙を記憶して復元
- **多言語対応** — English、繁體中文、Deutsch、Español、Français、Русский、Українська

## スクリーンショット

<img width="2560" height="1440" alt="スクリーンショット" src="https://github.com/user-attachments/assets/15c6dc78-f51b-4c1b-aeb1-f2bad88bc898" />
<img width="2560" height="1440" alt="スクリーンショット (2)" src="https://github.com/user-attachments/assets/d36990b8-641a-44fe-b4ff-ca582d9494da" />

## インストール（Arch Linux / Manjaro）

AUR からインストールするのが最も簡単です。バックエンド（`linux-wallpaperengine`）と全ての依存関係が自動的にインストールされます。

```bash
yay -S simple-linux-wallpaperengine-gui-git
```

## インストール（Nix）

**Flake インストール（推奨）**

flake の inputs に追加：
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

home-manager の設定：
```nix
{inputs, ...}: {
  imports = [inputs.simple-wallpaper-engine.homeManagerModules.default];
  programs.simple-wallpaper-engine.enable = true;
}
```

**手動インストール**
```bash
nix profile install github:Unayung/simple-linux-wallpaperengine-gui
```

## 手動インストール

### 1. 前提条件（バックエンド）

これは GUI フロントエンドです — まず [linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) を**インストールする必要があります**。AUR からインストールした場合は、依存関係として自動的にインストールされます。

**Arch / Manjaro：**
```bash
yay -S linux-wallpaperengine
```

**Debian / Ubuntu / Fedora（ソースからビルド）：**

[詳細な手順](https://github.com/Almamu/linux-wallpaperengine#compiling)を参照：
```bash
# Debian/Ubuntu
sudo apt install build-essential cmake libx11-dev libxrandr-dev liblz4-dev

# Fedora
sudo dnf install cmake gcc-c++ libX11-devel libXrandr-devel lz4-devel

# ビルド
git clone https://github.com/Almamu/linux-wallpaperengine.git
cd linux-wallpaperengine && mkdir build && cd build
cmake .. && make && sudo make install
```

### 2. GUI のインストール

```bash
git clone https://github.com/Unayung/simple-linux-wallpaperengine-gui.git
cd simple-linux-wallpaperengine-gui
chmod +x install.sh
./install.sh
```

### 3. 使い方

```bash
./run_gui.sh
```

システムトレイに最小化して起動：
```bash
./run_gui.sh --background
```

## Steam ワークショップの設定

Steam ワークショップから壁紙を閲覧・ダウンロードするには：

1. **steamcmd をインストール** — `yay -S steamcmd`（Arch/AUR）または [Valve のガイド](https://developer.valvesoftware.com/wiki/SteamCMD)を参照
2. **Steam Web API キーを取得** — [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) で無料取得
3. **ワークショップ**タブを開き、Steam アカウントでログインし、API キーを入力

> ワークショップアイテムをダウンロードするには、Steam で Wallpaper Engine を所有している必要があります。

## トラブルシューティング

**「linux-wallpaperengine が見つかりません」**
バックエンドがインストールされていることを確認してください。`linux-wallpaperengine --help` を実行して確認できます。

**壁紙が表示されない？**
「インストール済み」タブで**ライブラリをスキャン**をクリックするか、**フォルダを開く**で壁紙ディレクトリを手動で選択してください。アプリは `~/.local/share/Steam`、`~/.var/app/com.valvesoftware.Steam`、`~/snap/steam` などの標準 Steam パスを検索します。

**steamcmd が見つからない？**
Arch Linux では AUR からインストール：`yay -S steamcmd`。アプリが自動検出しますが、ワークショップタブからバイナリを手動で選択することもできます。

## プロジェクト構成

```
wallpaper_gui.py       # メインアプリケーション（PyQt6）
steamcmd_service.py    # steamcmd ラッパー（認証、ダウンロード）
workshop_api.py        # Steam ワークショップ API クライアント
process_manager.py     # 壁紙プロセスのライフサイクル管理
locales/               # 多言語翻訳ファイル（en, zh-TW, de, es, fr, ru, uk）
```

## 関連プロジェクト

- **[Open Wallpaper Engine for macOS](https://github.com/Unayung/wallpaper-engine-mac)** — シーン壁紙レンダリングとウェブ壁紙の修正を追加した、パッチ済み macOS バージョン。この Linux バージョンのワークショップ統合と UI デザインはこのプロジェクトから移植されました。

## クレジット

- バックエンド：[linux-wallpaperengine](https://github.com/Almamu/linux-wallpaperengine) by Almamu
- オリジナル GUI：[simple-linux-wallpaperengine-gui](https://github.com/Maxnights/simple-linux-wallpaperengine-gui) by Maxnights
- macOS 上流：[Open Wallpaper Engine](https://github.com/haren724/open-wallpaper-engine-mac) by Haren
