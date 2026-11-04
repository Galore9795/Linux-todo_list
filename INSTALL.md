# 下载、安装与升级

到 [GitHub Releases 最新版本](https://github.com/Galore9795/Linux-todo_list/releases/latest) 下载适合你系统的桌面包。包内含应用运行所需的 Python 和 Qt 程序库；无需单独安装 Python、开发工具或 Agent。

## Windows x64

1. 下载 `TodoNotes-windows-x86_64.zip` 并解压整个文件夹。
2. 双击 `TodoNotes\TodoNotes.exe` 启动。需要桌面快捷方式时，为这个 EXE 创建快捷方式；不要单独移动 EXE。
3. 升级时退出程序，解压新版并替换旧程序文件夹。

Windows SmartScreen 可能提示未识别的发布者，因为当前程序未签名。确认文件来自本仓库 Releases 后，可在提示中选择“更多信息”并运行；无需关闭 Windows 安全功能。

## macOS Apple Silicon / Intel

1. Apple Silicon 下载 `TodoNotes-macos-arm64.dmg`；Intel 下载 `TodoNotes-macos-x86_64.dmg`。
2. 打开 DMG，将 `TodoNotes` 拖入 `Applications`，然后从 Launchpad 或 Applications 启动。
3. 升级时退出应用，将新版拖入 Applications 并选择替换。便签保存在用户资料目录，不会随应用替换而删除。

命令行版本随应用安装，可从终端运行 `/Applications/TodoNotes.app/Contents/Resources/todo-notes-cli/todo-notes-cli list`；它与应用共用便签数据。

应用未使用 Apple 开发者证书签名或公证，因此 macOS 可能拦截首次打开。确认从本仓库 Releases 下载后，在“系统设置 → 隐私与安全性”查看该应用的“仍要打开”选项；不要关闭 Gatekeeper。

## Linux x86_64

1. 下载 `TodoNotes-linux-x86_64.tar.gz` 并解压。
2. 在解压目录运行 `./install.sh`。安装脚本将应用菜单项和程序文件放到当前用户目录，不需要管理员权限或 Python。
3. 从应用菜单打开 **Desktop Todo Notes**。升级时退出程序、解压新版并再次运行 `./install.sh`；本地便签和截图不会被覆盖。

CLI 同样包含在包内，安装后可从终端运行：

```sh
linux-todo-notes-cli add '准备演示' --body '检查材料'
linux-todo-notes-cli list
linux-todo-notes-cli edit
```

## GUI、CLI 与数据

各平台 GUI 和 CLI 使用同一份 SQLite 数据，命令行写入后运行中的界面会刷新。数据与程序文件分开保存：

| 系统 | 默认便签数据目录 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\linux-todo-notes` |
| macOS | `~/Library/Application Support/linux-todo-notes` |
| Linux | `~/.local/share/linux-todo-notes` |

`TODO_NOTES_DATA_DIR` 可指定完整目录；`XDG_DATA_HOME` 可用于 Linux 和隔离测试。升级程序不迁移、不覆盖这份数据。迁移电脑时，先退出应用，再复制整个 `linux-todo-notes` 目录，来源截图也在其中。

Windows 和 macOS 使用原生 Qt 窗口；拖动、缩放、置顶、折叠、草稿与恢复功能共用现有实现。“显示桌面”、全屏窗口层级、Spaces/虚拟桌面以及纸角缺口的点击穿透尚未在 Windows/macOS 桌面环境实测，行为可能因系统和窗口管理器而异。Linux 的显示桌面适配仅针对 X11；Crosspet 右键菜单也是本仓库的 Linux 定制，不代表其他系统支持 Crosspet 集成。

## 从源码安装（开发者）

需要 Python 3.10 或更新版本：

```sh
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\todo-notes-desktop.exe
.\.venv\Scripts\todo-notes.exe list
```

macOS：

```sh
.venv/bin/python -m pip install .
.venv/bin/todo-notes-desktop
.venv/bin/todo-notes list
```

Linux 现有源码安装和 Crosspet 集成仍保留，见 [README.md](README.md)。
