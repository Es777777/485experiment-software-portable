import importlib
import os
import unittest
from datetime import datetime

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

    def test_previous_second_average_returns_empty_when_previous_second_missing(self) -> None:
        second_ts, averages = serial_logger_with_plot.compute_previous_second_averages(
            {},
            datetime(2026, 4, 21, 12, 0, 5, 300000),
        )

        self.assertIsNone(second_ts)
        self.assertEqual(averages, {})

    def test_previous_second_average_returns_empty_for_empty_previous_bucket(self) -> None:
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
    def test_format_previous_second_title_includes_second_force_and_tare_message(self) -> None:
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
    def test_manual_tare_mid_second_keeps_previous_second_average_post_tare_only(self) -> None:
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

            second_ts, averages = serial_logger_with_plot.compute_previous_second_averages(
                plotter.second_buckets,
                datetime(2026, 4, 21, 12, 0, 5, 100000),
            )

            self.assertEqual(second_ts, datetime(2026, 4, 21, 12, 0, 4))
            self.assertEqual(averages["weight_ch1"], 1.0)
            self.assertEqual(averages["weight_ch2"], 1.0)
            self.assertEqual(averages["weight_ch3"], 1.0)
            self.assertEqual(averages[serial_logger_with_plot.TOTAL_FORCE_NAME], 3.0)
        finally:
            plotter.close()


if __name__ == "__main__":
    unittest.main()
