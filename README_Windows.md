# cotton-filter 使用说明

## 推荐方式

从 GitHub Release 下载对应系统的构建产物:

- Windows: `cotton-filter.exe`
- macOS: `cotton-filter-macos.zip`

打开后先添加 Excel 文件或文件夹,再选择一次保存目录,最后点击开始处理。

## Windows 脚本方式

如果不用 Release 里的 exe,也可以直接运行源码:

1. **装 Python 3.9+**
   下载 https://www.python.org/downloads/
   安装时**勾选 `Add Python to PATH`**(很重要)

2. **拷贝两个文件到任意位置**(建议放桌面或 `D:\tools\cotton-filter\`)
   - `cotton_filter.py`
   - `cotton-filter.bat`
   ⚠️ 两个文件**必须在同一目录**

3. **首次双击 `cotton-filter.bat`**
   会自动 `pip install pandas openpyxl xlrd`,等约 30 秒装完

## 日常使用

- **GUI**:双击打开页面,添加 Excel 文件或文件夹,选择一次保存目录,点击开始处理
- **拖拽**:把 `.xlsx` 文件或文件夹拖到 `cotton-filter.bat` 图标上,会直接处理
- **命令行**:`python cotton_filter.py 文件或文件夹`

未手动选择保存目录时,结果默认写入原文件同目录的 `cotton-filter-results` 文件夹。

## 让图标更顺手

- **发送到桌面快捷方式**:右键 `cotton-filter.bat` → 发送到 → 桌面快捷方式
  快捷方式同样支持拖拽,且可以改图标(右键 → 属性 → 更改图标)
- **固定到任务栏**:Windows 默认不允许把 .bat 钉到任务栏。
  解决:把 .bat 的快捷方式拖到任务栏,会自动跳过限制

## 改规则

打开 `cotton_filter.py`,用记事本/VSCode 编辑 `score_record()` 函数。
保存后下次拖拽就生效,不用重启任何东西。

## 出问题排查

- 日志在 `%TEMP%\cotton-filter.log`(运行 `%TEMP%` 回车可打开)
- 提示"未检测到 Python":重装时确认勾了 Add to PATH,或重启电脑
- 中文路径乱码:.bat 已 `chcp 65001`,理论上无碍;如果还有问题告诉我
