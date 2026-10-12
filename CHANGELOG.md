# Changelog

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
