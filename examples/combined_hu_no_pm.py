#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
combined_hu_no_pms.py - Enviro plus script without PMS5003
Displays Hungarian text on the LCD, but code remains in English.

Press Ctrl+C to exit.
"""

import colorsys
import sys
import time
import logging

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

from enviroplus import gas


logging.basicConfig(
    format="%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)

logging.info(__doc__)

# BME280 sensor
bme280 = BME280()
time.sleep(1.0)

# Set up the ST7735 LCD
st7735 = st7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

st7735.begin()

WIDTH = st7735.width
HEIGHT = st7735.height

# Create canvas and fonts
img = Image.new("RGB", (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
font_size_small = 10
font_size_large = 20
font = ImageFont.truetype(UserFont, font_size_large)
smallfont = ImageFont.truetype(UserFont, font_size_small)

x_offset = 2
y_offset = 2
top_pos = 25

# Hungarian variable names for the LCD
variables = [
    "Hőmérséklet",    # Temperature
    "Légnyomás",      # Pressure
    "Páratartalom",   # Humidity
    "Fény",           # Light
    "Oxidált",        # Oxidised
    "Redukált",       # Reduced
    "NH3"             # NH3
]

# Hungarian units for the LCD
units = [
    "°C",
    "hPa",
    "%",
    "Lux",
    "kO",
    "kO",
    "kO"
]

# The sensor limits remain the same, though you can adjust them
limits = [
    [4, 18, 28, 35],        # Temperature
    [250, 650, 1013.25, 1015],  # Pressure
    [20, 30, 60, 70],       # Humidity
    [-1, -1, 30000, 100000], # Light
    [-1, -1, 40, 50],       # Oxidised
    [-1, -1, 450, 550],     # Reduced
    [-1, -1, 200, 300]      # NH3
]

# Color palette for categories (Danger Low, Low, Normal, High, Danger High)
palette = [
    (0, 0, 255),    # Dangerously Low
    (0, 255, 255),  # Low
    (0, 255, 0),    # Normal
    (255, 255, 0),  # High
    (255, 0, 0)     # Dangerously High
]

# Dictionary to track rolling data for each variable
values = {}


def get_cpu_temperature():
    """
    Reads the CPU temperature from /sys/class/thermal/thermal_zone0/temp.
    Returns a fallback if unavailable.
    """
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp_str = f.read().strip()
        return float(temp_str) / 1000.0
    except (FileNotFoundError, ValueError):
        logging.warning("Could not read /sys/class/thermal/thermal_zone0/temp")
        return 20.0  # fallback


def display_text(variable, data, unit):
    """
    Displays data for a single variable on the LCD in Hungarian.
    """
    # Keep the last data points in a rolling list
    values[variable] = values[variable][1:] + [data]

    vmin = min(values[variable])
    vmax = max(values[variable])
    spread = (vmax - vmin) + 1
    data_scaled = [(v - vmin + 1) / spread for v in values[variable]]

    # Log info in English
    message_eng = f"Var: {variable} => {data:.1f} {unit}"
    logging.info(message_eng)

    # Hungarian label on the display
    message_hu = f"{variable[:4]}: {data:.1f} {unit}"

    # Clear the screen to white
    draw.rectangle((0, 0, WIDTH, HEIGHT), (255, 255, 255))

    for i, c in enumerate(data_scaled):
        color_scale = (1.0 - c) * 0.6
        r, g, b = [int(x * 255.0) for x in colorsys.hsv_to_rgb(color_scale, 1.0, 1.0)]
        draw.rectangle((i, top_pos, i + 1, HEIGHT), (r, g, b))
        line_y = HEIGHT - (top_pos + (c * (HEIGHT - top_pos))) + top_pos
        draw.rectangle((i, line_y, i + 1, line_y + 1), (0, 0, 0))

    draw.text((0, 0), message_hu, font=font, fill=(0, 0, 0))
    st7735.display(img)


def save_data(idx, data):
    """
    Saves/updates the rolling data list for the variable at index idx.
    Logs it in English, but display text is Hungarian.
    """
    variable = variables[idx]
    values[variable] = values[variable][1:] + [data]

    unit = units[idx]
    message_eng = f"Var: {variable} => {data:.1f} {unit}"
    logging.info(message_eng)


def display_everything():
    """
    Displays all variables on one screen in Hungarian.
    Colors text based on defined warning limits (English logic, Hungarian labels).
    """
    draw.rectangle((0, 0, WIDTH, HEIGHT), (0, 0, 0))
    column_count = 2
    row_count = len(variables) / column_count

    for i, variable in enumerate(variables):
        data_value = values[variable][-1]
        unit = units[i]

        col_idx = i // int(row_count)
        row_idx = i % int(row_count)

        x = x_offset + ((WIDTH // column_count) * col_idx)
        y = y_offset + int((HEIGHT / row_count) * row_idx)

        # Truncate the Hungarian label to 4 chars plus value
        msg_hu = f"{variable[:4]}: {data_value:.1f} {unit}"

        # Determine color from the “limits” array
        lim = limits[i]
        rgb = palette[0]
        for j, threshold in enumerate(lim):
            if data_value > threshold:
                rgb = palette[j + 1]

        draw.text((x, y), msg_hu, font=smallfont, fill=rgb)

    st7735.display(img)


def main():
    # Temperature compensation factor
    factor = 2.25
    cpu_temps = [get_cpu_temperature()] * 5

    # Start in "combined" mode at index 7 (if we have 7 variables => indices 0..6 => mode=7 for "all")
    mode = 7
    last_page = time.time()
    proximity_delay = 0.5

    # Initialize rolling data
    for var in variables:
        values[var] = [1] * WIDTH

    try:
        while True:
            proximity = ltr559.get_proximity()

            # If proximity is high (tap), cycle mode
            if proximity > 1500 and (time.time() - last_page) > proximity_delay:
                mode = (mode + 1) % (len(variables) + 1)
                last_page = time.time()

            if mode == 0:  # Temperature
                unit = "°C"
                cpu_temp = get_cpu_temperature()
                cpu_temps = cpu_temps[1:] + [cpu_temp]
                avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
                bme_temp = bme280.get_temperature()
                adjusted_temp = bme_temp - ((avg_cpu_temp - bme_temp) / factor)
                display_text(variables[mode], adjusted_temp, unit)

            elif mode == 1:  # Pressure
                unit = "hPa"
                pressure = bme280.get_pressure()
                display_text(variables[mode], pressure, unit)

            elif mode == 2:  # Humidity
                unit = "%"
                humidity = bme280.get_humidity()
                display_text(variables[mode], humidity, unit)

            elif mode == 3:  # Light
                unit = "Lux"
                light = ltr559.get_lux() if proximity < 10 else 1
                display_text(variables[mode], light, unit)

            elif mode == 4:  # Oxidised
                unit = "kO"
                g_data = gas.read_all()
                oxid = g_data.oxidising / 1000
                display_text(variables[mode], oxid, unit)

            elif mode == 5:  # Reduced
                unit = "kO"
                g_data = gas.read_all()
                reduc = g_data.reducing / 1000
                display_text(variables[mode], reduc, unit)

            elif mode == 6:  # NH3
                unit = "kO"
                g_data = gas.read_all()
                nh3_val = g_data.nh3 / 1000
                display_text(variables[mode], nh3_val, unit)

            else:
                # Combined mode: update everything and display on one screen
                cpu_temp = get_cpu_temperature()
                cpu_temps = cpu_temps[1:] + [cpu_temp]
                avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
                bme_temp = bme280.get_temperature()
                adjusted_temp = bme_temp - ((avg_cpu_temp - bme_temp) / factor)
                save_data(0, adjusted_temp)

                pressure = bme280.get_pressure()
                save_data(1, pressure)

                humidity = bme280.get_humidity()
                save_data(2, humidity)

                light = ltr559.get_lux() if proximity < 10 else 1
                save_data(3, light)

                g_data = gas.read_all()
                save_data(4, g_data.oxidising / 1000)
                save_data(5, g_data.reducing / 1000)
                save_data(6, g_data.nh3 / 1000)

                display_everything()

            # ADD A SHORT DELAY to slow down refresh rate
            time.sleep(5.0)

    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()