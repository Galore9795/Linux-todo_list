# Windows / macOS 安装

## 下载桌面版

在 GitHub 仓库的 **Actions → Desktop builds → 最新成功运行 → Artifacts** 下载对应压缩包：

- `TodoNotes-windows-latest`：Windows x64；解压后运行 `TodoNotes/TodoNotes.exe`。
- `TodoNotes-macos-15`：Apple Silicon；解压后将 `TodoNotes.app` 拖入“应用程序”。
- `TodoNotes-macos-15-intel`：Intel Mac；操作相同。

下载的 artifact ZIP 内还有一个 `TodoNotes-系统-架构.zip`，再解压一层。Windows 可为 EXE 创建桌面快捷方式；不要只移动 EXE，需保留同目录的 `_internal`。macOS 请用 Finder 或“归档实用工具”解压，以保留程序权限。

构建未使用付费开发者证书签名或 Apple 公证。Windows 可能显示 SmartScreen 提示；macOS 如被拦截，在“系统设置 → 隐私与安全性”查看该应用的“仍要打开”。

每个包还包含独立的命令行版本，可供本机 agent 调用：

```powershell
# Windows，在解压目录运行
.\todo-notes-cli\todo-notes-cli.exe add "准备演示" --body "检查材料"
.\todo-notes-cli\todo-notes-cli.exe edit
```

```sh
# macOS，在解压目录运行
./todo-notes-cli/todo-notes-cli add '准备演示' --body '检查材料'
./todo-notes-cli/todo-notes-cli edit
```

GUI 和 CLI 共享同一份本机数据，程序升级或更换文件夹不会清除便签。

## 从源码运行

需要 Python 3.10 或更新版本。Windows 可使用 `py` 替代以下 `python`；macOS 通常使用 `python3`。

```sh
python -m venv .venv
```

Windows：

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

也可以在安装依赖后直接运行 `python -m todo_notes edit`。Linux 的 `scripts/install-local.sh` 和原 `linux-todo-notes` 命令仍保留。

## 数据位置

| 系统 | 默认目录 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\linux-todo-notes` |
| macOS | `~/Library/Application Support/linux-todo-notes` |
| Linux | `~/.local/share/linux-todo-notes` |

`TODO_NOTES_DATA_DIR` 可指定完整数据目录；已有 `XDG_DATA_HOME` 设置仍优先于系统默认目录，并在其下使用 `linux-todo-notes` 子目录。任务、草稿、截图和刷新信号都使用同一目录。数据库格式保持一致；迁移需先退出程序，再复制完整目录。原来已运行的 Linux 版本升级后须退出并重启，以切换到跨平台单实例锁。

## 功能与系统差异

三种系统共用便签本、纸张样式、清单、拖动缩放、置顶、折叠、草稿与删除恢复、来源截图、备份和日历状态字段。Windows/macOS 使用原生 Qt 窗口；“显示桌面”、全屏层级、Spaces/虚拟桌面及缺口点击穿透需在实际桌面验收。GNOME/X11 特有的“显示桌面仍可见”适配只在 Linux X11 启用。

仓库现有 Crosspet 菜单补丁、安装脚本与 Cursor 桥属于 Linux 定制；未移植成 Windows/macOS Crosspet 补丁。新平台可以直接使用独立桌面入口和 CLI。聊天日历实际读写仍由有权限的聊天环境执行，程序本身不持有 iCloud 凭证；后台同步仍暂缓。

## 自行构建

在对应系统中安装 `python -m pip install . pyinstaller`，运行 `python scripts/build-desktop.py`。压缩包生成在 `dist/`，无需用户电脑在线即可由 GitHub Actions 构建。流水线检查自动测试、打包后 CLI 的中文写入与读取，以及打包后 GUI 的启动和重复启动。
