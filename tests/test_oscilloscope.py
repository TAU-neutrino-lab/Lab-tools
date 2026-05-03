from pathlib import Path
import tempfile
import unittest

from lab_tools.io import read_keysight_h5, read_oscilloscope_h5, read_segment_time_tags


try:
    import h5py
    import numpy as np
except ModuleNotFoundError:
    h5py = None
    np = None


FIXTURE = Path(__file__).parents[1] / "examples" / "data" / "run530_5waveforms.h5"


@unittest.skipUnless(h5py is not None and np is not None, "h5py/numpy are not installed")
class KeysightH5ReaderTests(unittest.TestCase):
    def _write_single_segment_fixture(self, path):
        with h5py.File(path, "w") as h5_file:
            file_type = h5_file.create_group("FileType")
            file_type.create_dataset("KeysightH5FileType", data=b"Keysight Waveform")

            frame_dtype = np.dtype(
                [("Model", "S12"), ("Serial", "S12"), ("Date", "S22")]
            )
            frame = h5_file.create_group("Frame")
            frame.create_dataset(
                "TheFrame",
                data=np.array((b"EXR054A", b"TEST000000", b"01-Jan-2026"), dtype=frame_dtype),
            )

            waveforms = h5_file.create_group("Waveforms")
            channel = waveforms.create_group("Channel 1")
            channel.attrs["NumSegments"] = 1
            channel.attrs["NumPoints"] = 4
            channel.attrs["XInc"] = 0.5
            channel.attrs["XOrg"] = -1.0
            channel.attrs["XUnits"] = b"Second"
            channel.attrs["YInc"] = 0.1
            channel.attrs["YOrg"] = -1.0
            channel.attrs["YUnits"] = b"Volt"

            dataset = channel.create_dataset(
                "Channel 1 Data",
                data=np.array([10, 11, 12, 13], dtype=np.int16),
            )
            dataset.attrs["SegmentedTimeTag"] = 2.0
            dataset.attrs["SegmentedXOrg"] = -1.0

    def test_reads_all_segments_from_fixture(self):
        time, voltage, metadata = read_keysight_h5(FIXTURE)

        self.assertEqual(time.shape, (1600,))
        self.assertEqual(voltage.shape, (5, 1600))
        self.assertEqual(metadata["file_type"], "Keysight Waveform")
        self.assertEqual(metadata["frame"]["Model"], "EXR054A")
        self.assertEqual(metadata["channel"], "Channel 1")
        self.assertEqual(metadata["segment_numbers"], [1, 2, 3, 4, 5])
        self.assertEqual(metadata["channel_attrs"]["NumSegments"], 5)
        self.assertEqual(metadata["channel_attrs"]["XUnits"], "Second")
        self.assertEqual(metadata["channel_attrs"]["YUnits"], "Volt")

    def test_selects_segments_and_applies_voltage_scaling(self):
        time, voltage, metadata = read_keysight_h5(FIXTURE, segment_numbers=[1, 5])

        self.assertEqual(time.shape, (1600,))
        self.assertEqual(voltage.shape, (2, 1600))
        self.assertEqual(metadata["segment_numbers"], [1, 5])
        np.testing.assert_allclose(
            voltage[0, :5],
            [0.00060625, 0.00058648, 0.00055089, 0.00053508, 0.00051531],
            atol=1e-8,
        )

    def test_supports_absolute_time_axis(self):
        time, voltage, metadata = read_oscilloscope_h5(
            FIXTURE,
            segment_numbers=[1, 2],
            time_axis="absolute",
        )

        self.assertEqual(time.shape, (2, 1600))
        self.assertEqual(voltage.shape, (2, 1600))
        np.testing.assert_allclose(
            time[:, 0],
            [-1.387500119210247e-08, 0.0019491095296861887],
        )
        self.assertEqual(metadata["segment_numbers"], [1, 2])

    def test_reads_second_channel(self):
        time, voltage, metadata = read_keysight_h5(FIXTURE, channel=2)

        self.assertEqual(time.shape, (1600,))
        self.assertEqual(voltage.shape, (5, 1600))
        self.assertEqual(metadata["channel"], "Channel 2")
        self.assertEqual(metadata["segment_numbers"], [1, 2, 3, 4, 5])
        np.testing.assert_allclose(voltage.max(axis=1), [0.245, 0.25, 0.255, 0.26, 0.265])

    def test_reads_segment_time_tags(self):
        segments, tags = read_segment_time_tags(FIXTURE)

        np.testing.assert_array_equal(segments, [1, 2, 3, 4, 5])
        np.testing.assert_allclose(
            tags,
            [
                0.0,
                0.0019491234046873807,
                0.003898280365625,
                0.005847429945312619,
                0.0077964492468747615,
            ],
        )

    def test_reads_single_unsegmented_waveform_dataset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "single_segment.h5"
            self._write_single_segment_fixture(path)

            time, voltage, metadata = read_keysight_h5(path)

            np.testing.assert_allclose(time, [0.0, 0.5, 1.0, 1.5])
            np.testing.assert_allclose(voltage, [[0.0, 0.1, 0.2, 0.3]])
            self.assertEqual(metadata["segment_numbers"], [1])
            self.assertEqual(metadata["channel_attrs"]["NumSegments"], 1)

            time, voltage, metadata = read_keysight_h5(path, segment_numbers=[1])

            np.testing.assert_allclose(time, [0.0, 0.5, 1.0, 1.5])
            np.testing.assert_allclose(voltage, [[0.0, 0.1, 0.2, 0.3]])
            self.assertEqual(metadata["segment_numbers"], [1])

            segments, tags = read_segment_time_tags(path)

            np.testing.assert_array_equal(segments, [1])
            np.testing.assert_allclose(tags, [2.0])


if __name__ == "__main__":
    unittest.main()
