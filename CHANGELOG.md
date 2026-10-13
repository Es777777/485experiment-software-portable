# Changelog

## v1.0.4

- 双 COM 串口：485 采集与 PWM 输出在代码与启动器中拆为两路独立串口（`PwmSerialConfig` + 启动器新增 "PWM 串口" 下拉 + CLI `--pwm-port` 覆盖）
- 说明书新增 "串口选型（双 COM）与设备管理器排查" 章节，含两个 COM 编号的差异、设备管理器查找步骤、串口驱动（CH340/FTDI/CP210x）安装、串口占用排查
- 说明书封面新增邮箱 `koji3527@qq.com`，页脚新增 GitHub 水印 `github.com/Es777777/485experiment-software-portable`
- 4 张关键截图重拍 + 重新标注，启动器标注新增 "PWM 串口" 红框
- 邮件每日上限从 20 封降到 8 封（沿用上一 commit）

## v1.0.3

- PWM Modbus 写入：分组测量输入的 PWM 值通过功能码 06 写到 `logger_config.json` 里登记的寄存器
- PWM 列写入主表：live data 的 Excel 表多出 `pwm` 列，记录每次采集时下发的 PWM
- 统一 xlsx 导出：分组测量结果与主数据共用同一份 Excel 的 `data` + `measurements` sheet
- 线程修复：串口读跑在 daemon 线程，UI 用 Tk `after()` 调度刷新，画布用 `draw_idle()` 替换 `plt.pause`
- 问题反馈邮件：内置"问题反馈"页签，通过 QQ SMTP 发到 `koji3527@qq.com`，限流 60 秒/封、20 封/天
- 显示问题修复：分组测量页签字号与对齐修正；测量表格自适应列宽

## v1.0.2

- 显示问题修复
- PWM 分组测量工作流上线
- 便携版打包脚本
