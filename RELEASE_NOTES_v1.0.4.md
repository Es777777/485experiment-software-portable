# v1.0.4

## 新增

- **双 COM 串口**：485 采集与 PWM 输出在代码与启动器中拆为两路独立串口
  - `config/logger_config.json` 的 `pwm.port` 字段独立配置（默认 COM5/9600）
  - 启动器 "Modbus" 页签新增 "PWM 串口" 下拉（与原 485 串口下拉并列）
  - CLI 新增 `--pwm-port` 覆盖配置
  - `write_pwm_value` 优先用独立 PWM 客户端，未配置时回退到 485 客户端（向后兼容）
- **说明书更新**（`实验软件说明书_20260705.pdf`）
  - 新增 "串口选型（双 COM）与设备管理器排查" 章节
  - 设备管理器查 COM 编号步骤、CH340/FTDI/CP210x 驱动安装、串口被占用排查
  - 封面新增邮箱 `koji3527@qq.com`、GitHub 项目主页
  - 页脚新增 GitHub 水印
  - 4 张关键截图重拍 + 重新标注（启动器红框新增 "PWM 串口" 行）

## 修复

- 邮件每日上限从 20 封降到 8 封（沿用上一 commit）

## 已知问题

- 无

## 下载

便携版 zip：[485experiment-software-portable-v1.0.4-20261013.zip](https://github.com/Es777777/485experiment-software-portable/releases/download/v1.0.4/485experiment-software-portable-v1.0.4-20261013.zip)

解压后双击 `实验软件.exe` 即可使用，无需安装 Python。
