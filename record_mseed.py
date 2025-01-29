# -*- coding: utf-8 -*-
import time
import os
import struct
import numpy as np
from obspy import Trace, Stream, UTCDateTime
import ADS1256
import RPi.GPIO as GPIO

# Configuration
SAMPLE_RATE = 100  # 100 SPS
BUFFER_SIZE = 1000  # Buffer before writing to disk
DATA_DIR = "./mseed"  # Directory to save MiniSEED files
CHANNELS = ["HHZ", "HHE", "HHN"]  # Seismometer channel names

# Manually define Gain and Data Rate for ADS1256
GAIN = 0x00  # Gain 1x
DATA_RATE = 0xF2  # 100 SPS

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)


def configure_adc(adc):
    """
    Configure ADS1256 ADC:
    - Gain 1x
    - 100 SPS
    - Perform self-calibration
    """
    print("🔄 Performing Self-Calibration...")

    # Set ADC gain and sampling rate
    adc.ADS1256_ConfigADC(GAIN, DATA_RATE)

    # Self-calibrate
    adc.ADS1256_WriteCmd(0xF0)  # Self-calibration command
    time.sleep(0.1)
    print("✅ Self-Calibration Completed.")


def get_next_hour_filename():
    """
    Generate the next filename based on the system clock.
    Ensures a new file starts **exactly** at the beginning of the next hour.
    """
    current_time = UTCDateTime()
    next_hour = current_time.replace(minute=0, second=0, microsecond=0) + 3600  # Next full hour
    filename = f"{DATA_DIR}/geophone_{next_hour.strftime('%Y%m%d_%H')}.mseed"
    return filename, next_hour


def record_geophone():
    """
    Record geophone data continuously, ensuring new Mini-SEED file at every full hour.
    """
    adc = ADS1256.ADS1256()
    if adc.ADS1256_init() == -1:
        print("❌ Failed to initialize ADC.")
        return

    configure_adc(adc)

    print("📡 Starting geophone data collection...")

    while True:
        next_file, next_hour = get_next_hour_filename()
        stream = Stream()
        buffer = {ch: [] for ch in CHANNELS}
        start_time = UTCDateTime()

        print(f"🎤 Recording geophone data -> {next_file} until {next_hour.strftime('%H:%M:%S')}")

        while UTCDateTime() < next_hour:
            try:
                # Read ADC values
                for i, ch in enumerate(CHANNELS):
                    adc.ADS1256_SetDiffChannal(i)  # Set to channel
                    value = adc.ADS1256_Read_ADC_Data()  # Read ADC
                    buffer[ch].append(value)

                # If buffer is full, write to file
                if len(buffer["HHZ"]) >= BUFFER_SIZE:
                    for ch in CHANNELS:
                        trace = Trace(np.array(buffer[ch], dtype=np.int32))
                        trace.stats.sampling_rate = SAMPLE_RATE
                        trace.stats.starttime = start_time
                        trace.stats.network = "XX"
                        trace.stats.station = "GEO"
                        trace.stats.location = "00"
                        trace.stats.channel = ch
                        stream.append(trace)

                    # Save Mini-SEED file
                    stream.write(next_file, format="MSEED")

                    # Reset buffer
                    for ch in CHANNELS:
                        buffer[ch] = []

                    print(f"📊 {len(stream)} traces saved to {next_file}")

                time.sleep(1.0 / SAMPLE_RATE)

            except Exception as e:
                print(f"❌ Error reading ADC: {e}")
                GPIO.cleanup()
                break

        print("🛑 Stopping data collection. New hour detected.")


if __name__ == "__main__":
    try:
        record_geophone()
    except KeyboardInterrupt:
        print("❌ Interrupted by user.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        GPIO.cleanup()
