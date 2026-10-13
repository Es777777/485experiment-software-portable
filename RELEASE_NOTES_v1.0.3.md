# v1.0.3

## 新增

- **PWM Modbus 写入**：分组测量输入的 PWM 值通过功能码 06 写入 `logger_config.json` 中登记的寄存器
- **PWM 列写入主表**：live data 的 Excel 表多出 `pwm` 列，记录每次采集时下发的 PWM 值
- **统一 xlsx 导出**：分组测量结果与主数据共用同一份 Excel（`data` + `measurements` 两个 sheet）
- **线程修复**：串口读取跑在 daemon 线程，UI 用 Tk `after()` 调度刷新，画布用 `draw_idle()` 替换 `plt.pause`
- **问题反馈邮件**：内置"问题反馈"页签，通过 QQ SMTP 发送到 `koji3527@qq.com`，每日上限 8 封、间隔 60 秒

## 修复

- 邮件每日上限从 20 封降到 8 封

## 下载

便携版 zip：[485experiment-software-portable-v1.0.3-20261013.zip](https://github.com/Es777777/485experiment-software-portable/releases/download/v1.0.3/485experiment-software-portable-v1.0.3-20261013.zip)

解压后双击 `实验软件.exe` 即可使用，无需安装 Python。
