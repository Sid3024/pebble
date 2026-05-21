/**
 * @file main.cpp
 * @brief PlatformIO firmware for the Seeed Studio XIAO ESP32-S3 Plus and Expansion Base.
 * 
 * Part of the Maker Start Kit, this firmware provides a comprehensive board bring-up 
 * and diagnostic suite, followed by a functional clock and weather display application.
 * 
 * Features:
 * - Boot-time mode selection (hold USER button for Diagnostics).
 * - WiFiManager for captive portal network setup.
 * - NTP time synchronization and PCF8563 RTC support.
 * - Open-Meteo API integration for Singapore weather data.
 * - Dual OLED clock faces (Digital/Analog) and diagnostic frames.
 * - I2C bus scanner and peripheral health checks.
 * 
 * @copyright © 2026 SL2 - Sustainable Living Lab
 * @license MIT
 */

#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <math.h>
#include <time.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <WiFi.h>
#include <WiFiManager.h>

/* --- Feature Toggles --- */
#define ENABLE_BOARD_TEST 1              // Master switch for board test logic
#define ENABLE_SERIAL_OUTPUT 1           // Enable logging to Serial Monitor
#define ENABLE_HEARTBEAT_LED 1           // Blink built-in LED to show activity
#define ENABLE_STATUS_MESSAGES 1         // Periodic system status in Serial
#define ENABLE_I2C_SCANNER 1             // Scan I2C bus for devices
#define ENABLE_EXPECTED_I2C_CHECKS 1     // Explicitly check for OLED and RTC
#define ENABLE_OLED_TEST 1               // Enable OLED display routines
#define ENABLE_OLED_MONITOR_DIAGNOSTICS 1 // Log OLED status to Serial
#define ENABLE_OLED_PICTURE_TEST 1       // Show geometric test patterns on OLED
#define ENABLE_BUZZER_TEST 1             // Play test tones on the buzzer
#define ENABLE_WIFI_MANAGER 1            // Enable WiFiManager captive portal
#define ENABLE_NTP_SYNC 1                // Sync system time with NTP servers
#define ENABLE_RTC_CLOCK 1               // Interface with PCF8563 hardware RTC
#define ENABLE_WEATHER_FETCH 1           // Fetch weather data from Open-Meteo

/* --- Timing & Intervals --- */
#define SERIAL_BAUD_RATE 115200
#define HEARTBEAT_INTERVAL_MS 250        // LED toggle speed
#define STATUS_INTERVAL_MS 1000          // Serial status report frequency
#define I2C_SCAN_INTERVAL_MS 5000         // Frequency of I2C bus scans in Test Mode
#define OLED_FRAME_INTERVAL_MS 1500      // Pattern rotation speed in Test Mode
#define CLOCK_DISPLAY_INTERVAL_MS 1000   // Clock UI refresh rate
#define WEATHER_RETRY_INTERVAL_MS 60000  // Wait before retrying failed weather fetch
#define WEATHER_UPDATE_INTERVAL_MS 900000 // Update weather every 15 minutes (900s)
#define BUZZER_SEQUENCE_INTERVAL_MS 6000 // Wait between buzzer test cycles
#define BOOT_BUTTON_SAMPLE_DELAY_MS 30   // Debounce delay for boot mode detection
#define WELCOME_SCREEN_HOLD_MS 5000      // How long to show welcome screen in Normal Mode
#define NTP_SYNC_TIMEOUT_MS 15000        // Max time to wait for NTP response
#define NTP_GMT_OFFSET_SECONDS 28800     // UTC+8 (Singapore)
#define NTP_DAYLIGHT_OFFSET_SECONDS 0

/* --- Hardware Configuration --- */
#define EXPECTED_OLED_ADDRESS 0x3C       // Standard SSD1306 address
#define EXPECTED_RTC_ADDRESS 0x51        // PCF8563 RTC address
#define BUZZER_TEST_PIN A3               // Expansion Base passive buzzer pin
#define USER_BUTTON_PIN 2                // Expansion Base User Button (D1 -> GPIO 2)

namespace {

/* --- Global Peripherals --- */
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);
WiFiManager wifiManager;

/* --- System State Variables --- */
unsigned long lastHeartbeatAt = 0;
unsigned long lastStatusAt = 0;
unsigned long lastI2cScanAt = 0;
unsigned long lastOledFrameAt = 0;
unsigned long lastBuzzerEventAt = 0;
unsigned long nextBuzzerChangeAt = 0;
unsigned long normalModeStartedAt = 0;
unsigned long lastClockDisplayAt = 0;
unsigned long lastWeatherFetchAt = 0;
unsigned long lastWeatherFetchAttemptAt = 0;

bool heartbeatLedState = false;
bool oledDetected = false;
bool oledDetectedAt3C = false;
bool oledInitialized = false;
bool oledTextWritten = false;
bool rtcDetected = false;
bool buzzerSequenceActive = false;
bool testModeEnabled = false;
bool wifiManagerStarted = false;
bool wifiManagerPortalActive = false;
bool wifiConnected = false;
bool ntpSyncAttempted = false;
bool ntpSyncComplete = false;
bool rtcTimeValid = false;
bool analogClockVisible = false;
bool userButtonPressed = false;
bool weatherDataValid = false;

uint8_t i2cDeviceCount = 0;
uint8_t oledFrameIndex = 0;
uint8_t buzzerStepIndex = 0;

/* --- Identity and Network Constants --- */
char wifiManagerApName[32] = "UTC2738";
char wifiManagerHostName[32] = "utc2738";

constexpr char kNtpServerPrimary[] = "pool.ntp.org";
constexpr char kNtpServerSecondary[] = "time.nist.gov";
constexpr char kSingaporeWeatherUrl[] =
    "https://api.open-meteo.com/v1/forecast?latitude=1.3521&longitude=103.8198&current=temperature_2m,relative_humidity_2m,weather_code&timezone=Asia%2FSingapore";
constexpr uint8_t kPcf8563TimeRegister = 0x02;

/* --- Weather Data Structures --- */
enum class WeatherIconKind : uint8_t {
    unknown,
    sunny,
    cloudy,
    rainy,
    stormy,
};

float singaporeTemperatureC = 0.0f;
int singaporeHumidityPercent = 0;
WeatherIconKind singaporeWeatherIcon = WeatherIconKind::unknown;
char singaporeWeatherOutlook[16] = "weather";

/* --- Buzzer Patterns --- */
constexpr uint16_t buzzerPatternFrequencies[] = {
    523, 0, 659, 0, 784, 0, 1047, 0, 784, 0, 659, 0, 523, 0 // C5, E5, G5, C6...
};
constexpr uint16_t buzzerPatternDurations[] = {
    140, 60, 140, 60, 140, 60, 220, 100, 140, 60, 140, 60, 220, 400
};
constexpr size_t buzzerPatternLength =
    sizeof(buzzerPatternFrequencies) / sizeof(buzzerPatternFrequencies[0]);

/* --- Serial Logging Helpers --- */

void printBoxTop() {
    Serial.println("+--------------------------------------------------+");
}

void printBoxBottom() {
    Serial.println("+--------------------------------------------------+");
}

void printBoxLine(const char* text) {
    Serial.print("| ");
    Serial.print(text);
    size_t length = strlen(text);
    for (size_t index = length; index < 48; ++index) {
        Serial.print(' ');
    }
    Serial.println("|");
}

/* --- I2C and RTC Helpers --- */

bool probeI2cAddress(uint8_t address) {
    Wire.beginTransmission(address);
    return Wire.endTransmission() == 0;
}

void formatI2cAddress(uint8_t address, char* buffer, size_t bufferSize) {
    snprintf(buffer, bufferSize, "0x%02X", address);
}

void formatIpAddress(const IPAddress& ip, char* buffer, size_t bufferSize) {
    snprintf(buffer, bufferSize, "%u.%u.%u.%u", ip[0], ip[1], ip[2], ip[3]);
}

uint8_t decimalToBcd(uint8_t value) {
    return static_cast<uint8_t>(((value / 10) << 4) | (value % 10));
}

uint8_t bcdToDecimal(uint8_t value) {
    return static_cast<uint8_t>(((value >> 4) * 10) + (value & 0x0F));
}

/* --- Time and Weather Formatting --- */

void formatClockTime(const tm& timeInfo, char* buffer, size_t bufferSize) {
    snprintf(buffer, bufferSize, "%02d:%02d:%02d", timeInfo.tm_hour, timeInfo.tm_min, timeInfo.tm_sec);
}

void formatClockDate(const tm& timeInfo, char* buffer, size_t bufferSize) {
    snprintf(buffer, bufferSize, "%04d-%02d-%02d", timeInfo.tm_year + 1900, timeInfo.tm_mon + 1, timeInfo.tm_mday);
}

void formatWeatherSummary(char* buffer, size_t bufferSize) {
    if (!weatherDataValid) {
        snprintf(buffer, bufferSize, "weather loading");
        return;
    }
    snprintf(buffer, bufferSize, "%.1fC %d%%", static_cast<double>(singaporeTemperatureC), singaporeHumidityPercent);
}

void setWeatherOutlook(const char* outlook, WeatherIconKind iconKind) {
    snprintf(singaporeWeatherOutlook, sizeof(singaporeWeatherOutlook), "%s", outlook);
    singaporeWeatherIcon = iconKind;
}

/**
 * @brief Map WMO weather codes to internal outlook strings and icons.
 * Reference: https://open-meteo.com/en/docs
 */
void applyWeatherCode(int weatherCode) {
    switch (weatherCode) {
    case 0:
        setWeatherOutlook("sunny", WeatherIconKind::sunny);
        break;
    case 1: case 2: case 3: case 45: case 48:
        setWeatherOutlook("cloudy", WeatherIconKind::cloudy);
        break;
    case 51: case 53: case 55: case 56: case 57:
    case 61: case 63: case 65: case 66: case 67:
    case 80: case 81: case 82:
        setWeatherOutlook("raining", WeatherIconKind::rainy);
        break;
    case 95: case 96: case 99:
        setWeatherOutlook("storm", WeatherIconKind::stormy);
        break;
    default:
        setWeatherOutlook("mixed", WeatherIconKind::cloudy);
        break;
    }
}

/* --- RTC Hardware Access --- */

bool readRtcRegisters(uint8_t startRegister, uint8_t* buffer, size_t length) {
    Wire.beginTransmission(EXPECTED_RTC_ADDRESS);
    Wire.write(startRegister);
    if (Wire.endTransmission(false) != 0) return false;

    const size_t received = Wire.requestFrom(static_cast<int>(EXPECTED_RTC_ADDRESS), static_cast<int>(length));
    if (received != length) return false;

    for (size_t index = 0; index < length; ++index) {
        buffer[index] = Wire.read();
    }
    return true;
}

bool writeRtcRegisters(uint8_t startRegister, const uint8_t* buffer, size_t length) {
    Wire.beginTransmission(EXPECTED_RTC_ADDRESS);
    Wire.write(startRegister);
    for (size_t index = 0; index < length; ++index) {
        Wire.write(buffer[index]);
    }
    return Wire.endTransmission() == 0;
}

/**
 * @brief Read current time from PCF8563 RTC.
 */
bool readRtcTime(tm* timeInfo) {
#if ENABLE_RTC_CLOCK
    if (timeInfo == nullptr || !probeI2cAddress(EXPECTED_RTC_ADDRESS)) return false;

    uint8_t registers[7] = { 0 };
    if (!readRtcRegisters(kPcf8563TimeRegister, registers, sizeof(registers))) return false;

    if ((registers[0] & 0x80) != 0) return false; // VL bit set: clock integrity not guaranteed

    timeInfo->tm_sec = bcdToDecimal(registers[0] & 0x7F);
    timeInfo->tm_min = bcdToDecimal(registers[1] & 0x7F);
    timeInfo->tm_hour = bcdToDecimal(registers[2] & 0x3F);
    timeInfo->tm_mday = bcdToDecimal(registers[3] & 0x3F);
    timeInfo->tm_wday = bcdToDecimal(registers[4] & 0x07);
    timeInfo->tm_mon = bcdToDecimal(registers[5] & 0x1F) - 1;
    timeInfo->tm_year = 100 + bcdToDecimal(registers[6]);
    timeInfo->tm_isdst = 0;

    return mktime(timeInfo) != static_cast<time_t>(-1);
#else
    (void)timeInfo;
    return false;
#endif
}

/**
 * @brief Update PCF8563 RTC with provided time.
 */
bool writeRtcTime(const tm& timeInfo) {
#if ENABLE_RTC_CLOCK
    if (!probeI2cAddress(EXPECTED_RTC_ADDRESS)) return false;

    const int year = timeInfo.tm_year + 1900;
    if (year < 2000 || year > 2099) return false;

    const uint8_t registers[7] = {
        decimalToBcd(static_cast<uint8_t>(timeInfo.tm_sec)),
        decimalToBcd(static_cast<uint8_t>(timeInfo.tm_min)),
        decimalToBcd(static_cast<uint8_t>(timeInfo.tm_hour)),
        decimalToBcd(static_cast<uint8_t>(timeInfo.tm_mday)),
        decimalToBcd(static_cast<uint8_t>(timeInfo.tm_wday)),
        decimalToBcd(static_cast<uint8_t>(timeInfo.tm_mon + 1)),
        decimalToBcd(static_cast<uint8_t>(year - 2000)),
    };

    return writeRtcRegisters(kPcf8563TimeRegister, registers, sizeof(registers));
#else
    (void)timeInfo;
    return false;
#endif
}

/* --- OLED UI Primitives --- */

void drawCenteredText(int y, const char* text, const uint8_t* font) {
    oled.setFont(font);
    const int width = oled.getStrWidth(text);
    const int x = (128 - width) / 2;
    oled.drawStr(x < 0 ? 0 : x, y, text);
}

void drawTextCenteredAtX(int centerX, int y, const char* text, const uint8_t* font) {
    oled.setFont(font);
    const int width = oled.getStrWidth(text);
    const int x = centerX - (width / 2);
    oled.drawStr(x < 0 ? 0 : x, y, text);
}

void drawPageFooter(const char* label) {
    oled.drawHLine(0, 54, 128);
    drawCenteredText(63, label, u8g2_font_5x8_tf);
}

/* --- Initialization Routines --- */

/**
 * @brief Build unique host and AP names using the ESP32 MAC address suffix.
 */
void buildWifiManagerNames() {
    const uint64_t chipId = ESP.getEfuseMac();
    const uint32_t chipSuffix = static_cast<uint32_t>(chipId & 0xFFFFFF);
    snprintf(wifiManagerApName, sizeof(wifiManagerApName), "UTC2738-%06lX", static_cast<unsigned long>(chipSuffix));
    snprintf(wifiManagerHostName, sizeof(wifiManagerHostName), "utc2738-%06lx", static_cast<unsigned long>(chipSuffix));
}

void renderOledMessageFrame(const char* line1, const char* line2, const char* line3, const char* line4, const char* line5) {
    if (!oledInitialized) return;
    oled.clearBuffer();
    oled.drawFrame(0, 0, 128, 64);
    drawCenteredText(10, line1, u8g2_font_6x10_tf);
    drawCenteredText(24, line2, u8g2_font_7x14_tf);
    drawCenteredText(40, line3, u8g2_font_5x8_tf);
    drawCenteredText(48, line4, u8g2_font_5x8_tf);
    drawCenteredText(56, line5, u8g2_font_5x8_tf);
    oled.sendBuffer();
}

void initializeUserButton() {
    pinMode(USER_BUTTON_PIN, INPUT_PULLUP);
}

/**
 * @brief Check if the user is holding the button during startup to enter Test Mode.
 */
bool detectTestModeRequest() {
    delay(BOOT_BUTTON_SAMPLE_DELAY_MS);
    return digitalRead(USER_BUTTON_PIN) == LOW;
}

void initializeLed() {
#if ENABLE_HEARTBEAT_LED && defined(LED_BUILTIN)
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);
#endif
}

void initializeSerial() {
#if ENABLE_SERIAL_OUTPUT
    Serial.begin(SERIAL_BAUD_RATE);
    delay(250);
    Serial.println();
    printBoxTop();
    printBoxLine("UTC_2738_STEER board test starting");
    printBoxLine("Target: Seeed Studio XIAO ESP32-S3 Plus");
    printBoxLine("Mode: Maker Start Kit board bring-up");
    printBoxBottom();
#endif
}

void initializeI2c() {
#if ENABLE_I2C_SCANNER || ENABLE_OLED_TEST || ENABLE_RTC_CLOCK
    Wire.begin();
#endif
}

void initializeBuzzerTest() {
#if ENABLE_BUZZER_TEST
    pinMode(BUZZER_TEST_PIN, OUTPUT);
    noTone(BUZZER_TEST_PIN);
#endif
}

/* --- Normal Mode UI Rendering --- */

void renderOledStandbyFrame() {
    renderOledMessageFrame("Welcome to", "UTC2738", "Hold user button", "during boot for", "test mode");
}

void renderOledWifiManagerFrame(const char* line3, const char* line4, const char* line5) {
    renderOledMessageFrame("Welcome to", "UTC2738", line3, line4, line5);
}

/**
 * @brief Standard Digital Clock View.
 */
void renderOledClockFrame(const tm& timeInfo) {
    if (!oledInitialized) return;

    char timeLine[16], dateLine[16], ipLine[20], weatherLine[24];
    formatClockTime(timeInfo, timeLine, sizeof(timeLine));
    formatClockDate(timeInfo, dateLine, sizeof(dateLine));
    formatIpAddress(WiFi.localIP(), ipLine, sizeof(ipLine));
    formatWeatherSummary(weatherLine, sizeof(weatherLine));

    oled.clearBuffer();
    oled.drawFrame(0, 0, 128, 64);
    drawCenteredText(10, "UTC2738 clock", u8g2_font_6x10_tf);
    drawCenteredText(28, timeLine, u8g2_font_7x14_tf);
    drawCenteredText(weatherDataValid ? 40 : 46, dateLine, u8g2_font_6x10_tf);
    drawCenteredText(weatherDataValid ? 49 : 58, ipLine, u8g2_font_5x8_tf);
    if (weatherDataValid) {
        drawCenteredText(57, singaporeWeatherOutlook, u8g2_font_5x8_tf);
        drawCenteredText(60, weatherLine, u8g2_font_5x8_tf);
    }
    oled.sendBuffer();
}

/* --- Analog Clock Drawing --- */

void drawClockHand(int centerX, int centerY, int length, float angleRadians) {
    const int x = centerX + static_cast<int>(sinf(angleRadians) * length);
    const int y = centerY - static_cast<int>(cosf(angleRadians) * length);
    oled.drawLine(centerX, centerY, x, y);
}

void drawWeatherIconSun(int centerX, int centerY) {
    oled.drawCircle(centerX, centerY, 5);
    for (int i = 0; i < 8; i++) {
        float angle = i * M_PI / 4.0;
        oled.drawLine(centerX + sin(angle) * 7, centerY + cos(angle) * 7, centerX + sin(angle) * 9, centerY + cos(angle) * 9);
    }
}

void drawWeatherIconCloud(int centerX, int centerY) {
    oled.drawDisc(centerX - 5, centerY, 4);
    oled.drawDisc(centerX + 1, centerY - 2, 5);
    oled.drawDisc(centerX + 7, centerY, 4);
    oled.drawBox(centerX - 9, centerY, 18, 5);
}

void drawWeatherIconRain(int centerX, int centerY) {
    drawWeatherIconCloud(centerX, centerY - 2);
    oled.drawLine(centerX - 5, centerY + 6, centerX - 7, centerY + 10);
    oled.drawLine(centerX, centerY + 6, centerX - 2, centerY + 10);
    oled.drawLine(centerX + 5, centerY + 6, centerX + 3, centerY + 10);
}

void drawWeatherIconStorm(int centerX, int centerY) {
    drawWeatherIconCloud(centerX, centerY - 2);
    oled.drawLine(centerX - 1, centerY + 4, centerX + 3, centerY + 4);
    oled.drawLine(centerX + 3, centerY + 4, centerX, centerY + 10);
    oled.drawLine(centerX, centerY + 10, centerX + 4, centerY + 10);
}

void drawWeatherIcon(int centerX, int centerY, WeatherIconKind iconKind) {
    switch (iconKind) {
    case WeatherIconKind::sunny: drawWeatherIconSun(centerX, centerY); break;
    case WeatherIconKind::cloudy: drawWeatherIconCloud(centerX, centerY); break;
    case WeatherIconKind::rainy: drawWeatherIconRain(centerX, centerY); break;
    case WeatherIconKind::stormy: drawWeatherIconStorm(centerX, centerY); break;
    default: oled.drawFrame(centerX - 9, centerY - 8, 18, 16); break;
    }
}

/**
 * @brief Functional Analog Clock View with weather on the side.
 */
void renderOledAnalogClockFrame(const tm& timeInfo) {
    if (!oledInitialized) return;

    constexpr int centerX = 41, centerY = 28, radius = 22;
    char dateLine[16], weatherLine[24];
    formatClockDate(timeInfo, dateLine, sizeof(dateLine));
    formatWeatherSummary(weatherLine, sizeof(weatherLine));

    oled.clearBuffer();
    oled.drawFrame(0, 0, 128, 64);
    oled.drawCircle(centerX, centerY, radius);
    if (weatherDataValid) drawWeatherIcon(103, 16, singaporeWeatherIcon);

    for (uint8_t marker = 0; marker < 12; ++marker) {
        float angle = (marker / 12.0f) * 2.0f * M_PI;
        oled.drawLine(centerX + sinf(angle) * (radius - 3), centerY - cosf(angle) * (radius - 3), centerX + sinf(angle) * radius, centerY - cosf(angle) * radius);
    }

    float secondAngle = (timeInfo.tm_sec / 60.0f) * 2.0f * M_PI;
    float minuteAngle = ((timeInfo.tm_min + timeInfo.tm_sec / 60.0f) / 60.0f) * 2.0f * M_PI;
    float hourAngle = ((timeInfo.tm_hour % 12 + timeInfo.tm_min / 60.0f) / 12.0f) * 2.0f * M_PI;

    drawClockHand(centerX, centerY, 11, hourAngle);
    drawClockHand(centerX, centerY, 16, minuteAngle);
    drawClockHand(centerX, centerY, 20, secondAngle);
    oled.drawDisc(centerX, centerY, 2);

    drawTextCenteredAtX(centerX, 58, dateLine, u8g2_font_5x8_tf);
    if (weatherDataValid) {
        oled.setFont(u8g2_font_5x8_tf);
        oled.drawStr(84, 34, singaporeWeatherOutlook);
        oled.drawStr(84, 44, weatherLine);
    }
    oled.sendBuffer();
}

void initializeOledStandby() {
    oledDetected = probeI2cAddress(EXPECTED_OLED_ADDRESS);
    if (!oledDetected) return;
    oled.begin();
    oled.setFlipMode(1);
    oledInitialized = true;
    renderOledStandbyFrame();
}

/* --- Status Printing --- */

void printWifiAddress() {
#if ENABLE_SERIAL_OUTPUT && ENABLE_WIFI_MANAGER
    if (!wifiConnected) return;
    char ipAddress[20], ipLine[49];
    formatIpAddress(WiFi.localIP(), ipAddress, sizeof(ipAddress));
    snprintf(ipLine, sizeof(ipLine), "WiFi connected %s", ipAddress);
    printBoxTop(); printBoxLine(ipLine); printBoxBottom();
#endif
}

void printClockStatus(const tm& timeInfo, bool rtcWriteSucceeded) {
#if ENABLE_SERIAL_OUTPUT
    char dateText[16], timeText[16], timeLine[49], statusLine[49];
    formatClockDate(timeInfo, dateText, sizeof(dateText));
    formatClockTime(timeInfo, timeText, sizeof(timeText));
    snprintf(timeLine, sizeof(timeLine), "NTP time %s %s UTC", dateText, timeText);
    snprintf(statusLine, sizeof(statusLine), "RTC set %s", rtcWriteSucceeded ? "PASS" : "FAIL");
    printBoxTop(); printBoxLine("clock_sync status"); printBoxLine(timeLine); printBoxLine(statusLine); printBoxBottom();
#endif
}

void printClockMode() {
#if ENABLE_SERIAL_OUTPUT
    printBoxTop(); printBoxLine(analogClockVisible ? "Clock mode: ANALOG" : "Clock mode: DIGITAL"); printBoxBottom();
#endif
}

/* --- Weather Fetching --- */

bool fetchSingaporeWeather() {
#if ENABLE_WEATHER_FETCH
    HTTPClient http;
    if (!http.begin(kSingaporeWeatherUrl)) return false;
    int httpStatus = http.GET();
    if (httpStatus != HTTP_CODE_OK) { http.end(); return false; }

    DynamicJsonDocument doc(1536);
    deserializeJson(doc, http.getStream());
    http.end();

    JsonVariant current = doc["current"];
    if (current.isNull()) return false;

    singaporeTemperatureC = current["temperature_2m"] | singaporeTemperatureC;
    singaporeHumidityPercent = current["relative_humidity_2m"] | singaporeHumidityPercent;
    applyWeatherCode(current["weather_code"] | -1);
    weatherDataValid = true;
    return true;
#else
    return false;
#endif
}

void updateWeatherData(unsigned long now) {
#if ENABLE_WEATHER_FETCH
    if (!wifiConnected) return;
    if (weatherDataValid && now - lastWeatherFetchAt < WEATHER_UPDATE_INTERVAL_MS) return;
    if (!weatherDataValid && lastWeatherFetchAttemptAt != 0 && now - lastWeatherFetchAttemptAt < WEATHER_RETRY_INTERVAL_MS) return;

    lastWeatherFetchAttemptAt = now;
    if (fetchSingaporeWeather()) lastWeatherFetchAt = now;
#endif
}

/* --- Time Management --- */

bool syncClockFromNtpAndRtc() {
#if ENABLE_NTP_SYNC
    if (ntpSyncAttempted) return ntpSyncComplete;
    ntpSyncAttempted = true;
    configTime(NTP_GMT_OFFSET_SECONDS, NTP_DAYLIGHT_OFFSET_SECONDS, kNtpServerPrimary, kNtpServerSecondary);

    tm timeInfo = {};
    unsigned long startedAt = millis();
    while (millis() - startedAt < NTP_SYNC_TIMEOUT_MS) {
        if (getLocalTime(&timeInfo, 250)) {
            bool rtcWriteSucceeded = writeRtcTime(timeInfo);
            rtcDetected = probeI2cAddress(EXPECTED_RTC_ADDRESS);
            rtcTimeValid = rtcWriteSucceeded || readRtcTime(&timeInfo);
            ntpSyncComplete = true;
            printClockStatus(timeInfo, rtcWriteSucceeded);
            renderOledClockFrame(timeInfo);
            return true;
        }
    }
    rtcTimeValid = readRtcTime(&timeInfo);
    if (rtcTimeValid) renderOledClockFrame(timeInfo);
    return false;
#else
    return false;
#endif
}

bool getClockTime(tm* timeInfo) {
    if (timeInfo == nullptr) return false;
    if (rtcTimeValid && readRtcTime(timeInfo)) return true;
#if ENABLE_NTP_SYNC
    if (wifiConnected && getLocalTime(timeInfo, 0)) return true;
#endif
    return false;
}

void updateNormalModeClock(unsigned long now) {
    if (!oledInitialized || now - lastClockDisplayAt < CLOCK_DISPLAY_INTERVAL_MS) return;
    tm timeInfo = {};
    if (!getClockTime(&timeInfo)) return;
    lastClockDisplayAt = now;
    if (analogClockVisible) renderOledAnalogClockFrame(timeInfo);
    else renderOledClockFrame(timeInfo);
}

void handleNormalModeButton() {
    bool buttonIsPressed = digitalRead(USER_BUTTON_PIN) == LOW;
    if (buttonIsPressed && !userButtonPressed && (wifiConnected || rtcTimeValid)) {
        analogClockVisible = !analogClockVisible;
        lastClockDisplayAt = 0;
        printClockMode();
    }
    userButtonPressed = buttonIsPressed;
}

/* --- WiFi Lifecycle --- */

void startWifiManager() {
#if ENABLE_WIFI_MANAGER
    if (wifiManagerStarted) return;
    wifiManagerStarted = true;
    WiFi.mode(WIFI_STA);
    wifiManager.setConfigPortalBlocking(false);
    wifiManager.setTitle("UTC2738 Setup");
    wifiConnected = wifiManager.autoConnect(wifiManagerApName);
    wifiManagerPortalActive = !wifiConnected;

    if (wifiConnected) {
        renderOledMessageFrame("Welcome to", "UTC2738", "WiFi connected", "Station mode active", "");
        printWifiAddress();
    } else {
        renderOledWifiManagerFrame("Starting WiFi", wifiManagerApName, "Connect to configure");
    }
#endif
}

void runNormalMode(unsigned long now) {
#if ENABLE_WIFI_MANAGER
    if (!wifiManagerStarted) {
        if (now - normalModeStartedAt < WELCOME_SCREEN_HOLD_MS) return;
        startWifiManager();
        return;
    }

    if (wifiManagerPortalActive) {
        wifiManager.process();
        if (WiFi.status() == WL_CONNECTED) {
            wifiConnected = true; wifiManagerPortalActive = false;
            printWifiAddress(); syncClockFromNtpAndRtc();
        }
        return;
    }

    if (!wifiConnected && WiFi.status() == WL_CONNECTED) {
        wifiConnected = true; printWifiAddress(); syncClockFromNtpAndRtc();
    }

    if (wifiConnected && !ntpSyncAttempted) syncClockFromNtpAndRtc();
    updateWeatherData(now);
    handleNormalModeButton();
    updateNormalModeClock(now);
#endif
}

/* --- Diagnostic Mode (Test Mode) Frames --- */

void drawOledFrame0() {
    oled.drawFrame(0, 0, 128, 64);
    drawCenteredText(10, "Welcome to", u8g2_font_6x10_tf);
    drawCenteredText(22, "UTC2738", u8g2_font_7x14_tf);

    oled.setFont(u8g2_font_5x8_tf);
    oled.drawStr(6, 26, "MODE:"); oled.drawStr(44, 26, testModeEnabled ? "TEST" : "NORMAL");
    oled.drawStr(6, 34, "OLED:"); oled.drawStr(44, 34, oledInitialized ? "OK" : "FAIL");
    oled.drawStr(6, 42, "RTC:");  oled.drawStr(44, 42, rtcDetected ? "OK" : "MISS");
    oled.drawStr(6, 50, "BUZ:");  oled.drawStr(44, 50, ENABLE_BUZZER_TEST ? "SERIES" : "OFF");

    char buf[20];
    snprintf(buf, sizeof(buf), "I2C:%u", i2cDeviceCount); oled.drawStr(76, 34, buf);
    snprintf(buf, sizeof(buf), "FRAME:%u", oledFrameIndex % 4); oled.drawStr(76, 42, buf);
    snprintf(buf, sizeof(buf), "STEP:%u", buzzerStepIndex); oled.drawStr(76, 50, buf);
    drawPageFooter("status 1/4");
}

void drawOledFrame1() {
    oled.drawFrame(0, 0, 128, 64);
    drawCenteredText(10, "Welcome to UTC2738", u8g2_font_5x8_tf);
    oled.drawCircle(64, 32, 22); oled.drawDisc(56, 26, 3); oled.drawDisc(72, 26, 3);
    oled.drawLine(54, 40, 59, 45); oled.drawLine(59, 45, 69, 45); oled.drawLine(69, 45, 74, 40);
    drawPageFooter("smile 2/4");
}

void drawOledFrame2() {
    oled.drawFrame(0, 0, 128, 64);
    drawCenteredText(10, "Welcome to UTC2738", u8g2_font_5x8_tf);
    for (int i = 0; i < 6; i++) oled.drawFrame(8 + i * 8, 8 + i * 4, 112 - i * 16, 48 - i * 8);
    oled.drawLine(8, 8, 119, 55); oled.drawLine(119, 8, 8, 55);
    drawPageFooter("geometry 3/4");
}

void drawOledFrame3() {
    oled.drawFrame(0, 0, 128, 64);
    drawCenteredText(10, "Welcome to UTC2738", u8g2_font_5x8_tf);
    for (int r = 0; r < 4; r++) {
        for (int c = 0; c < 8; c++) {
            if ((r + c) % 2 == 0) oled.drawBox(8 + c * 14, 8 + r * 12, 10, 8);
            else oled.drawFrame(8 + c * 14, 8 + r * 12, 10, 8);
        }
    }
    drawPageFooter("pattern 4/4");
}

void renderOledDiagnosticsFrame() {
#if ENABLE_OLED_TEST && ENABLE_OLED_PICTURE_TEST
    if (!oledInitialized) return;
    oled.clearBuffer();
    switch (oledFrameIndex % 4) {
    case 0: drawOledFrame0(); break;
    case 1: drawOledFrame1(); break;
    case 2: drawOledFrame2(); break;
    default: drawOledFrame3(); break;
    }
    oled.sendBuffer();
    oledTextWritten = true;
#endif
}

void initializeOledTest() {
#if ENABLE_OLED_TEST
    oledDetected = probeI2cAddress(EXPECTED_OLED_ADDRESS);
    rtcDetected = probeI2cAddress(EXPECTED_RTC_ADDRESS);
    if (!oledDetected) return;
    oled.begin(); oled.setFlipMode(1); oledInitialized = true;
    renderOledDiagnosticsFrame();
#endif
}

void updateOledTest(unsigned long now) {
#if ENABLE_OLED_TEST && ENABLE_OLED_PICTURE_TEST
    if (oledInitialized && now - lastOledFrameAt >= OLED_FRAME_INTERVAL_MS) {
        lastOledFrameAt = now; ++oledFrameIndex; renderOledDiagnosticsFrame();
    }
#endif
}

/* --- Heartbeat and Buzzer Logic --- */

void runHeartbeatLed(unsigned long now) {
#if ENABLE_HEARTBEAT_LED && defined(LED_BUILTIN)
    if (now - lastHeartbeatAt >= HEARTBEAT_INTERVAL_MS) {
        lastHeartbeatAt = now; heartbeatLedState = !heartbeatLedState;
        digitalWrite(LED_BUILTIN, heartbeatLedState ? HIGH : LOW);
    }
#endif
}

void updateBuzzerTest(unsigned long now) {
#if ENABLE_BUZZER_TEST
    if (!buzzerSequenceActive) {
        if (now - lastBuzzerEventAt < BUZZER_SEQUENCE_INTERVAL_MS) return;
        buzzerSequenceActive = true; buzzerStepIndex = 0; nextBuzzerChangeAt = now;
    }

    if (now >= nextBuzzerChangeAt) {
        if (buzzerStepIndex >= buzzerPatternLength) {
            noTone(BUZZER_TEST_PIN); buzzerSequenceActive = false;
            lastBuzzerEventAt = now; return;
        }
        uint16_t freq = buzzerPatternFrequencies[buzzerStepIndex];
        uint16_t dur = buzzerPatternDurations[buzzerStepIndex];
        if (freq == 0) noTone(BUZZER_TEST_PIN); else tone(BUZZER_TEST_PIN, freq);
        nextBuzzerChangeAt = now + dur; ++buzzerStepIndex;
    }
#endif
}

/* --- I2C Bus Scanning --- */

void scanI2cBus(unsigned long now) {
#if ENABLE_I2C_SCANNER
    if (now - lastI2cScanAt < I2C_SCAN_INTERVAL_MS) return;
    lastI2cScanAt = now;
    uint8_t count = 0;
    char buf[49];
    printBoxTop(); printBoxLine("i2c_scan begin");
    for (uint8_t addr = 1; addr < 127; addr++) {
        Wire.beginTransmission(addr);
        if (Wire.endTransmission() == 0) {
            snprintf(buf, sizeof(buf), "device found at 0x%02X", addr); printBoxLine(buf);
            count++;
        }
    }
    i2cDeviceCount = count;
    rtcDetected = probeI2cAddress(EXPECTED_RTC_ADDRESS);
    snprintf(buf, sizeof(buf), "devices_found=%u", count); printBoxLine(buf);
    printBoxBottom();
#endif
}

void printBoardStatus(unsigned long now) {
#if ENABLE_STATUS_MESSAGES
    if (now - lastStatusAt < STATUS_INTERVAL_MS) return;
    lastStatusAt = now;
    char buf[49];
    snprintf(buf, sizeof(buf), "uptime_ms=%lu free_heap=%u", now, (unsigned)ESP.getFreeHeap());
    printBoxTop(); printBoxLine("board_test status"); printBoxLine(buf); printBoxBottom();
#endif
}

} // namespace

/* --- Arduino Lifecycle Hooks --- */

void setup() {
#if ENABLE_BOARD_TEST
    buildWifiManagerNames();
    initializeLed();
    initializeUserButton();
    testModeEnabled = detectTestModeRequest();
    normalModeStartedAt = millis();
    initializeSerial();
    initializeI2c();
    initializeBuzzerTest();

    if (testModeEnabled) initializeOledTest();
    else initializeOledStandby();
#endif
}

void loop() {
#if ENABLE_BOARD_TEST
    unsigned long now = millis();
    if (!testModeEnabled) { runNormalMode(now); return; }

    runHeartbeatLed(now);
    updateBuzzerTest(now);
    updateOledTest(now);
    printBoardStatus(now);
    scanI2cBus(now);
#endif
}
