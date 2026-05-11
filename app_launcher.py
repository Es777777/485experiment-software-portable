from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk
from typing import Callable, Mapping, Sequence

from runtime_paths import ensure_runtime_directories, get_app_root

try:
    from serial.tools import list_ports  # type: ignore
except ImportError:
    list_ports = None


APP_TITLE = "实验软件便携版"


def configure_text_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def build_child_process_environment(
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def select_preferred_port(
    detected_ports: Sequence[str], configured_port: str
) -> str:
    ports = [port.strip() for port in detected_ports if port.strip()]
    config_port = configured_port.strip()
    config_upper = config_port.upper()
    if config_upper:
        for port in ports:
            if port.upper() == config_upper:
                return port
    if ports:
        return ports[0]
    return config_port


def configure_default_fonts(root: tk.Tk) -> None:
    preferred_families = (
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "SimSun",
        "Arial Unicode MS",
        "Arial",
    )
    try:
        available_families = set(tkfont.families(root))
    except tk.TclError:
        return
    family = next(
        (name for name in preferred_families if name in available_families), None
    )
    if family is None:
        return

    for font_name in (
        "TkDefaultFont",
        "TkTextFont",
        "TkMenuFont",
        "TkHeadingFont",
        "TkCaptionFont",
        "TkSmallCaptionFont",
        "TkIconFont",
        "TkTooltipFont",
    ):
        try:
            tkfont.nametofont(font_name).configure(family=family)
        except tk.TclError:
            pass


def run_internal_tool(argv: Sequence[str]) -> int | None:
    if len(argv) < 3 or argv[1] != "__tool__":
        return None

    configure_text_streams()
    tool_name = argv[2]
    tool_args = list(argv[3:])

    try:
        if tool_name == "modbus":
            from scripts import serial_excel_logger

            return serial_excel_logger.main(tool_args)
        if tool_name == "liveplot":
            from scripts import serial_logger_with_plot

            return serial_logger_with_plot.main(tool_args)
        if tool_name == "raw":
            from scripts import serial_raw_excel_logger

            return serial_raw_excel_logger.main(tool_args)
        if tool_name == "video":
            import video_meter_to_excel

            return video_meter_to_excel.main(tool_args)
        if tool_name == "extract":
            from scripts import extract_reliable_data

            return extract_reliable_data.main(tool_args)
    except Exception as exc:
        print("工具运行失败: {0}".format(exc), file=sys.stderr)
        return 1

    raise SystemExit("Unknown internal tool: {0}".format(tool_name))


class ToolLauncherApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.app_root = ensure_runtime_directories(get_app_root())
        self.process: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.start_buttons: list[ttk.Button] = []
        self.stop_buttons: list[ttk.Button] = []
        self.modbus_detected_ports: list[str] = []
        self.raw_detected_ports: list[str] = []
        self.status_var = tk.StringVar(value="就绪")

        self.modbus_config_var = tk.StringVar(
            value=str(self.app_root / "config" / "logger_config.json")
        )
        self.modbus_port_var = tk.StringVar(value="")
        self.modbus_once_var = tk.BooleanVar(value=False)
        self.live_plot_window_var = tk.StringVar(value="60")
        self.live_plot_smooth_var = tk.BooleanVar(value=False)
        self.modbus_port_combo: ttk.Combobox | None = None

        self.raw_config_var = tk.StringVar(
            value=str(self.app_root / "config" / "raw_logger_config.json")
        )
        self.raw_port_var = tk.StringVar(value="")
        self.raw_once_var = tk.BooleanVar(value=False)
        self.raw_port_combo: ttk.Combobox | None = None

        self.video_dir_var = tk.StringVar(value=str(self.app_root / "videos"))
        self.excel_dir_var = tk.StringVar(value=str(self.app_root / "logs"))
        self.video_output_var = tk.StringVar(value="")

        self.extract_input_var = tk.StringVar(value="")
        self.extract_output_var = tk.StringVar(value="")
        self.extract_stability_var = tk.StringVar(value="5.0")
        self.extract_tolerance_var = tk.StringVar(value="0.15")

        self.root.title(APP_TITLE)
        self.root.geometry("1080x820")
        self.root.minsize(940, 700)
        self.root.protocol("WM_DELETE_WINDOW", self.handle_close)

        self._build_ui()
        self.refresh_serial_ports("modbus", log_results=False)
        self.refresh_serial_ports("raw", log_results=False)
        self.use_config_port("modbus", prefer_detected=True, log_results=False)
        self.use_config_port("raw", prefer_detected=True, log_results=False)
        self.root.after(120, self._poll_log_queue)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text=APP_TITLE, font=("Microsoft YaHei UI", 18, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            outer,
            text="支持 Modbus 采集、实时曲线、原始串口采集、视频回填和后处理。可直接搜索可用 COM 口并临时切换。",
        ).pack(anchor="w", pady=(6, 10))

        quick_links = ttk.Frame(outer)
        quick_links.pack(fill="x", pady=(0, 12))
        for label, path in (
            ("打开 config", self.app_root / "config"),
            ("打开 logs", self.app_root / "logs"),
            ("打开 videos", self.app_root / "videos"),
            ("打开 output", self.app_root / "output"),
        ):
            ttk.Button(
                quick_links,
                text=label,
                command=lambda target=path: self._open_folder(target),
            ).pack(side="left", padx=(0, 8))

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="x", pady=(0, 12))

        modbus_tab = ttk.Frame(notebook, padding=12)
        raw_tab = ttk.Frame(notebook, padding=12)
        video_tab = ttk.Frame(notebook, padding=12)
        extract_tab = ttk.Frame(notebook, padding=12)

        notebook.add(modbus_tab, text="Modbus 采集")
        notebook.add(raw_tab, text="原始串口采集")
        notebook.add(video_tab, text="视频回填")
        notebook.add(extract_tab, text="可靠数据与曲线")

        self._build_modbus_tab(modbus_tab)
        self._build_raw_tab(raw_tab)
        self._build_video_tab(video_tab)
        self._build_extract_tab(extract_tab)

        status_row = ttk.Frame(outer)
        status_row.pack(fill="x")
        ttk.Label(status_row, text="当前状态:").pack(side="left")
        ttk.Label(status_row, textvariable=self.status_var).pack(
            side="left", padx=(6, 0)
        )

        log_frame = ttk.LabelFrame(outer, text="运行日志", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(12, 0))

        self.log_text = tk.Text(
            log_frame, wrap="word", height=18, font=("Consolas", 10)
        )
        scrollbar = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._append_log("启动器已就绪。实时曲线已经接到 Modbus 页面。")

    def _build_modbus_tab(self, parent: ttk.Frame) -> None:
        self._add_path_row(
            parent,
            0,
            "配置文件",
            self.modbus_config_var,
            "file",
            "选择 Modbus 配置文件",
            file_types=[("JSON", "*.json"), ("All files", "*.*")],
        )
        self.modbus_port_combo = self._add_port_override_row(
            parent, 1, "临时串口", self.modbus_port_var, "modbus"
        )
        ttk.Checkbutton(
            parent, text="只采集一次后退出", variable=self.modbus_once_var
        ).grid(
            row=2,
            column=1,
            sticky="w",
            pady=(4, 10),
        )

        live_row = ttk.Frame(parent)
        live_row.grid(row=3, column=1, sticky="w", pady=(0, 10))
        ttk.Label(live_row, text="实时窗口秒数").pack(side="left")
        ttk.Entry(live_row, textvariable=self.live_plot_window_var, width=8).pack(
            side="left", padx=(8, 16)
        )
        ttk.Checkbutton(
            live_row, text="平滑曲线", variable=self.live_plot_smooth_var
        ).pack(side="left")

        ttk.Label(
            parent,
            text="“开始实时曲线采集”会打开独立曲线窗口，支持测定过程中手动去皮、PWM 分组测量、总电流录入、合力平均值统计和表格导出。",
        ).grid(
            row=4,
            column=1,
            sticky="w",
            pady=(0, 10),
        )

        actions = ttk.Frame(parent)
        actions.grid(row=5, column=1, sticky="w")
        start_button = ttk.Button(
            actions, text="开始普通采集", command=self.start_modbus
        )
        live_button = ttk.Button(
            actions, text="开始实时曲线采集", command=self.start_modbus_live_plot
        )
        stop_button = ttk.Button(
            actions,
            text="停止当前任务",
            command=self.stop_current_process,
            state="disabled",
        )
        start_button.pack(side="left")
        live_button.pack(side="left", padx=(8, 0))
        stop_button.pack(side="left", padx=(8, 0))
        self.start_buttons.extend([start_button, live_button])
        self.stop_buttons.append(stop_button)
        parent.columnconfigure(1, weight=1)

    def _build_raw_tab(self, parent: ttk.Frame) -> None:
        self._add_path_row(
            parent,
            0,
            "配置文件",
            self.raw_config_var,
            "file",
            "选择原始串口配置文件",
            file_types=[("JSON", "*.json"), ("All files", "*.*")],
        )
        self.raw_port_combo = self._add_port_override_row(
            parent, 1, "临时串口", self.raw_port_var, "raw"
        )
        ttk.Checkbutton(
            parent, text="只采集一次后退出", variable=self.raw_once_var
        ).grid(
            row=2,
            column=1,
            sticky="w",
            pady=(4, 10),
        )
        self._add_action_row(parent, 3, "开始原始串口采集", self.start_raw)
        parent.columnconfigure(1, weight=1)

    def _build_video_tab(self, parent: ttk.Frame) -> None:
        self._add_path_row(
            parent, 0, "视频目录", self.video_dir_var, "directory", "选择视频目录"
        )
        self._add_path_row(
            parent,
            1,
            "Excel 目录",
            self.excel_dir_var,
            "directory",
            "选择 Excel 日志目录",
        )
        self._add_path_row(
            parent,
            2,
            "输出文件",
            self.video_output_var,
            "save",
            "选择输出 Excel 文件",
            file_types=[("Excel", "*.xlsx"), ("All files", "*.*")],
            optional=True,
        )
        ttk.Label(
            parent, text="留空时会自动在最新日志旁边生成 *_video_ocr.xlsx。"
        ).grid(
            row=3,
            column=1,
            sticky="w",
            pady=(4, 10),
        )
        self._add_action_row(parent, 4, "开始视频回填", self.start_video)
        parent.columnconfigure(1, weight=1)

    def _build_extract_tab(self, parent: ttk.Frame) -> None:
        self._add_path_row(
            parent,
            0,
            "输入文件",
            self.extract_input_var,
            "file",
            "选择 *_video_ocr.xlsx 文件",
            file_types=[("Excel", "*.xlsx"), ("All files", "*.*")],
            optional=True,
        )
        self._add_path_row(
            parent,
            1,
            "输出文件",
            self.extract_output_var,
            "save",
            "选择可靠数据输出文件",
            file_types=[("Excel", "*.xlsx"), ("All files", "*.*")],
            optional=True,
        )
        ttk.Label(parent, text="稳定窗口秒数").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Entry(parent, textvariable=self.extract_stability_var).grid(
            row=2, column=1, sticky="ew", pady=6
        )
        ttk.Label(parent, text="允许偏差比例").grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Entry(parent, textvariable=self.extract_tolerance_var).grid(
            row=3, column=1, sticky="ew", pady=6
        )
        self._add_action_row(parent, 4, "提取可靠数据并绘图", self.start_extract)
        parent.columnconfigure(1, weight=1)

    def _add_port_override_row(
        self,
        parent: ttk.Frame,
        row_index: int,
        label: str,
        variable: tk.StringVar,
        target: str,
    ) -> ttk.Combobox:
        ttk.Label(parent, text=label).grid(
            row=row_index, column=0, sticky="w", padx=(0, 12), pady=6
        )
        row = ttk.Frame(parent)
        row.grid(row=row_index, column=1, sticky="w", pady=6)

        combo = ttk.Combobox(row, textvariable=variable, width=24)
        combo.pack(side="left")
        ttk.Button(
            row, text="搜索串口", command=lambda: self.refresh_serial_ports(target)
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            row, text="使用配置", command=lambda: self.use_config_port(target)
        ).pack(side="left", padx=(8, 0))
        ttk.Button(row, text="清空", command=lambda: variable.set("")).pack(
            side="left", padx=(8, 0)
        )
        return combo

    def _add_path_row(
        self,
        parent: ttk.Frame,
        row_index: int,
        label: str,
        variable: tk.StringVar,
        choose_kind: str,
        dialog_title: str,
        file_types: list[tuple[str, str]] | None = None,
        optional: bool = False,
    ) -> None:
        ttk.Label(parent, text=label).grid(
            row=row_index, column=0, sticky="w", padx=(0, 12), pady=6
        )
        ttk.Entry(parent, textvariable=variable).grid(
            row=row_index, column=1, sticky="ew", pady=6
        )

        def choose_path() -> None:
            if choose_kind == "directory":
                selected = filedialog.askdirectory(
                    title=dialog_title, initialdir=variable.get() or str(self.app_root)
                )
            elif choose_kind == "save":
                initial = (
                    Path(variable.get())
                    if variable.get()
                    else self.app_root / "output" / "result.xlsx"
                )
                selected = filedialog.asksaveasfilename(
                    title=dialog_title,
                    initialdir=str(initial.parent),
                    initialfile=initial.name,
                    defaultextension=".xlsx",
                    filetypes=file_types or [("All files", "*.*")],
                )
            else:
                initial = Path(variable.get()) if variable.get() else self.app_root
                selected = filedialog.askopenfilename(
                    title=dialog_title,
                    initialdir=str(initial.parent if initial.suffix else initial),
                    filetypes=file_types or [("All files", "*.*")],
                )
            if selected:
                variable.set(selected)

        ttk.Button(parent, text="浏览", command=choose_path).grid(
            row=row_index, column=2, padx=(8, 0), pady=6
        )
        if optional:
            ttk.Button(parent, text="清空", command=lambda: variable.set("")).grid(
                row=row_index,
                column=3,
                padx=(8, 0),
                pady=6,
            )

    def _add_action_row(
        self,
        parent: ttk.Frame,
        row_index: int,
        start_text: str,
        start_command: Callable[[], None],
    ) -> None:
        row = ttk.Frame(parent)
        row.grid(row=row_index, column=1, sticky="w", pady=(4, 0))

        start_button = ttk.Button(row, text=start_text, command=start_command)
        stop_button = ttk.Button(
            row,
            text="停止当前任务",
            command=self.stop_current_process,
            state="disabled",
        )
        start_button.pack(side="left")
        stop_button.pack(side="left", padx=(8, 0))

        self.start_buttons.append(start_button)
        self.stop_buttons.append(stop_button)

    def _scan_serial_ports(self) -> list[str]:
        if list_ports is None:
            return []
        return sorted((info.device for info in list_ports.comports()), key=str.upper)

    def _set_detected_ports(self, target: str, ports: list[str]) -> None:
        if target == "modbus":
            self.modbus_detected_ports = ports
        else:
            self.raw_detected_ports = ports

    def _detected_ports_for(self, target: str) -> list[str]:
        return self.modbus_detected_ports if target == "modbus" else self.raw_detected_ports

    def _load_config_port(self, config_path: Path) -> str:
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return ""
        return str(payload.get("port", "")).strip()

    def refresh_serial_ports(self, target: str, log_results: bool = True) -> None:
        ports = self._scan_serial_ports()
        self._set_detected_ports(target, ports)
        combo = self.modbus_port_combo if target == "modbus" else self.raw_port_combo
        variable = self.modbus_port_var if target == "modbus" else self.raw_port_var
        current = variable.get().strip()

        values = list(ports)
        if current and current not in values:
            values.insert(0, current)
        if combo is not None:
            combo["values"] = values
        if not current and values:
            variable.set(values[0])

        if log_results:
            self._append_log(
                "已检测到可用串口: {0}".format(", ".join(values))
                if values
                else "未检测到可用 COM 串口。"
            )

    def use_config_port(
        self,
        target: str,
        prefer_detected: bool = False,
        log_results: bool = True,
    ) -> None:
        config_var = (
            self.modbus_config_var if target == "modbus" else self.raw_config_var
        )
        port_var = self.modbus_port_var if target == "modbus" else self.raw_port_var
        combo = self.modbus_port_combo if target == "modbus" else self.raw_port_combo

        config_path = Path(config_var.get().strip())
        if not config_path.exists():
            return

        port = self._load_config_port(config_path)
        if port:
            detected_ports = self._detected_ports_for(target)
            selected_port = (
                select_preferred_port(detected_ports, port)
                if prefer_detected
                else port
            )
            port_var.set(selected_port)
            current_values = list(combo["values"]) if combo is not None else []
            if combo is not None and selected_port not in current_values:
                combo["values"] = [selected_port] + current_values
            if (
                log_results
                and detected_ports
                and port.upper() not in {item.upper() for item in detected_ports}
            ):
                self._append_log(
                    "配置文件中的串口 {0} 当前未检测到，已选择 {1}。".format(
                        port, selected_port
                    )
                    if prefer_detected
                    else "配置文件中的串口 {0} 当前未检测到，启动前请确认设备连接。".format(
                        port
                    )
                )

    def _resolve_port_override(self, target: str, config_path: Path) -> str | None:
        self.refresh_serial_ports(target, log_results=False)
        port_var = self.modbus_port_var if target == "modbus" else self.raw_port_var
        selected_port = port_var.get().strip()
        config_port = self._load_config_port(config_path)
        effective_port = selected_port or config_port
        detected_ports = self._detected_ports_for(target)

        if not effective_port:
            messagebox.showerror(
                "串口未设置",
                "未检测到可用 COM 串口，配置文件中也没有 port。请连接设备后点击“搜索串口”，或手动填写 COM 口。",
            )
            return None

        detected_upper = {port.upper() for port in detected_ports}
        if detected_ports and effective_port.upper() not in detected_upper:
            messagebox.showerror(
                "串口不可用",
                "未检测到 {0}。\n当前可用串口: {1}\n\n请点击“搜索串口”选择实际连接设备的 COM 口，或确认驱动和连接线。".format(
                    effective_port,
                    ", ".join(detected_ports),
                ),
            )
            self._append_log(
                "串口不可用: 未检测到 {0}；当前可用串口: {1}".format(
                    effective_port, ", ".join(detected_ports)
                )
            )
            return None

        return selected_port

    def _build_command(self, tool_name: str, extra_args: list[str]) -> list[str]:
        if getattr(sys, "frozen", False):
            return [sys.executable, "__tool__", tool_name] + extra_args
        return [
            sys.executable,
            str(Path(__file__).resolve()),
            "__tool__",
            tool_name,
        ] + extra_args

    def _append_log(self, message: str) -> None:
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")

    def _poll_log_queue(self) -> None:
        while True:
            try:
                kind, payload = self.log_queue.get_nowait()
            except queue.Empty:
                break

            if kind == "line":
                self._append_log(payload)
            elif kind == "done":
                self._set_running_state(False)
                self.status_var.set(payload)
                self.process = None
                self._append_log(payload)

        self.root.after(120, self._poll_log_queue)

    def _set_running_state(self, is_running: bool) -> None:
        for button in self.start_buttons:
            button.configure(state="disabled" if is_running else "normal")
        for button in self.stop_buttons:
            button.configure(state="normal" if is_running else "disabled")

    def _stream_process_output(
        self, process: subprocess.Popen[str], tool_label: str
    ) -> None:
        assert process.stdout is not None
        try:
            for line in iter(process.stdout.readline, ""):
                if not line:
                    break
                self.log_queue.put(("line", line.rstrip()))
        finally:
            process.stdout.close()
            exit_code = process.wait()
            message = (
                "{0} 已结束。".format(tool_label)
                if exit_code == 0
                else "{0} 异常结束，退出码 {1}。".format(tool_label, exit_code)
            )
            self.log_queue.put(("done", message))

    def _start_tool(
        self, tool_name: str, tool_label: str, extra_args: list[str]
    ) -> None:
        if self.process is not None and self.process.poll() is None:
            messagebox.showwarning("任务进行中", "当前已有任务在运行，请先停止它。")
            return

        command = self._build_command(tool_name, extra_args)
        self._append_log("")
        self._append_log("[{0}] 启动任务".format(tool_label))
        self._append_log("命令: {0}".format(" ".join(command)))

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(self.app_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                env=build_child_process_environment(),
            )
        except OSError as exc:
            self.status_var.set("{0} 启动失败".format(tool_label))
            self._append_log("启动失败: {0}".format(exc))
            messagebox.showerror(
                "启动失败",
                "{0} 无法启动。\n\n详细信息: {1}".format(tool_label, exc),
            )
            return
        self.status_var.set("{0} 运行中".format(tool_label))
        self._set_running_state(True)

        threading.Thread(
            target=self._stream_process_output,
            args=(self.process, tool_label),
            daemon=True,
        ).start()

    def start_modbus(self) -> None:
        config_path = Path(self.modbus_config_var.get().strip())
        if not config_path.exists():
            messagebox.showerror("配置文件不存在", "请先选择有效的 Modbus 配置文件。")
            return

        args = ["--config", str(config_path)]
        port = self._resolve_port_override("modbus", config_path)
        if port is None:
            return
        if port:
            args.extend(["--port", port])
        if self.modbus_once_var.get():
            args.append("--once")
        self._start_tool("modbus", "Modbus 采集", args)

    def start_modbus_live_plot(self) -> None:
        config_path = Path(self.modbus_config_var.get().strip())
        if not config_path.exists():
            messagebox.showerror("配置文件不存在", "请先选择有效的 Modbus 配置文件。")
            return

        args = ["--config", str(config_path)]
        port = self._resolve_port_override("modbus", config_path)
        if port is None:
            return
        if port:
            args.extend(["--port", port])

        plot_window = self.live_plot_window_var.get().strip()
        try:
            int(plot_window)
        except ValueError:
            messagebox.showerror("参数错误", "实时窗口秒数必须是整数。")
            return

        args.extend(["--plot-window", plot_window])
        if self.live_plot_smooth_var.get():
            args.append("--smooth")
        if self.modbus_once_var.get():
            args.append("--once")
        self._start_tool("liveplot", "Modbus 实时曲线", args)

    def start_raw(self) -> None:
        config_path = Path(self.raw_config_var.get().strip())
        if not config_path.exists():
            messagebox.showerror("配置文件不存在", "请先选择有效的原始串口配置文件。")
            return

        args = ["--config", str(config_path)]
        port = self._resolve_port_override("raw", config_path)
        if port is None:
            return
        if port:
            args.extend(["--port", port])
        if self.raw_once_var.get():
            args.append("--once")
        self._start_tool("raw", "原始串口采集", args)

    def start_video(self) -> None:
        video_dir = Path(self.video_dir_var.get().strip())
        excel_dir = Path(self.excel_dir_var.get().strip())
        if not video_dir.exists():
            messagebox.showerror("目录不存在", "视频目录不存在，请先确认。")
            return
        if not excel_dir.exists():
            messagebox.showerror("目录不存在", "Excel 日志目录不存在，请先确认。")
            return

        args = ["--video-dir", str(video_dir), "--excel-dir", str(excel_dir)]
        output_value = self.video_output_var.get().strip()
        if output_value:
            args.extend(["--output", output_value])
        self._start_tool("video", "视频回填", args)

    def start_extract(self) -> None:
        args: list[str] = []
        input_value = self.extract_input_var.get().strip()
        output_value = self.extract_output_var.get().strip()
        stability_value = self.extract_stability_var.get().strip()
        tolerance_value = self.extract_tolerance_var.get().strip()

        if input_value:
            input_path = Path(input_value)
            if not input_path.exists():
                messagebox.showerror(
                    "输入文件不存在", "请选择有效的 *_video_ocr.xlsx 文件。"
                )
                return
            args.extend(["--input", str(input_path)])

        if output_value:
            args.extend(["--output", output_value])

        try:
            float(stability_value)
            float(tolerance_value)
        except ValueError:
            messagebox.showerror("参数错误", "稳定窗口秒数和允许偏差比例必须是数字。")
            return

        args.extend(["--stability-seconds", stability_value])
        args.extend(["--percentage-tolerance", tolerance_value])
        self._start_tool("extract", "可靠数据与曲线", args)

    def stop_current_process(self) -> None:
        if self.process is None or self.process.poll() is not None:
            return
        self._append_log("正在停止当前任务...")
        self.process.terminate()

    def handle_close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            if not messagebox.askyesno("退出", "当前任务还在运行，确定停止并退出吗？"):
                return
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.root.destroy()

    def _open_folder(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(str(folder))


def main() -> int:
    internal_result = run_internal_tool(sys.argv)
    if internal_result is not None:
        return internal_result

    root = tk.Tk()
    configure_default_fonts(root)
    style = ttk.Style()
    if "vista" in style.theme_names():
        style.theme_use("vista")
    ToolLauncherApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
