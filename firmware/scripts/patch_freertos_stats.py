"""
PlatformIO pre-build script that patches the Arduino-ESP32 framework sources.

This script is executed automatically by PlatformIO before compiling the
firmware for the XIAO ESP32S3 pods. It fixes a known bug in the ESP32
Arduino core's I2C slave initialisation code.

Problem:
    The stock ``esp32-hal-i2c-slave.c`` calls ``i2c_ll_slave_init()`` which
    does not properly configure the I2C control register for the ESP32-S3,
    leading to I2C slave communication failures on the XIAO ESP32S3 pods.

Solution:
    This script replaces the ``i2c_ll_slave_init()`` call with a manual
    register configuration sequence that explicitly sets:
        - sda_force_out = 1 (drive SDA line)
        - scl_force_out = 1 (drive SCL line)
        - fifo_addr_cfg_en = 0 (disable FIFO address configuration)

Approach:
    1. PlatformIO calls this script via ``Import("env")`` and the SCons
       build system.
    2. The script locates the installed ``framework-arduinoespressif32``
       package directory through the PlatformIO API.
    3. It reads the target C source file, performs a one-shot string
       replacement, and writes it back. The patch is idempotent -- if the
       replacement text is already present, it prints "already applied" and
       does nothing.

Libraries used:
    - pathlib.Path: for cross-platform file path handling.
    - PlatformIO SCons environment (``env``): accessed via ``Import("env")``
      to discover the framework package directory.

Functions:
    - patch_file(): generic idempotent text-replacement helper for any file.
    - patch_framework_sources(): locates and patches the I2C slave source.

Fits into the Pebble project as a build-time fix for the XIAO ESP32S3 firmware,
ensuring reliable I2C slave communication between pods.
"""

from pathlib import Path

# PlatformIO SCons integration: imports the build environment object which
# provides access to platform configuration and package directories.
Import("env")


def patch_file(target, old, new, label):
    """Perform an idempotent single-occurrence text replacement in a file.

    Reads the file at *target*, replaces the first occurrence of *old* with
    *new*, and writes the result back. If *old* is not found but *new* already
    exists in the file, the patch has already been applied. If neither is found,
    the target text structure may have changed (prints a warning).

    Args:
        target: pathlib.Path to the file to patch.
        old:    the exact text to search for and replace.
        new:    the replacement text.
        label:  human-readable label for log messages (e.g. "esp32-hal-i2c-slave patch").
    """
    if not target.exists():
        print(f"{label}: missing file: {target}")
        return

    content = target.read_text(encoding="utf-8")
    if old not in content:
        if new in content:
            print(f"{label}: already applied")
        else:
            print(f"{label}: target text not found")
        return

    target.write_text(content.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def patch_framework_sources():
    """Locate the Arduino-ESP32 framework and apply the I2C slave patch.

    Uses the PlatformIO environment to find the ``framework-arduinoespressif32``
    package, then patches ``cores/esp32/esp32-hal-i2c-slave.c`` to replace the
    broken ``i2c_ll_slave_init()`` call with correct manual register setup.
    """
    framework_dir = env.PioPlatform().get_package_dir("framework-arduinoespressif32")
    if not framework_dir:
        print("framework patch: framework-arduinoespressif32 not found")
        return

    patch_file(
        Path(framework_dir) / "cores" / "esp32" / "esp32-hal-i2c-slave.c",
        "  i2c_ll_slave_init(i2c->dev);",
        "  typeof(i2c->dev->ctr) ctrl_reg;\n  ctrl_reg.val = 0;\n  ctrl_reg.sda_force_out = 1;\n  ctrl_reg.scl_force_out = 1;\n  i2c->dev->ctr.val = ctrl_reg.val;\n  i2c->dev->fifo_conf.fifo_addr_cfg_en = 0;",
        "esp32-hal-i2c-slave patch",
    )


# Execute the patch immediately when PlatformIO loads this script.
patch_framework_sources()