/*
 * Pixel Update Receiver for Seeed Studio Wio Terminal (ILI9341 320x240)
 * Receives per-pixel updates (x, y, RGB565) over TCP and applies them.
 */

#include <TFT_eSPI.h>         // Built-in Wio Terminal display library
#include <WiFiManager.h>      // Wio Terminal WiFi manager library (for network handling)

// Display dimensions (Note the dimensions of Wio Terminal's display)
#define DISPLAY_WIDTH 320
#define DISPLAY_HEIGHT 240

// TFT_eSPI instance
TFT_eSPI tft = TFT_eSPI();

// WiFi Credentials and Server Initialization
WiFiServer server(8090);  // dedicated port for pixel updates
WiFiClient client;

// Network settings (provide network credentials)
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Pixel update structure
struct PixelUpdate {
    uint8_t x;
    uint8_t y;
    uint16_t color;
};
PixelUpdate pixelUpdateBuffer;

// Stats
unsigned long frameCount = 0;
unsigned long lastStats = 0;
unsigned long updatesApplied = 0;

// Functions
void setupWiFi() {
    WiFi.begin(ssid, password);
    Serial.print("Connecting to WiFi...");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi connected");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setCursor(0, 120);
    tft.println(WiFi.localIP());
}

void setup() {
    Serial.begin(115200);
    Serial.println("=== Pixel Update Receiver for Seeed Studio Wio Terminal ===");
    tft.begin();
    tft.setRotation(0);  // Adjust rotation for portrait/landscape mode
    tft.fillScreen(TFT_BLACK);
    tft.setTextColor(TFT_WHITE, TFT_BLACK);
    tft.setCursor(0, 0);
    tft.println("Starting!");
    
    setupWiFi();
    server.begin();
    Serial.println("Server listening...");
}

bool readExactly(WiFiClient& c, uint8_t* dst, size_t len) {
    size_t received = 0;
    while (received < len && c.connected()) {
        int bytesRead = c.read(dst + received, len - received);
        if (bytesRead > 0) {
            received += bytesRead;
        } else {
            delay(1);
        }
    }
    return received == len;
}

void handleClient() {
    // Accept new client
    if (!client || !client.connected()) {
        client = server.available();
        if (client) {
            Serial.println("Client connected");
            frameCount = 0;
            updatesApplied = 0;
            tft.fillScreen(TFT_BLACK);
        }
    }
    
    // Skip if client isn't connected
    if (!client || !client.connected()) {
        return;
    }

    // Read and apply updates
    uint8_t entry[4];
    while (client.available()) {
        if (readExactly(client, entry, 4)) {
            pixelUpdateBuffer.x = entry[0];
            pixelUpdateBuffer.y = entry[1];
            pixelUpdateBuffer.color = entry[2] | (entry[3] << 8);
            
            // Apply pixel update
            if (pixelUpdateBuffer.x < DISPLAY_WIDTH && pixelUpdateBuffer.y < DISPLAY_HEIGHT) {
                tft.drawPixel(pixelUpdateBuffer.x, pixelUpdateBuffer.y, pixelUpdateBuffer.color);
                updatesApplied++;
            }
        } else {
            client.stop();
            break;
        }
    }
}

void loop() {
    handleClient();
    delay(1);
}