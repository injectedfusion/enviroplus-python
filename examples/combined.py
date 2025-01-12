#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
combined.py - Displays readings from all of Enviro plus' sensors

Press Ctrl+C to exit!
"""

import colorsys
import sys
import time
import logging
from subprocess import PIPE, Popen

import st7735

try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    import ltr559

from bme280 import BME280
from fonts.ttf import RobotoMedium as UserFont
from PIL import Image, ImageDraw, ImageFont
from pms5003 import PMS5003
from pms5003 import ReadTimeoutError as pmsReadTimeoutError
from pms5003 import SerialTimeoutError

from enviroplus import gas


logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)

logging.info(__doc__)

# BME280 temperature/pressure/humidity sensor
bme280 = BME280()

# PMS5003 particulate sensor
pms5003 = PMS5003()
time.sleep(1.0)

# Create ST7735 LCD display class
# Changed from dc="GPIO9", backlight="GPIO12" to dc=9, backlight=12 (BCM pins)
st7735 = st7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display
st7735.begin()

WIDTH = st7735.width
HEIGHT = st7735.height

# Set up canvas and font
img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
font_size_small = 10
font_size_large = 20
font = ImageFont.truetype(UserFont, font_size_large)
smallfont = ImageFont.truetype(UserFont, font_size_small)
x_offset = 2
y_offset = 2

message = ""

# The position of the top bar
top_pos = 25

# Create a values dict to store the data
variables = [
    "temperature",
    "pressure",
    "humidity",
    "light",
    "oxidised",
    "reduced",
    "nh3",
    "pm1",
    "pm25",
    "pm10"
]

units = [
    "C",
    "hPa",
    "%",
    "Lux",
    "kO",
    "kO",
    "kO",
    "ug/m3",
    "ug/m3",
    "ug/m3"
]

# Define your own warning limits
# The limits definition follows the order of the variables array.
# For example, temperature has [4, 18, 28, 35], meaning:
#  <= 4        => Dangerously Low
#  >4  to <=18 => Low
#  >18 to <=28 => Normal
#  >28 to <=35 => High
#  >35         => Dangerously High
limits = [
    [4, 18, 28, 35],        # temperature
    [250, 650, 1013.25, 1015],  # pressure
    [20, 30, 60, 70],       # humidity
    [-1, -1, 30000, 100000],  # light
    [-1, -1, 40, 50],       # oxidised
    [-1, -1, 450, 550],     # reduced
    [-1, -1, 200, 300],     # nh3
    [-1, -1, 50, 100],      # pm1
    [-1, -1, 50, 100],      # pm25
    [-1, -1, 50, 100]       # pm10
]

# RGB palette for values on the combined screen
palette = [
    (0, 0, 255),    # Dangerously Low
    (0, 255, 255),  # Low
    (0, 255, 0),    # Normal
    (255, 255, 0),  # High
    (255, 0, 0)     # Dangerously High
]

values = {}


def get_cpu_temperature():
    """
    Reads the CPU temperature from /sys/class/thermal/thermal_zone0/temp.
    Falls back to a default if not available.
    """
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_str = f.read().strip()
        return float(temp_str) / 1000.0
    except (FileNotFoundError, ValueError):
        logging.warning("Could not read /sys/class/thermal/thermal_zone0/temp")
        return 20.0  # a safe fallback


def display_text(variable, data, unit):
    """
    Displays data and text on the 0.96" LCD for a single variable.
    Shows a colored bar (0→blue to 1→red) and a small line graph of recent data.
    """
    # Maintain length of list
    values[variable] = values[variable][1:] + [data]

    # Scale the values for the variable between 0 and 1
    vmin = min(values[variable])
    vmax = max(values[variable])
    # Avoid division by zero if all values are the same
    spread = (vmax - vmin) + 1
    colours = [(v - vmin + 1) / spread for v in values[variable]]

    # Format the variable name and value
    msg = f"{variable[:4]}: {data:.1f} {unit}"
    logging.info(msg)

    # Clear the screen to white
    draw.rectangle((0, 0, WIDTH, HEIGHT), (255, 255, 255))

    for i, c in enumerate(colours):
        # Convert the values to colours from red (1.0) to blue (0.0)
        colour_scale = (1.0 - c) * 0.6
        r, g, b = [int(x * 255.0)
                   for x in colorsys.hsv_to_rgb(colour_scale, 1.0, 1.0)]

        # Draw a 1-pixel wide rectangle of colour
        draw.rectangle((i, top_pos, i + 1, HEIGHT), (r, g, b))

        # Draw a line graph in black
        line_y = HEIGHT - (top_pos + (c * (HEIGHT - top_pos))) + top_pos
        draw.rectangle((i, line_y, i + 1, line_y + 1), (0, 0, 0))

    # Write the text at the top in black
    draw.text((0, 0), msg, font=font, fill=(0, 0, 0))
    st7735.display(img)


def save_data(idx, data):
    """
    Saves the most recent reading into the list of values for the corresponding
    variable and logs it. Used when displaying everything on one screen.
    """
    variable = variables[idx]
    values[variable] = values[variable][1:] + [data]
    unit = units[idx]
    msg = f"{variable[:4]}: {data:.1f} {unit}"
    logging.info(msg)


def display_everything():
    """
    Splits the screen into multiple rows/columns so that each variable can be
    displayed simultaneously with color-coded text (based on defined limits).
    """
    draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
    column_count = 2
    row_count = len(variables) / column_count

    for i, variable in enumerate(variables):
        data_value = values[variable][-1]
        unit = units[i]

        # Calculate the row & column
        col_index = i // int(row_count)
        row_index = i % int(row_count)

        x = x_offset + ((WIDTH // column_count) * col_index)
        y = y_offset + int((HEIGHT / row_count) * row_index)
        msg = f"{variable[:4]}: {data_value:.1f} {unit}"

        # Determine the color of the text using the user-defined limits
        lim = limits[i]
        rgb = palette[0]
        for j, limit in enumerate(lim):
            if data_value > limit:
                rgb = palette[j + 1]

        draw.text((x, y), msg, font=smallfont, fill=rgb)

    st7735.display(img)


def main():
    """
    Main loop: cycles through single-variable modes (0–9) and a combined mode (10)
    that shows everything on one screen. Tap near the sensor to change modes.
    """
    # Tuning factor for compensation. Decrease to adjust temperature down,
    # increase to adjust up
    factor = 2.25

    cpu_temps = [get_cpu_temperature()] * 5

    delay = 0.5  # Debounce the proximity tap
    mode = 10    # The starting mode
    last_page = 0

    # Initialize the values dictionary
    for var in variables:
        values[var] = [1] * WIDTH

    try:
        while True:
            proximity = ltr559.get_proximity()

            # If the proximity crosses the threshold, toggle the mode
            if proximity > 1500 and time.time() - last_page > delay:
                mode = (mode + 1) % (len(variables) + 1)
                last_page = time.time()

            if mode == 0:
                # Temperature
                unit = "°C"
                cpu_temp = get_cpu_temperature()
                cpu_temps = cpu_temps[1:] + [cpu_temp]
                avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
                raw_temp = bme280.get_temperature()
                data = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
                display_text(variables[mode], data, unit)

            elif mode == 1:
                # Pressure
                unit = "hPa"
                data = bme280.get_pressure()
                display_text(variables[mode], data, unit)

            elif mode == 2:
                # Humidity
                unit = "%"
                data = bme280.get_humidity()
                display_text(variables[mode], data, unit)

            elif mode == 3:
                # Light
                unit = "Lux"
                data = ltr559.get_lux() if proximity < 10 else 1
                display_text(variables[mode], data, unit)

            elif mode == 4:
                # Oxidised
                unit = "kO"
                gas_data = gas.read_all()
                data = gas_data.oxidising / 1000
                display_text(variables[mode], data, unit)

            elif mode == 5:
                # Reduced
                unit = "kO"
                gas_data = gas.read_all()
                data = gas_data.reducing / 1000
                display_text(variables[mode], data, unit)

            elif mode == 6:
                # NH3
                unit = "kO"
                gas_data = gas.read_all()
                data = gas_data.nh3 / 1000
                display_text(variables[mode], data, unit)

            elif mode == 7:
                # PM1
                unit = "ug/m3"
                try:
                    pms_data = pms5003.read()
                    data = float(pms_data.pm_ug_per_m3(1.0))
                except (SerialTimeoutError, pmsReadTimeoutError):
                    logging.warning("Failed to read PMS5003")
                    data = 0
                display_text(variables[mode], data, unit)

            elif mode == 8:
                # PM2.5
                unit = "ug/m3"
                try:
                    pms_data = pms5003.read()
                    data = float(pms_data.pm_ug_per_m3(2.5))
                except (SerialTimeoutError, pmsReadTimeoutError):
                    logging.warning("Failed to read PMS5003")
                    data = 0
                display_text(variables[mode], data, unit)

            elif mode == 9:
                # PM10
                unit = "ug/m3"
                try:
                    pms_data = pms5003.read()
                    data = float(pms_data.pm_ug_per_m3(10))
                except (SerialTimeoutError, pmsReadTimeoutError):
                    logging.warning("Failed to read PMS5003")
                    data = 0
                display_text(variables[mode], data, unit)

            else:
                # Everything on one screen (mode == 10)
                cpu_temp = get_cpu_temperature()
                cpu_temps = cpu_temps[1:] + [cpu_temp]
                avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
                raw_temp = bme280.get_temperature()
                adjusted_temp = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
                save_data(0, adjusted_temp)

                raw_data = bme280.get_pressure()
                save_data(1, raw_data)

                raw_data = bme280.get_humidity()
                save_data(2, raw_data)

                lux_data = ltr559.get_lux() if proximity < 10 else 1
                save_data(3, lux_data)

                gas_data = gas.read_all()
                save_data(4, gas_data.oxidising / 1000)
                save_data(5, gas_data.reducing / 1000)
                save_data(6, gas_data.nh3 / 1000)

                try:
                    pms_data = pms5003.read()
                    save_data(7, float(pms_data.pm_ug_per_m3(1.0)))
                    save_data(8, float(pms_data.pm_ug_per_m3(2.5)))
                    save_data(9, float(pms_data.pm_ug_per_m3(10)))
                except (SerialTimeoutError, pmsReadTimeoutError):
                    logging.warning("Failed to read PMS5003")

                display_everything()
            
            time.sleep(5.0)

    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()