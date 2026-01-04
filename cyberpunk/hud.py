#!/usr/bin/env python3
"""
reTerminal Cyberpunk-style System HUD - Kiosk mode version
- Runs forever, cannot be closed by normal user input
- Designed to be started as systemd service at boot
"""

import os
import time
import psutil
import pygame
import math
import logging

# ================= CONFIGURATION =================
WIDTH, HEIGHT = 1280, 720           # reTerminal native resolution
FPS = 30

COLOR_BG = (3, 5, 12)
COLOR_NEON_CYAN = (0, 255, 255)
COLOR_NEON_MAGENTA = (255, 40, 255)
COLOR_GRID = (18, 35, 55)
COLOR_TEXT = (210, 245, 255)
COLOR_GLOW = (0, 120, 120)

# ================= LOGGING SETUP =================
# Changed: Added proper logging to file for debugging when running as service
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-8s %(message)s',
    filename='/var/log/reterminal-hud.log',
    filemode='a'
)
logger = logging.getLogger(__name__)

# ================= CYBER GAUGE CLASS =================
class CyberGauge:
    """Circular neon-style gauge with smooth animation"""
    def __init__(self, x, y, radius, label, unit="%", max_value=100):
        self.x = x
        self.y = y
        self.radius = radius
        self.label = label
        self.unit = unit
        self.max_value = max_value
        
        self.target_val = 0.0
        self.smooth_val = 0.0

    def update(self, value):
        """Set new target value (clamped)"""
        self.target_val = min(max(value, 0), self.max_value)

    def tick(self):
        """Smooth the value toward target (called every frame)"""
        # Changed: Slightly faster smoothing factor for more responsive feel
        self.smooth_val += (self.target_val - self.smooth_val) * 0.12

    def draw(self, surface):
        rect = pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius*2, self.radius*2)
        
        # Background arc (static 180° bottom)
        pygame.draw.arc(surface, COLOR_GRID, rect, math.pi, 0, 4)
        
        # Progress arc with neon glow
        progress = self.smooth_val / self.max_value
        end_angle = math.pi + progress * math.pi
        
        pygame.draw.arc(surface, COLOR_NEON_CYAN, rect, math.pi, end_angle, 8)
        pygame.draw.arc(surface, COLOR_GLOW, rect, math.pi, end_angle, 14)
        
        # Text rendering
        font_val = pygame.font.SysFont('dejavusansmono', 46, bold=True)
        font_unit = pygame.font.SysFont('dejavusansmono', 20)
        font_label = pygame.font.SysFont('dejavusansmono', 18)
        
        val_str = f"{int(round(self.smooth_val))}"
        val_surf = font_val.render(val_str, True, COLOR_TEXT)
        unit_surf = font_unit.render(self.unit, True, COLOR_NEON_MAGENTA)
        label_surf = font_label.render(self.label.upper(), True, COLOR_GRID)
        
        surface.blit(val_surf,   (self.x - val_surf.get_width()//2,   self.y - 38))
        surface.blit(unit_surf,  (self.x + self.radius - 15,          self.y - 12))
        surface.blit(label_surf, (self.x - label_surf.get_width()//2, self.y + self.radius//2 + 8))


def get_cpu_temp():
    """Read CPU temperature from reTerminal (Raspberry Pi CM4)"""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return float(f.read()) / 1000
    except Exception as e:
        logger.warning(f"Cannot read CPU temp: {e}")
        return 35.0


def main():
    # ================= VERY IMPORTANT FOR SYSTEMD/BOOT =================
    # Changed: Critical for correct display initialization on reTerminal when run as service
    os.environ['SDL_VIDEODRIVER'] = 'fbcon'
    os.environ['SDL_FBDEV'] = '/dev/fb1'          # reTerminal usually uses fb1 (try fb0 if it fails)
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    
    pygame.init()
    
    # Changed: Hide mouse cursor (essential for clean kiosk look on touchscreen)
    pygame.mouse.set_visible(False)
    
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF)
        logger.info("Display initialized successfully on reTerminal")
    except Exception as e:
        logger.error(f"CRITICAL: Display init failed: {e}")
        return 1

    pygame.display.set_caption("reTerminal SYSTEM HUD")
    clock = pygame.time.Clock()

    # Fonts prepared once
    font_header = pygame.font.SysFont('dejavusansmono', 28, bold=True)

    # Gauges layout - slightly adjusted positions for better balance
    gauges = [
        CyberGauge(240,  240, 125, "CPU",    "%"),
        CyberGauge(640,  240, 125, "MEMORY", "%"),
        CyberGauge(1040, 240, 125, "STORAGE","%"),
        CyberGauge(340,  520, 105, "TEMP",   "°C"),
        CyberGauge(940,  520, 105, "CLOCK",  "MHz"),
    ]

    frame_count = 0

    # ================= MAIN LOOP - KIOSK MODE =================
    # Changed: 
    #   - Removed 'running' flag → now infinite loop
    #   - No reaction to QUIT, KEYDOWN, MOUSEBUTTONDOWN etc.
    #   - Only pump events silently to prevent queue overflow
    while True:
        try:
            # Pump all events but ignore them completely
            # This is what makes the HUD "unclosable" by user
            for event in pygame.event.get():
                pass  # ← intentionally empty - no exit conditions!

            # Update system stats only every ~0.8 seconds
            if frame_count % 24 == 0:
                try:
                    cpu  = psutil.cpu_percent(interval=None)
                    ram  = psutil.virtual_memory().percent
                    disk = psutil.disk_usage('/').percent
                    temp = get_cpu_temp()
                    
                    # CPU frequency handling with fallback
                    try:
                        freq_raw = psutil.cpu_freq().current
                    except:
                        freq_raw = 1200.0
                    
                    gauges[0].update(cpu)
                    gauges[1].update(ram)
                    gauges[2].update(disk)
                    gauges[3].update(temp)
                    # Changed: Better scaling (most CM4 max around 1500-2000MHz)
                    gauges[4].update(freq_raw / 20.0)

                except Exception as e:
                    logger.warning(f"Stats collection error: {e}")

            # Smooth animation step for all gauges
            for g in gauges:
                g.tick()

            # ── DRAWING ───────────────────────────────────────────────
            screen.fill(COLOR_BG)

            # Light background grid
            for x in range(0, WIDTH, 80):
                pygame.draw.line(screen, COLOR_GRID, (x, 0), (x, HEIGHT), 1)
            for y in range(0, HEIGHT, 80):
                pygame.draw.line(screen, COLOR_GRID, (0, y), (WIDTH, y), 1)

            # Header
            header = font_header.render("RETERMINAL  •  SYSTEM MONITOR", True, COLOR_NEON_CYAN)
            screen.blit(header, (WIDTH//2 - header.get_width()//2, 18))

            # Draw all gauges
            for gauge in gauges:
                gauge.draw(screen)

            # Bottom-right real-time info
            if frame_count % 10 == 0:
                try:
                    real_freq = psutil.cpu_freq().current
                    freq_text = f"CPU {real_freq:>4.0f} MHz   •   {temp:>3.0f}°C"
                    txt = font_header.render(freq_text, True, COLOR_TEXT)
                    screen.blit(txt, (WIDTH - txt.get_width() - 30, HEIGHT - 50))
                except:
                    pass

            pygame.display.flip()
            clock.tick(FPS)
            frame_count += 1

        except Exception as e:
            logger.error(f"Main loop error (will continue): {e}", exc_info=True)
            time.sleep(1)  # prevent CPU spin if something is repeatedly failing

    # Code never reaches here normally
    pygame.quit()
    return 0


if __name__ == "__main__":
    try:
        exit(main())
    except KeyboardInterrupt:
        logger.info("Terminated by SIGINT (keyboard interrupt)")
    except Exception as e:
        logger.critical(f"Fatal unhandled error: {e}", exc_info=True)
        exit(1)