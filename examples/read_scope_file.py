from pathlib import Path

from lab_tools.io import read_keysight_h5


data_file = Path(__file__).parent / "data" / "run530_5waveforms.h5"

time, voltage, metadata = read_keysight_h5(
    data_file,
    segment_numbers=[1, 2, 3, 5],
)

print(f"Segments: {metadata['segment_numbers']}")
print(f"Time shape: {time.shape}")
print(f"Voltage shape: {voltage.shape}")
print(f"First sample: {time[0]}, {voltage[0, 0]}")
