import os
import time
import psutil
import pygame
import math

# --- CONFIGURATION ---
WIDTH, HEIGHT = 1280, 720  # reTerminal native resolution
FPS = 30
COLOR_BG = (5, 5, 15)
COLOR_NEON_CYAN = (0, 255, 255)
COLOR_NEON_MAGENTA = (255, 0, 255)
COLOR_GRID = (20, 40, 60)
COLOR_TEXT = (200, 240, 255)

class CyberGauge:
    """A circular gauge with neon aesthetics."""
    def __init__(self, x, y, radius, label, unit="%"):
        self.x = x
        self.y = y
        self.radius = radius
        self.label = label
        self.unit = unit
        self.current_val = 0
        self.target_val = 0
        self.smooth_val = 0

    def update(self, value):
        self.target_val = value
        # Smooth interpolation for animation
        self.smooth_val += (self.target_val - self.smooth_val) * 0.1

    def draw(self, surface):
        # Draw base arc
        rect = pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)
        pygame.draw.arc(surface, COLOR_GRID, rect, math.pi, 0, 2)
        
        # Draw progress arc
        angle = math.pi + (self.smooth_val / 100.0) * math.pi
        pygame.draw.arc(surface, COLOR_NEON_CYAN, rect, math.pi, angle, 6)
        
        # Glow effect (simplified)
        pygame.draw.arc(surface, (0, 100, 100), rect, math.pi, angle, 2)

        # Labels
        font_large = pygame.font.SysFont('Monospace', 40, bold=True)
        font_small = pygame.font.SysFont('Monospace', 18)
        
        val_text = font_large.render(f"{int(self.smooth_val)}", True, COLOR_TEXT)
        unit_text = font_small.render(self.unit, True, COLOR_NEON_MAGENTA)
        label_text = font_small.render(self.label, True, COLOR_GRID)

        surface.blit(val_text, (self.x - val_text.get_width()//2, self.y - 30))
        surface.blit(unit_text, (self.x + 25, self.y - 10))
        surface.blit(label_text, (self.x - label_text.get_width()//2, self.y + 15))

def get_cpu_temp():
    """Reads reTerminal CPU temperature."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return float(f.read()) / 1000.0
    except:
        return 0.0

def main():
    # Force full screen on the built-in display
    # Note: reTerminal usually maps LCD to :0.0
    os.environ['SDL_VIDEO_CENTERED'] = '1'
    pygame.init()
    
    # Try to open in fullscreen. If testing on desktop, use pygame.RESIZABLE
    try:
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN | pygame.DOUBLEBUF | pygame.HWSURFACE)
    except:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        
    pygame.display.set_caption("reTerminal HUD")
    clock = pygame.time.Clock()
    font_main = pygame.font.SysFont('Monospace', 22)

    # Initialize Gauges
    gauges = [
        CyberGauge(250, 250, 120, "CPU LOAD"),
        CyberGauge(640, 250, 120, "RAM USAGE"),
        CyberGauge(1030, 250, 120, "DISK I/O"),
        CyberGauge(250, 520, 100, "TEMP", "°C"),
        CyberGauge(640, 520, 100, "CLOCK", "MHz"),
    ]

    running = True
    frame_count = 0

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                running = False

        # 1. Background and Grid
        screen.fill(COLOR_BG)
        for i in range(0, WIDTH, 40):
            pygame.draw.line(screen, (10, 20, 30), (i, 0), (i, HEIGHT))
        for i in range(0, HEIGHT, 40):
            pygame.draw.line(screen, (10, 20, 30), (0, i), (WIDTH, i))

        # 2. Update Stats (Throttle heavy calls)
        if frame_count % 15 == 0:
            cpu_p = psutil.cpu_percent()
            ram_p = psutil.virtual_memory().percent
            disk_p = psutil.disk_usage('/').percent
            temp = get_cpu_temp()
            freq = psutil.cpu_freq().current / 20.0 # Normalized to 0-100 gauge scale for 2GHz
            
            gauges[0].update(cpu_p)
            gauges[1].update(ram_p)
            gauges[2].update(disk_p)
            gauges[3].update(temp)
            gauges[4].update(freq)

        # 3. Draw UI Elements
        # Decorative border
        pygame.draw.rect(screen, COLOR_NEON_MAGENTA, (10, 10, WIDTH-20, HEIGHT-20), 1)
        pygame.draw.line(screen, COLOR_NEON_CYAN, (50, 60), (400, 60), 4)
        
        header = font_main.render("RE-TERMINAL // SYSTEM_OVERRIDE_ACTIVE", True, COLOR_NEON_CYAN)
        screen.blit(header, (60, 30))

        # 4. Draw Gauges
        for gauge in gauges:
            gauge.draw(screen)

        # 5. Scanline Effect (Cyberpunk aesthetic)
        if frame_count % 2 == 0:
            for y in range(0, HEIGHT, 4):
                pygame.draw.line(screen, (0, 0, 0, 50), (0, y), (WIDTH, y))

        # 6. Real-time Clock Speed text
        freq_raw = psutil.cpu_freq().current
        freq_txt = font_main.render(f"CORE_CLOCK: {freq_raw:.1f} MHz", True, COLOR_TEXT)
        screen.blit(freq_txt, (WIDTH - 350, 30))

        pygame.display.flip()
        clock.tick(FPS)
        frame_count += 1

    pygame.quit()

if __name__ == "__main__":
    main()