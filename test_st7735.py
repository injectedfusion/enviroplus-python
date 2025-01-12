import st7735

# Initialize the ST7735 display
st7735 = st7735.ST7735(
    port=0,
    cs=1,
    dc=9,  # BCM pin number
    backlight=12,  # BCM pin number
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize the display
try:
    st7735.begin()
    print("Display initialized successfully!")
except Exception as e:
    print(f"Failed to initialize display: {e}")