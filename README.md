# 485 实验软件便携版

基于 Modbus RTU 的 RS485 实验采集软件。提供 PWM 分组测量、实时曲线、问题反馈等功能。

## 功能亮点

- **PWM 分组测量**：在 UI 输入 PWM 字符串，自动写入 Modbus 寄存器（功能码 06），采集一段时间后录入总电流，计算 M_y / M_x / M / θ。
- **实时曲线**：后台线程读串口，前台 Tk `after()` 调度刷新，画布使用 `draw_idle()`，不卡顿。
- **统一 xlsx 导出**：分组测量结果与主数据共用同一份 Excel 的不同 sheet（`data` + `measurements`）。
- **问题反馈**：内置"问题反馈"页签，通过 QQ SMTP 发送反馈到 `koji3527@qq.com`，限流 60 秒/封、20 封/天。
- **PWM 列写入主表**：live data 的 Excel 表里多出一列 `pwm`，方便后期核对当时下发的 PWM 值。

## 便携版下载

从 [Releases](../../releases) 页面下载最新便携版：

- [485experiment-software-portable-v1.0.4-20261013.zip](../../releases/download/v1.0.4/485experiment-software-portable-v1.0.4-20261013.zip)
- [485experiment-software-portable-v1.0.3-20261013.zip](../../releases/download/v1.0.3/485experiment-software-portable-v1.0.3-20261013.zip)
- [485experiment-software-portable-v1.0.2-20260522.zip](../../releases/download/v1.0.2/485experiment-software-portable-v1.0.2-20260522.zip)

便携版已包含 Python 运行时与 PyInstaller 打包的可执行文件，解压后双击 `实验软件.exe` 即可使用。

## PWM 分组测量流程

1. 在主界面"Modbus"页签选好串口、波特率、从站地址。
2. 切到"PWM 分组测量"页签，输入 PWM 值（例如 `500`），点"开始测量"。
3. 软件把 PWM 通过 Modbus 功能码 06 写入配置里登记的寄存器，同时启动后台采集。
4. 等待曲线稳定后，录入"总电流"，点"结束测量"。
5. 软件自动计算 M_y / M_x / M / θ，可点"下一组"继续测下一个 PWM。
6. 全部测完后点"导出表格"，结果追加到当前 Excel 的 `measurements` sheet。

## 从源码运行

```bash
py -m pip install -r requirements.txt
py app_launcher.py
```

## 目录说明

- `config`：配置（`logger_config.json`、`email.json` 等）
- `logs`：默认的采集 Excel 输出目录
- `output`：测量结果与图表输出目录
- `videos`：视频回填输入目录
- `docs`：开发文档与发布说明

## 反馈

软件内置"问题反馈"页签，可直接发邮件到 `koji3527@qq.com`。发件人需在 `config/email.json` 配置（QQ 邮箱授权码，非登录密码）。
