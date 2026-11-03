# Linux Todo Notes

把聊天里的任务变成 Linux 桌面上的便签，并通过 Apple Calendar 安排执行时间。

发一段文字或一张截图，整理成带描述的勾选清单。普通便签留在桌面，重要事项用图钉置顶，在工作时也能看见。

## 计划体验

- 桌面右键新建便签，随机柔和配色，自由拖动和缩放。
- 一句话记录，支持描述、清单、完成和恢复。
- 每张便签独立置顶，可收成简短标题条。
- 从不同项目的聊天写入同一份本地任务清单。
- 聊天中查看日历空档，确认后安排任务；便签显示执行时间和上次核对时间。

## 开发进度

本地便签及共享命令入口正在开发，尚未完成全部验收。

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 需求与技术调查 | 桌面环境、置顶、日历、跨聊天入口 | 已完成初步调查 |
| 本地便签 | 清单、保存、配色、位置、置顶 | 已实现基础功能，待桌面验收 |
| 聊天入口 | 本地任务接口、跨项目调用、刷新检查 | 已实现命令与本地 skill，待聊天和钩子验证 |
| 日历安排 | 查空档、关联事件、核对时间 | 待开发 |
| 后续增强 | 手机日历变更自动同步 | 后续 |

实现方向：Python / Qt 桌面应用、SQLite 本地任务数据、统一的聊天操作入口。

## 项目文档

- [项目计划](PROJECT.md)：范围、决策和后续事项。
- [Agent 接手指南](AGENTS.md)：下一步实现顺序与验收要求。

## 开发原则

完整交付已确认功能，再根据实际使用反馈小修。开发按步骤推进，交付以完整使用流程验收；少见情况没有实际影响时，不为它增加复杂度。

仓库用于同步代码和项目进度，个人任务数据保存在本机应用数据目录。

## 当前开发代码

已建立实验性 PyQt6 便签和 SQLite 存储，尚未达到上面的完整交付范围。安装 PyQt6 后，在仓库目录运行 `python3 -m todo_notes`。用 `python3 -m todo_notes add '标题' --body '内容' --source '原文'` 添加，`python3 -m todo_notes list` 查看，`python3 -m todo_notes update ID --deleted 0` 恢复删除，`python3 -m todo_notes export` 导出 JSON。数据位于 `$XDG_DATA_HOME/linux-todo-notes`（默认 `~/.local/share/linux-todo-notes`）。

已做命令添加和 Qt 离屏启动检查；尚未完成桌面实际验收。桌面右键、对话触发检查及日历安排等仍待实现。

清单：在便签中输入项目并按回车添加，勾选完成，双击文字编辑；选中项目后可删除。命令行可使用 `python3 -m todo_notes item-add 便签ID '项目'`、`python3 -m todo_notes item-update 项目ID --done 1`；列表与导出包含项目 ID 和完成状态。自动化检查：`python3 -m unittest discover -s tests -v`。

便签上的“恢复”可找回删除的便签和当前便签中删除的清单项目；删除最后一张便签时会保留一个空白入口。命令行可用 `python3 -m todo_notes item-restore 项目ID` 恢复项目，`list --all` 和 `export` 包含已删除项目。

## 跨项目使用

运行 `scripts/install-local.sh`，安装 `~/.local/bin/linux-todo-notes` 和用户级 Codex skill。确保 `~/.local/bin` 在 PATH 中；新启动的本地 Codex 会话可发现该 skill。安装入口引用当前仓库位置，移动仓库后需删除这两个入口并重新安装。命令行可在任意目录运行；当前已通过独立临时数据目录的跨目录调用检查，尚未验证另一个 Codex 会话实际自动调用。

时间与日历记录：`update ID --reminder-at ISO时间 --start-at ISO时间 --end-at ISO时间 --due-at ISO时间` 分别保存提醒、执行开始和结束、截止时间，时间须带时区偏移，空字符串可清除。便签显示这些时间、上次核对时间及写入状态。`calendar-check ID success|failed` 和 `calendar-write ID success|failed` 只记录实际日历操作的结果，不会访问日历；成功写入时须提供 `--calendar-id` 和 `--event-id`。失败保留已有事件关联和上次成功核对时间。聊天端日历实际读写流程仍需验证。

桌面菜单：`python3 scripts/install-ding-menu.py` 在用户目录复制当前系统 DING 并加入“新建便签”，不修改系统文件；GNOME 会话重新登录后才加载该副本。该副本不会自动跟随系统 DING 更新；撤销时删除 `~/.local/share/gnome-shell/extensions/ding@rastersoft.com` 并重新登录。安装脚本不会覆盖已有用户版 DING。入口通过 `linux-todo-notes new` 创建便签并启动应用（已有实例时由其刷新）。本机已安装用户副本，尚未重新登录验证菜单。
