# RS485 Excel Logger

This project includes two ways to save RS485 serial data into Excel:

- `serial_excel_logger.py`: for Modbus RTU request/response devices
- `serial_raw_excel_logger.py`: for devices that actively send serial data or use a custom frame format

## Files

- `serial_excel_logger.py`: main program
- `serial_raw_excel_logger.py`: passive serial logger
- `logger_config.json`: serial port and register settings
- `raw_logger_config.json`: passive serial logger settings
- `requirements.txt`: Python dependencies
- `run_logger.bat`: Windows launcher
- `run_raw_logger.bat`: passive logger launcher

## Install

```bash
py -m pip install -r requirements.txt
```

## Configure

### 1. Modbus RTU mode

Edit `logger_config.json` before running:

- `port`: Windows serial port, for example `COM3`
- `baudrate`, `parity`, `stopbits`, `bytesize`: must match the transmitter
- `slave_id`: Modbus device address
- `poll_interval_seconds`: how often to read the device
- `workbook_path`: output Excel file path, supports `{start_time}` in the filename
- `workbook_name_timestamp_format`: filename timestamp format used by `{start_time}`
- `tare_on_startup`: whether to send the startup tare command automatically
- `startup_tare_use_reference_mapping`: auto-select the tare register based on the same version mapping used by the desktop software
- `startup_tare_address`: tare register address, matching the reference desktop software
- `startup_tare_value`: tare trigger value, matching the reference desktop software
- `startup_tare_settle_seconds`: wait time after the startup tare command
- `fields`: the registers you want to save

Each field supports:

- `name`: Excel column name
- `function_code`: usually `3` or `4`
- `address`: zero-based Modbus register offset
- `data_type`: `uint16`, `int16`, `uint32`, `int32`, or `float32`
- `scale`: optional multiplier
- `offset`: optional offset after scaling
- `precision`: optional rounding digits
- `byte_order`: optional, `big` or `little`
- `word_order`: optional, `big` or `little`

If your manual shows addresses like `30001` or `40001`, convert them to zero-based offsets first. Example: `30001 -> 0`, `30002 -> 1`.

### 2. Passive raw serial mode

Edit `raw_logger_config.json` if your transmitter sends data by itself or is not Modbus RTU:

- `read_mode`: `chunk` for binary frames, `line` for text lines ending with `\n`
- `chunk_size`: maximum bytes to read at once in `chunk` mode
- `encoding`: how to decode bytes into text for the `raw_text` Excel column
- `workbook_path`: output Excel file path

## Run

### Modbus RTU logger

Read continuously:

```bash
py -3 serial_excel_logger.py --config logger_config.json
```

The default config creates one workbook per run, for example `logs/485_weight_data_20260322_200204.xlsx`.

Read once for testing:

```bash
py -3 serial_excel_logger.py --config logger_config.json --once
```

On Windows you can also double-click `run_logger.bat`.

### Passive raw logger

Read continuously:

```bash
py -3 serial_raw_excel_logger.py --config raw_logger_config.json
```

Read once for testing:

```bash
py -3 serial_raw_excel_logger.py --config raw_logger_config.json --once
```

On Windows you can also double-click `run_raw_logger.bat`.

## Excel Output

Modbus workbook columns:

- `timestamp`
- `unix_time`
- `port`
- `baudrate`
- `slave_id`
- `status`
- `error`
- `raw_frames`
- one column for each configured field

Passive raw workbook columns:

- `timestamp`
- `unix_time`
- `port`
- `baudrate`
- `bytesize`
- `parity`
- `stopbits`
- `byte_count`
- `raw_hex`
- `raw_text`

## Notes

- This program assumes the transmitter uses Modbus RTU over RS485.
- If your device uses a custom frame format instead of Modbus RTU, the read logic in `serial_excel_logger.py` needs to be adjusted.
- If values look wrong, check `baudrate`, `parity`, `stopbits`, `slave_id`, register address, function code, data type, and byte/word order.
- The default startup tare uses the same desktop-software logic: first read version register `60000`, then send Modbus `06` with value `1` to register `21` or `38` depending on device version.

## Troubleshooting

- If `serial_excel_logger.py` reports `received 0 bytes`, the serial port opened successfully but the device did not reply.
- Common causes: wrong `slave_id`, wrong `baudrate/parity/stopbits`, A/B wires reversed, missing RS485 converter, or the device is not Modbus RTU.
- The sample `temperature_c` and `humidity_rh` registers in `logger_config.json` are placeholders. Replace them with your actual manual values.
- If you are unsure whether the device is Modbus, run `serial_raw_excel_logger.py` first. If that script can receive data but the Modbus script cannot, your device is probably not using the Modbus request/response flow expected here.
