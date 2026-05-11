import importlib
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

os.environ["SERIAL_LOGGER_MPL_BACKEND"] = "Agg"

serial_logger_with_plot = importlib.import_module("scripts.serial_logger_with_plot")


class PreviousSecondAverageTests(unittest.TestCase):
    def test_previous_second_average_uses_only_last_complete_second(self) -> None:
        buckets = {}
        serial_logger_with_plot.record_second_bucket(
            buckets,
            datetime(2026, 4, 21, 12, 0, 4, 100000),
            {
                "weight_ch1": 10.0,
                "weight_ch2": 20.0,
                "weight_ch3": 30.0,
                serial_logger_with_plot.TOTAL_FORCE_NAME: 60.0,
            },
        )
        serial_logger_with_plot.record_second_bucket(
            buckets,
            datetime(2026, 4, 21, 12, 0, 4, 800000),
            {
                "weight_ch1": 14.0,
                "weight_ch2": 24.0,
                "weight_ch3": 34.0,
                serial_logger_with_plot.TOTAL_FORCE_NAME: 72.0,
            },
        )
        serial_logger_with_plot.record_second_bucket(
            buckets,
            datetime(2026, 4, 21, 12, 0, 5, 100000),
            {
                "weight_ch1": 999.0,
                "weight_ch2": 999.0,
                "weight_ch3": 999.0,
                serial_logger_with_plot.TOTAL_FORCE_NAME: 999.0,
            },
        )

        second_ts, averages = serial_logger_with_plot.compute_previous_second_averages(
            buckets,
            datetime(2026, 4, 21, 12, 0, 5, 300000),
        )

        self.assertEqual(second_ts, datetime(2026, 4, 21, 12, 0, 4))
        self.assertEqual(averages["weight_ch1"], 12.0)
        self.assertEqual(averages["weight_ch2"], 22.0)
        self.assertEqual(averages["weight_ch3"], 32.0)
        self.assertEqual(averages[serial_logger_with_plot.TOTAL_FORCE_NAME], 66.0)

    def test_compute_total_force_requires_all_channels(self) -> None:
        total_force = serial_logger_with_plot.compute_total_force(
            {"weight_ch1": 1.0, "weight_ch2": 2.0, "weight_ch3": 3.0},
            ["weight_ch1", "weight_ch2", "weight_ch3"],
        )
        missing_total_force = serial_logger_with_plot.compute_total_force(
            {"weight_ch1": 1.0, "weight_ch2": 2.0},
            ["weight_ch1", "weight_ch2", "weight_ch3"],
        )

        self.assertEqual(total_force, 6.0)
        self.assertIsNone(missing_total_force)

    def test_previous_second_average_returns_empty_when_previous_second_missing(
        self,
    ) -> None:
        second_ts, averages = serial_logger_with_plot.compute_previous_second_averages(
            {},
            datetime(2026, 4, 21, 12, 0, 5, 300000),
        )

        self.assertIsNone(second_ts)
        self.assertEqual(averages, {})

    def test_previous_second_average_returns_empty_for_empty_previous_bucket(
        self,
    ) -> None:
        buckets = {
            datetime(2026, 4, 21, 12, 0, 4): {},
        }

        second_ts, averages = serial_logger_with_plot.compute_previous_second_averages(
            buckets,
            datetime(2026, 4, 21, 12, 0, 5, 300000),
        )

        self.assertIsNone(second_ts)
        self.assertEqual(averages, {})

    def test_record_second_bucket_ignores_none_values(self) -> None:
        buckets = {}
        ts = datetime(2026, 4, 21, 12, 0, 4, 100000)
        empty_ts = datetime(2026, 4, 21, 12, 0, 5, 100000)

        serial_logger_with_plot.record_second_bucket(
            buckets,
            ts,
            {"weight_ch1": None, "weight_ch2": 2.0},
        )
        serial_logger_with_plot.record_second_bucket(
            buckets,
            empty_ts,
            {"weight_ch1": None, serial_logger_with_plot.TOTAL_FORCE_NAME: None},
        )

        self.assertEqual(
            buckets[serial_logger_with_plot.floor_to_second(ts)],
            {"weight_ch2": [2.0]},
        )
        self.assertNotIn(serial_logger_with_plot.floor_to_second(empty_ts), buckets)

    def test_second_helpers_use_natural_second_boundaries(self) -> None:
        self.assertEqual(
            serial_logger_with_plot.floor_to_second(
                datetime(2026, 4, 21, 12, 0, 5, 999999)
            ),
            datetime(2026, 4, 21, 12, 0, 5),
        )
        self.assertEqual(
            serial_logger_with_plot.previous_complete_second(
                datetime(2026, 4, 21, 12, 0, 5)
            ),
            datetime(2026, 4, 21, 12, 0, 4),
        )


class TareAndSamplePreparationTests(unittest.TestCase):
    def test_build_manual_tare_offsets_uses_latest_raw_values(self) -> None:
        offsets = serial_logger_with_plot.build_manual_tare_offsets(
            {"weight_ch1": 101.0, "weight_ch2": 202.0, "weight_ch3": 303.0},
            ["weight_ch1", "weight_ch2", "weight_ch3"],
        )

        self.assertEqual(
            offsets,
            {"weight_ch1": 101.0, "weight_ch2": 202.0, "weight_ch3": 303.0},
        )

    def test_prepare_plot_sample_applies_offsets_and_adds_total_force(self) -> None:
        sample = serial_logger_with_plot.prepare_plot_sample(
            {"weight_ch1": 110.0, "weight_ch2": 215.0, "weight_ch3": 320.0},
            {"weight_ch1": 100.0, "weight_ch2": 200.0, "weight_ch3": 300.0},
            ["weight_ch1", "weight_ch2", "weight_ch3"],
        )

        self.assertEqual(sample["weight_ch1"], 10.0)
        self.assertEqual(sample["weight_ch2"], 15.0)
        self.assertEqual(sample["weight_ch3"], 20.0)
        self.assertEqual(sample[serial_logger_with_plot.TOTAL_FORCE_NAME], 45.0)

    def test_append_series_snapshot_fills_missing_values_with_nan(self) -> None:
        history = {
            "weight_ch1": [],
            "weight_ch2": [],
            "weight_ch3": [],
            serial_logger_with_plot.TOTAL_FORCE_NAME: [],
        }

        serial_logger_with_plot.append_series_snapshot(
            history,
            [
                "weight_ch1",
                "weight_ch2",
                "weight_ch3",
                serial_logger_with_plot.TOTAL_FORCE_NAME,
            ],
            {"weight_ch1": 1.0, "weight_ch2": 2.0},
        )

        self.assertEqual(history["weight_ch1"][0], 1.0)
        self.assertEqual(history["weight_ch2"][0], 2.0)
        self.assertTrue(serial_logger_with_plot.math.isnan(history["weight_ch3"][0]))
        self.assertTrue(
            serial_logger_with_plot.math.isnan(
                history[serial_logger_with_plot.TOTAL_FORCE_NAME][0]
            )
        )


class TitleFormattingTests(unittest.TestCase):
    def test_format_previous_second_title_includes_second_force_and_tare_message(
        self,
    ) -> None:
        title = serial_logger_with_plot.format_previous_second_title(
            datetime(2026, 4, 21, 12, 0, 4),
            {
                "weight_ch1": 1.0,
                "weight_ch2": 2.0,
                "weight_ch3": 3.0,
                serial_logger_with_plot.TOTAL_FORCE_NAME: 6.0,
            },
            [
                "weight_ch1",
                "weight_ch2",
                "weight_ch3",
                serial_logger_with_plot.TOTAL_FORCE_NAME,
            ],
            "已去皮 12:00:05",
        )

        self.assertIn("已去皮 12:00:05", title)
        self.assertIn("上一秒均值 12:00:04", title)
        self.assertIn("weight_ch1=1.00", title)
        self.assertIn("total_force=6.00", title)


class LivePlotterManualTareTests(unittest.TestCase):
    def test_manual_tare_mid_second_keeps_previous_second_average_post_tare_only(
        self,
    ) -> None:
        plotter = serial_logger_with_plot.LivePlotter(
            ["weight_ch1", "weight_ch2", "weight_ch3"],
            window_seconds=60,
            smooth=False,
        )
        plotter.tare_done = True

        try:
            plotter.add_point(
                datetime(2026, 4, 21, 12, 0, 4, 100000),
                {"weight_ch1": 10.0, "weight_ch2": 20.0, "weight_ch3": 30.0},
            )
            plotter.add_point(
                datetime(2026, 4, 21, 12, 0, 4, 400000),
                {"weight_ch1": 12.0, "weight_ch2": 22.0, "weight_ch3": 32.0},
            )

            plotter.request_manual_tare()

            plotter.add_point(
                datetime(2026, 4, 21, 12, 0, 4, 700000),
                {"weight_ch1": 13.0, "weight_ch2": 23.0, "weight_ch3": 33.0},
            )

            second_ts, averages = (
                serial_logger_with_plot.compute_previous_second_averages(
                    plotter.second_buckets,
                    datetime(2026, 4, 21, 12, 0, 5, 100000),
                )
            )

            self.assertEqual(second_ts, datetime(2026, 4, 21, 12, 0, 4))
            self.assertEqual(averages["weight_ch1"], 1.0)
            self.assertEqual(averages["weight_ch2"], 1.0)
            self.assertEqual(averages["weight_ch3"], 1.0)
            self.assertEqual(averages[serial_logger_with_plot.TOTAL_FORCE_NAME], 3.0)
        finally:
            plotter.close()


class GroupedMeasurementHelperTests(unittest.TestCase):
    def test_finish_measurement_uses_only_recorded_group_samples(self) -> None:
        state = serial_logger_with_plot.MeasurementSessionState()
        start_time = datetime(2026, 5, 8, 15, 0, 0, 100000)
        end_time = datetime(2026, 5, 8, 15, 0, 1, 400000)

        serial_logger_with_plot.start_measurement_group(state, "1200", start_time)
        serial_logger_with_plot.record_measurement_sample(
            state,
            datetime(2026, 5, 8, 15, 0, 0, 200000),
            {"weight_ch1": 1.0, "weight_ch2": 2.0, "weight_ch3": 3.0},
            6.0,
        )
        serial_logger_with_plot.record_measurement_sample(
            state,
            datetime(2026, 5, 8, 15, 0, 1, 100000),
            {"weight_ch1": 2.0, "weight_ch2": 3.0, "weight_ch3": 4.0},
            9.0,
        )

        group = serial_logger_with_plot.finish_measurement_group(
            state, "3.25", end_time
        )

        self.assertEqual(group.pwm, "1200")
        self.assertEqual(group.start_time, start_time)
        self.assertEqual(group.end_time, end_time)
        self.assertEqual(group.total_current, 3.25)
        self.assertEqual(group.average_total_force, 7.5)
        self.assertEqual(len(group.samples), 2)
        self.assertEqual(len(state.completed_groups), 1)

    def test_finish_measurement_requires_total_force_samples(self) -> None:
        state = serial_logger_with_plot.MeasurementSessionState()
        serial_logger_with_plot.start_measurement_group(
            state,
            "800",
            datetime(2026, 5, 8, 15, 1, 0),
        )

        with self.assertRaisesRegex(ValueError, "No valid total force samples"):
            serial_logger_with_plot.finish_measurement_group(
                state,
                "1.20",
                datetime(2026, 5, 8, 15, 1, 1),
            )

    def test_reset_for_next_group_keeps_completed_results(self) -> None:
        state = serial_logger_with_plot.MeasurementSessionState(
            completed_groups=[
                serial_logger_with_plot.MeasurementGroupResult(
                    index=1,
                    pwm="600",
                    start_time=datetime(2026, 5, 8, 15, 2, 0),
                    end_time=datetime(2026, 5, 8, 15, 2, 1),
                    total_current=0.8,
                    average_total_force=5.5,
                    samples=[],
                )
            ]
        )
        serial_logger_with_plot.start_measurement_group(
            state,
            "900",
            datetime(2026, 5, 8, 15, 2, 2),
        )

        serial_logger_with_plot.reset_for_next_group(state)

        self.assertEqual(len(state.completed_groups), 1)
        self.assertIsNone(state.current_group)

    def test_build_measurement_export_rows_expands_summary_and_raw_columns(
        self,
    ) -> None:
        groups = [
            serial_logger_with_plot.MeasurementGroupResult(
                index=1,
                pwm="700",
                start_time=datetime(2026, 5, 8, 15, 3, 0),
                end_time=datetime(2026, 5, 8, 15, 3, 2),
                total_current=1.5,
                average_total_force=8.0,
                samples=[
                    serial_logger_with_plot.MeasurementSample(
                        timestamp=datetime(2026, 5, 8, 15, 3, 0, 100000),
                        raw_values={
                            "weight_ch1": 1.0,
                            "weight_ch2": 2.0,
                            "weight_ch3": 3.0,
                        },
                        total_force=6.0,
                    ),
                    serial_logger_with_plot.MeasurementSample(
                        timestamp=datetime(2026, 5, 8, 15, 3, 1, 100000),
                        raw_values={
                            "weight_ch1": 2.0,
                            "weight_ch2": 3.0,
                            "weight_ch3": 4.0,
                        },
                        total_force=9.0,
                    ),
                ],
            )
        ]

        headers, rows = serial_logger_with_plot.build_measurement_export_rows(groups)

        self.assertEqual(
            headers[:6],
            [
                "序号",
                "PWM",
                "开始时间(北京时间)",
                "结束时间(北京时间)",
                "总电流",
                "合力平均值",
            ],
        )
        self.assertIn("原始时间戳_1", headers)
        self.assertIn("原始合力_2", headers)
        self.assertIn("原始ch1_1", headers)
        self.assertEqual(rows[0][0], 1)
        self.assertEqual(rows[0][1], "700")

    def test_build_measurement_export_path_contains_datetime(self) -> None:
        export_path = serial_logger_with_plot.build_measurement_export_path(
            serial_logger_with_plot.Path("C:/temp/output"),
            datetime(2026, 5, 8, 15, 4, 5),
        )

        self.assertEqual(export_path.name, "measurement_results_20260508_150405.xlsx")


class ExcelLoggerPersistenceTests(unittest.TestCase):
    def test_close_verifies_last_timestamp_was_saved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = Path(temp_dir) / "logger.xlsx"
            logger = serial_logger_with_plot.ExcelLogger(
                workbook_path=workbook_path,
                sheet_name="data",
                field_names=["weight_ch1", "weight_ch2", "weight_ch3"],
                autosave_every_rows=10,
                autosave_interval_seconds=60.0,
            )

            logger.append_row(
                {
                    "timestamp": "2026-05-11 17:00:00.123456",
                    "unix_time": 1.0,
                    "port": "COM4",
                    "baudrate": 115200,
                    "slave_id": 1,
                    "status": "ok",
                    "error": "",
                    "raw_frames": "{}",
                    "weight_ch1": 1.0,
                    "weight_ch2": 2.0,
                    "weight_ch3": 3.0,
                }
            )

            logger.close()

            self.assertEqual(
                logger._read_last_saved_timestamp(),
                "2026-05-11 17:00:00.123456",
            )

    def test_flush_keeps_pending_rows_when_save_verification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = Path(temp_dir) / "logger.xlsx"
            logger = serial_logger_with_plot.ExcelLogger(
                workbook_path=workbook_path,
                sheet_name="data",
                field_names=["weight_ch1", "weight_ch2", "weight_ch3"],
                autosave_every_rows=10,
                autosave_interval_seconds=60.0,
            )

            logger.append_row(
                {
                    "timestamp": "2026-05-11 17:00:01.123456",
                    "unix_time": 2.0,
                    "port": "COM4",
                    "baudrate": 115200,
                    "slave_id": 1,
                    "status": "ok",
                    "error": "",
                    "raw_frames": "{}",
                    "weight_ch1": 4.0,
                    "weight_ch2": 5.0,
                    "weight_ch3": 6.0,
                }
            )

            with mock.patch.object(
                logger,
                "_verify_last_saved_timestamp",
                side_effect=RuntimeError("verify failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "verify failed"):
                    logger.flush()

            self.assertEqual(len(logger.pending_rows), 1)
            self.assertEqual(logger.unsaved_rows, 1)


class LivePlotterGroupedMeasurementTests(unittest.TestCase):
    def test_live_plotter_records_samples_only_while_group_is_active(self) -> None:
        plotter = serial_logger_with_plot.LivePlotter(
            ["weight_ch1", "weight_ch2", "weight_ch3"],
            window_seconds=60,
            smooth=False,
        )
        plotter.tare_done = True

        try:
            plotter.add_point(
                datetime(2026, 5, 8, 15, 5, 0),
                {"weight_ch1": 1.0, "weight_ch2": 2.0, "weight_ch3": 3.0},
            )
            self.assertEqual(len(plotter.measurement_state.completed_groups), 0)

            serial_logger_with_plot.start_measurement_group(
                plotter.measurement_state,
                "1100",
                datetime(2026, 5, 8, 15, 5, 0, 100000),
            )
            plotter.add_point(
                datetime(2026, 5, 8, 15, 5, 0, 200000),
                {"weight_ch1": 2.0, "weight_ch2": 3.0, "weight_ch3": 4.0},
            )
            plotter.add_point(
                datetime(2026, 5, 8, 15, 5, 0, 300000),
                {"weight_ch1": 3.0, "weight_ch2": 4.0, "weight_ch3": 5.0},
            )

            result = serial_logger_with_plot.finish_measurement_group(
                plotter.measurement_state,
                "2.40",
                datetime(2026, 5, 8, 15, 5, 1),
            )

            self.assertEqual(result.average_total_force, 10.5)
            self.assertEqual(len(result.samples), 2)
        finally:
            plotter.close()

    def test_start_finish_and_prepare_next_group_update_measurement_state(self) -> None:
        plotter = serial_logger_with_plot.LivePlotter(
            ["weight_ch1", "weight_ch2", "weight_ch3"],
            window_seconds=60,
            smooth=False,
        )
        plotter.tare_done = True

        try:
            plotter.measurement_pwm_var.set("1300")
            plotter.start_measurement()
            plotter.add_point(
                datetime(2026, 5, 8, 15, 6, 0, 100000),
                {"weight_ch1": 3.0, "weight_ch2": 3.0, "weight_ch3": 3.0},
            )
            plotter.add_point(
                datetime(2026, 5, 8, 15, 6, 0, 200000),
                {"weight_ch1": 4.0, "weight_ch2": 4.0, "weight_ch3": 4.0},
            )
            plotter.measurement_current_var.set("2.80")
            plotter.finish_measurement()

            self.assertEqual(plotter.measurement_status_var.get(), "已完成")
            self.assertEqual(len(plotter.measurement_state.completed_groups), 1)
            self.assertIn("PWM=1300", plotter.measurement_summary_var.get())
            self.assertIn("1300", plotter.measurement_history_var.get())
            self.assertIn("2.800", plotter.measurement_history_var.get())

            plotter.prepare_next_group()

            self.assertEqual(plotter.measurement_status_var.get(), "未开始")
            self.assertEqual(plotter.measurement_pwm_var.get(), "")
            self.assertEqual(plotter.measurement_current_var.get(), "")
            self.assertEqual(len(plotter.measurement_state.completed_groups), 1)
        finally:
            plotter.close()

    def test_export_measurements_writes_file_to_output_dir(self) -> None:
        plotter = serial_logger_with_plot.LivePlotter(
            ["weight_ch1", "weight_ch2", "weight_ch3"],
            window_seconds=60,
            smooth=False,
        )

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                plotter.measurement_output_dir = serial_logger_with_plot.Path(temp_dir)
                plotter.measurement_state.completed_groups.append(
                    serial_logger_with_plot.MeasurementGroupResult(
                        index=1,
                        pwm="400",
                        start_time=datetime(2026, 5, 8, 17, 0, 0),
                        end_time=datetime(2026, 5, 8, 17, 0, 1),
                        total_current=0.55,
                        average_total_force=3.0,
                        samples=[
                            serial_logger_with_plot.MeasurementSample(
                                timestamp=datetime(2026, 5, 8, 17, 0, 0, 100000),
                                raw_values={
                                    "weight_ch1": 1.0,
                                    "weight_ch2": 1.0,
                                    "weight_ch3": 1.0,
                                },
                                total_force=3.0,
                            )
                        ],
                    )
                )

                export_path = plotter.export_measurements()

                self.assertTrue(export_path.exists())
                self.assertEqual(
                    export_path.parent, serial_logger_with_plot.Path(temp_dir)
                )
        finally:
            plotter.close()


class MeasurementWorkbookTests(unittest.TestCase):
    def test_write_measurement_workbook_creates_expected_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = (
                serial_logger_with_plot.Path(temp_dir)
                / "measurement_results_20260508_150405.xlsx"
            )
            groups = [
                serial_logger_with_plot.MeasurementGroupResult(
                    index=1,
                    pwm="500",
                    start_time=datetime(2026, 5, 8, 16, 0, 0),
                    end_time=datetime(2026, 5, 8, 16, 0, 1),
                    total_current=0.75,
                    average_total_force=4.5,
                    samples=[
                        serial_logger_with_plot.MeasurementSample(
                            timestamp=datetime(2026, 5, 8, 16, 0, 0, 100000),
                            raw_values={
                                "weight_ch1": 1.0,
                                "weight_ch2": 1.5,
                                "weight_ch3": 2.0,
                            },
                            total_force=4.5,
                        )
                    ],
                )
            ]

            serial_logger_with_plot.write_measurement_workbook(output_path, groups)

            workbook = serial_logger_with_plot.load_workbook(output_path)
            worksheet = workbook.active
            headers = [cell.value for cell in worksheet[1]]
            max_row = worksheet.max_row
            workbook.close()

            self.assertEqual(
                headers[:6],
                [
                    "序号",
                    "PWM",
                    "开始时间(北京时间)",
                    "结束时间(北京时间)",
                    "总电流",
                    "合力平均值",
                ],
            )
            self.assertIn("原始时间戳_1", headers)
            self.assertEqual(max_row, 2)


if __name__ == "__main__":
    unittest.main()
