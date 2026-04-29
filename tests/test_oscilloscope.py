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


@unittest.skipUnless(h5py is not None and np is not None, "h5py/numpy are not installed")
class KeysightH5ReaderTests(unittest.TestCase):
    def test_reads_selected_segments(self):
        path = _write_scope_file()

        time, voltage, metadata = read_keysight_h5(path, segment_numbers=[2])

        np.testing.assert_allclose(time, [0.0, 0.5, 1.0])
        np.testing.assert_allclose(voltage, [[1.0, 1.1, 1.2]])
        self.assertEqual(metadata["file_type"], "Keysight Waveform")
        self.assertEqual(metadata["frame"]["Model"], "EXR054A")
        self.assertEqual(metadata["channel_attrs"]["XUnits"], "Second")
        self.assertEqual(metadata["segment_numbers"], [2])
        np.testing.assert_allclose(metadata["time_tags"], [10.0])

    def test_supports_absolute_time_axis(self):
        path = _write_scope_file()

        time, voltage, metadata = read_oscilloscope_h5(
            path,
            segment_numbers=[1, 2],
            time_axis="absolute",
        )

        np.testing.assert_allclose(time, [[-1.0, -0.5, 0.0], [9.0, 9.5, 10.0]])
        np.testing.assert_allclose(voltage, [[0.0, 0.1, 0.2], [1.0, 1.1, 1.2]])
        self.assertEqual(metadata["segment_numbers"], [1, 2])

    def test_supports_zero_based_waveform_ids_and_raw_data(self):
        path = _write_scope_file()

        time, voltage, metadata = read_keysight_h5(path, waveform_ids=[0, 1], include_raw=True)

        np.testing.assert_allclose(time, [0.0, 0.5, 1.0])
        np.testing.assert_allclose(voltage, [[0.0, 0.1, 0.2], [1.0, 1.1, 1.2]])
        np.testing.assert_array_equal(metadata["raw"], [[10, 11, 12], [20, 21, 22]])

    def test_reads_a_second_channel(self):
        path = _write_scope_file()

        time, voltage, metadata = read_keysight_h5(path, channel=2, segment_numbers=[1, 2])

        np.testing.assert_allclose(time, [0.0, 0.5, 1.0])
        np.testing.assert_allclose(voltage, [[0.0, 0.24, 0.0], [0.0, 0.25, 0.0]])
        self.assertEqual(metadata["channel"], "Channel 2")
        self.assertEqual(metadata["segment_numbers"], [1, 2])

    def test_reads_segment_time_tags(self):
        path = _write_scope_file()

        segments, tags = read_segment_time_tags(path)

        np.testing.assert_array_equal(segments, [1, 2])
        np.testing.assert_allclose(tags, [0.0, 10.0])


def _write_scope_file() -> Path:
    tmpdir = tempfile.TemporaryDirectory()
    path = Path(tmpdir.name) / "scope.h5"
    _TEMP_DIRS.append(tmpdir)

    with h5py.File(path, "w") as h5_file:
        file_type = h5_file.create_group("FileType")
        file_type.create_dataset("KeysightH5FileType", data=b"Keysight Waveform")

        frame_dtype = np.dtype([("Model", "S12"), ("Serial", "S12"), ("Date", "S22")])
        frame = h5_file.create_group("Frame")
        frame.create_dataset(
            "TheFrame",
            data=np.array((b"EXR054A", b"MY63310243", b"20-Mar-2025"), dtype=frame_dtype),
        )

        waveforms = h5_file.create_group("Waveforms")
        channel = waveforms.create_group("Channel 1")
        channel.attrs["NumPoints"] = 3
        channel.attrs["NumSegments"] = 2
        channel.attrs["XInc"] = 0.5
        channel.attrs["XOrg"] = -1.0
        channel.attrs["XUnits"] = b"Second"
        channel.attrs["YInc"] = 0.1
        channel.attrs["YOrg"] = -1.0
        channel.attrs["YUnits"] = b"Volt"

        channel_2 = waveforms.create_group("Channel 2")
        for key, value in channel.attrs.items():
            channel_2.attrs[key] = value
        channel_2.attrs["YInc"] = 0.01
        channel_2.attrs["YOrg"] = 0.0

        segment_1 = channel.create_dataset("Channel 1 Seg1Data", data=np.array([10, 11, 12], dtype=np.int16))
        segment_1.attrs["SegmentedTimeTag"] = 0.0
        segment_1.attrs["SegmentedXOrg"] = -1.0
        segment_1.attrs["RawNumPts"] = 4

        segment_2 = channel.create_dataset("Channel 1 Seg2Data", data=np.array([20, 21, 22], dtype=np.int16))
        segment_2.attrs["SegmentedTimeTag"] = 10.0
        segment_2.attrs["SegmentedXOrg"] = -1.0
        segment_2.attrs["RawNumPts"] = 4

        segment_1_ch2 = channel_2.create_dataset("Channel 2 Seg1Data", data=np.array([0, 24, 0], dtype=np.int16))
        for key, value in segment_1.attrs.items():
            segment_1_ch2.attrs[key] = value

        segment_2_ch2 = channel_2.create_dataset("Channel 2 Seg2Data", data=np.array([0, 25, 0], dtype=np.int16))
        for key, value in segment_2.attrs.items():
            segment_2_ch2.attrs[key] = value

    return path


_TEMP_DIRS = []


if __name__ == "__main__":
    unittest.main()
